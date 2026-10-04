"""Compare like-for-like evaluation reports without calling AI or writing quotes."""

import argparse
import json
from pathlib import Path

try:
    from .evaluate_extraction import write_report, reject_non_finite
except ImportError:
    from evaluate_extraction import write_report, reject_non_finite


def indexed_fields(report):
    fields = {}
    cases = report.get("cases")
    if report.get("format_version") != 1 or not isinstance(cases, list) or not cases:
        raise ValueError("Unsupported or empty evaluation report")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or case["id"] in ids:
            raise ValueError("Invalid or duplicate case IDs")
        ids.add(case["id"])
        if not isinstance(case.get("fields"), list) or not case["fields"]:
            raise ValueError("Missing evaluated fields")
        for field in case["fields"]:
            if not isinstance(field, dict) or not isinstance(field.get("field"), str):
                raise ValueError("Invalid report field")
            key = (case["id"], field["field"])
            if key in fields or any(type(field.get(k)) is not bool for k in ("correct", "critical")) or "expected" not in field:
                raise ValueError("Duplicate or malformed evaluated field")
            fields[key] = field
    return fields


def compare_reports(baseline, candidate):
    if not isinstance(baseline, dict) or not isinstance(candidate, dict):
        raise ValueError("Report roots must be objects")
    dataset = baseline.get("dataset_sha256")
    if not isinstance(dataset, str) or len(dataset) != 64 or any(c not in "0123456789abcdef" for c in dataset) or dataset != candidate.get("dataset_sha256"):
        raise ValueError("Reports must use the same dataset checksum")
    if baseline.get("mode") not in {"live", "recorded"} or baseline.get("mode") != candidate.get("mode"):
        raise ValueError("Do not compare live and recorded runs as like-for-like")
    before, after = indexed_fields(baseline), indexed_fields(candidate)
    if before.keys() != after.keys():
        raise ValueError("Reports must evaluate the same cases and fields")
    input_hashes = baseline.get("input_sha256")
    if baseline["mode"] == "live":
        ids = {key[0] for key in before}
        if not isinstance(input_hashes, dict) or set(input_hashes) != ids or any(
            not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h)
            for h in input_hashes.values()
        ):
            raise ValueError("Live comparisons require complete input content hashes")
    if input_hashes != candidate.get("input_sha256"):
        raise ValueError("Input content changed between runs")
    regressions, improvements, confidence_regressions = [], [], []
    for key, old in before.items():
        new = after[key]
        if type(old["expected"]) is not type(new["expected"]) or old["expected"] != new["expected"] or old["critical"] != new["critical"]:
            raise ValueError("Ground-truth labels or critical-field policy changed")
        identity = {"id": key[0], "field": key[1], "critical": new["critical"]}
        if old["correct"] and not new["correct"]:
            regressions.append(identity)
        elif not old["correct"] and new["correct"]:
            improvements.append(identity)
        old_false_high = not old["correct"] and old.get("confidence") == "high"
        new_false_high = not new["correct"] and new.get("confidence") == "high"
        if new_false_high and not old_false_high:
            confidence_regressions.append(identity)
    correct_before = sum(f["correct"] for f in before.values())
    correct_after = sum(f["correct"] for f in after.values())
    return {
        "format_version": 1,
        "dataset_sha256": dataset,
        "summary": {
            "fields": len(before), "correct_before": correct_before,
            "correct_after": correct_after, "accuracy_delta": (correct_after - correct_before) / len(before),
            "regressions": len(regressions), "improvements": len(improvements),
            "new_false_high_confidence": len(confidence_regressions),
            "no_regressions": not regressions and not confidence_regressions,
            "candidate_all_fields_pass": all(f["correct"] for f in after.values()),
        },
        "regressions": regressions, "improvements": improvements,
        "confidence_regressions": confidence_regressions,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--output", default="evals/private/comparison.json")
    args = parser.parse_args()
    try:
        report = compare_reports(json.loads(Path(args.baseline).read_text(), parse_constant=reject_non_finite), json.loads(Path(args.candidate).read_text(), parse_constant=reject_non_finite))
        write_report(args.output, report)
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report["summary"], sort_keys=True))
    # No regression is not the same as passing the release gate.
    return int(not report["summary"]["no_regressions"] or not report["summary"]["candidate_all_fields_pass"])


if __name__ == "__main__":
    raise SystemExit(main())
