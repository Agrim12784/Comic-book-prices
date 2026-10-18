from __future__ import annotations

import argparse

from sqlalchemy import func, select

from .adapters.ebay import EbayAdapter
from .db import get_engine, init_db, make_session
from .ingest import ingest
from .models import Edition, Issue, Item, PriceObservation, PriceType
from .pricing import estimate

ADAPTERS = {"ebay": EbayAdapter}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="comicprice")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest", help="fetch listings from a source and store them")
    ing.add_argument("--source", choices=ADAPTERS, required=True)
    ing.add_argument("--query", required=True)
    ing.add_argument("--limit", type=int, default=50)
    q = sub.add_parser("price", help="estimate price for an issue")
    q.add_argument("--series", required=True)
    q.add_argument("--number", required=True)
    sub.add_parser("stats", help="row counts and review-queue size")
    args = ap.parse_args(argv)

    engine = get_engine()
    init_db(engine)
    s = make_session(engine)

    if args.cmd == "ingest":
        st = ingest(s, ADAPTERS[args.source]().search(args.query, args.limit))
        print(f"seen={st.seen} inserted={st.inserted} dup={st.duplicates} "
              f"matched={st.matched} review={st.review_queue} match_rate={st.match_rate:.0%}")
    elif args.cmd == "stats":
        print("observations:", s.scalar(select(func.count(PriceObservation.id))))
        print("unmatched   :", s.scalar(select(func.count(PriceObservation.id))
                                        .where(PriceObservation.item_id.is_(None))))
    elif args.cmd == "price":
        from .parser import normalize_series
        rows = s.execute(
            select(Edition.edition_key, Item.grader, Item.grade, PriceObservation.price_minor)
            .join(Item, Item.edition_id == Edition.id)
            .join(Issue, Issue.id == Edition.issue_id)
            .join(PriceObservation, PriceObservation.item_id == Item.id)
            .where(Issue.series_key == normalize_series(args.series), Issue.number == args.number,
                   PriceObservation.price_type == PriceType.ASK)).all()
        groups: dict[tuple, list[int]] = {}
        for ed, grader, grade, p in rows:
            groups.setdefault((ed, grader, grade), []).append(p)
        for (ed, grader, grade), prices in sorted(groups.items()):
            e = estimate(prices)
            val = f"${e.median_minor / 100:,.2f}" if e.median_minor else "n/a"
            print(f"{ed:<32} {grader:<5} {grade:<9} ask-median={val:<12} n={e.n} [{e.status}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
