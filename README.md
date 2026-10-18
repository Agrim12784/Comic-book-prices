# comicprice

Fetch and normalize comic book prices, including variants, collectibles and limited editions.

## Design

`Issue -> Edition -> Item -> PriceObservation`. An *edition* is a printing / cover / ratio
variant / foil / virgin / signed combination; an *item* is an edition in a specific condition
(raw grade or CGC/CBCS slab). Prices attach to items only. `sold`, `ask` and `guide` prices are
never mixed. Money is stored as integer minor units.

Listing titles are parsed by a deterministic rule-based parser (`parser.py`) that returns a
0-100 confidence. Below 60 (or for multi-item lots) the observation is stored with
`item_id = NULL` for review rather than guessed.

## Quickstart

    make install && make test
    cp .env.example .env   # add eBay credentials
    comicprice ingest --source ebay --query "amazing spider-man 300 cgc" --limit 50
    comicprice price --series "Amazing Spider-Man" --number 300
    comicprice stats

## Status (Phase 1-2 skeleton)

- [x] Schema, idempotent ingest, integer-cents storage
- [x] eBay Browse API adapter (active listings => `ask`), retry/backoff, rate limiting
- [x] Title parser, labeled-set precision test, median + IQR estimator with sample floor
- [ ] Grow `tests/fixtures/labeled_titles.json` to 300 titles (exit criterion for precision >= 90%)
- [ ] Metron/ComicVine identity ingest (Phase 1 exit: >= 10k issues)
- [ ] Sold-price source, guide-price source
- [ ] Alembic migrations, FastAPI service, scheduled refresh

## Compliance

Use official APIs. Do not scrape sites whose ToS forbid it, and do not redistribute scans,
images or licensed price-guide data; store IDs and derived numbers only.
