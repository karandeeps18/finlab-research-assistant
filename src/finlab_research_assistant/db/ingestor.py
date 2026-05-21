async def _ingest_with_client(
        self, ticker: str, form_type: str, client: EdgarClient
    ) -> tuple[Company, Filing] | None:
    
    # same as idempotency checks 
        company = await self._resolver.resolve(ticker, client)
        all_filings = await self._index.fetch_recent(company.cik, client)
        filing = self._index.latest(all_filings, form_type=form_type)
        
        # warning for None filing 
        if filing is None:
            log.warning("no_filing_found", ticker=ticker, form_type=form_type)
            return None

        # Idempotency check on disk
        if self._storage.is_ingested(company, filing):
            log.info(
                "filing.skipped_already_ingested",
                ticker=ticker,
                accession=filing.accession_number,
            )
            # Still ensure DB is in sync (in case disk has it but DB doesn't)
            await self._sync_to_db(company, filing)
            return company, filing

        # Download
        url = filing.document_url(company.cik)
        log.info("filing.downloading", url=url)
        document_bytes = await client.get_bytes(url)

        # Write to raw layer
        target_dir = self._storage.write_filing(
            company=company,
            filing=filing,
            document_bytes=document_bytes,
            source_url=url,
        )

        # Persist metadata to DB
        await self._sync_to_db(company, filing, raw_path=str(target_dir))

        return company, filing

    async def _sync_to_db(
        self,
        company: Company,
        filing: Filing,
        raw_path: str | None = None,
    ) -> None:
        """Upsert company and filing into the metadata DB."""
        from finlab_research_assistant.db.repository import (
            upsert_company,
            upsert_filing,
        )
        from finlab_research_assistant.db.session import get_session

        # If we don't have raw_path (idempotency path), derive it
        if raw_path is None:
            raw_path = str(self._storage.filing_dir(company, filing))

        async with get_session() as session:
            db_company = await upsert_company(session, company)
            await upsert_filing(session, db_company, filing, raw_path)