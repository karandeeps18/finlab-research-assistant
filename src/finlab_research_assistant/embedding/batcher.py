from collections.abc import Iterable, Iterator
from finlab_research_assistant.embedding.contracts import BatchItem, BatchLimits

def validate_items(items: Iterable[BatchItem], limits: BatchLimits) -> None:
    """Raise when the first item exeeding the limits.max_token_per_items.
    
    Run this before creating batches. Gaurantees: if this returns, every subsequent
    call to batch_items on the same data will produce valid batches.
    """
    for item in items: 
        if item.token_count > limits.max_tokens_per_item:
            raise ValueError(f"item {item.id!r}: token_count={item.token_count} "
    f"exceeds max_tokens_per_item={limits.max_tokens_per_item}"
)
    

def batch_items(items: Iterable[BatchItem], limits: BatchLimits) -> Iterator[list[BatchItem]]:
    """Greedy next fit algoritm with generator, this function assumes the items are validated
    
    Invariant: for every yielded batch
    1. len(batch) <= limits.max_items
    2. sum(item.token_count for item in batch) <= limits.max_tokens_per_batch
"""
    current_tokens = 0
    current_batch: list[BatchItem] = []
    
    
    for item in items:
        if current_batch and (
            current_tokens + item.token_count > limits.max_tokens_per_batch
            or len(current_batch) >= limits.max_items 
            ):
            yield current_batch 
            
            current_batch = []
            current_tokens = 0 
            
        current_batch.append(item)
        current_tokens += item.token_count
            
    if current_batch:
        yield current_batch    