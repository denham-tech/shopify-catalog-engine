import json
import time
import urllib.request
from enricher_v2 import check_mx_records, generate_decision_maker_candidates

# Mid-market independent DTC brands ($1M-$15M GMV tier)
MIDMARKET_TARGETS = [
    {"domain": "ugmonk.com", "first": "Jeff", "last": "Sheldon", "title": "Founder"},
    {"domain": "piccalio.com", "first": "Liat", "last": "Kadmon", "title": "Co-Founder"},
    {"domain": "ridge.com", "first": "Sean", "last": "Frank", "title": "CEO"},
    {"domain": "orbitkey.com", "first": "Charles", "last": "Ng", "title": "Co-Founder"},
    {"domain": "westernrise.com", "first": "Will", "last": "Watters", "title": "Co-Founder"},
    {"domain": "publicrec.com", "first": "Zach", "last": "Goldstein", "title": "Founder / CEO"},
    {"domain": "thousandfell.com", "first": "Stuart", "last": "Ahlum", "title": "Co-Founder"},
    {"domain": "carawayhome.com", "first": "Jordan", "last": "Nathan", "title": "Founder / CEO"},
    {"domain": "craighill.co", "first": "Hunter", "last": "Craighill", "title": "Founder"},
    {"domain": "aluratek.com", "first": "John", "last": "Lee", "title": "VP of Sales & Ops"},
    {"domain": "solostove.com", "first": "John", "last": "Merris", "title": "CEO"},
    {"domain": "coterie.com", "first": "Ben", "last": "Stern", "title": "Founder / CEO"},
    {"domain": "loopearplugs.com", "first": "Maarten", "last": "Bodewes", "title": "Co-Founder"},
    {"domain": "bellroy.com", "first": "Andy", "last": "Fallshaw", "title": "Co-Founder"},
    {"domain": "nativecos.com", "first": "Moiz", "last": "Ali", "title": "Founder"}
]

def fetch_shopify_catalog(domain):
    url = f"https://{domain}/products.json?limit=250"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                products = data.get("products", [])
                
                total_variants = 0
                out_of_stock = 0
                
                for prod in products:
                    for v in prod.get("variants", []):
                        total_variants += 1
                        if not v.get("available", True):
                            out_of_stock += 1
                            
                return total_variants, out_of_stock
    except Exception as e:
        print(f"[-] Fetch failed for {domain}: {e}")
        return 0, 0
    return 0, 0

def execute():
    manifest = []
    print(f"[*] Staging {len(MIDMARKET_TARGETS)} mid-market targets...\n")

    for target in MIDMARKET_TARGETS:
        domain = target["domain"]
        first = target["first"]
        last = target["last"]
        brand_display = domain.split(".")[0].capitalize()

        print(f"--- Telemetry Audit: {brand_display} ({domain}) ---")

        # 1. DNS MX Check
        if not check_mx_records(domain):
            print(f"[-] Skipped {brand_display}: MX check failed.")
            continue

        # 2. Public Catalog Telemetry Fetch
        total_vars, oos_vars = fetch_shopify_catalog(domain)
        if total_vars == 0:
            print(f"[-] Skipped {brand_display}: Catalog endpoint protected or timed out.")
            continue

        gap_rate = (oos_vars / total_vars) * 100
        if gap_rate < 8.0:
            print(f"[-] Skipped {brand_display}: Variant gap below threshold ({gap_rate:.1f}%).")
            continue

        # 3. Decision Maker Candidate Generation
        candidates = generate_decision_maker_candidates(first, last, domain)
        primary_inbox = candidates[1]  # first.last@domain

        payload = {
            "brand": brand_display,
            "domain": domain,
            "executive_name": f"{first} {last}",
            "title": target["title"],
            "primary_email": primary_inbox,
            "alternative_candidates": candidates,
            "total_variants": total_vars,
            "oos_variants": oos_vars,
            "gap_rate": f"{gap_rate:.1f}%"
        }
        manifest.append(payload)
        print(f"[+] Staged {brand_display}: {oos_vars}/{total_vars} OOS ({gap_rate:.1f}%) -> {primary_inbox}")
        time.sleep(1)

    with open("midmarket_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[✓] Staging complete. {len(manifest)} verified leads exported to midmarket_manifest.json")

if __name__ == "__main__":
    execute()