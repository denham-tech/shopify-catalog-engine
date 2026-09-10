import asyncio
import json
import sqlite3
import pandas as pd
from playwright.async_api import async_playwright

class ShopifyCatalogEngine:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.endpoint = f"{self.base_url}/products.json"
        self.records = []

    async def fetch_catalog(self, max_pages: int = 2):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            for page_num in range(1, max_pages + 1):
                target = f"{self.endpoint}?limit=250&page={page_num}"
                print(f"[*] Ingesting page {page_num}: {target}")

                try:
                    response = await page.goto(target, wait_until="networkidle", timeout=20000)
                    if response.status != 200:
                        print(f"[!] Warning: HTTP {response.status}. Terminating pagination.")
                        break

                    content = await page.inner_text("body")
                    data = json.loads(content)
                    products = data.get("products", [])

                    if not products:
                        print(f"[*] Reached end of catalog at page {page_num}.")
                        break

                    for prod in products:
                        for variant in prod.get("variants", []):
                            self.records.append({
                                "product_id": prod.get("id"),
                                "title": prod.get("title"),
                                "handle": prod.get("handle"),
                                "vendor": prod.get("vendor"),
                                "product_type": prod.get("product_type"),
                                "variant_id": variant.get("id"),
                                "variant_title": variant.get("title"),
                                "sku": variant.get("sku"),
                                "price": float(variant.get("price", 0.0)),
                                "available": variant.get("available"),
                                "inventory_quantity": variant.get("inventory_quantity", None),
                                "url": f"{self.base_url}/products/{prod.get('handle')}"
                            })

                except Exception as err:
                    print(f"[!] Pipeline error on page {page_num}: {err}")
                    break

            await browser.close()

    def process_and_persist(self):
        if not self.records:
            print("[!] No records to process.")
            return

        df = pd.DataFrame(self.records)
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df.drop_duplicates(subset=["variant_id"], inplace=True)

        csv_filename = "shopify_catalog_audit.csv"
        df.to_csv(csv_filename, index=False)
        print(f"[✓] Exported {len(df)} variants to {csv_filename}")

        db_filename = "catalog_warehouse.db"
        conn = sqlite3.connect(db_filename)
        df.to_sql("products", conn, if_exists="replace", index=False)
        conn.close()
        print(f"[✓] Ingested into database: {db_filename} (Table: 'products')")


if __name__ == "__main__":
    target_store = "https://kith.com"
    engine = ShopifyCatalogEngine(target_store)
    asyncio.run(engine.fetch_catalog(max_pages=2))
    engine.process_and_persist()