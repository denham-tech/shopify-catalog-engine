import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone

SHOE_TARGETS = [
    "thousandfell.com",
    "helmboots.com",
    "amberjack.shop",
    "koio.co",
    "nisolo.com",
    "beckettsimonon.com",
    "greats.com",
    "velasca.com",
    "suavs.com",
    "atoms.com"
]

LEDGER_FILE = "drift_ledger.json"

US_SEQUENCE = ["5", "5.5", "6", "6.5", "7", "7.5", "8", "8.5", "9", "9.5", "10", "10.5", "11", "11.5", "12", "12.5", "13", "14", "15"]
EU_SEQUENCE = ["38", "39", "40", "41", "42", "42.5", "43", "44", "45", "46", "47"]

CORE_SHOE_SIZES = {"8.5", "9", "9.5", "10", "10.5", "11", "41", "42", "42.5", "43", "44"}
EDGE_SHOE_SIZES = {"5", "5.5", "6", "6.5", "7", "7.5", "12", "12.5", "13", "14", "15", "38", "39", "40", "45", "46", "47"}
ALL_SHOE_SIZES = CORE_SHOE_SIZES | EDGE_SHOE_SIZES

CLEARANCE_KEYWORDS = ("final sale", "clearance", "last chance", "archive sale", "discontinued")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    return None


def parse_variant_size_and_group(variant):
    opts = [
        str(variant.get("option1") or "").strip(),
        str(variant.get("option2") or "").strip(),
        str(variant.get("option3") or "").strip()
    ]
    found_size = None
    group_parts = []

    for opt in opts:
        if not opt or opt == "Default Title":
            continue
        tokens = re.findall(r"\b\d{1,2}(?:\.5)?\b", opt)
        matched = next((t for t in tokens if t in ALL_SHOE_SIZES), None)
        if matched and not found_size:
            found_size = matched
        else:
            group_parts.append(opt)

    colorway = " / ".join(group_parts) if group_parts else "Standard"
    return found_size, colorway


def parse_iso_days(iso_str):
    """Returns integer days elapsed since an ISO UTC timestamp."""
    if not iso_str:
        return 0
    match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", str(iso_str))
    if not match:
        return 0
    try:
        dt = datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0, (now - dt).days)
    except Exception:
        return 0


def get_stocked_neighbors(size, stocked_sizes_set):
    seq = EU_SEQUENCE if size in EU_SEQUENCE else US_SEQUENCE
    if size not in seq:
        return []
    idx = seq.index(size)
    neighbors = []
    if idx > 0 and seq[idx - 1] in stocked_sizes_set:
        neighbors.append(seq[idx - 1])
    if idx < len(seq) - 1 and seq[idx + 1] in stocked_sizes_set:
        neighbors.append(seq[idx + 1])
    return neighbors


def pick_nearest_edge_size(core_size, edge_stocked_list):
    """Sorts numerically and picks the edge size closest to the OOS core size."""
    try:
        c_val = float(core_size)
        return sorted(edge_stocked_list, key=lambda s: abs(float(s) - c_val))[0]
    except Exception:
        return sorted(edge_stocked_list)[0]


def clean_product_grammar(title):
    """Prevents 'Your The Royale 2.0' mail-merge grammar glitch."""
    cleaned = title.strip()
    if cleaned.lower().startswith("the "):
        return cleaned[4:]
    return cleaned


def fetch_paginated_catalog(domain, max_pages=5):
    all_products = []
    for page in range(1, max_pages + 1):
        url = f"https://{domain}/products.json?limit=250&page={page}"
        data = fetch_json(url)
        if not data or not isinstance(data.get("products"), list):
            break
        batch = data["products"]
        if not batch:
            break
        all_products.extend(batch)
        if len(batch) < 250:
            break
        time.sleep(0.4)
    return all_products


def fetch_top20_handles(domain):
    url = f"https://{domain}/collections/all/products.json?limit=20"
    data = fetch_json(url)
    if data and isinstance(data.get("products"), list) and data["products"]:
        return {p.get("handle") for p in data["products"] if p.get("handle")}, True
    return set(), False


def load_drift_ledger():
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"_meta": {"run_count": 0, "first_initialized_utc": None}, "stores": {}}


def save_drift_ledger(ledger):
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)


def audit_store(domain, ledger, is_first_run):
    print(f"[*] Auditing {domain} (paginated)...")
    products = fetch_paginated_catalog(domain)
    if not products:
        print(f"[-] {domain}: Endpoint gated or unreachable. Skipping.")
        return None

    top20_handles, top20_verified = fetch_top20_handles(domain)
    hero_handles = {p.get("handle") for p in products[:5]}
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    prev_store_state = ledger["stores"].get(domain, {})
    current_store_state = {}

    total_variants = 0
    total_oos = 0
    hero_total_v = 0
    hero_oos_v = 0
    oos_featured_count = 0
    newly_oos_count = 0

    asymmetry_candidates = []

    for prod in products:
        p_name = prod.get("title", "Unknown Product")
        p_handle = prod.get("handle", "")
        in_top20 = (p_handle in top20_handles) if top20_verified else False
        in_hero5 = p_handle in hero_handles
        is_clearance = any(kw in p_name.lower() or kw in p_handle.lower() for kw in CLEARANCE_KEYWORDS)

        color_groups = {}

        for v in prod.get("variants", []):
            v_id = str(v.get("id"))
            avail = bool(v.get("available", False))
            price = v.get("price", "0.00")
            size, colorway = parse_variant_size_and_group(v)
            proxy_days = max(1, parse_iso_days(v.get("updated_at")))

            total_variants += 1
            if in_hero5:
                hero_total_v += 1

            prev_v = prev_store_state.get(v_id)
            first_seen_oos = None
            ledger_days_oos = 0

            if not avail:
                if prev_v and prev_v.get("available") is True:
                    newly_oos_count += 1
                    first_seen_oos = now_iso
                elif prev_v and prev_v.get("first_seen_oos_utc"):
                    first_seen_oos = prev_v["first_seen_oos_utc"]
                    ledger_days_oos = parse_iso_days(first_seen_oos)
                else:
                    first_seen_oos = now_iso

            current_store_state[v_id] = {
                "product": p_name,
                "colorway": colorway,
                "size": size,
                "available": avail,
                "proxy_days_stale": proxy_days,
                "first_seen_oos_utc": first_seen_oos
            }

            if not avail:
                total_oos += 1
                if in_hero5:
                    hero_oos_v += 1
                if in_top20:
                    oos_featured_count += 1

            # Do not pitch anomalies on Final Sale / Clearance items
            if size and not is_clearance:
                color_groups.setdefault(colorway, []).append({
                    "variant_id": v_id,
                    "size": size,
                    "available": avail,
                    "ledger_days_oos": ledger_days_oos,
                    "proxy_days": proxy_days,
                    "price": price
                })

        for colorway, v_list in color_groups.items():
            stocked_sizes = {item["size"] for item in v_list if item["available"]}
            edge_stocked = [s for s in stocked_sizes if s in EDGE_SHOE_SIZES]
            core_oos_items = [item for item in v_list if not item["available"] and item["size"] in CORE_SHOE_SIZES]

            if not core_oos_items or not edge_stocked:
                continue

            for oos_item in core_oos_items:
                c_size = oos_item["size"]
                stocked_neighbors = get_stocked_neighbors(c_size, stocked_sizes)
                if len(stocked_neighbors) == 2:  # Strict: both neighbor sizes on left & right are in stock
                    # Prefer confirmed ledger duration over updated_at proxy
                    confirmed_days = oos_item["ledger_days_oos"]
                    effective_days = confirmed_days if confirmed_days >= 1 else oos_item["proxy_days"]
                    score = effective_days + (15 if in_top20 else 0) + (10 if confirmed_days >= 1 else 0)
                    full_title = f"{p_name} ({colorway})" if colorway != "Standard" else p_name

                    asymmetry_candidates.append({
                        "product_name": full_title,
                        "variant_id": oos_item["variant_id"],
                        "verify_url": f"https://{domain}/products/{p_handle}?variant={oos_item['variant_id']}",
                        "in_top20_verified": in_top20,
                        "core_size_oos": c_size,
                        "adjacent_sizes_in_stock": stocked_neighbors,
                        "nearest_edge_size_in_stock": pick_nearest_edge_size(c_size, edge_stocked),
                        "confirmed_ledger_days_oos": confirmed_days,
                        "proxy_days_oos": oos_item["proxy_days"],
                        "rank_score": score,
                        "price": oos_item["price"]
                    })

    ledger["stores"][domain] = current_store_state

    catalog_oos_pct = round((total_oos / total_variants * 100), 1) if total_variants else 0.0
    hero_bleed_pct = round((hero_oos_v / hero_total_v * 100), 1) if hero_total_v else 0.0

    # Skip stores with < 5% catalog OOS (e.g., made-to-order stores like Beckett Simonon)
    if catalog_oos_pct < 5.0:
        print(f"  [~] {domain}: Catalog OOS is only {catalog_oos_pct}% (likely made-to-order). Skipping pitch.")
        return None

    asymmetry_candidates.sort(key=lambda x: x["rank_score"], reverse=True)
    lead = asymmetry_candidates[0] if asymmetry_candidates else None

    hook_str = None
    if lead:
        adj_a, adj_b = lead["adjacent_sizes_in_stock"][0], lead["adjacent_sizes_in_stock"][1]
        clean_name = clean_product_grammar(lead["product_name"])

        if lead["confirmed_ledger_days_oos"] >= 2:
            dur_text = f"has been sold out for {lead['confirmed_ledger_days_oos']} straight days"
        elif lead["proxy_days_oos"] >= 4:
            dur_text = f"has been sitting sold out for ~{lead['proxy_days_oos']} days"
        else:
            dur_text = "is sold out right in the middle of the size curve"

        hook_str = (
            f"Your {clean_name} in size {lead['core_size_oos']} {dur_text} "
            f"— while sizes {adj_a} and {adj_b} are still live right next to it."
        )

    return {
        "store_url": domain,
        "products_indexed": len(products),
        "total_variants": total_variants,
        "catalog_oos_rate": f"{catalog_oos_pct}%",
        "hero_bleed_rate": f"{hero_bleed_pct}%",
        "oos_featured_top20_variants": oos_featured_count,
        "top20_order_verified": top20_verified,
        "newly_oos_since_last_run": newly_oos_count,
        "primary_size_asymmetry": lead,
        "hook": hook_str
    }


def main():
    ledger = load_drift_ledger()
    run_count = ledger["_meta"].get("run_count", 0) + 1
    is_first_run = (run_count == 1)

    if is_first_run:
        ledger["_meta"]["first_initialized_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    ledger["_meta"]["run_count"] = run_count
    print(f"[*] Running Anomaly Detector (Ledger Run #{run_count})...\n")

    results = []
    for idx, domain in enumerate(SHOE_TARGETS):
        res = audit_store(domain, ledger, is_first_run)
        if res and res.get("hook"):
            results.append(res)
            print(f"  [+] HOOK: {res['hook']}")
            print(f"  [>] DEEP-LINK VERIFY: {res['primary_size_asymmetry']['verify_url']}\n")
        if idx < len(SHOE_TARGETS) - 1:
            time.sleep(1.2)

    save_drift_ledger(ledger)

    with open("footwear_anomalies.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"[✓] Audit complete. {len(results)} verified hooks exported to footwear_anomalies.json")


if __name__ == "__main__":
    main()