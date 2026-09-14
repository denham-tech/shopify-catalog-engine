# Shopify Catalog Engine

CLI data extraction tool designed for public Shopify storefront product catalogs. Ingests paginated JSON feeds, unpacks nested variant schemas, and outputs clean tabular snapshots for downstream validation and delta tracking.

## Features
- **Deterministic Feed Parsing:** Pulls structured product and variant records via Shopify's public catalog endpoints.
- **Relational Normalization:** Flattens multi-variant products into standard relational rows (`variant_id`, `title`, `sku`, `price`, `available`).
- **Configurable Crawl Depth:** Supports parameterized page limits and automated rate-limiting backoffs.

## Usage

```bash
# Extract live product variants from any Shopify storefront
python engine.py --url [https://colourpop.com](https://colourpop.com) --pages 1 --output data/live_snapshot.csv