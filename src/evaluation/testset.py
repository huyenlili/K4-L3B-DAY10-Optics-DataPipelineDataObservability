from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import compact_join, first_sentence, normalize_whitespace, write_json


def build_test_set(df: pd.DataFrame, output_path: str | Path) -> list[dict[str, Any]]:
   """Build and save ten balanced ground-truth evaluation questions."""
   required_columns = {"paper_id", "title", "summary", "published", "authors", "categories"}
   missing_columns = required_columns.difference(df.columns)
   if missing_columns:
      raise ValueError(f"DataFrame is missing required columns: {', '.join(sorted(missing_columns))}")

   def clean_text(value: Any) -> str:
      if not isinstance(value, str):
         if pd.isna(value):
            return ""
         value = str(value)
      return normalize_whitespace(value)

   def list_text(values: Any) -> str:
      if not isinstance(values, (list, tuple)):
         return clean_text(values)
      return compact_join([clean_text(value) for value in values if clean_text(value)])

   prepared: list[dict[str, str]] = []
   seen_ids: set[str] = set()
   for row in df.to_dict(orient="records"):
      paper_id = clean_text(row.get("paper_id"))
      title = clean_text(row.get("title"))
      summary = clean_text(row.get("summary"))
      published = clean_text(row.get("published"))
      authors = clean_text(row.get("authors_joined")) or list_text(row.get("authors"))
      categories = clean_text(row.get("categories_joined")) or list_text(row.get("categories"))
      if not all((paper_id, title, summary, published, authors, categories)):
         continue
      if paper_id in seen_ids:
         continue
      seen_ids.add(paper_id)
      prepared.append(
         {
            "paper_id": paper_id,
            "title": title,
            "summary": summary,
            "published": published[:10],
            "authors": authors,
            "categories": categories,
         }
      )

   if len(prepared) < 10:
      raise ValueError(f"At least 10 complete, unique papers are required; found {len(prepared)}.")

   question_templates = (
      ("summary", "Summarize the paper '{title}'."),
      ("authors", "Who authored '{title}'?"),
      ("date", "When was '{title}' published?"),
      ("categories", "What categories describe '{title}'?"),
   )
   questions: list[dict[str, Any]] = []
   for index, paper in enumerate(prepared[:10]):
      question_type, template = question_templates[index % len(question_templates)]
      ground_truth = {
         "summary": first_sentence(paper["summary"]),
         "authors": paper["authors"],
         "date": paper["published"],
         "categories": paper["categories"],
      }[question_type]
      questions.append(
         {
            "id": f"test-{index + 1:02d}",
            "question_type": question_type,
            "question": template.format(title=paper["title"]),
            "ground_truth": ground_truth,
            "ground_truth_doc_ids": [paper["paper_id"]],
         }
      )

   write_json(Path(output_path), questions)
   return questions
