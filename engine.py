"""
Shopify Catalog Engine
High-throughput extraction of product variants from Shopify endpoints
into standardized tabular data snapshots.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import requests
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ShopifyCatalogEngine")


class ShopifyCatalogEngine:
    """Ingests, parses, and normalizes catalog state from Shopify endpoints."""

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    def __init__(self, store_url: str, request_timeout: int = 15):
        cleaned_url = store_url.rstrip("/")
        self.store_url = cleaned_url
        self.base_url = cleaned_url
        self.timeout = request_timeout
        self.headers = dict(self.DEFAULT_HEADERS)
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.products: List[Dict[str, Any]] = []

    def fetch_page(
        self,
        page: int = 1,
        page_num: Optional[int] = None,
        limit: int = 250,
        **kwargs: Any
    ) -> Union[Dict[str, Any], List[Any]]:
        """Public interface returning JSON dict, or [] on network/domain failure."""
        target_page = page_num if page_num is not None else page
        endpoint = f"{self.store_url}/products.json?limit={limit}&page={target_page}"
        result = self._fetch_with_retry(endpoint)
        return result if result is not None else []

    def scrape(self, pages: int = 10, limit: int = 250) -> List[Dict[str, Any]]:
        """Paginates through /products.json and extracts flattened variant snapshots."""
        logger.info("Initializing extraction pipeline for: %s", self.store_url)
        self.products.clear()

        for page_idx in range(1, pages + 1):
            logger.info("Fetching page %d...", page_idx)
            data = self.fetch_page(page=page_idx, limit=limit)
            if not data or not isinstance(data, dict):
                logger.warning("Terminating pagination at page %d (no payload received).", page_idx)
                break

            page_products = data.get("products", [])
            if not page_products:
                logger.info("No further products detected. Reached end of catalog at page %d.", page_idx)
                break

            parsed_count = self._parse_page_products(page_products)
            logger.info("Page %d complete: Extracted %d variants.", page_idx, parsed_count)
            time.sleep(0.5)

        logger.info("Pipeline completed. Total records processed: %d", len(self.products))
        return self.products

    def _fetch_with_retry(self, url: str, retries: int = 3, backoff: float = 2.0) -> Optional[Dict[str, Any]]:
        """Executes HTTP request with backoff on transients, returning None on unresolvable hosts."""
        for attempt in range(1, retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    wait_time = backoff ** attempt
                    logger.warning("Rate-limited (429). Retrying in %.1fs...", wait_time)
                    time.sleep(wait_time)
                elif response.status_code == 403:
                    logger.warning("Direct HTTP forbidden (403). Engaging headless fallback.")
                    return self._fetch_via_playwright(url)
                elif response.status_code == 404:
                    logger.error("Endpoint not found (404): %s", url)
                    return None
                else:
                    logger.error("HTTP request error: %s [Status %d]", url, response.status_code)
                    return None
            except requests.RequestException as exc:
                logger.warning("Connection failure on attempt %d/%d: %s", attempt, retries, exc)
                # Fail immediately on invalid/non-existent hostnames to prevent long test timeouts
                err_repr = str(exc)
                if "getaddrinfo failed" in err_repr or "NameResolutionError" in err_repr:
                    return None
                if attempt == retries:
                    return None
                time.sleep(backoff ** attempt)
        return None

    def _fetch_via_playwright(self, url: str) -> Optional[Dict[str, Any]]:
        """Headless browser fallback for Cloudflare-intercepted or gated endpoints."""
        logger.info("Engaging Playwright fallback bypass...")
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_default_timeout(30000)
                response = page.goto(url, wait_until="domcontentloaded")
                if response and response.ok:
                    raw_text = page.locator("body").inner_text()
                    browser.close()
                    return json.loads(raw_text)
                browser.close()
        except Exception as err:
            logger.error("Playwright bypass failed: %s", err)
        return None

    def _parse_page_products(self, products_data: List[Dict[str, Any]]) -> int:
        """Flattens raw product entities into standardized tabular schemas."""
        initial_length = len(self.products)
        ingest_timestamp = datetime.now(timezone.utc).isoformat()

        for product in products_data:
            product_id = str(product.get("id", ""))
            title = product.get("title", "").strip()

            for variant in product.get("variants", []):
                variant_id = str(variant.get("id", ""))
                price = self._sanitize_price(variant.get("price"))

                self.products.append({
                    "variant_id": variant_id,
                    "product_id": product_id,
                    "title": title,
                    "variant_title": variant.get("title", "Default"),
                    "sku": variant.get("sku") or f"AUTO-{variant_id}",
                    "price": price,
                    "available": bool(variant.get("available", False)),
                    "inventory_quantity": variant.get("inventory_quantity"),
                    "scraped_at": ingest_timestamp
                })
        return len(self.products) - initial_length

    @staticmethod
    def _sanitize_price(raw_price: Any) -> float:
        """Normalizes variant pricing into validated floating-point formats."""
        try:
            return round(float(raw_price), 2)
        except (ValueError, TypeError):
            return 0.0

    def save_snapshot(self, output_path: str) -> Path:
        """Persists the extracted catalog state to CSV."""
        if not self.products:
            logger.warning("No records extracted. Skipping disk persistence.")
            return Path(output_path)

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(self.products)
        df.to_csv(path, index=False, encoding="utf-8")
        logger.info("Catalog snapshot saved successfully: %s (%d rows)", path.resolve(), len(df))
        return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shopify High-Throughput Catalog Ingestion Engine")
    parser.add_argument("--url", required=True, type=str, help="Shopify store domain")
    parser.add_argument("--output", default="data/snapshot.csv", type=str, help="Destination CSV path")
    parser.add_argument("--pages", default=10, type=int, help="Maximum number of paginated pages to extract")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = ShopifyCatalogEngine(store_url=args.url)
    try:
        engine.scrape(pages=args.pages)
        engine.save_snapshot(output_path=args.output)
        sys.exit(0)
    except KeyboardInterrupt:
        logger.warning("Process aborted by user.")
        sys.exit(130)
    except Exception as exc:
        logger.critical("Engine encountered fatal failure: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()