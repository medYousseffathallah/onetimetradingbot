import copy
import json
from pathlib import Path

import pytest

from bvmt.rules import REQUIRED_FIELDS, competition_blockers

ROOT = Path(__file__).resolve().parents[1]


def complete_metadata_fixture():
    fields = {
        name: {
            "value": "TEST DOCUMENT TEXT - NOT REAL RULES",
            "status": "verified",
            "source": "tests/synthetic-rules",
            "evidence_locator": "test-only",
            "reviewed_by": "unit-test",
            "reviewed_at": "2026-01-01T00:00:00Z",
        }
        for name in REQUIRED_FIELDS
    }
    fields["initial_cash_tnd"]["value"] = "1000"
    fields["start_date"]["value"] = "2026-01-01"
    fields["end_date"]["value"] = "2026-12-31"
    return {
        "schema_version": 1,
        "mode": "competition_exact",
        "execution_enabled": False,
        "fields": fields,
    }


def test_shipped_rules_are_blocked():
    config = json.loads((ROOT / "configs/competition.json").read_text())
    assert competition_blockers(config)
    assert any("initial_cash_tnd:not_verified" == b for b in competition_blockers(config))


def test_metadata_complete_means_only_ready_for_review():
    assert competition_blockers(complete_metadata_fixture()) == []


def test_verified_flag_without_evidence_does_not_pass():
    config = complete_metadata_fixture()
    config["fields"]["execution_matching"]["source"] = None
    assert "execution_matching:missing_source" in competition_blockers(config)


def test_execution_cannot_be_enabled():
    config = complete_metadata_fixture()
    config["execution_enabled"] = True
    assert "execution_must_remain_disabled_in_this_starter" in competition_blockers(config)


@pytest.mark.parametrize("value", ["NaN", "-1", "0", "bad", True])
def test_invalid_cash_rejected(value):
    config = complete_metadata_fixture()
    config["fields"]["initial_cash_tnd"]["value"] = value
    assert "initial_cash_tnd:invalid_cash" in competition_blockers(config)


def test_end_before_start_rejected():
    config = complete_metadata_fixture()
    config["fields"]["end_date"]["value"] = "2025-12-31"
    assert "end_date_must_follow_start_date" in competition_blockers(config)


def test_malformed_config_fails_closed():
    assert competition_blockers([]) == ["config_must_be_an_object"]
    assert competition_blockers({"fields": []})


def test_no_config_mutation():
    config = complete_metadata_fixture()
    before = copy.deepcopy(config)
    competition_blockers(config)
    assert config == before
