import json
from pathlib import Path

from bvmt.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_demo_is_labeled_and_writes_report(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(ROOT)
    out = tmp_path / "report.json"
    assert main(["demo", "--output", str(out)]) == 0
    payload = json.loads(out.read_text())
    assert payload["mode"] == "synthetic_demo"
    assert payload["execution_authorized"] is False
    assert payload["competition_readiness"] == "blocked"
    assert len(payload["rankings"]) == 2
    assert json.loads(capsys.readouterr().out) == payload


def test_unknown_rules_exit_two(monkeypatch, capsys):
    monkeypatch.chdir(ROOT)
    assert main(["rules-check"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"


def test_missing_file_is_actionable_error(tmp_path, capsys):
    assert main(["validate-csv", str(tmp_path / "absent.csv")]) == 1
    assert "ERROR:" in capsys.readouterr().err


def test_import_csv_cli_command(tmp_path, capsys):
    fixture = ROOT / "tests/fixtures/french_bvmt_sample.csv"
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "processed"
    code = main(
        [
            "import-csv",
            str(fixture),
            "--source-id",
            "bvmt_hist_sample",
            "--format",
            "french_bvmt",
            "--permission-status",
            "authorized_local_import",
            "--retrieved-at",
            "2026-01-15T18:00:00+00:00",
            "--raw-dir",
            str(raw_dir),
            "--output-dir",
            str(out_dir),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["accepted_rows"] == 4
    assert payload["rejected_rows"] == 7
    assert (out_dir / "daily_bars.canonical.csv").is_file()
    assert (out_dir / "rejections.json").is_file()
    assert (out_dir / "manifest.json").is_file()
