"""Evaluate RFQ extraction against human-labelled JSONL, without writing quotes."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone


NUMERIC_FIELDS = {
    "layer", "qty", "length_mm", "width_mm", "area_inch", "thickness_mm",
    "delivery_days", "enig_thickness_uinch", "issue_ratio", "pitch_mm",
    "copper_outer_oz", "copper_inner_oz",
}
BOOLEAN_FIELDS = {"enig", "vip", "impedance", "back_drill", "bvh", "hard_gold", "is_reorder"}
STRING_FIELDS = {"material", "surface_finish", "copper_weight"}
FIELDS = NUMERIC_FIELDS | BOOLEAN_FIELDS | STRING_FIELDS
CRITICAL_FIELDS = {"layer", "qty", "length_mm", "width_mm", "area_inch", "thickness_mm", "enig", "enig_thickness_uinch"}


def reject_non_finite(value):
    raise ValueError("Non-finite JSON")


def read_jsonl(path):
    records = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line, parse_constant=reject_non_finite)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid JSON on line {line_number}") from exc
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip():
            raise ValueError(f"Line {line_number} needs a non-empty case ID")
        records.append(row)
    if not records or len({row["id"] for row in records}) != len(records):
        raise ValueError("Dataset must be non-empty and have unique case IDs")
    return records


def load_cases(path):
    cases = read_jsonl(path)
    for case in cases:
        expected = case.get("expected")
        if not isinstance(expected, dict) or not expected or set(expected) - FIELDS:
            raise ValueError(f"Invalid expected fields for {case['id']}")
        for field, value in expected.items():
            if value is None:
                continue
            if field in BOOLEAN_FIELDS and not isinstance(value, bool):
                raise ValueError(f"Expected {field} must be boolean or null")
            if field in NUMERIC_FIELDS and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError(f"Expected {field} must be finite numeric or null")
            if field in STRING_FIELDS and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"Expected {field} must be non-empty text or null")
        critical = case.get("critical_fields", sorted(set(expected) & CRITICAL_FIELDS))
        if not isinstance(critical, list) or any(not isinstance(f, str) or f not in expected for f in critical):
            raise ValueError("Critical fields must be labelled expected fields")
        case["critical_fields"] = critical
        source = case.get("input", {})
        if not isinstance(source, dict) or source.get("type") not in {"text", "image"}:
            raise ValueError("Input type must be text or image")
        key = "text" if source["type"] == "text" else "path"
        if not isinstance(source.get(key), str) or not source[key].strip():
            raise ValueError(f"Input requires {key}")
    return cases


def field_matches(field, expected, actual):
    if expected is None:
        return actual is None
    if field in BOOLEAN_FIELDS:
        return type(actual) is bool and actual is expected
    if field in NUMERIC_FIELDS:
        if isinstance(actual, bool):
            return False
        try:
            number = float(actual)
        except (ValueError, TypeError, OverflowError):
            return False
        tolerance = 0.05 if field == "enig_thickness_uinch" else 0.001
        if field in {"layer", "qty", "delivery_days"}:
            tolerance = 0
        return math.isfinite(number) and abs(number - expected) <= tolerance
    if not isinstance(actual, str):
        return False
    expected, actual = " ".join(expected.split()).casefold(), " ".join(actual.split()).casefold()
    if field == "material" and expected.replace("-", "") == "fr4":
        return actual.replace("-", "") == "fr4"
    return actual == expected


def evaluate(cases, predictions):
    by_id = {p["id"]: p for p in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {c["id"] for c in cases}:
        raise ValueError("Prediction IDs must match the dataset exactly")
    results, totals = [], {"fields": 0, "correct_fields": 0, "critical_errors": 0, "false_high_confidence": 0, "review_assessed_fields": 0, "high_confidence_fields": 0, "unassessed_review_errors": 0, "parser_errors": 0}
    per_field = {}
    for case in cases:
        prediction = by_id[case["id"]]
        parsed = prediction.get("parsed")
        failed = bool(prediction.get("error")) or not isinstance(parsed, dict)
        totals["parser_errors"] += int(failed)
        parsed = parsed if isinstance(parsed, dict) and not failed else {}
        if "thickness_mm" not in parsed and "thickness" in parsed:
            parsed = {**parsed, "thickness_mm": parsed["thickness"]}
        review = prediction.get("review") or {}
        if not isinstance(review, dict) or not isinstance(review.get("fields", []), list):
            raise ValueError("Malformed extraction review")
        review_items = review.get("fields", [])
        if any(not isinstance(r, dict) or not isinstance(r.get("field"), str) for r in review_items):
            raise ValueError("Malformed review field")
        review_by_field = {r["field"]: r for r in review_items}
        fields = []
        for field, expected in case["expected"].items():
            actual = parsed.get(field)
            correct = not failed and field_matches(field, expected, actual)
            confidence = review_by_field.get(field, {}).get("confidence")
            if not isinstance(confidence, str) or confidence not in {"high", "medium", "low", "missing"}:
                confidence = None
            critical = field in case["critical_fields"]
            totals["fields"] += 1
            totals["correct_fields"] += int(correct)
            totals["critical_errors"] += int(critical and not correct)
            totals["false_high_confidence"] += int(not correct and confidence == "high")
            totals["review_assessed_fields"] += int(confidence is not None)
            totals["high_confidence_fields"] += int(confidence == "high")
            totals["unassessed_review_errors"] += int(not correct and confidence is None)
            metric = per_field.setdefault(field, {"total": 0, "correct": 0})
            metric["total"] += 1
            metric["correct"] += int(correct)
            fields.append({"field": field, "expected": expected, "actual": actual, "correct": correct, "critical": critical, "confidence": confidence})
        results.append({"id": case["id"], "passed": all(f["correct"] for f in fields), "parser_error": failed, "latency_ms": prediction.get("latency_ms"), "fields": fields})
    return {"format_version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "summary": {**totals, "cases": len(cases), "passed_cases": sum(c["passed"] for c in results), "field_accuracy": totals["correct_fields"] / totals["fields"]}, "per_field": per_field, "cases": results}


def live_predictions(cases, dataset_path):
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required for live evaluation")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.ai_parser import parse_pcb_text
    from app.image_parser import parse_pcb_image
    from app.extraction_review import build_extraction_review
    results = []
    for case in cases:
        started = time.monotonic()
        try:
            source = case["input"]
            if source["type"] == "text":
                parsed = parse_pcb_text(source["text"])
            else:
                parsed = parse_pcb_image(str((Path(dataset_path).parent / source["path"]).resolve()))
            normalized = dict(parsed)
            if "thickness_mm" not in normalized and "thickness" in normalized:
                normalized["thickness_mm"] = normalized["thickness"]
            review = build_extraction_review(normalized, raw_input=source.get("text", ""), input_type=source["type"])
            result = {"id": case["id"], "parsed": normalized, "review": review}
        except Exception:
            # SDK errors may contain request content. Reports never persist them.
            result = {"id": case["id"], "error": "extraction_failed"}
        results.append({**result, "latency_ms": round((time.monotonic() - started) * 1000)})
    return results


def write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            name = handle.name
            os.chmod(name, 0o600)
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--predictions", help="Grade recorded JSONL without API calls")
    mode.add_argument("--live", action="store_true", help="Send dataset inputs to the configured AI API")
    parser.add_argument("--output", default="evals/private/latest-report.json")
    args = parser.parse_args()
    try:
        cases = load_cases(args.dataset)
        input_hashes = {}
        if args.live:
            for case in cases:
                source = case["input"]
                data = source["text"].encode() if source["type"] == "text" else (Path(args.dataset).parent / source["path"]).read_bytes()
                input_hashes[case["id"]] = hashlib.sha256(data).hexdigest()
        predictions = live_predictions(cases, args.dataset) if args.live else read_jsonl(args.predictions)
        report = evaluate(cases, predictions)
        report["dataset_sha256"] = hashlib.sha256(Path(args.dataset).read_bytes()).hexdigest()
        try:
            report["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1], text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            report["git_commit"] = None
        report["mode"] = "live" if args.live else "recorded"
        report["model"] = "gpt-4.1-mini" if args.live else None
        root = Path(__file__).resolve().parents[1]
        files = ["scripts/evaluate_extraction.py"]
        if args.live:
            files += ["app/ai_parser.py", "app/image_parser.py", "app/extraction_review.py"]
        report["source_sha256"] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}
        report["input_sha256"] = input_hashes
        write_report(args.output, report)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report["summary"], sort_keys=True))
    return int(report["summary"]["passed_cases"] != len(cases))


if __name__ == "__main__":
    raise SystemExit(main())
