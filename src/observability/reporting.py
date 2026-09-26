from __future__ import annotations

import json
from typing import Any

from core.utils import write_text


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write the baseline source, evaluation, quality, and freshness summary."""
    lines = ["# Phase 1 Baseline Report", "", "## Source"]
    lines.extend(f"- **{key}**: {value}" for key, value in source_summary.items())
    lines.extend(["", "## RAG Evaluation"])
    lines.extend(
        f"- **{key}**: {json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value}"
        for key, value in metrics.items()
    )
    lines.extend(
        [
            "",
            "## Great Expectations Quality Gate",
            f"- **Overall success**: {quality.get('success', False)}",
        ]
    )
    gx_result = quality.get("great_expectations", {})
    statistics = gx_result.get("statistics", {})
    if statistics:
        lines.append(
            "- **Expectations**: "
            f"{statistics.get('successful_expectations', 0)}/"
            f"{statistics.get('evaluated_expectations', 0)} passed"
        )
    for result in gx_result.get("results", []):
        expectation = result.get("expectation_config", {})
        name = expectation.get("type", expectation.get("expectation_type", "Expectation"))
        lines.append(f"- `{name}`: {'PASS' if result.get('success') else 'FAIL'}")

    lines.extend(["", "## Freshness SLA"])
    lines.extend(f"- **{key}**: {value}" for key, value in freshness.items())
    lines.append("")
    write_text(report_path, "\n".join(lines))


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write the three-state RAG, quality, and freshness comparison."""
    def metric_value(metrics: dict[str, Any], key: str) -> str:
        value = metrics.get(key)
        if value is None:
            return "N/A"
        if isinstance(value, (int, float)):
            return f"{value:.3f}" if isinstance(value, float) else str(value)
        return str(value)

    def quality_value(quality: dict[str, Any]) -> str:
        return "PASS" if quality.get("success") else "FAIL"

    def freshness_value(freshness: dict[str, Any]) -> str:
        status = "FRESH" if freshness.get("is_fresh") else "STALE"
        ratio = freshness.get("stale_ratio")
        return f"{status} ({ratio:.1%} stale)" if isinstance(ratio, (int, float)) else status

    table_rows = [
        ("Retrieval Hit Rate", "retrieval_hit_rate"),
        ("Mean Token F1", "mean_token_f1"),
        ("Judge Accuracy", "judge_accuracy"),
        ("Mean Judge Score", "mean_judge_score"),
    ]
    lines = [
        "# Corruption and Repair Report",
        "",
        "| Metric | Baseline | Corrupted | Repaired |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label, key in table_rows:
        lines.append(
            f"| {label} | {metric_value(baseline_metrics, key)} "
            f"| {metric_value(corrupted_metrics, key)} "
            f"| {metric_value(repaired_metrics, key)} |"
        )
    lines.extend(
        [
            f"| Great Expectations Quality Gate | N/A | {quality_value(corrupted_quality)} "
            f"| {quality_value(repaired_quality)} |",
            f"| Freshness SLA | N/A | {freshness_value(corrupted_freshness)} "
            f"| {freshness_value(repaired_freshness)} |",
            "",
            "## Observed Impact",
        ]
    )
    for label, key in table_rows[:2]:
        baseline = baseline_metrics.get(key)
        corrupted = corrupted_metrics.get(key)
        repaired = repaired_metrics.get(key)
        if all(isinstance(value, (int, float)) for value in (baseline, corrupted, repaired)):
            lines.append(
                f"- **{label}**: corruption delta "
                f"{corrupted - baseline:+.3f}; repair delta from corrupted "
                f"{repaired - corrupted:+.3f}."
            )
    lines.append("")
    write_text(report_path, "\n".join(lines))
