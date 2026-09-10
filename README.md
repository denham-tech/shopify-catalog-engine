# Headless Shopify Catalog Extraction & ETL Engine

Autonomous, production-grade extraction engine built with **Python**, **Playwright**, and **Pandas**. Extracts variant schemas, real-time inventory availability, and pricing telemetry directly from dynamic Shopify storefronts into structured SQLite and CSV feeds.

## Features
- **Headless Ingestion:** Emulates active browser sessions via Playwright to bypass WAF heuristics and scrape guards.
- **Dynamic Normalization:** Handles complex SKU hierarchies, nested variants, and price casting.
- **Relational Warehousing:** Automatically validates and persists clean records into an audit SQLite database.

## Architecture
- `engine.py` - Core asynchronous extraction, normalization, and database pipeline.
- `catalog_warehouse.db` - Local relational sink for analytical queries.
- `shopify_catalog_audit.csv` - Client-facing operational data deliverable.