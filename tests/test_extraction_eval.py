import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.evaluate_extraction import evaluate, field_matches, load_cases, write_report


def case(expected=None):
    return {"id": "case-1", "input": {"type": "text", "text": "6 layers"}, "expected": expected or {"layer": 6}, "critical_fields": ["layer"]}


@pytest.mark.parametrize("field,expected,actual,matched", [
    ("layer", 6, True, False), ("qty", 10, 10.001, False),
    ("layer", 6, "6", True), ("layer", 6, float("nan"), False),
    ("enig", False, 0, False), ("enig", False, False, True),
    ("enig", None, False, False), ("enig", None, None, True),
    ("enig_thickness_uinch", 5, 5.001, True),
    ("enig_thickness_uinch", 5, 196.85, False),
    ("material", "FR4", "FR-4", True),
    ("material", "M6 FR4-HTG", "FR4", False),
])
def test_field_comparisons(field, expected, actual, matched):
    assert field_matches(field, expected, actual) is matched


def test_grade_catches_false_high_confidence_and_missing_predictions():
    report = evaluate([case()], [{"id": "case-1", "parsed": {"layer": 4}, "review": {"fields": [{"field": "layer", "confidence": "high"}]}}])
    assert report["summary"]["critical_errors"] == 1
    assert report["summary"]["false_high_confidence"] == 1
    assert report["summary"]["field_accuracy"] == 0
    assert report["per_field"]["layer"] == {"total": 1, "correct": 0}
    with pytest.raises(ValueError, match="IDs"):
        evaluate([case()], [])
    with pytest.raises(ValueError, match="IDs"):
        evaluate([case()], [{"id": "case-1"}, {"id": "case-1"}])


def test_parser_failure_cannot_pass_null_expectations():
    null_case = case({"enig": None})
    null_case["critical_fields"] = ["enig"]
    report = evaluate([null_case], [{"id": "case-1", "error": "upstream failed"}])
    assert report["summary"]["parser_errors"] == 1
    assert report["summary"]["correct_fields"] == 0
    assert report["summary"]["passed_cases"] == 0
    assert report["summary"]["unassessed_review_errors"] == 1


def test_report_normalizes_thickness_without_defaulting_missing_values():
    c = case({"layer": 6, "thickness_mm": 1.6, "enig": None})
    report = evaluate([c], [{"id": "case-1", "parsed": {"layer": 6, "thickness": 1.6}}])
    assert report["summary"]["correct_fields"] == 3


def test_unknown_confidence_is_unassessed_and_malformed_review_is_rejected():
    report = evaluate([case()], [{"id": "case-1", "parsed": {"layer": 4}, "review": {"fields": [{"field": "layer", "confidence": []}]}}])
    assert report["summary"]["review_assessed_fields"] == 0
    assert report["summary"]["unassessed_review_errors"] == 1
    with pytest.raises(ValueError, match="review"):
        evaluate([case()], [{"id": "case-1", "parsed": {}, "review": {"fields": [{"field": []}]}}])


@pytest.mark.parametrize("mutation", [
    lambda c: c.update(expected={}),
    lambda c: c.update(expected={"not_a_field": 1}),
    lambda c: c.update(expected={"layer": True}),
    lambda c: c.update(expected={"layer": math.inf}),
    lambda c: c.update(expected={"enig": "false"}),
    lambda c: c.update(critical_fields=["qty"]),
    lambda c: c.update(input={"type": "text", "text": ""}),
])
def test_dataset_rejects_invalid_labels(tmp_path, mutation):
    c = case()
    mutation(c)
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(c))
    with pytest.raises(ValueError):
        load_cases(path)


def test_synthetic_dataset_is_valid_and_private_reports_are_restricted(tmp_path):
    cases = load_cases("evals/synthetic_rfq.jsonl")
    assert len(cases) == 10
    path = tmp_path / "report.json"
    write_report(path, {"summary": "no input content"})
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())["summary"] == "no input content"


def test_offline_cli_needs_no_api_key_and_fails_regressions(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    report_path = tmp_path / "report.json"
    dataset.write_text(json.dumps(case()) + "\n")
    predictions.write_text(json.dumps({"id": "case-1", "parsed": {"layer": 4}}) + "\n")
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env["DEBUG"] = "invalid-on-purpose"
    runner = Path("scripts/evaluate_extraction.py").resolve()
    result = subprocess.run([sys.executable, str(runner), str(dataset), "--predictions", str(predictions), "--output", str(report_path)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(report_path.read_text())
    assert report["summary"]["critical_errors"] == 1
    assert "input" not in report["cases"][0]
    assert "6 layers" not in report_path.read_text()
    predictions.write_text(json.dumps({"id": "case-1", "parsed": {"layer": 6}}) + "\n")
    result = subprocess.run([sys.executable, str(runner), str(dataset), "--predictions", str(predictions), "--output", str(report_path)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0
