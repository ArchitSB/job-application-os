"""Conservative, deterministic lookup normalization; never automatically merges records."""

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SUFFIXES = {"inc", "incorporated", "llc", "ltd", "limited", "pvt", "private", "corp", "corporation"}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[^\w\s+#]", " ", value).split())


def normalize_company(value: str) -> str:
    words = normalize_text(value).split()
    while len(words) > 1 and words[-1] in SUFFIXES:
        words.pop()
    return " ".join(words)


def normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.casefold().startswith("utm_") and k.casefold() not in {"gclid", "fbclid"}
    ]
    # Preserve identifiers, path case and non-tracking query parameters.
    host = (parts.hostname or "").casefold()
    if parts.port and parts.port not in (80, 443):
        host += f":{parts.port}"
    return urlunsplit(("https", host, parts.path.rstrip("/") or "/", urlencode(sorted(query)), ""))
