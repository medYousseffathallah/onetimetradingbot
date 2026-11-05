from pathlib import Path

import pytest

from bvmt.data import read_bars_csv

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bars():
    return read_bars_csv(ROOT / "tests/fixtures/daily_bars.csv")
