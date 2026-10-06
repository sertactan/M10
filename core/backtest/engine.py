from __future__ import annotations

from collections.abc import Iterable

from core.backtest.contracts import HistoricalBacktestResult, TerminalConsideration
from core.backtest.metrics import prediction_error_class
from core.backtest.outcomes import CanonicalForwardOutcomeEngine
from core.backtest.spec_manifest import Phase6SpecificationBinding
from core.models.s153_v12 import S153V12Model
from core.models.s153_v12_contracts import S153V12Input
from core.models.s153_v14 import S153V14Model
from core.models.s153_v14_contracts import S153V14Input
from core.prices.models import SourcePriceBar


class Phase6SpecificationMissing(RuntimeError):
    pass


class HistoricalBacktestEngine:
    """Score PIT inputs first, then join future outcomes.

    This class has no external data provider. Callers must pass canonical model
    inputs and a canonical single-source adjusted price series from Phases 1-3.
    """

    def __init__(
        self,
        *,
        v12_model: S153V12Model | None = None,
        v14_model: S153V14Model | None = None,
        binding: Phase6SpecificationBinding | None = None,
    ) -> None:
        self.v12_model = v12_model or S153V12Model()
        self.v14_model = v14_model or S153V14Model()
        self.binding = binding or Phase6SpecificationBinding()
        self.outcomes = CanonicalForwardOutcomeEngine()

    def evaluate(
        self,
        *,
        v12_input: S153V12Input,
        v14_input: S153V14Input,
        bars: Iterable[SourcePriceBar],
        terminal_consideration: TerminalConsideration | None = None,
        terminal_value_unknown: bool = False,
    ) -> HistoricalBacktestResult:
        if v12_input.security_id != v14_input.security_id:
            raise ValueError("V1.2 and V1.4 inputs must reference the same security_id")
        if v12_input.as_of != v14_input.as_of:
            raise ValueError("V1.2 and V1.4 inputs must use the same PIT as_of timestamp")

        # Critical physical/logical firewall: score first. Future labels are not
        # computed or joined until both model engines have completed.
        v12_result = self.v12_model.analyze(v12_input)
        v14_result = self.v14_model.analyze(v14_input)

        outcome = self.outcomes.compute(
            security_id=v12_input.security_id,
            as_of_date_requested=v12_input.as_of.date(),
            bars=bars,
            terminal_consideration=terminal_consideration,
            terminal_value_unknown=terminal_value_unknown,
        )
        return HistoricalBacktestResult(
            security_id=v12_input.security_id,
            ticker=v12_input.ticker,
            as_of=v12_input.as_of,
            v12=v12_result,
            v14=v14_result,
            outcome=outcome,
            error_class_v12=prediction_error_class(
                precision_confirmed=v12_result.precision_confirmed,
                outcome=outcome,
            ),
            error_class_v14=prediction_error_class(
                precision_confirmed=bool(v14_result.flags.get("PRECISION_CONFIRMED", False)),
                outcome=outcome,
            ),
        )
