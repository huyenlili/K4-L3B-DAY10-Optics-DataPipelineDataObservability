from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from math import ceil
from pathlib import Path

import pandas as pd

from core.utils import write_json


def corrupt_clean_dataframe(
    clean_df: pd.DataFrame,
    log_path: str | Path,
) -> pd.DataFrame:
    """Apply six deterministic data corruptions and log every affected row."""
    corrupted_df = clean_df.reset_index(drop=True).copy(deep=True)
    events: list[dict[str, object]] = []

    def snapshot(row_index: int) -> dict[str, object]:
        serialized = corrupted_df.loc[[row_index]].to_json(
            orient="records", date_format="iso"
        )
        return json.loads(serialized)[0]

    def log_event(
        corruption_type: str,
        before: dict[str, object],
        after: dict[str, object] | None,
        action: str,
    ) -> None:
        events.append(
            {
                "corruption_type": corruption_type,
                "paper_id": before.get("paper_id"),
                "action": action,
                "before": before,
                "after": after,
            }
        )

    def select_rows(operation_index: int, predicate=lambda _row: True) -> list[int]:
        available = [
            row_index
            for row_index in corrupted_df.index
            if predicate(corrupted_df.loc[row_index])
        ]
        if not available:
            return []
        count = min(len(available), max(1, ceil(len(corrupted_df) * 0.1)))
        start = (operation_index * count) % len(available)
        return [available[(start + offset) % len(available)] for offset in range(count)]

    def rebuild_embedding_text(row_index: int) -> None:
        row = corrupted_df.loc[row_index]
        parts = [f"Title: {row['title']}", f"Summary: {row['summary']}"]
        authors = row.get("authors_joined", "")
        categories = row.get("categories_joined", "")
        if isinstance(authors, str) and authors:
            parts.append(f"Authors: {authors}")
        if isinstance(categories, str) and categories:
            parts.append(f"Categories: {categories}")
        corrupted_df.at[row_index, "text_for_embedding"] = "\n".join(parts)

    if corrupted_df.empty:
        write_json(
            Path(log_path),
            {"source_rows": 0, "output_rows": 0, "entries": events},
        )
        return corrupted_df

    if len(corrupted_df) > 1:
        drop_count = min(len(corrupted_df) - 1, ceil(len(corrupted_df) * 0.2))
        published_dates = pd.to_datetime(
            corrupted_df["published"], errors="coerce", utc=True
        )
        latest_indices = published_dates.sort_values(
            ascending=False, kind="stable", na_position="last"
        ).index[:drop_count]
        for row_index in latest_indices:
            log_event("drop_latest_records", snapshot(row_index), None, "dropped")
        corrupted_df = corrupted_df.drop(index=latest_indices).copy()

    blank_indices = select_rows(
        0, lambda row: isinstance(row.get("summary"), str) and bool(row["summary"])
    )
    for row_index in blank_indices:
        before = snapshot(row_index)
        corrupted_df.at[row_index, "summary"] = ""
        if "summary_chars" in corrupted_df:
            corrupted_df.at[row_index, "summary_chars"] = 0
        rebuild_embedding_text(row_index)
        log_event("blank_summary", before, snapshot(row_index), "modified")

    noise_indices = select_rows(
        1, lambda row: isinstance(row.get("summary"), str) and bool(row["summary"])
    )
    for row_index in noise_indices:
        before = snapshot(row_index)
        corrupted_df.at[row_index, "summary"] = (
            f"{corrupted_df.at[row_index, 'summary']} ### NOISE 0xFF !!!"
        )
        if "summary_chars" in corrupted_df:
            corrupted_df.at[row_index, "summary_chars"] = len(
                corrupted_df.at[row_index, "summary"]
            )
        rebuild_embedding_text(row_index)
        log_event("inject_noise", before, snapshot(row_index), "modified")

    title_indices = select_rows(
        2, lambda row: isinstance(row.get("title"), str) and len(row["title"]) >= 8
    )
    for row_index in title_indices:
        before = snapshot(row_index)
        corrupted_df.at[row_index, "title"] = corrupted_df.at[row_index, "title"][:7]
        rebuild_embedding_text(row_index)
        log_event("truncate_title", before, snapshot(row_index), "modified")

    date_indices = select_rows(
        3,
        lambda row: pd.notna(row.get("published"))
        and pd.notna(pd.to_datetime(row.get("published"), errors="coerce", utc=True)),
    )
    stale_date = (datetime.now(UTC).date() - timedelta(days=365)).isoformat()
    for row_index in date_indices:
        before = snapshot(row_index)
        corrupted_df.at[row_index, "published"] = stale_date
        if "age_days" in corrupted_df:
            corrupted_df.at[row_index, "age_days"] = 365
        log_event("stale_date", before, snapshot(row_index), "modified")

    duplicate_indices = select_rows(4)
    duplicate_rows = corrupted_df.loc[duplicate_indices].copy()
    for row_index in duplicate_indices:
        row_snapshot = snapshot(row_index)
        log_event(
            "duplicate_rows",
            row_snapshot,
            row_snapshot.copy(),
            "duplicate_added",
        )
    corrupted_df = pd.concat([corrupted_df, duplicate_rows], ignore_index=True)

    write_json(
        Path(log_path),
        {
            "source_rows": len(clean_df),
            "output_rows": len(corrupted_df),
            "entries": events,
        },
    )
    return corrupted_df
