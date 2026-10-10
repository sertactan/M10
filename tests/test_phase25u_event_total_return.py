from datetime import date, datetime, timezone, timedelta
import unittest

from core.research.event_total_return import (
    CorporateActionTerms, EvidenceNotReady, ObservedValue, event_total_return
)

NOW = datetime(2024, 10, 2, tzinfo=timezone.utc)
EARLIER = NOW - timedelta(days=1)
SRC = "https://www.sec.gov/Archives/edgar/data/894315/"


def value(v, when=EARLIER):
    return ObservedValue(v, when, SRC)


def terms(ratio=1, cash=None, child=None, terminal=False):
    return CorporateActionTerms(
        ex_date=date(2024, 10, 1), parent_shares_after_per_before=value(ratio),
        cash_per_before_share=value(cash) if cash is not None else None,
        child_shares_per_before_share=value(child) if child is not None else None,
        event_source_url=SRC, issuer_and_share_class_verified=True,
        ex_date_independently_verified=True, terminal_delisting_verified=terminal,
    )


class EventReturnTest(unittest.TestCase):
    def compute(self, t, child=None, terminal=None, before=100, after=100):
        return event_total_return(
            previous_close=value(before), next_parent_close=value(after), terms=t,
            decision_at=NOW,
            next_child_close=value(child) if child is not None else None,
            terminal_cash_per_before_share=value(terminal) if terminal is not None else None,
        )

    def test_four_to_one_reverse_split_preserves_value(self):
        r = self.compute(terms(ratio=0.25), before=10, after=40)
        self.assertAlmostEqual(r["gross_return"], 0)
        self.assertFalse(r["canonical_pit_accepted"])

    def test_two_child_shares_per_parent_spinoff(self):
        r = self.compute(terms(child=2), child=8, before=100, after=84)
        self.assertAlmostEqual(r["gross_return"], 0)
        self.assertEqual(r["spin_child_value"], 16)

    def test_special_cash_and_terminal_merger_payment(self):
        r = self.compute(terms(ratio=0, cash=1, terminal=True), terminal=47.5, before=45, after=0)
        self.assertAlmostEqual(r["gross_return"], 48.5/45 - 1)

    def test_no_child_price_no_implied_total_return(self):
        with self.assertRaisesRegex(EvidenceNotReady, "SPINOFF_CHILD_PRICE_MISSING"):
            self.compute(terms(child=2), before=100, after=84)

    def test_future_price_is_never_used_for_pit_decision(self):
        with self.assertRaisesRegex(EvidenceNotReady, "LOOKAHEAD_EVIDENCE"):
            event_total_return(
                previous_close=value(100), next_parent_close=value(84, NOW + timedelta(seconds=1)),
                terms=terms(child=2), decision_at=NOW, next_child_close=value(8)
            )

    def test_terminal_payment_must_be_independently_verified(self):
        with self.assertRaisesRegex(EvidenceNotReady, "UNVERIFIED_TERMINAL_PAYMENT"):
            self.compute(terms(ratio=0), terminal=47.5, before=45, after=0)

    def test_missing_verified_ex_date_stays_quarantined(self):
        t = terms()
        t = CorporateActionTerms(
            ex_date=t.ex_date, parent_shares_after_per_before=t.parent_shares_after_per_before,
            event_source_url=t.event_source_url, issuer_and_share_class_verified=True,
            ex_date_independently_verified=False,
        )
        with self.assertRaisesRegex(EvidenceNotReady, "HISTORICAL_IDENTITY_OR_EX_DATE_UNVERIFIED"):
            self.compute(t)


if __name__ == "__main__":
    unittest.main()
