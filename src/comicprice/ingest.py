from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .adapters.base import RawListing
from .models import Edition, Issue, Item, PriceObservation
from .parser import ParsedListing, normalize_series, parse_title

MIN_CONFIDENCE = 60  # below this, store the observation unmatched (item_id NULL) for review


@dataclass
class IngestStats:
    seen: int = 0
    inserted: int = 0
    duplicates: int = 0
    matched: int = 0
    review_queue: int = 0

    @property
    def match_rate(self) -> float:
        return self.matched / self.inserted if self.inserted else 0.0


def _get_or_create_item(s: Session, p: ParsedListing) -> Item:
    key = normalize_series(p.series_name or "")
    issue = s.scalar(select(Issue).where(Issue.series_key == key, Issue.number == p.number))
    if issue is None:
        issue = Issue(series_key=key, series_name=p.series_name, number=p.number)
        s.add(issue)
        s.flush()
    ed = s.scalar(select(Edition).where(Edition.issue_id == issue.id,
                                        Edition.edition_key == p.edition_key))
    if ed is None:
        ed = Edition(issue_id=issue.id, edition_key=p.edition_key, printing=p.printing,
                     cover=p.cover, ratio=p.ratio, flags=",".join(sorted(p.flags)))
        s.add(ed)
        s.flush()
    item = s.scalar(select(Item).where(Item.edition_id == ed.id, Item.grader == p.grader,
                                       Item.grade == p.grade))
    if item is None:
        item = Item(edition_id=ed.id, grader=p.grader, grade=p.grade)
        s.add(item)
        s.flush()
    return item


def ingest(session: Session, listings: Iterable[RawListing]) -> IngestStats:
    stats = IngestStats()
    for raw in listings:
        stats.seen += 1
        exists = session.scalar(select(PriceObservation.id).where(
            PriceObservation.source == raw.source,
            PriceObservation.source_id == raw.source_id,
            PriceObservation.price_type == raw.price_type,
            PriceObservation.price_minor == raw.price_minor))
        if exists:
            stats.duplicates += 1
            continue

        parsed = parse_title(raw.title)
        item_id = None
        if parsed.confidence >= MIN_CONFIDENCE and not parsed.is_lot and parsed.number:
            item_id = _get_or_create_item(session, parsed).id
            stats.matched += 1
        else:
            stats.review_queue += 1

        session.add(PriceObservation(
            item_id=item_id, source=raw.source, source_id=raw.source_id,
            price_type=raw.price_type, price_minor=raw.price_minor, currency=raw.currency,
            title=raw.title[:500], url=raw.url, match_confidence=parsed.confidence,
            observed_at=raw.observed_at))
        stats.inserted += 1
    session.commit()
    return stats
