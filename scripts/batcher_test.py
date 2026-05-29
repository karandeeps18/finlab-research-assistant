"""Verify batcher contract holds on synthetic data."""

from finlab_research_assistant.embedding.contracts import BatchItem, BatchLimits
from finlab_research_assistant.embedding.batcher import batch_items, validate_items


def test_count_limit():
    """Items pack until max_items, then a new batch starts."""
    limits = BatchLimits(max_items=3, max_tokens_per_batch=1000, max_tokens_per_item=100)
    items = [BatchItem(id=f"c{i}", text="x", token_count=10) for i in range(7)]
    validate_items(items, limits)
    batches = list(batch_items(items, limits))
    sizes = [len(b) for b in batches]
    print(f"count_limit: batch sizes = {sizes}")
    assert sizes == [3, 3, 1], f"expected [3, 3, 1], got {sizes}"


def test_token_limit():
    """Items pack until max_tokens_per_batch."""
    limits = BatchLimits(max_items=100, max_tokens_per_batch=50, max_tokens_per_item=40)
    items = [BatchItem(id=f"c{i}", text="x", token_count=30) for i in range(5)]
    validate_items(items, limits)
    batches = list(batch_items(items, limits))
    tokens_per_batch = [sum(item.token_count for item in batch) for batch in batches]
    assert all(t <= 50 for t in tokens_per_batch), "token limit violated"


def test_failfast_on_oversized():
    """validate_items raises BEFORE any batch yields."""
    limits = BatchLimits(max_items=10, max_tokens_per_batch=1000, max_tokens_per_item=50)
    items = [
        BatchItem(id="c0", text="x", token_count=10),
        BatchItem(id="c1", text="x", token_count=100),  # oversized
        BatchItem(id="c2", text="x", token_count=10),
    ]
    try:
        validate_items(items, limits)
        print("FAIL: should have raised")
    except ValueError as e:
        print(f"failfast: correctly raised: {e}")


def test_empty_input():
    """No items in → no batches out."""
    limits = BatchLimits()
    batches = list(batch_items([], limits))
    print(f"empty: batches = {batches}")
    assert batches == [], f"expected [], got {batches}"


def test_order_preserved():
    """Items come out in the same order they went in."""
    limits = BatchLimits(max_items=2, max_tokens_per_batch=1000, max_tokens_per_item=100)
    items = [BatchItem(id=f"c{i}", text="x", token_count=10) for i in range(5)]
    batches = list(batch_items(items, limits))
    flat_ids = [item.id for batch in batches for item in batch]
    expected = ["c0", "c1", "c2", "c3", "c4"]
    print(f"order: flat ids = {flat_ids}")
    assert flat_ids == expected, f"expected {expected}, got {flat_ids}"


if __name__ == "__main__":
    test_count_limit()
    test_token_limit()
    test_failfast_on_oversized()
    test_empty_input()
    test_order_preserved()
    print("\nAll batcher contract tests passed.") 