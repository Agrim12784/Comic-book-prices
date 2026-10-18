"""Listing-title parser: free text -> structured edition/condition fields + confidence.

Deliberately rule-based and deterministic. Every field is extracted by an explicit pattern so
that precision can be measured against a labeled set (see tests/fixtures/labeled_titles.json).
Low confidence means "send to the review queue", never "guess".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

GRADERS = ("CGC", "CBCS", "PGX")
RAW_GRADES = ("MT", "NM/MT", "NM+", "NM", "NM-", "VF/NM", "VF+", "VF", "VF-", "FN/VF",
              "FN", "VG/FN", "VG", "GD", "FR", "PR")

_ISSUE = re.compile(r"(?:#|\bno\.?\s*|\bissue\s*)(\d+/\d+|-?\d+(?:\.\d+)?)", re.IGNORECASE)
_RATIO = re.compile(r"(?<![\w#./])(?:1\s*:\s*|ratio\s+)(\d{1,4})\b", re.IGNORECASE)
_PRINTING = re.compile(r"\b(\d)(?:st|nd|rd|th)\s+print(?:ing)?\b", re.IGNORECASE)
_COVER = re.compile(r"\bcover\s+([A-Z])\b|\b([A-Z])\s+cover\b")
_SLAB = re.compile(r"\b(CGC|CBCS|PGX)\b\W{0,3}(?:SS\W{0,3}|signature series\W{0,3})?(\d{1,2}(?:\.\d)?)", re.IGNORECASE)
_SLAB_NO_GRADE = re.compile(r"\b(CGC|CBCS|PGX)\b", re.IGNORECASE)
_RAW = re.compile(r"(?<![\w/])(" + "|".join(re.escape(g) for g in sorted(RAW_GRADES, key=len, reverse=True)) + r")(?![\w/])")

FLAG_PATTERNS = {
    "virgin": r"\bvirgin\b",
    "foil": r"\bfoil\b",
    "sketch": r"\bsketch\b",
    "signed": r"\b(?:signed|signature series|\bSS\b|autograph(?:ed)?)\b",
    "exclusive": r"\b(?:exclusive|nycc|sdcc|ecc|con exclusive|store exclusive)\b",
    "newsstand": r"\bnewsstand\b",
    "limited": r"\blimited (?:edition|to \d+)\b|\blimited print run\b|\b/\d{2,4}\b",
    "facsimile": r"\bfacsimile\b",
    "reprint": r"\breprint\b",
    "lot": r"\blot of\b|\bcomplete set\b|\b\d+\s*(?:comics|issues|books)\b",
}


@dataclass
class ParsedListing:
    raw_title: str
    series_name: str | None = None
    number: str | None = None
    printing: int = 1
    cover: str | None = None
    ratio: str | None = None
    flags: list[str] = field(default_factory=list)
    grader: str = "RAW"
    grade: str = "UNGRADED"
    confidence: int = 0
    reasons: list[str] = field(default_factory=list)

    @property
    def edition_key(self) -> str:
        parts = [f"p{self.printing}"]
        if self.cover:
            parts.append(f"cover={self.cover}")
        if self.ratio:
            parts.append(f"ratio={self.ratio}")
        parts.extend(sorted(f for f in self.flags if f != "signed"))
        if "signed" in self.flags:
            parts.append("signed")
        return "|".join(parts)

    @property
    def is_lot(self) -> bool:
        return "lot" in self.flags


def normalize_series(name: str) -> str:
    name = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    name = re.sub(r"\b(the|vol(?:ume)?\s*\d+|marvel|dc|comics?)\b", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _series_guess(title: str, issue_match: re.Match | None) -> str | None:
    if not issue_match:
        return None
    head = title[: issue_match.start()]
    head = re.sub(r"\b(CGC|CBCS|PGX)\b.*$", "", head, flags=re.IGNORECASE)
    head = re.sub(r"[\[\](){}\"'*]+", " ", head)
    head = re.sub(r"\s+", " ", head).strip(" -:,")
    return head or None


def parse_title(title: str) -> ParsedListing:
    p = ParsedListing(raw_title=title)
    score = 0

    m_issue = _ISSUE.search(title)
    if m_issue:
        p.number = m_issue.group(1)
        score += 35
    else:
        p.reasons.append("no issue number")
    p.series_name = _series_guess(title, m_issue)
    if p.series_name:
        score += 25
    else:
        p.reasons.append("no series name")

    if (m := _RATIO.search(title)):
        p.ratio = f"1:{m.group(1)}"
    if (m := _PRINTING.search(title)):
        p.printing = int(m.group(1))
    if (m := _COVER.search(title)):
        p.cover = (m.group(1) or m.group(2)).upper()

    for flag, pat in FLAG_PATTERNS.items():
        if re.search(pat, title, re.IGNORECASE):
            p.flags.append(flag)
    # A "1:25" ratio variant is limited by definition; keep the flag set consistent.
    if p.ratio and "limited" not in p.flags:
        p.flags.append("limited")

    if (m := _SLAB.search(title)):
        p.grader, p.grade = m.group(1).upper(), m.group(2)
        score += 30
    elif _SLAB_NO_GRADE.search(title):
        p.grader = _SLAB_NO_GRADE.search(title).group(1).upper()
        p.reasons.append("slab company without grade")
        score += 10
    elif (m := _RAW.search(title)):
        p.grade = m.group(1)
        score += 20
    else:
        p.reasons.append("no grade")
        score += 5

    if p.is_lot:
        score = min(score, 30)
        p.reasons.append("multi-item lot")

    p.confidence = min(score, 100)
    return p
