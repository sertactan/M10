from core.features.wf_raw_metrics import (
    exact_period_per_share_series,
    latest_cagr,
    latest_growth,
)


def test_exact_period_per_share_never_uses_cross_period_share_proxy() -> None:
    numerators = [
        {"period_end": "2022-12-31", "value": 100.0},
        {"period_end": "2023-12-31", "value": 150.0},
        {"period_end": "2024-12-31", "value": 240.0},
    ]
    shares = [
        {"period_end": "2022-12-31", "value": 10.0},
        {"period_end": "2024-12-31", "value": 12.0},
    ]
    points = exact_period_per_share_series(numerators, shares)
    assert [(p.period_end, p.value) for p in points] == [
        ("2022-12-31", 10.0),
        ("2024-12-31", 20.0),
    ]


def test_raw_per_share_growth_and_cagr_are_deterministic() -> None:
    numerators = [
        {"period_end": f"{year}-12-31", "value": value}
        for year, value in [(2021,100.0),(2022,120.0),(2023,150.0),(2024,200.0)]
    ]
    shares = [
        {"period_end": f"{year}-12-31", "value": 10.0}
        for year in (2021,2022,2023,2024)
    ]
    points = exact_period_per_share_series(numerators, shares)
    assert latest_growth(points) == 200.0 / 150.0 - 1.0
    assert latest_cagr(points, 3) == (20.0 / 10.0) ** (1.0 / 3.0) - 1.0
