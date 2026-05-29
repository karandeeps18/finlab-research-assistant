from dataclasses import dataclass

@dataclass(frozen=True)
class BatchLimits:
    """Limits for Batching the Chunk for embedding requests"""
    max_items: int = 128 
    max_tokens_per_batch: int = 120000 
    max_tokens_per_item: int = 2000 
    
    def __post_init__(self) -> None:
        """custom validation: max_tokens_per_items cannot be greater than max_tokens_per_batch and single non-negative invariants"""
        if self.max_items <= 0:
            raise ValueError(f"Max items: ({self.max_items}) must be greater than 0")
        if self.max_tokens_per_batch <= 0:
            raise ValueError(f"Max tokens per batch: ({self.max_tokens_per_batch}) must be greater than 0")
        if self.max_tokens_per_item <= 0:                  
            raise ValueError(f"Max token per item: ({self.max_tokens_per_item}) must be greater than 0")
        
        if self.max_tokens_per_item > self.max_tokens_per_batch:
            raise ValueError(
                f"Max Tokens for Items ({self.max_tokens_per_item}) cannot be greater"
                f"({self.max_tokens_per_batch}) than Max Tokens for Batch"
                )

            
@dataclass(frozen=True)
class BatchItem:
    """Type setting for the individual items in the batching-embedding pipeline"""
    id: str 
    text: str 
    token_count: int 