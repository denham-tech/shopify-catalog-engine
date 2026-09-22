import os
import pandas as pd

DATA_DIR = "data"
REPORTS_DIR = "reports"

os.makedirs(REPORTS_DIR, exist_ok=True)

def generate_executive_audit(brand_slug: str):
    """
    Transforms a raw catalog snapshot into a high-leverage 
    Executive Stockout & Hygiene Audit CSV ready to send to clients.
    """
    snapshot_path = os.path.join(DATA_DIR, f"{brand_slug}_snapshot.csv")
    
    if not os.path.exists(snapshot_path):
        print(f"[-] Snapshot not found: {snapshot_path}")
        return

    print(f"[*] Parsing catalog snapshot for {brand_slug.upper()}...")
    df = pd.read_csv(snapshot_path)
    df.columns = [c.lower() for c in df.columns]

    # Detect availability column
    avail_col = next((c for c in ["available", "inventory_available", "in_stock"] if c in df.columns), None)
    if not avail_col:
        print("[-] Availability column missing.")
        return

    # Filter strictly for out-of-stock items
    is_oos = (df[avail_col] == False) | (df[avail_col].astype(str).str.lower() == "false")
    oos_df = df[is_oos].copy()

    # Identify primary descriptive columns
    title_col = next((c for c in ["title", "product_title", "name"] if c in df.columns), None)
    sku_col = next((c for c in ["sku", "variant_sku", "id"] if c in df.columns), None)
    price_col = next((c for c in ["price", "variant_price"] if c in df.columns), None)
    type_col = next((c for c in ["product_type", "type", "category"] if c in df.columns), None)

    # Build clean output dataframe
    report_df = pd.DataFrame()
    report_df["Product_Name"] = oos_df[title_col] if title_col else "N/A"
    report_df["SKU_Identifier"] = oos_df[sku_col] if sku_col else "N/A"
    report_df["Category"] = oos_df[type_col] if type_col else "General"
    report_df["Price_Point"] = oos_df[price_col] if price_col else "0.00"
    report_df["Telemetry_Status"] = "DEPLETED / OUT_OF_STOCK"
    report_df["Audit_Timestamp"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    report_filename = os.path.join(REPORTS_DIR, f"{brand_slug}_executive_stockout_audit.csv")
    report_df.to_csv(report_filename, index=False)

    print(f"[+] Clean audit generated: {report_filename}")
    print(f"[+] Total Depleted Variants Indexed: {len(report_df)}")

if __name__ == "__main__":
    # Test generation on active high-priority targets
    test_slugs = ["thousandfell", "americanmeadows"]
    for slug in test_slugs:
        generate_executive_audit(slug)