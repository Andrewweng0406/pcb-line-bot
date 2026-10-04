from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.compare_extraction_reports import compare_reports


def report():
    return {"format_version": 1, "dataset_sha256": "a" * 64, "mode": "live", "input_sha256": {"a": "b" * 64}, "cases": [{"id": "a", "fields": [
        {"field": "layer", "expected": 6, "actual": 6, "correct": True, "critical": True, "confidence": "high"},
        {"field": "material", "expected": "FR4", "actual": "FR4", "correct": True, "critical": False, "confidence": "medium"},
    ]}]}


def test_comparison_exposes_regression_even_if_another_field_improves():
    old, new = report(), report()
    old["cases"][0]["fields"][1]["correct"] = False
    new["cases"][0]["fields"][0]["correct"] = False
    result = compare_reports(old, new)
    assert result["summary"]["accuracy_delta"] == 0
    assert result["summary"]["regressions"] == 1
    assert result["summary"]["improvements"] == 1
    assert result["summary"]["new_false_high_confidence"] == 1
    assert not result["summary"]["no_regressions"]
    assert result["regressions"][0]["critical"] is True


def test_same_wrong_value_becoming_high_confidence_is_a_regression():
    old = report()
    old["cases"][0]["fields"][0].update(correct=False, confidence="medium")
    new = deepcopy(old)
    new["cases"][0]["fields"][0]["confidence"] = "high"
    result = compare_reports(old, new)
    assert result["summary"]["regressions"] == 0
    assert result["summary"]["new_false_high_confidence"] == 1


@pytest.mark.parametrize("change", [
    lambda r: r.update(dataset_sha256="c" * 64),
    lambda r: r.update(mode="recorded"),
    lambda r: r.update(input_sha256={"a": "d" * 64}),
    lambda r: r.update(input_sha256=None),
    lambda r: r.update(input_sha256={}),
    lambda r: r["cases"][0]["fields"][0].update(expected=8),
    lambda r: r["cases"][0]["fields"][0].update(critical=False),
    lambda r: r["cases"].append(deepcopy(r["cases"][0])),
    lambda r: r["cases"][0]["fields"].pop(),
    lambda r: r["cases"][0]["fields"][0].update(correct="false"),
])
def test_incomparable_reports_are_rejected(change):
    old, new = report(), report()
    change(new)
    with pytest.raises(ValueError):
        compare_reports(old, new)


def test_unchanged_failure_is_not_a_release_pass_and_cli_is_private(tmp_path):
    old = report()
    old["cases"][0]["fields"][0].update(correct=False, confidence="medium")
    result = compare_reports(old, old)
    assert result["summary"]["no_regressions"]
    assert not result["summary"]["candidate_all_fields_pass"]
    first, second = tmp_path / "old.json", tmp_path / "new.json"
    first.write_text(json.dumps(old)); second.write_text(json.dumps(old))
    output = tmp_path / "diff.json"
    command = [sys.executable, str(Path("scripts/compare_extraction_reports.py").resolve()), str(first), str(second), "--output", str(output)]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 1
    assert output.stat().st_mode & 0o777 == 0o600
    assert "actual" not in output.read_text() and "FR4" not in output.read_text()
