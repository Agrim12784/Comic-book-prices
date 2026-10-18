"""eBay Browse API adapter (active listings => price_type=ASK).

Uses the official API with OAuth client-credentials; no HTML scraping. Sold-price data
requires separate access from eBay: verify current program terms before relying on it.
"""
from __future__ import annotations

import base64
import os
import time
from collections.abc import Iterator
from decimal import Decimal

import httpx

from ..models import PriceType
from .base import RateLimiter, RawListing, SourceAdapter

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"
COMICS_CATEGORY = os.environ.get("EBAY_COMICS_CATEGORY", "259104")  # verify for your marketplace


class EbayAdapter(SourceAdapter):
    name = "ebay"

    def __init__(self, client: httpx.Client | None = None, client_id: str | None = None,
                 client_secret: str | None = None, limiter: RateLimiter | None = None,
                 max_retries: int = 4):
        self.client = client or httpx.Client(timeout=20)
        self.client_id = client_id or os.environ.get("EBAY_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("EBAY_CLIENT_SECRET", "")
        self.limiter = limiter or RateLimiter(0.25)
        self.max_retries = max_retries
        self._token: str | None = None
        self._token_exp = 0.0

    def _auth(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        if not (self.client_id and self.client_secret):
            raise RuntimeError("EBAY_CLIENT_ID / EBAY_CLIENT_SECRET not set")
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        r = self.client.post(
            TOKEN_URL,
            headers={"Authorization": f"Basic {basic}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": SCOPE},
        )
        r.raise_for_status()
        body = r.json()
        self._token = body["access_token"]
        self._token_exp = time.time() + int(body.get("expires_in", 7200))
        return self._token

    def _get(self, params: dict) -> dict:
        """GET with exponential backoff on 429/5xx."""
        for attempt in range(self.max_retries + 1):
            self.limiter.wait()
            r = self.client.get(SEARCH_URL, params=params,
                                headers={"Authorization": f"Bearer {self._auth()}"})
            if r.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                time.sleep(min(2 ** attempt, 30))
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError("unreachable")

    @staticmethod
    def normalize(item: dict) -> RawListing | None:
        price = item.get("price") or {}
        if "value" not in price or "itemId" not in item:
            return None
        return RawListing(
            source="ebay",
            source_id=item["itemId"],
            title=item.get("title", ""),
            price=Decimal(str(price["value"])),
            currency=price.get("currency", "USD"),
            price_type=PriceType.ASK,
            url=item.get("itemWebUrl"),
        )

    def search(self, query: str, limit: int = 50) -> Iterator[RawListing]:
        offset, page = 0, min(limit, 200)
        while offset < limit:
            data = self._get({"q": query, "category_ids": COMICS_CATEGORY,
                              "limit": page, "offset": offset})
            items = data.get("itemSummaries", [])
            if not items:
                return
            for it in items:
                if (listing := self.normalize(it)) is not None:
                    yield listing
            offset += page
            if offset >= data.get("total", 0):
                return
