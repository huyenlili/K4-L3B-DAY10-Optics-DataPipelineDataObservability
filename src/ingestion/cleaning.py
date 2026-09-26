from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
     """TODO(student): clean raw records thanh dataframe san sang de embed.

     Pseudo-code:
     1. Normalize title, summary, authors, categories.
     2. Parse published/updated date.
     3. Tinh age_days.
     4. Tao cot helper:
        - authors_joined
        - categories_joined
        - summary_chars
        - text_for_embedding
     5. Drop duplicates va filter row xau.
     6. Sort dataframe va return.
     """
     field_names = list(PaperRecord.__dataclass_fields__)
     dataframe = pd.DataFrame([asdict(record) for record in records], columns=field_names)

     text_columns = (
         "paper_id",
         "title",
         "summary",
         "primary_category",
         "published",
         "updated",
         "abs_url",
         "pdf_url",
         "comment",
     )
     for column in text_columns:
         dataframe[column] = dataframe[column].map(
             lambda value: normalize_whitespace(value) if isinstance(value, str) else ""
         )

     for column in ("authors", "categories"):
         dataframe[column] = dataframe[column].map(
             lambda values: [
                 normalize_whitespace(value)
                 for value in values
                 if isinstance(value, str) and normalize_whitespace(value)
             ]
             if isinstance(values, list)
             else []
         )

     dataframe = dataframe.loc[
         dataframe["paper_id"].ne("")
         & dataframe["title"].ne("")
         & dataframe["summary"].ne("")
     ].copy()
     dataframe = dataframe.drop_duplicates(subset="paper_id", keep="first").copy()

     published_dates = pd.to_datetime(dataframe["published"], errors="coerce", utc=True)
     updated_dates = pd.to_datetime(dataframe["updated"], errors="coerce", utc=True)
     dataframe["published"] = published_dates.dt.strftime("%Y-%m-%d").fillna("")
     dataframe["updated"] = updated_dates.dt.strftime("%Y-%m-%d").fillna("")

     normalized_run_date = pd.Timestamp(run_date)
     if normalized_run_date.tzinfo is None:
         normalized_run_date = normalized_run_date.tz_localize("UTC")
     else:
         normalized_run_date = normalized_run_date.tz_convert("UTC")
     dataframe["age_days"] = (
         normalized_run_date.normalize() - published_dates.dt.normalize()
     ).dt.days.astype("Int64")

     dataframe["authors_joined"] = dataframe["authors"].map(compact_join)
     dataframe["categories_joined"] = dataframe["categories"].map(compact_join)
     dataframe["summary_chars"] = dataframe["summary"].str.len()
     dataframe["text_for_embedding"] = dataframe.apply(
         lambda row: "\n".join(
             value
             for value in (
                 f"Title: {row['title']}",
                 f"Summary: {row['summary']}",
                 f"Authors: {row['authors_joined']}" if row["authors_joined"] else "",
                 f"Categories: {row['categories_joined']}" if row["categories_joined"] else "",
             )
             if value
         ),
         axis=1,
     )

     return dataframe.sort_values(
         "published", ascending=False, kind="stable", na_position="last"
     ).reset_index(drop=True)
