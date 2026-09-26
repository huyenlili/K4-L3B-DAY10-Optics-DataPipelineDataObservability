from __future__ import annotations

from typing import Any

import pandas as pd
import great_expectations as gx

from core.config import Settings
from core.utils import safe_slug, write_json


def evaluate_freshness_sla(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    """Evaluate whether no more than 25% of rows exceed the freshness limit."""
    total_rows = len(df)
    threshold_days = settings.freshness_threshold_days
    if "age_days" in df:
        ages = pd.to_numeric(df["age_days"], errors="coerce")
        stale_mask = ages.isna() | ages.gt(threshold_days)
        stale_rows = int(stale_mask.sum())
        missing_age_rows = int(ages.isna().sum())
    else:
        stale_rows = total_rows
        missing_age_rows = total_rows

    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    return {
        "is_fresh": total_rows > 0 and stale_ratio <= 0.25,
        "freshness_threshold_days": threshold_days,
        "max_stale_ratio": 0.25,
        "stale_rows": stale_rows,
        "missing_age_rows": missing_age_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, stage: str) -> dict[str, Any]:
    """Run four Great Expectations checks and the freshness SLA."""
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    suite = gx.ExpectationSuite(name=f"{safe_slug(stage)}_quality_suite")
    suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=1,
            max_value=settings.max_results,
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="title")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToBeBetween(
            column="summary",
            min_value=1,
            max_value=10000,
        )
    )

    gx_result = batch.validate(suite).to_json_dict()
    freshness = evaluate_freshness_sla(df, settings)
    report = {
        "success": bool(gx_result["success"] and freshness["is_fresh"]),
        "stage": stage,
        "great_expectations": gx_result,
        "freshness_sla": freshness,
    }

    stage_key = stage.strip().lower()
    if stage_key == "baseline":
        report_path = settings.paths.baseline_quality_report
    elif stage_key == "corrupted":
        report_path = settings.paths.corrupted_quality_report
    else:
        report_path = settings.paths.quality_dir / f"{safe_slug(stage)}_quality_report.json"
    write_json(report_path, report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """TODO(student): tong hop freshness report.

    Pseudo-code:
    1. Tim latest va oldest published date.
    2. Dem so dong stale.
    3. Tao payload:
       - latest_published
       - oldest_published
       - stale_rows
       - total_rows
       - is_fresh
    4. Ghi JSON report.
    """
    raise NotImplementedError("Student task: implement freshness reporting.")
