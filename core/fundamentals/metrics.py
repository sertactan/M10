from __future__ import annotations

from datetime import date


XBRL_CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "REVENUE": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ),
    "NET_INCOME": (
        "NetIncomeLoss",
        "ProfitLoss",
    ),
    "GROSS_PROFIT": ("GrossProfit",),
    "OPERATING_INCOME": ("OperatingIncomeLoss",),
    "OPERATING_CASH_FLOW": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    "CAPEX": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ),
    "CASH": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "ASSETS": ("Assets",),
    "LIABILITIES": ("Liabilities",),
    "EQUITY": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "CURRENT_ASSETS": ("AssetsCurrent",),
    "CURRENT_LIABILITIES": ("LiabilitiesCurrent",),
    "LONG_TERM_DEBT": (
        "LongTermDebtNoncurrent",
        "LongTermDebt",
    ),
    "SHARES_OUTSTANDING": (
        "CommonStockSharesOutstanding",
    ),
    "DILUTED_EPS": ("EarningsPerShareDiluted",),
    "BASIC_EPS": ("EarningsPerShareBasic",),
    "SBC": ("ShareBasedCompensation", "StockBasedCompensation"),
    "R_AND_D": ("ResearchAndDevelopmentExpense",),
    "SG_AND_A": ("SellingGeneralAndAdministrativeExpense",),
}

_ALIAS_LOOKUP = {
    alias: canonical
    for canonical, aliases in XBRL_CANONICAL_ALIASES.items()
    for alias in aliases
}

_TAXONOMY_ALIAS_LOOKUP = {
    ("dei", "EntityCommonStockSharesOutstanding"): "SHARES_OUTSTANDING",
}


def canonical_metric(taxonomy: str, tag: str) -> str:
    direct = _TAXONOMY_ALIAS_LOOKUP.get((taxonomy, tag))
    if direct:
        return direct
    if taxonomy == "us-gaap" and tag in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[tag]
    return f"XBRL:{taxonomy}:{tag}"


FLOW_METRICS = {
    "REVENUE",
    "NET_INCOME",
    "GROSS_PROFIT",
    "OPERATING_INCOME",
    "OPERATING_CASH_FLOW",
    "CAPEX",
    "SBC",
    "R_AND_D",
    "SG_AND_A",
}


def classify_period(start: date | None, end: date) -> str:
    if start is None:
        return "INSTANT"
    days = (end - start).days
    if 60 <= days <= 120:
        return "QUARTER"
    if 150 <= days <= 300:
        return "YTD"
    if 300 <= days <= 400:
        return "ANNUAL"
    return "OTHER"
