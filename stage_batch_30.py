import os
import json
import glob
import pandas as pd
from lead_enricher import harvest_brand_email

DATA_DIR = "data"
BATCH_FILE = "batch_30_manifest.json"

# Targets that should be excluded due to enterprise scale, legal traps, or prior dispatch
DISQUALIFIED = {
    "barnesandnoble", "decathlon", "dickies", "zulily", 
    "fashionnova", "karl", "studs", "thousandfell", 
    "americanmeadows", "taylorstitch"
}

def analyze_snapshot(csv_path: str):
    try:
        df = pd.read_csv(csv_path)
        df.columns = [c.lower() for c in df.columns]
        
        total_variants = len(df)
        if total_variants < 50:
            return None

        avail_col = next((c for c in ["available", "inventory_available", "in_stock"] if c in df.columns), None)
        if not avail_col:
            return None

        out_of_stock = (df[avail_col] == False) | (df[avail_col].astype(str).str.lower() == "false")
        oos_count = int(out_of_stock.sum())
        gap_rate = (oos_count / total_variants) * 100

        return {
            "total_variants": total_variants,
            "out_of_stock": oos_count,
            "gap_rate": f"{gap_rate:.1f}%",
            "raw_gap": gap_rate
        }
    except Exception:
        return None

def build_batch():
    csv_files = glob.glob(os.path.join(DATA_DIR, "*_snapshot.csv"))
    staged = []

    print(f"[*] Scanning {len(csv_files)} local snapshots for high-leverage DTC targets...")

    for path in csv_files:
        brand = os.path.basename(path).replace("_snapshot.csv", "").lower()
        if brand in DISQUALIFIED:
            continue

        metrics = analyze_snapshot(path)
        if not metrics or metrics["raw_gap"] < 10.0:
            continue

        target_url = f"https://{brand}.com"
        print(f"[*] Enriching {brand} ({metrics['total_variants']} SKUs, {metrics['gap_rate']} gap)...")
        
        email = harvest_brand_email(target_url)
        if not email:
            print(f"[-] No verified contact for {brand}. Skipping.")
            continue

        brand_display = brand.capitalize()
        entry = {
            "brand": brand_display,
            "target_url": target_url,
            "recipient_email": email,
            "total_variants": metrics["total_variants"],
            "out_of_stock": metrics["out_of_stock"],
            "gap_rate": metrics["gap_rate"],
            "subject": f"Catalog availability & variant monitoring for {brand_display}",
            "body": (
                f"Hi there,\n\n"
                f"I analyzed {brand_display}’s digital storefront catalog and indexed {metrics['total_variants']:,} active product variants.\n\n"
                f"During our automated telemetry run, our pipeline flagged {metrics['out_of_stock']:,} variants currently marked out of stock "
                f"(~{metrics['gap_rate']} catalog inventory gap). For scaling DTC brands, unmonitored variant drop-offs create dropped conversions "
                f"when paid marketing routes high-intent traffic to unavailable sizes or options.\n\n"
                f"I built an automated e-commerce telemetry pipeline that tracks daily catalog deltas, schema hygiene, and automated variant stockout triggers.\n\n"
                f"I already indexed your active catalog data and generated an initial schema hygiene and variant breakdown for {brand_display}.\n\n"
                f"Would you like me to send over the CSV audit for your operations team to review?\n\n"
                f"Best,\nDenham"
            )
        }
        staged.append(entry)
        print(f"[+] Verified target staged: {brand_display} -> {email}")

        if len(staged) >= 30:
            break

    with open(BATCH_FILE, "w", encoding="utf-8") as f:
        json.dump(staged, f, indent=2)

    print(f"\n[+] Staging Complete. {len(staged)} verified candidates saved to {BATCH_FILE}.")

if __name__ == "__main__":
    build_batch()