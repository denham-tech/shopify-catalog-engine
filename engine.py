"""
Shopify Public Catalog Ingestion Engine
Extracts paginated product feeds directly from Shopify storefront endpoints,
normalizing them into structured relational snapshots for validation and delta monitoring.
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
import requests
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ShopifyExtractor")


class ShopifyCatalogEngine:
    def __init__(self, base_url: str, user_agent: str = "CatalogMonitor/1.0"):
        # Strip trailing slashes and clean base domain
        self.base_url = base_url.rstrip("/")
        self.headers = {"User-Agent": user_agent}

    def fetch_page(self, page: int = 1, limit: int = 250) -> List[Dict[str, Any]]:
        endpoint = f"{self.base_url}/products.json?limit={limit}&page={page}"
        logger.info(f"Ingesting endpoint: {endpoint}")
        
        try:
            response = requests.get(endpoint, headers=self.headers, timeout=12)
            if response.status_code == 404:
                logger.error(f"Endpoint not found (404). Confirm {self.base_url} is a Shopify store.")
                return []
            response.raise_for_status()
            data = response.json()
            return data.get("products", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP fetch failure on page {page}: {e}")
            return []

    def extract_full_catalog(self, max_pages: int = 5) -> pd.DataFrame:
        records = []
        for page in range(1, max_pages + 1):
            products = self.fetch_page(page=page)
            if not products:
                logger.info(f"No further products returned at page {page}. Finalizing ingestion.")
                break

            for prod in products:
                prod_title = prod.get("title", "Unknown")
                for variant in prod.get("variants", []):
                    records.append({
                        "variant_id": variant.get("id"),
                        "title": f"{prod_title} - {variant.get('title', '')}".strip(" -"),
                        "sku": variant.get("sku") or f"SKU-{variant.get('id')}",
                        "price": float(variant.get("price", 0.0)),
                        "available": bool(variant.get("available", False))
                    })
            
            time.sleep(0.5)  # Rate limiting hygiene

        df = pd.DataFrame(records)
        logger.info(f"Ingestion complete: Extracted {len(df)} variants across {self.base_url}")
        return df

    def save_snapshot(self, df: pd.DataFrame, output_path: str) -> None:
        if df.empty:
            logger.warning("Empty snapshot. Nothing written to disk.")
            return
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info(f"Snapshot written successfully to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract live product catalogs from Shopify stores.")
    parser.add_argument("--url", "-u", required=True, help="Base storefront URL (e.g., https://colourpop.com or https://gymshark.com)")
    parser.add_argument("--output", "-o", default="data/live_catalog_snapshot.csv", help="Path to save output CSV")
    parser.add_argument("--pages", "-p", type=int, default=2, help="Max pagination depth to crawl")

    args = parser.parse_args()

    engine = ShopifyCatalogEngine(base_url=args.url)
    catalog_df = engine.extract_full_catalog(max_pages=args.pages)
    
    if catalog_df.empty:
        logger.error("Scraper terminated with 0 records extracted.")
        sys.exit(1)

    engine.save_snapshot(catalog_df, args.output)
    sys.exit(0)


if __name__ == "__main__":
    main()