import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """
    Move test_full_pipeline items to the end, with test_st_omer before test_marmande.
    """
    pipeline_items = [i for i in items if "test_full_pipeline" in i.nodeid]
    others = [i for i in items if i not in pipeline_items]

    def order_key(item: pytest.Item) -> int:
        """
        Give test_st_omer (subkey 0) a smaller key than test_marmande (subkey 1)
        so it sorts first.
        """
        nodeid = item.nodeid
        if "test_st_omer" in nodeid:
            return 0
        return 1

    items[:] = others + sorted(pipeline_items, key=order_key)
