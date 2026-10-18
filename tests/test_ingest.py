from decimal import Decimal

import httpx
from sqlalchemy import func, select

from comicprice.adapters.base import RateLimiter, RawListing
from comicprice.adapters.ebay import EbayAdapter
from comicprice.db import get_engine, init_db, make_session
from comicprice.ingest import ingest
from comicprice.models import Item, PriceObservation, PriceType


def _listings():
    mk = lambda i, t, p: RawListing("test", i, t, Decimal(p), "USD", PriceType.ASK)
    return [
        mk("1", "Amazing Spider-Man #300 CGC 9.8", "1200.00"),
        mk("2", "Amazing Spider-Man #300 CGC 9.8", "1150.50"),
        mk("3", "Batman #100 1:25 Variant NM", "40.00"),
        mk("4", "Lot of 20 comics assorted", "30.00"),
    ]


def _session():
    e = get_engine("sqlite://")
    init_db(e)
    return make_session(e)


def test_ingest_matches_and_queues_review():
    s = _session()
    st = ingest(s, _listings())
    assert (st.inserted, st.matched, st.review_queue) == (4, 3, 1)
    assert s.scalar(select(func.count(Item.id))) == 2  # two listings share one item


def test_ingest_is_idempotent():
    s = _session()
    ingest(s, _listings())
    st = ingest(s, _listings())
    assert st.inserted == 0 and st.duplicates == 4
    assert s.scalar(select(func.count(PriceObservation.id))) == 4


def test_price_stored_as_integer_cents():
    s = _session()
    ingest(s, _listings())
    prices = set(s.scalars(select(PriceObservation.price_minor)))
    assert 115050 in prices and 4000 in prices


def test_rate_limiter_sleeps():
    t = [0.0]
    slept = []
    rl = RateLimiter(1.0, clock=lambda: t[0], sleep=lambda d: slept.append(d))
    rl.wait()
    t[0] = 0.25
    rl.wait()
    assert slept == [0.75]


def test_ebay_adapter_with_mock_transport():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 7200})
        return httpx.Response(200, json={"total": 2, "itemSummaries": [
            {"itemId": "v1|1|0", "title": "Saga #1 NM", "price": {"value": "9.99", "currency": "USD"},
             "itemWebUrl": "https://example.test/1"},
            {"itemId": "v1|2|0", "title": "bad item without price"}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ad = EbayAdapter(client=client, client_id="a", client_secret="b",
                     limiter=RateLimiter(0, sleep=lambda d: None))
    out = list(ad.search("saga", limit=10))
    assert len(out) == 1 and out[0].price_minor == 999 and out[0].price_type == PriceType.ASK
