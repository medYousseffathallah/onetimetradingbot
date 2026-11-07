from dataclasses import replace
from datetime import timedelta

import pytest

from bvmt.execution import run_historical_backtest, run_walk_forward_evaluation


def test_subyear_sample_retains_sufficiency_warning(bars):
    sample = [
        replace(bars[0], session_date=bars[0].session_date + timedelta(days=i)) for i in range(194)
    ]
    result = run_historical_backtest(sample, [])
    assert "194 sessions" in result.data_sufficiency_warning


@pytest.mark.parametrize(
    "field", ["train_window_sessions", "test_window_sessions", "step_sessions"]
)
@pytest.mark.parametrize("value", [0, -1, True])
def test_walk_forward_rejects_invalid_window_sizes(bars, field, value):
    with pytest.raises(ValueError, match="positive integer"):
        run_walk_forward_evaluation(bars, lambda history, cutoff: [], **{field: value})


def test_walk_forward_builder_receives_only_rolling_training_window(bars):
    sample = [
        replace(bars[0], session_date=bars[0].session_date + timedelta(days=i)) for i in range(10)
    ]
    histories = []

    def builder(history, cutoff):
        assert all(b.session_date <= cutoff for b in history)
        histories.append([b.session_date for b in history])
        return []

    result = run_walk_forward_evaluation(
        sample, builder, train_window_sessions=4, test_window_sessions=2, step_sessions=2
    )
    assert [len(h) for h in histories] == [4, 4, 4]
    assert histories[1][0] == sample[2].session_date
    assert result.total_folds == 3
    assert not result.is_statistically_conclusive
