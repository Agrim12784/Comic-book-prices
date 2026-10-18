"""Schema: issue -> edition -> item -> price_observation.

Identity is layered on purpose. "Amazing Spider-Man #300" is one Issue, but dozens of
Editions (printings, cover variants, ratio variants) and many Items (edition x condition).
Prices attach to Items only, and `price_type` keeps sold, ask and guide data separate.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class PriceType(str, enum.Enum):
    SOLD = "sold"
    ASK = "ask"
    GUIDE = "guide"


class Issue(Base):
    __tablename__ = "issue"
    __table_args__ = (UniqueConstraint("series_key", "number", name="uq_issue_series_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    series_key: Mapped[str] = mapped_column(String(200), index=True)  # normalized series name
    series_name: Mapped[str] = mapped_column(String(200))
    number: Mapped[str] = mapped_column(String(20))  # string: "1/2", "-1", "100.1"
    publisher: Mapped[str | None] = mapped_column(String(100))
    year: Mapped[int | None] = mapped_column(Integer)
    external_ids: Mapped[str | None] = mapped_column(String(500))  # JSON: metron/comicvine ids

    editions: Mapped[list[Edition]] = relationship(back_populates="issue")


class Edition(Base):
    __tablename__ = "edition"
    __table_args__ = (UniqueConstraint("issue_id", "edition_key", name="uq_edition_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issue.id"), index=True)
    # Canonical string such as "p1|ratio=1:25|virgin" so editions dedupe deterministically.
    edition_key: Mapped[str] = mapped_column(String(200))
    printing: Mapped[int] = mapped_column(Integer, default=1)
    cover: Mapped[str | None] = mapped_column(String(20))
    ratio: Mapped[str | None] = mapped_column(String(20))  # "1:25"
    flags: Mapped[str] = mapped_column(String(200), default="")  # csv: virgin,foil,signed,...

    issue: Mapped[Issue] = relationship(back_populates="editions")
    items: Mapped[list[Item]] = relationship(back_populates="edition")


class Item(Base):
    __tablename__ = "item"
    __table_args__ = (
        UniqueConstraint("edition_id", "grader", "grade", name="uq_item_condition"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("edition.id"), index=True)
    grader: Mapped[str] = mapped_column(String(10), default="RAW")  # RAW | CGC | CBCS | PGX
    grade: Mapped[str] = mapped_column(String(10), default="UNGRADED")  # "9.8" or "NM"

    edition: Mapped[Edition] = relationship(back_populates="items")
    observations: Mapped[list[PriceObservation]] = relationship(back_populates="item")


class PriceObservation(Base):
    __tablename__ = "price_observation"
    __table_args__ = (
        # Idempotent ingest: same listing at the same price is stored once.
        UniqueConstraint("source", "source_id", "price_type", "price_minor", name="uq_obs"),
        Index("ix_obs_item_time", "item_id", "observed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("item.id"))  # NULL = needs review
    source: Mapped[str] = mapped_column(String(30))
    source_id: Mapped[str] = mapped_column(String(100))
    price_type: Mapped[PriceType] = mapped_column(Enum(PriceType))
    price_minor: Mapped[int] = mapped_column(Integer)  # cents: never store money as float
    currency: Mapped[str] = mapped_column(String(3))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(1000))
    match_confidence: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    item: Mapped[Item | None] = relationship(back_populates="observations")
