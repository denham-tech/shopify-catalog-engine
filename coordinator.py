import os
import json
import glob
import pandas as pd
from lead_enricher import harvest_brand_email

DATA_DIR = "data"
MANIFEST_FILE = "outbox_manifest.json"

def calculate_snapshot_metrics(csv_path: str) -> dict:
    """Computes variant totals, out-of-stock count, and catalog gap rate."""
    try:
        df = pd.read_csv(csv_path)
        
        # Normalize column names to lowercase for consistency
        df.columns = [c.lower() for c in df.columns]
        
        total_variants = len(df)
        if total_variants == 0:
            return None

        # Detect inventory availability column
        avail_col = None
        for candidate in ["available", "inventory_available", "in_stock"]:
            if candidate in df.columns:
                avail_col = candidate
                break

        if not avail_col:
            return None

        # Convert boolean / string indicators to stockout counts
        out_of_stock = (df[avail_col] == False) | (df[avail_col].astype(str).str.lower() == "false")
        oos_count = int(out_of_stock.sum())
        gap_rate = (oos_count / total_variants) * 100

        return {
            "total_variants": total_variants,
            "out_of_stock": oos_count,
            "gap_rate": f"{gap_rate:.1f}%",
            "raw_gap_rate": gap_rate
        }
    except Exception as e:
        print(f"[-] Error calculating metrics for {csv_path}: {e}")
        return None

def generate_pitch_body(brand_name: str, metrics: dict) -> str:
    """Generates direct, link-free outbound copy to protect deliverability."""
    name_display = brand_name.capitalize()
    return (
        f"Hi there,\n\n"
        f"I analyzed {name_display}’s online storefront catalog and indexed {metrics['total_variants']:,} active product variants.\n\n"
        f"During our automated telemetry run, our pipeline detected {metrics['out_of_stock']:,} variants currently marked out of stock "
        f"(~{metrics['gap_rate']} catalog inventory gap). For high-demand collections, silent variant stockouts create dropped conversions "
        f"when inbound customer traffic lands on unavailable sizes or colorways.\n\n"
        f"I built an automated e-commerce telemetry pipeline that tracks daily catalog deltas, schema hygiene, and automated variant stockout triggers.\n\n"
        f"I already indexed your active catalog data and generated an initial schema hygiene and variant breakdown for {name_display}.\n\n"
        f"Would you like me to send over the CSV audit for your operations team to review?\n\n"
        f"Best,\nDenham"
    )

def assemble_manifest():
    """Iterates through snapshot files, resolves contact addresses, and stages verified audits."""
    if not os.path.exists(DATA_DIR):
        print(f"[-] Data directory '{DATA_DIR}' not found.")
        return

    csv_files = glob.glob(os.path.join(DATA_DIR, "*_snapshot.csv"))
    if not csv_files:
        print("[-] No snapshot files found in data directory.")
        return

    manifest = []
    print(f"[*] Processing {len(csv_files)} snapshot datasets...")

    for csv_path in csv_files:
        filename = os.path.basename(csv_path)
        brand = filename.replace("_snapshot.csv", "")
        
        # Extract target domain
        target_url = f"https://{brand}.com"

        metrics = calculate_snapshot_metrics(csv_path)
        if not metrics or metrics["raw_gap_rate"] < 5.0:
            print(f"[-] Skipping {brand}: Insufficient gap rate or unreadable snapshot.")
            continue

        print(f"[*] Resolving contact endpoint for {brand}...")
        recipient_email = harvest_brand_email(target_url)

        # Do not stage targets without a verified MX contact
        if not recipient_email:
            print(f"[!] Dropping {brand}: No valid contact endpoint or MX record resolved.")
            continue

        entry = {
            "brand": brand.capitalize(),
            "target_url": target_url,
            "recipient_email": recipient_email,
            "snapshot_file": csv_path,
            "metrics": {
                "total_variants": metrics["total_variants"],
                "out_of_stock": metrics["out_of_stock"],
                "gap_rate": metrics["gap_rate"]
            },
            "suggested_subject": f"Catalog availability & variant monitoring for {brand.capitalize()}",
            "body": generate_pitch_body(brand, metrics)
        }
        manifest.append(entry)
        print(f"[+] Staged: {brand.capitalize()} -> {recipient_email}")

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[+] Pipeline Run Complete. {len(manifest)} verified audits prepared in {MANIFEST_FILE}.")

if __name__ == "__main__":
    assemble_manifest()