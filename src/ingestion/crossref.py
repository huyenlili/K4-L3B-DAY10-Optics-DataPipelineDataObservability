from __future__ import annotations

from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """TODO(student): parse Crossref payload thanh list PaperRecord.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    message = payload.get("message", {})
    items = message.get("items", []) if isinstance(message, dict) else []
    if not isinstance(items, list):
        return []

    def clean_text(value: object) -> str:
        if not isinstance(value, str):
            return ""
        return normalize_whitespace(unescape(re.sub(r"<[^>]*>", " ", value)))

    def first_text(value: object) -> str:
        if isinstance(value, list):
            return next((clean_text(item) for item in value if clean_text(item)), "")
        return clean_text(value)

    def format_date(value: object) -> str:
        if not isinstance(value, dict):
            return ""
        date_parts = value.get("date-parts")
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list):
            parts = date_parts[0]
            if parts:
                return "-".join(
                    f"{int(part):02d}" if index else f"{int(part):04d}"
                    for index, part in enumerate(parts[:3])
                )
        date_text = value.get("date-time") or value.get("timestamp")
        if isinstance(date_text, str):
            return date_text[:10]
        return ""

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = clean_text(item.get("DOI"))
        title = first_text(item.get("title"))
        summary = clean_text(item.get("abstract"))
        if not paper_id or not title or not summary:
            continue

        authors = []
        raw_authors = item.get("author", [])
        if isinstance(raw_authors, list):
            for author in raw_authors:
                if not isinstance(author, dict):
                    continue
                name = clean_text(author.get("name")) or clean_text(
                    " ".join(
                        part for part in (author.get("given"), author.get("family"))
                        if isinstance(part, str) and part.strip()
                    )
                )
                if name:
                    authors.append(name)

        raw_categories = item.get("subject", [])
        categories = (
            [clean_text(category) for category in raw_categories if clean_text(category)]
            if isinstance(raw_categories, list)
            else []
        )

        published = next(
            (
                date
                for date in (
                    format_date(item.get("published")),
                    format_date(item.get("published-print")),
                    format_date(item.get("published-online")),
                    format_date(item.get("issued")),
                )
                if date
            ),
            "",
        )
        updated = format_date(item.get("updated")) or format_date(item.get("created"))

        abs_url = clean_text(item.get("URL")) or f"https://doi.org/{paper_id}"
        pdf_url = abs_url
        links = item.get("link", [])
        if isinstance(links, list):
            pdf_url = next(
                (
                    clean_text(link.get("URL"))
                    for link in links
                    if isinstance(link, dict)
                    and clean_text(link.get("URL"))
                    and (
                        "pdf" in clean_text(link.get("content-type")).lower()
                        or clean_text(link.get("URL")).lower().endswith(".pdf")
                    )
                ),
                abs_url,
            )

        comment = clean_text(item.get("comment")) or f"Crossref record {paper_id}"
        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """TODO(student): goi source API, luu raw response, parse thanh records.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    response_path = settings.paths.raw_api_response
    if settings.refresh_source:
        params = {
            "query": settings.source_query,
            "rows": settings.max_results,
        }
        if settings.source_filter:
            params["filter"] = settings.source_filter

        try:
            for attempt in range(3):
                response = requests.get(
                    "https://api.crossref.org/works",
                    params=params,
                    timeout=30,
                )
                if response.status_code in {429, 503} and attempt < 2:
                    time.sleep(0.5 * (2**attempt))
                    continue
                response.raise_for_status()
                payload = response.json()
                break
        except (requests.RequestException, ValueError):
            if not response_path.exists():
                raise
            payload = read_json(response_path)
    else:
        payload = read_json(response_path)

    write_json(response_path, payload)
    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Read a JSON record snapshot and map each object to a PaperRecord."""
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Raw records file must contain a JSON list: {path}")

    records: list[PaperRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        def text_value(name: str) -> str:
            value = item.get(name)
            return value if isinstance(value, str) else ""

        def text_list(name: str) -> list[str]:
            values = item.get(name)
            if not isinstance(values, list):
                return []
            return [value for value in values if isinstance(value, str)]

        records.append(
            PaperRecord(
                paper_id=text_value("paper_id"),
                title=text_value("title"),
                summary=text_value("summary"),
                authors=text_list("authors"),
                categories=text_list("categories"),
                primary_category=text_value("primary_category"),
                published=text_value("published"),
                updated=text_value("updated"),
                abs_url=text_value("abs_url"),
                pdf_url=text_value("pdf_url"),
                comment=text_value("comment"),
            )
        )

    return records
