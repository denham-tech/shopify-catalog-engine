import csv
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone

# 20 Mid-Market DTC Footwear Brands + Verified Founders/CEOs
FOOTWEAR_TARGETS = [
    {"domain": "suavs.com", "brand": "Suavs", "first": "Monxi", "last": "Garza", "title": "Founder"},
    {"domain": "thousandfell.com", "brand": "Thousand Fell", "first": "Stuart", "last": "Ahlum", "title": "Co-Founder"},
    {"domain": "nisolo.com", "brand": "Nisolo", "first": "Patrick", "last": "Woodyard", "title": "Co-Founder"},
    {"domain": "helmboots.com", "brand": "HELM Boots", "first": "Joshua", "last": "Bingaman", "title": "Founder"},
    {"domain": "greats.com", "brand": "GREATS", "first": "Ryan", "last": "Babenzien", "title": "Founder"},
    {"domain": "amberjack.shop", "brand": "Amberjack", "first": "John", "last": "Peters", "title": "Founder"},
    {"domain": "koio.co", "brand": "Koio", "first": "Chris", "last": "Wichert", "title": "Co-Founder"},
    {"domain": "velasca.com", "brand": "Velasca", "first": "Enrico", "last": "Casati", "title": "Co-Founder"},
    {"domain": "adelanteshoes.com", "brand": "Adelante", "first": "Peter", "last": "Sacco", "title": "Founder"},
    {"domain": "taftclothing.com", "brand": "TAFT", "first": "Kory", "last": "Stevens", "title": "Founder"},
    {"domain": "oakstreetbootmakers.com", "brand": "Oak Street", "first": "George", "last": "Vlagos", "title": "Founder"},
    {"domain": "grantstoneboots.com", "brand": "Grant Stone", "first": "Wyatt", "last": "Gilmore", "title": "Founder"},
    {"domain": "fluxfootwear.com", "brand": "Flux Footwear", "first": "Isaac", "last": "Mertens", "title": "Co-Founder & CEO"},
    {"domain": "kizik.com", "brand": "Kizik", "first": "Monte", "last": "Deere", "title": "CEO"},
    {"domain": "psudo.com", "brand": "PSUDO", "first": "Michael", "last": "Rich", "title": "Founder"},
    {"domain": "baabuk.com", "brand": "Baabuk", "first": "Dan", "last": "Witting", "title": "Co-Founder"},
    {"domain": "feiyue-shoes.com", "brand": "Feiyue", "first": "Patrice", "last": "Bastian", "title": "Director"},
    {"domain": "somfootwear.com", "brand": "SOM Footwear", "first": "Olie", "last": "Marchal", "title": "Founder"},
    {"domain": "lemsshoes.com", "brand": "Lems Shoes", "first": "Andrew", "last": "Rademacher", "title": "Founder"},
    {"domain": "xeroshoes.com", "brand": "Xero Shoes", "first": "Steven", "last": "Sashen", "title": "Co-Founder"}
]

LEDGER_FILE = "drift_ledger.json"
NEVERBOUNCE_CANDIDATES_CSV = "neverbounce_candidates.csv"
NEVERBOUNCE_VERIFIED_CSV = "neverbounce_verified.csv"

US_SEQUENCE = ["5", "5.5", "6", "6.5", "7", "7.5", "8", "8.5", "9", "9.5", "10", "10.5", "11", "11.5", "12", "12.5", "13", "14", "15"]
EU_SEQUENCE = ["38", "39", "40", "41", "42", "42.5", "43", "44", "45", "46", "47"]

CORE_SHOE_SIZES = {"8.5", "9", "9.5", "10", "10.5", "11", "41", "42", "42.5", "43", "44"}
EDGE_SHOE_SIZES = {"5", "5.5", "6", "6.5", "7", "7.5", "12", "12.5", "13", "14", "15", "38", "39", "40", "45", "46", "47"}
ALL_SHOE_SIZES = CORE_SHOE_SIZES | EDGE_SHOE_SIZES

CLEARANCE_REGEX = re.compile(r"\b(final sale|clearance|last chance|archive sale|discontinued|sample sale)\b", re.I)
ACCESSORY_TITLE_REGEX = re.compile(r"\b(gift card|care kit|replacement laces|shoelaces|crew socks|ankle socks|no-show socks|insoles|shoe horn|waterproofer)\b", re.I)
ACCESSORY_TYPES = {"accessories", "socks", "shoe care", "gift card", "gift cards", "laces", "insoles", "apparel", "merch"}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch_json(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    return None


def verify_mx_record(domain):
    """Residual 1 Fix: Cross-platform DNS-over-HTTPS (DoH) MX check with aggressive fail-open."""
    doh_url = f"https://dns.google/resolve?name={domain}&type=MX"
    data = fetch_json(doh_url, timeout=5)
    if data and isinstance(data, dict):
        status = data.get("Status")
        # Status 3 is explicit NXDOMAIN (domain does not exist)
        if status == 3:
            return False
        if status == 0 and data.get("Answer"):
            return True
    # Fail-open if DoH is blocked or returns SOA/no-answer so a live store is never silently dropped
    return True


def is_excluded_product(prod):
    p_title = str(prod.get("title") or "")
    p_handle = str(prod.get("handle") or "")
    p_type = str(prod.get("product_type") or "").strip().lower()

    if p_type in ACCESSORY_TYPES:
        return True
    if CLEARANCE_REGEX.search(p_title) or CLEARANCE_REGEX.search(p_handle.replace("-", " ")):
        return True
    if ACCESSORY_TITLE_REGEX.search(p_title):
        return True
    return False


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
        norm = opt.replace("½", ".5").replace("1/2", ".5")
        norm = re.sub(r"(\d),5\b", r"\1.5", norm)
        norm = re.sub(r"(?i)\b(us|eu|uk|men'?s|women'?s|size)\b", " ", norm)
        norm = re.sub(r"(?i)(?<=\d)(d|ee|eee|m|w)\b", "", norm)

        tokens = re.findall(r"\b\d{1,2}(?:\.5)?\b", norm)
        matched = next((t for t in tokens if t in ALL_SHOE_SIZES), None)
        if matched and not found_size:
            found_size = matched
        else:
            group_parts.append(opt)

    colorway = " / ".join(group_parts) if group_parts else "Standard"
    return found_size, colorway


def parse_iso_days(iso_str):
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
    try:
        c_val = float(core_size)
        return sorted(edge_stocked_list, key=lambda s: abs(float(s) - c_val))[0]
    except Exception:
        return sorted(edge_stocked_list)[0]


def clean_product_grammar(title):
    cleaned = title.strip()
    cleaned = re.sub(r"(?i)^men'?s\s+the\s+", "Men's ", cleaned)
    cleaned = re.sub(r"(?i)^women'?s\s+the\s+", "Women's ", cleaned)
    if cleaned.lower().startswith("the "):
        return cleaned[4:]
    return cleaned


def generate_ranked_permutations(first, last, domain):
    f = re.sub(r"[^a-z]", "", first.lower())
    l = re.sub(r"[^a-z]", "", last.lower())
    return [
        {"rank": 1, "type": "founder_first", "email": f"{f}@{domain}"},
        {"rank": 2, "type": "founder_dot", "email": f"{f}.{l}@{domain}"},
        {"rank": 3, "type": "founder_flast", "email": f"{f[0]}{l}@{domain}"},
        {"rank": 4, "type": "founder_firstl", "email": f"{f}{l[0]}@{domain}"},
        {"rank": 5, "type": "founder_full", "email": f"{f}{l}@{domain}"},
        {"rank": 6, "type": "ops_fallback", "email": f"ops@{domain}"}
    ]


def infer_fallback_rank(email, domain_lookup):
    """Infers 1-6 rank if NeverBounce strips custom columns from the exported CSV."""
    local, _, dom = email.partition("@")
    if local in ("ops", "inventory", "support", "info"):
        return 6
    meta = domain_lookup.get(dom)
    if meta:
        for item in generate_ranked_permutations(meta["first"], meta["last"], dom):
            if item["email"] == email:
                return item["rank"]
    if "." in local:
        return 2
    return 3


def load_verified_winners():
    """Residual 2 Fix: Row-level try/except + fallback rank inference if custom columns are stripped."""
    if not os.path.exists(NEVERBOUNCE_VERIFIED_CSV):
        return {}
    domain_lookup = {t["domain"]: t for t in FOOTWEAR_TARGETS}
    valid_by_domain = {}
    try:
        with open(NEVERBOUNCE_VERIFIED_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    email = (row.get("email") or row.get("Email") or "").strip().lower()
                    status = (
                        row.get("result") or row.get("status") or row.get("verification_status") or ""
                    ).strip().lower()
                    if "@" not in email or status not in ("valid", "deliverable", "safe"):
                        continue
                    dom = email.split("@", 1)[1]
                    raw_rank = row.get("priority_rank")
                    try:
                        rank = int(raw_rank) if raw_rank is not None and str(raw_rank).strip() != "" else infer_fallback_rank(email, domain_lookup)
                    except ValueError:
                        rank = infer_fallback_rank(email, domain_lookup)

                    if dom not in valid_by_domain or rank < valid_by_domain[dom]["rank"]:
                        valid_by_domain[dom] = {"email": email, "rank": rank, "status": status}
                except Exception as row_err:
                    print(f"[!] Warning: Skipped malformed row in {NEVERBOUNCE_VERIFIED_CSV}: {row_err}")
                    continue
    except Exception as file_err:
        print(f"[!] Warning: Could not read {NEVERBOUNCE_VERIFIED_CSV}: {file_err}")
        return {}
    return valid_by_domain


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


def build_cold_email(target_meta, lead, oos_top20_count, catalog_oos_pct, store_newly_oos_count):
    first_name = target_meta["first"]
    brand = target_meta["brand"]
    clean_sku = clean_product_grammar(lead["product_name"])
    c_size = lead["core_size_oos"]
    price = lead["price"]
    adj_a, adj_b = lead["adjacent_sizes_in_stock"][0], lead["adjacent_sizes_in_stock"][1]
    l_days = lead["confirmed_ledger_days_oos"]
    p_days = lead["proxy_days_oos"]
    sku_newly_oos = lead.get("sku_newly_oos_since_last_run", 0)

    if 2 <= l_days <= 10:
        time_clause = f"has remained unreplenished across our last {l_days} days of tracking"
    elif l_days > 10:
        time_clause = f"has been sitting sold out for over a week ({l_days}+ days)"
    elif p_days >= 5:
        time_clause = f"has been sitting sold out for ~{p_days} days"
    else:
        time_clause = "is sitting sold out right in the middle of the size curve"

    # Residual 3 Fix: Explicitly distinguish per-product vs. store-wide newly OOS drops
    if sku_newly_oos > 0:
        drift_clause = f" — including {sku_newly_oos} newly depleted size(s) on this exact shoe since our last check"
    elif store_newly_oos_count > 0:
        drift_clause = f" — with {store_newly_oos_count} additional variants dropping out of stock store-wide since our last check"
    else:
        drift_clause = ""

    if oos_top20_count >= 10:
        subject = f"{brand}: size {c_size} gap ({oos_top20_count} variants dead in top 20)"
        scope_line = (
            f"Across {brand}'s top 20 featured products, {oos_top20_count} variants are currently depleted "
            f"({catalog_oos_pct}% OOS across the full catalog){drift_clause}."
        )
    else:
        subject = f"{brand}: {clean_sku} size {c_size} gap ({catalog_oos_pct}% catalog OOS)"
        scope_line = (
            f"Right now, {catalog_oos_pct}% of {brand}'s catalog variants are sitting out of stock{drift_clause}."
        )

    body = (
        f"Hi {first_name},\n\n"
        f"Your {clean_sku} in size {c_size} {time_clause} — while adjacent sizes {adj_a} and {adj_b} are still live right next to it.\n\n"
        f"{scope_line} At ${price} a pair, size {c_size} is a core mid-curve revenue driver sitting with a dead buy-button while paid and organic traffic hits the page.\n\n"
        f"I pulled the full SKU-level gap sheet for {brand} this morning — reply 'send' and I'll drop the CSV right here (no deck, no sales call).\n\n"
        f"Best,\nDenham"
    )
    return {"subject": subject, "body": body}


def audit_store(target_meta, ledger, verified_winners):
    domain = target_meta["domain"]
    print(f"[*] Auditing {domain} (DoH MX + Paginated Catalog)...")

    mx_valid = verify_mx_record(domain)
    if not mx_valid:
        print(f"[-] {domain}: Explicit NXDOMAIN on DNS check. Skipping.")
        return None

    products = fetch_paginated_catalog(domain)
    if not products:
        print(f"[-] {domain}: Catalog endpoint gated or unreachable. Skipping.")
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
    store_newly_oos_count = 0

    asymmetry_candidates = []

    for prod in products:
        p_name = prod.get("title", "Unknown Product")
        p_handle = prod.get("handle", "")
        in_top20 = (p_handle in top20_handles) if top20_verified else False
        in_hero5 = p_handle in hero_handles
        excluded = is_excluded_product(prod)

        color_groups = {}
        sku_newly_oos_by_color = {}

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
                    store_newly_oos_count += 1
                    sku_newly_oos_by_color[colorway] = sku_newly_oos_by_color.get(colorway, 0) + 1
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

            if size and not excluded:
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
                if len(stocked_neighbors) == 2:
                    confirmed_days = oos_item["ledger_days_oos"]
                    effective_days = max(confirmed_days, oos_item["proxy_days"])
                    sku_drops = sku_newly_oos_by_color.get(colorway, 0)
                    score = effective_days + (15 if in_top20 else 0) + (10 if confirmed_days >= 1 else 0) + (5 if sku_drops > 0 else 0)
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
                        "sku_newly_oos_since_last_run": sku_drops,
                        "rank_score": score,
                        "price": oos_item["price"]
                    })

    ledger["stores"][domain] = current_store_state

    catalog_oos_pct = round((total_oos / total_variants * 100), 1) if total_variants else 0.0
    hero_bleed_pct = round((hero_oos_v / hero_total_v * 100), 1) if hero_total_v else 0.0

    if catalog_oos_pct < 5.0 or not asymmetry_candidates:
        print(f"  [~] {domain}: Filtered (<5% OOS or no strict 2-neighbor holes).")
        return None

    asymmetry_candidates.sort(key=lambda x: x["rank_score"], reverse=True)
    lead = asymmetry_candidates[0]

    ranked_candidates = generate_ranked_permutations(target_meta["first"], target_meta["last"], domain)
    winner_info = verified_winners.get(domain)
    email_artifact = build_cold_email(target_meta, lead, oos_featured_count, catalog_oos_pct, store_newly_oos_count)

    return {
        "store_url": domain,
        "brand": target_meta["brand"],
        "mx_verified": mx_valid,
        "decision_maker": f"{target_meta['first']} {target_meta['last']} ({target_meta['title']})",
        "verified_winning_email": winner_info["email"] if winner_info else "PENDING_NEVERBOUNCE_CSV",
        "ranked_candidate_inboxes": ranked_candidates,
        "products_indexed": len(products),
        "total_variants": total_variants,
        "catalog_oos_rate": f"{catalog_oos_pct}%",
        "hero_bleed_rate": f"{hero_bleed_pct}%",
        "oos_featured_top20_variants": oos_featured_count,
        "top20_order_verified": top20_verified,
        "store_newly_oos_since_last_run": store_newly_oos_count,
        "primary_size_asymmetry": lead,
        "hook": email_artifact["body"].split("\n\n")[1],
        "email_draft": email_artifact
    }


def main():
    ledger = load_drift_ledger()
    verified_winners = load_verified_winners()

    run_count = ledger["_meta"].get("run_count", 0) + 1
    if run_count == 1:
        ledger["_meta"]["first_initialized_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ledger["_meta"]["run_count"] = run_count

    print(f"[*] Executing Locked Footwear Telemetry & Enricher (Run #{run_count})...\n")

    results = []
    nb_rows = []

    for idx, target_meta in enumerate(FOOTWEAR_TARGETS):
        res = audit_store(target_meta, ledger, verified_winners)
        if res:
            results.append(res)
            print(f"  [+] {res['brand']} -> {res['email_draft']['subject']}")
            print(f"      Verify: {res['primary_size_asymmetry']['verify_url']}\n")
            for item in res["ranked_candidate_inboxes"]:
                nb_rows.append({
                    "brand": res["brand"],
                    "domain": res["store_url"],
                    "executive": res["decision_maker"],
                    "priority_rank": item["rank"],
                    "inbox_type": item["type"],
                    "email": item["email"]
                })
        if idx < len(FOOTWEAR_TARGETS) - 1:
            time.sleep(1.0)

    save_drift_ledger(ledger)

    with open("footwear_anomalies.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    with open(NEVERBOUNCE_CANDIDATES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["brand", "domain", "executive", "priority_rank", "inbox_type", "email"])
        writer.writeheader()
        writer.writerows(nb_rows)

    print(f"[✓] Complete: {len(results)} actionable stores exported to footwear_anomalies.json")
    print(f"[✓] Exported {len(nb_rows)} prioritized candidate emails to {NEVERBOUNCE_CANDIDATES_CSV}")


if __name__ == "__main__":
    main()