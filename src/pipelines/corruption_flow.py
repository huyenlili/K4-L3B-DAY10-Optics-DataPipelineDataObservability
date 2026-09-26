from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import read_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import evaluate_freshness_sla, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _save_dataframe(dataframe: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(csv_path, index=False)
    dataframe.to_json(json_path, orient="records", indent=2, force_ascii=False)


def repair_from_raw_snapshot(settings: Settings) -> pd.DataFrame:
    """Rebuild clean data from the immutable local raw-record snapshot."""
    records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(records, datetime.now(UTC))
    _save_dataframe(
        repaired_df,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_clean_json,
    )
    return repaired_df


def _evaluate_dataset(
    dataframe: pd.DataFrame,
    settings: Settings,
    embeddings_path: Path,
    metrics_path: Path,
    answers_path: Path,
) -> dict[str, Any]:
    index = LocalEmbeddingIndex.build(
        dataframe,
        settings,
        embeddings_output_path=embeddings_path,
    )
    evaluation = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        metrics_path,
        answers_path,
    )
    return evaluation.summary


def run_corruption_flow_pipeline(settings: Settings) -> dict[str, Any]:
    """Corrupt, evaluate, repair from raw, and compare all three data states."""
    clean_df = pd.read_json(settings.paths.clean_json)
    build_test_set(clean_df, settings.paths.eval_testset)

    if settings.paths.baseline_metrics.exists():
        baseline_metrics = read_json(settings.paths.baseline_metrics)
    else:
        baseline_metrics = _evaluate_dataset(
            clean_df,
            settings,
            settings.paths.embeddings_json,
            settings.paths.baseline_metrics,
            settings.paths.baseline_answers,
        )

    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    _save_dataframe(
        corrupted_df,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )
    corrupted_metrics = _evaluate_dataset(
        corrupted_df,
        settings,
        settings.paths.corrupted_embeddings_json,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = corrupted_quality.get("freshness_sla") or evaluate_freshness_sla(
        corrupted_df, settings
    )

    repaired_df = repair_from_raw_snapshot(settings)
    repaired_metrics = _evaluate_dataset(
        repaired_df,
        settings,
        settings.paths.repaired_embeddings_json,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = repaired_quality.get("freshness_sla") or evaluate_freshness_sla(
        repaired_df, settings
    )

    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )
    return {
        "baseline_metrics": baseline_metrics,
        "corrupted_metrics": corrupted_metrics,
        "repaired_metrics": repaired_metrics,
        "corrupted_quality": corrupted_quality,
        "repaired_quality": repaired_quality,
        "corruption_log_path": str(settings.paths.corruption_log),
        "report_path": str(settings.paths.comparison_report),
    }


def main() -> None:
    result = run_corruption_flow_pipeline(load_settings())
    print("Phase 2 complete:")
    print(
        "  Retrieval hit rate: "
        f"baseline={result['baseline_metrics']['retrieval_hit_rate']:.3f}, "
        f"corrupted={result['corrupted_metrics']['retrieval_hit_rate']:.3f}, "
        f"repaired={result['repaired_metrics']['retrieval_hit_rate']:.3f}"
    )
    print(
        "  Token F1: "
        f"baseline={result['baseline_metrics']['mean_token_f1']:.3f}, "
        f"corrupted={result['corrupted_metrics']['mean_token_f1']:.3f}, "
        f"repaired={result['repaired_metrics']['mean_token_f1']:.3f}"
    )
    print(f"Report: {result['report_path']}")
