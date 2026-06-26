"""CSV URL extraction for bulk reel fetching."""

import csv
import io

from .parsers import _URL_COLUMN_NAMES, find_url_in_row, row_is_header


def parse_urls_from_csv(file_bytes: bytes) -> list[str]:
    """
    Extract reel URLs from a CSV file.

    Priority:
      1. A named URL column (url, link, reel_url, etc.)
      2. Any cell containing an Instagram reel/post URL
      3. A single bare shortcode in the row
    """
    text = file_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        return []

    header = [c.strip().lower() for c in rows[0]]
    url_col_idx = next(
        (i for i, h in enumerate(header) if h in _URL_COLUMN_NAMES),
        None,
    )

    if url_col_idx is not None and row_is_header(rows[0]):
        urls: list[str] = []
        for row in rows[1:]:
            if url_col_idx < len(row):
                val = row[url_col_idx].strip()
                if val:
                    urls.append(val)
        if urls:
            return urls

    data_start = 1 if row_is_header(rows[0]) else 0
    urls = []
    for row in rows[data_start:]:
        found = find_url_in_row(row)
        if found:
            urls.append(found)
    return urls


def parse_urls_from_csv_path(path: str) -> list[str]:
    """Read a CSV file from disk and extract reel URLs."""
    with open(path, "rb") as f:
        return parse_urls_from_csv(f.read())
