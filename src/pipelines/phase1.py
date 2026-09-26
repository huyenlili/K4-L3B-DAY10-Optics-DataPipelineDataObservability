from __future__ import annotations

from datetime import UTC, datetime

from core.config import Settings, load_settings
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import evaluate_freshness_sla, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def run_phase1_pipeline(settings: Settings) -> dict:
    """Run ingestion, cleaning, indexing, evaluation, quality, and reporting."""
    records = fetch_source_records(settings)
    dataframe = build_clean_dataframe(records, datetime.now(UTC))

    settings.paths.clean_csv.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(settings.paths.clean_csv, index=False)
    dataframe.to_json(settings.paths.clean_json, orient="records", indent=2, force_ascii=False)

    index = LocalEmbeddingIndex.build(
        dataframe,
        settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    test_set = build_test_set(dataframe, settings.paths.eval_testset)
    evaluation = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )

    quality = run_data_quality_checks(dataframe, settings, "baseline")
    freshness = quality.get("freshness_sla") or evaluate_freshness_sla(dataframe, settings)
    source_summary = {
        "source_api": settings.source_api,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "record_count": len(records),
        "raw_response_path": str(settings.paths.raw_api_response),
        "raw_records_path": str(settings.paths.raw_records_json),
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary,
        evaluation.summary,
        quality,
        freshness,
    )

    return {
        "source": source_summary,
        "clean_rows": len(dataframe),
        "indexed_documents": len(index.documents),
        "test_questions": len(test_set),
        "metrics": evaluation.summary,
        "quality": quality,
        "freshness": freshness,
        "report_path": str(settings.paths.baseline_report),
    }

def main() -> None:
    result = run_phase1_pipeline(load_settings())
    print(
        "Phase 1 complete: "
        f"{result['clean_rows']} clean rows, "
        f"{result['test_questions']} test questions, "
        f"retrieval hit rate={result['metrics']['retrieval_hit_rate']:.3f}, "
        f"token F1={result['metrics']['mean_token_f1']:.3f}, "
        f"quality={result['quality']['success']}"
    )
    print(f"Report: {result['report_path']}")
