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


def test_practice_dataset_has_twenty_matching_sources_and_difficulty_coverage():
    cases = load_cases("evals/practice_rfq_20.jsonl")
    assert len(cases) == 20
    assert [c["id"] for c in cases] == [f"practice-{n:02d}" for n in range(1, 21)]
    assert {level: sum(c["difficulty"] == level for c in cases)
            for level in ("basic", "intermediate", "review")} == {
                "basic": 8, "intermediate": 6, "review": 6}
    sources = Path("evals/practice_rfq_20")
    assert len(list(sources.glob("*.txt"))) == 20
    for c in cases:
        assert c["input"]["type"] == "text"
        assert (sources / f"{c['id']}.txt").read_text().rstrip() == c["input"]["text"]
        assert c["input"]["text"].startswith("SYNTHETIC RFQ")
        assert c["manual_review"]


def test_practice_labels_preserve_ambiguity_and_explicit_unit_conversions():
    cases = {c["id"]: c for c in load_cases("evals/practice_rfq_20.jsonl")}
    for case_id, fields in {
        "practice-13": ["qty", "delivery_days"],
        "practice-14": ["surface_finish", "enig", "enig_thickness_uinch"],
        "practice-15": ["enig_thickness_uinch"],
        "practice-16": ["qty"],
        "practice-17": ["surface_finish", "enig", "hard_gold"],
        "practice-18": ["length_mm", "width_mm"],
        "practice-19": ["thickness_mm", "surface_finish", "delivery_days"],
        "practice-20": ["qty"],
    }.items():
        assert all(cases[case_id]["expected"][field] is None for field in fields)
    assert cases["practice-09"]["expected"]["enig_thickness_uinch"] == pytest.approx(0.127 * 39.37)
    assert cases["practice-10"]["expected"]["length_mm"] == pytest.approx(4 * 25.4)
    assert cases["practice-11"]["expected"]["qty"] == 40
    assert cases["practice-12"]["expected"]["layer"] == 6


def test_review_regression_variants_preserve_unknown_vs_rejected_and_board_totals():
    cases = load_cases("evals/review_regression_variants.jsonl")
    assert len(cases) == 6
    by_id = {c["id"]: c for c in cases}
    assert by_id["variant-negative-hard-gold"]["expected"]["hard_gold"] is False
    assert by_id["variant-unknown-not-negative"]["expected"]["hard_gold"] is None
    assert by_id["variant-unknown-not-negative"]["expected"]["enig"] is None
    assert by_id["variant-unresolved-sets"]["expected"]["qty"] is None
    assert by_id["variant-confirmed-board-total"]["expected"]["qty"] == 18


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
