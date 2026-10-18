import json
from pathlib import Path

import pytest

from comicprice.parser import normalize_series, parse_title

LABELED = json.loads((Path(__file__).parent / "fixtures" / "labeled_titles.json").read_text())


@pytest.mark.parametrize("row", LABELED, ids=lambda r: r["title"][:40])
def test_labeled_titles(row):
    p = parse_title(row["title"])
    assert (p.number, p.grader, p.grade, p.ratio, p.printing) == (
        row["number"], row["grader"], row["grade"], row["ratio"], row["printing"])


def test_labeled_precision_at_least_90pct():
    ok = 0
    for row in LABELED:
        p = parse_title(row["title"])
        ok += (p.number, p.grader, p.grade, p.ratio, p.printing) == (
            row["number"], row["grader"], row["grade"], row["ratio"], row["printing"])
    assert ok / len(LABELED) >= 0.9


def test_series_extraction_and_normalization():
    p = parse_title("The Amazing Spider-Man #300 CGC 9.8")
    assert normalize_series(p.series_name) == "amazing spider man"


def test_flags_and_edition_key():
    p = parse_title("Venom #1 Virgin Variant 1:100 CGC SS 9.9 Signed")
    assert {"virgin", "limited", "signed"} <= set(p.flags)
    assert p.edition_key == "p1|ratio=1:100|limited|virgin|signed"


def test_lot_is_capped_for_review():
    p = parse_title("Lot of 10 comics Batman #1-10 NM")
    assert p.is_lot and p.confidence <= 30


def test_no_issue_number_low_confidence():
    p = parse_title("Cool Marvel comic book")
    assert p.confidence < 60 and p.number is None


def test_slab_without_grade_noted():
    p = parse_title("Batman #1 CGC graded")
    assert "slab company without grade" in p.reasons


def test_ratio_does_not_eat_grade():
    p = parse_title("Batman #50 CGC 9.8")
    assert p.ratio is None


def test_half_issue_is_not_a_ratio():
    p = parse_title("Wolverine #1/2 NM")
    assert p.ratio is None and p.number == "1/2"
