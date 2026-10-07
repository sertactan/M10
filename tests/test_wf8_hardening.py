import pytest

from core.backtest.wf8_hardening import (
    WF8_ACCEPTANCE_ITEMS,
    WF8AcceptanceItem,
    release_status,
    require_wf8_acceptance_matrix,
)


def _items(passed=True):
    return [
        WF8AcceptanceItem(name=name,passed=passed,evidence="test")
        for name in WF8_ACCEPTANCE_ITEMS
    ]


def test_wf8_acceptance_requires_exact_matrix() -> None:
    require_wf8_acceptance_matrix(_items())
    with pytest.raises(ValueError):
        require_wf8_acceptance_matrix(_items()[:-1])


def test_wf8_release_is_fail_closed() -> None:
    status,blockers,warnings=release_status(_items())
    assert status=="PRODUCTION_EVIDENCE_READY"
    assert blockers==()
    assert warnings==()

    items=_items()
    items[0]=WF8AcceptanceItem(
        name=items[0].name,passed=False,evidence="wf5 incomplete"
    )
    status,blockers,_=release_status(items)
    assert status=="PRODUCTION_BLOCKED"
    assert blockers==("WF5 replay complete: wf5 incomplete",)
