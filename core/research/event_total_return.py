"""Evidence-gated, point-in-time one-event shareholder total-return arithmetic.

This deliberately does not infer corporate actions from vendor-adjusted prices.
Supply independently verified terms, price observations, and availability times.
No persistence, remote API, trading decision or canonical promotion is performed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import isfinite


class EvidenceNotReady(ValueError):
    """Missing or late independent evidence; the observation stays quarantined."""


@dataclass(frozen=True)
class ObservedValue:
    value: float
    available_at: datetime
    source_url: str

    def checked(self, decision_at: datetime) -> float:
        if not self.source_url.startswith(("https://", "http://")):
            raise EvidenceNotReady("SOURCE_URL_MISSING")
        for clock in (self.available_at, decision_at):
            if clock.tzinfo is None or clock.utcoffset() is None:
                raise EvidenceNotReady("NAIVE_PIT_CLOCK")
        if self.available_at.astimezone(timezone.utc) > decision_at.astimezone(timezone.utc):
            raise EvidenceNotReady("LOOKAHEAD_EVIDENCE")
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool) or not isfinite(self.value):
            raise EvidenceNotReady("INVALID_NUMERIC_OBSERVATION")
        return float(self.value)


@dataclass(frozen=True)
class CorporateActionTerms:
    ex_date: date
    parent_shares_after_per_before: ObservedValue
    cash_per_before_share: ObservedValue | None = None
    child_shares_per_before_share: ObservedValue | None = None
    event_source_url: str = ""
    issuer_and_share_class_verified: bool = False
    ex_date_independently_verified: bool = False
    terminal_delisting_verified: bool = False


def event_total_return(
    *, previous_close: ObservedValue, next_parent_close: ObservedValue,
    terms: CorporateActionTerms, decision_at: datetime,
    next_child_close: ObservedValue | None = None,
    terminal_cash_per_before_share: ObservedValue | None = None,
) -> dict:
    """Calculate ONE event's gross holding-period total return per pre-event share.

    Inputs must be separately source-verified and already available at decision_at.
    Spin-offs require contemporaneous child market value; cash delistings require
    an evidenced terminal payment. Use a new event for each distinct ex date;
    fees, withholding, FX, due bills and settlement are external to this result.
    This is arithmetic only and never certifies the underlying evidence itself.
    """
    if not terms.issuer_and_share_class_verified or not terms.ex_date_independently_verified:
        raise EvidenceNotReady("HISTORICAL_IDENTITY_OR_EX_DATE_UNVERIFIED")
    if not terms.event_source_url.startswith(("https://", "http://")):
        raise EvidenceNotReady("CORPORATE_ACTION_SOURCE_MISSING")
    prior = previous_close.checked(decision_at)
    parent = next_parent_close.checked(decision_at)
    ratio = terms.parent_shares_after_per_before.checked(decision_at)
    if prior <= 0 or parent < 0 or ratio < 0:
        raise EvidenceNotReady("INVALID_PRICE_OR_SHARE_RATIO")
    cash = terms.cash_per_before_share.checked(decision_at) if terms.cash_per_before_share else 0.0
    if cash < 0:
        raise EvidenceNotReady("NEGATIVE_DISTRIBUTION")
    child_value = 0.0
    if terms.child_shares_per_before_share is not None:
        if next_child_close is None:
            raise EvidenceNotReady("SPINOFF_CHILD_PRICE_MISSING")
        child_ratio = terms.child_shares_per_before_share.checked(decision_at)
        child_price = next_child_close.checked(decision_at)
        if child_ratio < 0 or child_price < 0:
            raise EvidenceNotReady("INVALID_CHILD_OBSERVATION")
        child_value = child_ratio * child_price
    elif next_child_close is not None:
        raise EvidenceNotReady("UNMATCHED_CHILD_OBSERVATION")
    terminal = 0.0
    if terminal_cash_per_before_share is not None:
        if not terms.terminal_delisting_verified:
            raise EvidenceNotReady("UNVERIFIED_TERMINAL_PAYMENT")
        terminal = terminal_cash_per_before_share.checked(decision_at)
        if terminal < 0:
            raise EvidenceNotReady("NEGATIVE_TERMINAL_PAYMENT")
    if ratio == 0 and terminal_cash_per_before_share is None:
        raise EvidenceNotReady("MISSING_TERMINAL_RETURN")
    payoff = ratio * parent + cash + child_value + terminal
    if not isfinite(payoff):
        raise EvidenceNotReady("OVERFLOW")
    return {
        "ex_date": terms.ex_date.isoformat(),
        "gross_return": payoff / prior - 1,
        "pre_event_value": prior,
        "post_event_parent_value": ratio * parent,
        "cash_distribution_value": cash,
        "spin_child_value": child_value,
        "terminal_payment_value": terminal,
        "canonical_pit_accepted": False,
        "validation_scope": "SOURCE_GATED_ARITHMETIC_ONLY",
    }
