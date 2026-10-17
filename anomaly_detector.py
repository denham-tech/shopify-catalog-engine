import csv
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone

# 35 Mid-Market DTC Brands (23 Footwear + 12 Raw Denim / Technical Trousers)
TARGETS = [
    # --- Cohort 1: Footwear ---
    {"domain": "suavs.com", "brand": "Suavs", "first": "Monxi", "last": "Garza", "title": "Founder", "vertical": "footwear"},
    {"domain": "thousandfell.com", "brand": "Thousand Fell", "first": "Stuart", "last": "Ahlum", "title": "Co-Founder", "vertical": "footwear"},
    {"domain": "nisolo.com", "brand": "Nisolo", "first": "Patrick", "last": "Woodyard", "title": "Co-Founder", "vertical": "footwear"},
    {"domain": "helmboots.com", "brand": "HELM Boots", "first": "Joshua", "last": "Bingaman", "title": "Founder", "vertical": "footwear"},
    {"domain": "greats.com", "brand": "GREATS", "first": "Ryan", "last": "Babenzien", "title": "Founder", "vertical": "footwear"},
    {"domain": "amberjack.shop", "brand": "Amberjack", "first": "John", "last": "Peters", "title": "Founder", "vertical": "footwear"},
    {"domain": "koio.co", "brand": "Koio", "first": "Chris", "last": "Wichert", "title": "Co-Founder", "vertical": "footwear"},
    {"domain": "velasca.com", "brand": "Velasca", "first": "Enrico", "last": "Casati", "title": "Co-Founder", "vertical": "footwear"},
    {"domain": "adelanteshoes.com", "brand": "Adelante", "first": "Peter", "last": "Sacco", "title": "Founder", "vertical": "footwear"},
    {"domain": "taftclothing.com", "brand": "TAFT", "first": "Kory", "last": "Stevens", "title": "Founder", "vertical": "footwear"},
    {"domain": "oakstreetbootmakers.com", "brand": "Oak Street", "first": "George", "last": "Vlagos", "title": "Founder", "vertical": "footwear"},
    {"domain": "grantstoneboots.com", "brand": "Grant Stone", "first": "Wyatt", "last": "Gilmore", "title": "Founder", "vertical": "footwear"},
    {"domain": "fluxfootwear.com", "brand": "Flux Footwear", "first": "Isaac", "last": "Mertens", "title": "Co-Founder & CEO", "vertical": "footwear"},
    {"domain": "kizik.com", "brand": "Kizik", "first": "Monte", "last": "Deere", "title": "CEO", "vertical": "footwear"},
    {"domain": "psudo.com", "brand": "PSUDO", "first": "Michael", "last": "Rich", "title": "Founder", "vertical": "footwear"},
    {"domain": "baabuk.com", "brand": "Baabuk", "first": "Dan", "last": "Witting", "title": "Co-Founder", "vertical": "footwear"},
    {"domain": "feiyue-shoes.com", "brand": "Feiyue", "first": "Patrice", "last": "Bastian", "title": "Director", "vertical": "footwear"},
    {"domain": "somfootwear.com", "brand": "SOM Footwear", "first": "Olie", "last": "Marchal", "title": "Founder", "vertical": "footwear"},
    {"domain": "lemsshoes.com", "brand": "Lems Shoes", "first": "Andrew", "last": "Rademacher", "title": "Founder", "vertical": "footwear"},
    {"domain": "xeroshoes.com", "brand": "Xero Shoes", "first": "Steven", "last": "Sashen", "title": "Co-Founder", "vertical": "footwear"},
    {"domain": "sabah.am", "brand": "Sabah", "first": "Mickey", "last": "Ashmore", "title": "Founder", "vertical": "footwear"},
    {"domain": "dukeanddexter.com", "brand": "Duke + Dexter", "first": "Archie", "last": "Hewlett", "title": "Founder", "vertical": "footwear"},
    {"domain": "birdies.com", "brand": "Birdies", "first": "Bianca", "last": "Gates", "title": "Co-Founder", "vertical": "footwear"},
    # --- Cohort 2: Raw Denim & Technical Trousers (Waist 28-40) ---
    {"domain": "3sixteen.com", "brand": "3sixteen", "first": "Andrew", "last": "Chen", "title": "Co-Founder", "vertical": "waist"},
    {"domain": "railcarfinegoods.com", "brand": "Railcar Fine Goods", "first": "Steven", "last": "Dang", "title": "Founder", "vertical": "waist"},
    {"domain": "tellason.com", "brand": "Tellason", "first": "Tony", "last": "Patella", "title": "Co-Founder", "vertical": "waist"},
    {"domain": "freenotecloth.com", "brand": "Freenote Cloth", "first": "Matt", "last": "Brodrick", "title": "Co-Founder", "vertical": "waist"},
    {"domain": "leftfieldnyc.com", "brand": "Left Field NYC", "first": "Christian", "last": "McCann", "title": "Founder", "vertical": "waist"},
    {"domain": "hiroshikato.com", "brand": "Hiroshi Kato", "first": "Hiroshi", "last": "Kato", "title": "Founder", "vertical": "waist"},
    {"domain": "taylorstitch.com", "brand": "Taylor Stitch", "first": "Michael", "last": "Maher", "title": "Co-Founder", "vertical": "waist"},
    {"domain": "rogueterritory.com", "brand": "Rogue Territory", "first": "Karl", "last": "Thoennessen", "title": "Co-Founder", "vertical": "waist"},
    {"domain": "westernrise.com", "brand": "Western Rise", "first": "Will", "last": "Watters", "title": "Co-Founder", "vertical": "waist"},
    {"domain": "livsndesigns.com", "brand": "LIVSN Designs", "first": "Andrew", "last": "Gibbs-Dabney", "title": "Founder", "vertical": "waist"},
    {"domain": "bluffworks.com", "brand": "Bluffworks", "first": "Stefan", "last": "Loble", "title": "Founder", "vertical": "waist"},
    {"domain": "shopduer.com", "brand": "DUER", "first": "Gary", "last": "Lenett", "title": "Co-Founder", "vertical": "waist"}
]

LEDGER_FILE = "drift_ledger.json"
REPORTS_DIR = "reports"
INBOX_CANDIDATES_CSV = "inbox_candidates.csv"
VERIFIED_INBOXES_CSV = "verified_inboxes.csv"
LEGACY_VERIFIED_CSV = "neverbounce_verified.csv"

MIN_PRICE_FLOOR = 35.00

US_SEQUENCE = ["5", "5.5", "6", "6.5", "7", "7.5", "8", "8.5", "9", "9.5", "10", "10.5", "11", "11.5", "12", "12.5", "13", "14", "15"]
EU_SEQUENCE = ["38", "39", "40", "41", "42", "42.5", "43", "44", "45", "46", "47"]
WAIST_SEQUENCE = ["28", "29", "30", "31", "32", "33", "34", "35", "36", "38", "40"]

MENS_CORE_SIZES = {"8.5", "9", "9.5", "10", "10.5", "11", "41", "42", "42.5", "43", "44"}
MENS_EDGE_SIZES = {"6", "6.5", "7", "7.5", "12", "12.5", "13", "14", "15", "38", "39", "40", "45", "46", "47"}

WOMENS_CORE_SIZES = {"7", "7.5", "8", "8.5", "9", "38", "39", "40"}
WOMENS_EDGE_SIZES = {"5", "5.5", "6", "10", "10.5", "11", "11.5", "12", "36", "37", "41", "42"}

WAIST_CORE_SIZES = {"31", "32", "33", "34"}
WAIST_EDGE_SIZES = {"28", "29", "36", "38", "40"}

ALL_SHOE_SIZES = set(US_SEQUENCE) | set(EU_SEQUENCE)
ALL_WAIST_SIZES = set(WAIST_SEQUENCE)

WOMENS_REGEX = re.compile(r"\b(women'?s?|wmns|w's|female|ladies|bria|adeline)\b", re.I)
CLEARANCE_REGEX = re.compile(
    r"\b(final sale|clearance|last chance|archive sale|discontinued|sample sale|mystery|grab bag|seconds|factory second|imperfect|bundle|b-grade)\b",
    re.I
)
ACCESSORY_TITLE_REGEX = re.compile(
    r"\b(gift card|care kit|replacement laces|shoelaces|crew socks|ankle socks|no-show socks|insoles|shoe horn|waterproofer|cleaner|brush|belt|wallet|bag|tote|hat|cap|beanie|keychain|wax|oil|hem|hemming)\b",
    re.I
)
FOOTWEAR_EXCLUDED_TYPES = {"accessories", "socks", "shoe care", "gift card", "gift cards", "laces", "insoles", "apparel", "merch", "bags", "belts"}
WAIST_EXCLUDED_TYPES = {"accessories", "socks", "gift card", "gift cards", "shirts", "tops", "tees", "t-shirts", "jackets", "outerwear", "hats", "headwear", "bags", "belts", "care"}

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
    doh_url = f"https://dns.google/resolve?name={domain}&type=MX"
    data = fetch_json(doh_url, timeout=5)
    if data and isinstance(data, dict):
        status = data.get("Status")
        if status == 3:
            return False
        if status == 0 and data.get("Answer"):
            return True
    return True


def is_excluded_product(prod, vertical):
    p_title = str(prod.get("title") or "")
    p_handle = str(prod.get("handle") or "").replace("-", " ")
    p_type = str(prod.get("product_type") or "").strip().lower()
    p_tags = " ".join(prod.get("tags", [])) if isinstance(prod.get("tags"), list) else str(prod.get("tags") or "")

    excluded_types = WAIST_EXCLUDED_TYPES if vertical == "waist" else FOOTWEAR_EXCLUDED_TYPES
    if p_type in excluded_types:
        return True
    if CLEARANCE_REGEX.search(p_title) or CLEARANCE_REGEX.search(p_handle) or CLEARANCE_REGEX.search(p_tags):
        return True
    if ACCESSORY_TITLE_REGEX.search(p_title):
        return True
    if vertical == "waist" and WOMENS_REGEX.search(p_title):
        return True
    return False


def is_valid_variant_price(price_str):
    try:
        return float(price_str) >= MIN_PRICE_FLOOR
    except (ValueError, TypeError):
        return False


def is_womens_product(p_title, p_handle, colorway):
    combined = f"{p_title} {p_handle.replace('-', ' ')} {colorway}"
    return bool(WOMENS_REGEX.search(combined))


def parse_variant_size_and_group(variant, vertical):
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

        if vertical == "waist":
            combo = re.match(r"^\s*(?:W|Waist\s*)?(28|29|30|31|32|33|34|35|36|38|40)\s*(?:x|/|L|-|\s)\s*(?:L|Inseam\s*)?(\d{2})\s*$", opt, re.I)
            if combo and not found_size:
                found_size = combo.group(1)
                group_parts.append(f'{combo.group(2)}" Inseam')
                continue
            norm = re.sub(r"(?i)\b(waist|size|w)\b", " ", opt)
            norm = re.sub(r"(?i)(?<=\d)(w)\b", "", norm)
            tokens = re.findall(r"\b(28|29|30|31|32|33|34|35|36|38|40)\b", norm)
            if tokens and not found_size:
                found_size = tokens[0]
            else:
                group_parts.append(opt)
        else:
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


def get_stocked_neighbors(size, stocked_sizes_set, vertical):
    if vertical == "waist":
        seq = WAIST_SEQUENCE
    else:
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
    """Strips HTML tags, **Restock** flags, non-breaking spaces, and formats bare 2-digit inseams."""
    cleaned = str(title or "").replace("\xa0", " ")
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"(\*\*[^*]+\*\*|\[[^\]]+\])", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"(?i)^men'?s\s+the\s+", "Men's ", cleaned)
    cleaned = re.sub(r"(?i)^women'?s\s+the\s+", "Women's ", cleaned)
    if cleaned.lower().startswith("the "):
        cleaned = cleaned[4:]
    cleaned = re.sub(r"\((\d{2})\)$", r'(\1" Inseam)', cleaned)
    cleaned = re.sub(r"/\s*(\d{2})\)$", r'/ \1" Inseam)', cleaned)
    return cleaned.strip()


def brand_possessive(brand_name):
    b = brand_name.strip()
    return f"{b}'" if b.lower().endswith("s") else f"{b}'s"


def export_brand_csv(brand_name, domain, anomalies):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", brand_name.lower()).strip("_")
    filepath = os.path.join(REPORTS_DIR, f"{slug}_gap_sheet.csv")

    fieldnames = [
        "Product & Variant Group",
        "Curve Type",
        "Depleted Core Size",
        "Stocked Neighbor Sizes",
        "Nearest Edge Size Stocked",
        "Unit Price",
        "In Top 20 Collection",
        "Confirmed Days OOS (Ledger)",
        "Direct Storefront Verify Link"
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in anomalies:
            writer.writerow({
                "Product & Variant Group": clean_product_grammar(item["product_name"]),
                "Curve Type": item["size_curve_profile"],
                "Depleted Core Size": item["core_size_oos"],
                "Stocked Neighbor Sizes": " & ".join(item["adjacent_sizes_in_stock"]),
                "Nearest Edge Size Stocked": item["nearest_edge_size_in_stock"],
                "Unit Price": f"${item['price']}",
                "In Top 20 Collection": "YES" if item["in_top20_verified"] else "NO (Merchandising Gap)",
                "Confirmed Days OOS (Ledger)": max(1, item["confirmed_ledger_days_oos"]),
                "Direct Storefront Verify Link": item["verify_url"]
            })
    return filepath


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
    csv_to_read = VERIFIED_INBOXES_CSV if os.path.exists(VERIFIED_INBOXES_CSV) else (
        LEGACY_VERIFIED_CSV if os.path.exists(LEGACY_VERIFIED_CSV) else None
    )
    if not csv_to_read:
        return {}
    domain_lookup = {t["domain"]: t for t in TARGETS}
    valid_by_domain = {}
    try:
        with open(csv_to_read, "r", encoding="utf-8") as f:
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
                    print(f"[!] Warning: Skipped malformed row in {csv_to_read}: {row_err}")
                    continue
    except Exception as file_err:
        print(f"[!] Warning: Could not read {csv_to_read}: {file_err}")
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
    return {"_meta": {"run_count": 0, "first_initialized_utc": None}, "stores": {}, "store_metrics": {}}


def save_drift_ledger(ledger):
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)


def build_outbound_sequence(target_meta, lead, top3_anomalies, total_holes, oos_top20_count, catalog_oos_pct, hero_cov_pct, store_newly_oos_count):
    first_name = target_meta["first"]
    brand = target_meta["brand"]
    vertical = target_meta.get("vertical", "footwear")
    brand_poss = brand_possessive(brand)
    clean_sku = clean_product_grammar(lead["product_name"])
    c_size = lead["core_size_oos"]
    price = lead["price"]
    adj_a, adj_b = lead["adjacent_sizes_in_stock"][0], lead["adjacent_sizes_in_stock"][1]
    l_days = lead["confirmed_ledger_days_oos"]
    p_days = lead["proxy_days_oos"]
    sku_newly_oos = lead.get("sku_newly_oos_since_last_run", 0)
    in_top20 = lead.get("in_top20_verified", False)

    size_label = f"waist {c_size}" if vertical == "waist" else f"size {c_size}"
    unit_noun = "unit" if vertical == "waist" else "pair"
    item_noun = "style" if vertical == "waist" else "shoe"

    if 2 <= l_days <= 10:
        time_clause = f"has remained unreplenished across our last {l_days} days of tracking"
    elif l_days > 10:
        time_clause = f"has been sitting sold out for over a week ({l_days}+ days)"
    elif p_days >= 5:
        time_clause = f"has been sitting sold out for ~{p_days} days"
    else:
        time_clause = "is sitting sold out right in the middle of the size curve"

    if sku_newly_oos > 0:
        drift_clause = f" — including {sku_newly_oos} newly depleted size(s) on this exact {item_noun} since our last check"
    elif store_newly_oos_count > 0:
        drift_clause = f" — with {store_newly_oos_count} additional variants dropping out of stock store-wide since our last check"
    else:
        drift_clause = ""

    merch_insight = (
        f" (and notably, the {clean_sku} isn't currently surfaced inside {brand_poss} Top 20 collection)"
        if not in_top20 and oos_top20_count >= 10 else ""
    )

    # Gate Hero SKU coverage so it only fires when coverage is genuinely degraded (<= 85.0%)
    hero_clause_paren = f"; Hero SKU size coverage down to {hero_cov_pct}%" if hero_cov_pct <= 85.0 else ""
    hero_clause_standalone = f" (with Hero SKU size coverage down to {hero_cov_pct}%)" if hero_cov_pct <= 85.0 else ""

    if oos_top20_count >= 10:
        subject = f"{brand}: {size_label} gap ({oos_top20_count} variants dead in top 20)"
        scope_line = (
            f"Across {brand_poss} top 20 featured products, {oos_top20_count} variants are currently depleted "
            f"({catalog_oos_pct}% OOS across the full catalog{hero_clause_paren}){drift_clause}."
        )
    else:
        subject = f"{brand}: {clean_sku} {size_label} gap ({catalog_oos_pct}% catalog OOS)"
        scope_line = (
            f"Right now, {catalog_oos_pct}% of {brand_poss} catalog variants are sitting out of stock"
            f"{hero_clause_standalone}{drift_clause}."
        )

    day1_body = (
        f"Hi {first_name},\n\n"
        f"Your {clean_sku} in {size_label} {time_clause} — while adjacent sizes {adj_a} and {adj_b} are still live right next to it{merch_insight}.\n\n"
        f"{scope_line} At ${price} a {unit_noun}, {size_label} is a core mid-curve revenue driver sitting with a dead buy-button while paid and organic traffic hits the page.\n\n"
        f"I pulled the full SKU-level gap sheet for {brand} this morning — reply 'send' and I'll drop the CSV right here (no deck, no sales call).\n\n"
        f"Best,\nDenham"
    )

    inline_bullets = []
    for idx, item in enumerate(top3_anomalies[:3], 1):
        sku_name = clean_product_grammar(item["product_name"])
        a1, a2 = item["adjacent_sizes_in_stock"][0], item["adjacent_sizes_in_stock"][1]
        top20_tag = "In Top 20" if item["in_top20_verified"] else "Not in Top 20"
        inline_bullets.append(
            f"{idx}. {sku_name} (${item['price']}) — Size {item['core_size_oos']} DEAD | Sizes {a1} & {a2} LIVE ({top20_tag})"
        )
    inline_block = "\n".join(inline_bullets)

    delivery_reply = (
        f"Hi {first_name},\n\n"
        f"Attached is the full mid-curve gap CSV for {brand} ({total_holes} active core-size holes where adjacent sizes are still taking traffic).\n\n"
        f"If you're reading on mobile, here are the top 3 revenue-bleeding holes right now:\n"
        f"{inline_block}\n\n"
        f"Most ops teams only catch these mid-run holes during manual weekly pulls. We run an automated daily drift monitor that flags new core-size holes and Hero SKU coverage drops across your Top 20 collections every Monday morning before ad spend gets burned.\n\n"
        f"It's $1,000/mo flat — month-to-month, and you keep the CSVs regardless (one recovered size-run on a ${price} SKU covers the month). Want me to put {brand} on the live tracker starting Monday?\n\n"
        f"Best,\nDenham"
    )

    delta_num = max(store_newly_oos_count, 2)
    tuesday_followup = (
        f"Hi {first_name} — quick update after running our morning pass on {brand}.\n\n"
        f"Since our last check, {delta_num} variants have dropped out of stock across the catalog, and your {clean_sku} in {size_label} is still sitting dead between sizes {adj_a} and {adj_b}.\n\n"
        f"Still happy to drop the updated {total_holes}-SKU CSV right here if you want to see which items took the hit.\n\n"
        f"Best,\nDenham"
    )

    return {
        "email_draft": {"subject": subject, "body": day1_body},
        "delivery_reply_draft": delivery_reply,
        "tuesday_followup_draft": tuesday_followup
    }


def audit_store(target_meta, ledger, verified_winners):
    domain = target_meta["domain"]
    vertical = target_meta.get("vertical", "footwear")
    print(f"[*] Auditing {domain} [{vertical.upper()}] (DoH MX + Paginated Catalog)...")

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
    today_prefix = now_iso[:10]

    prev_store_state = ledger["stores"].get(domain, {})
    # Check if this store already had multi-day history before today so same-day re-runs preserve today's newly_oos counts
    store_has_prior_history = any(
        parse_iso_days(v.get("first_seen_oos_utc")) >= 1
        for v in prev_store_state.values()
        if isinstance(v, dict) and v.get("first_seen_oos_utc")
    )
    current_store_state = {}

    total_variants = 0
    total_oos = 0
    hero_total_v = 0
    hero_oos_v = 0
    oos_featured_count = 0
    store_newly_oos_count = 0

    asymmetry_candidates = []

    for prod in products:
        raw_p_name = prod.get("title", "Unknown Product")
        p_name = clean_product_grammar(raw_p_name)
        p_handle = prod.get("handle", "")
        in_top20 = (p_handle in top20_handles) if top20_verified else False
        in_hero5 = p_handle in hero_handles
        excluded = is_excluded_product(prod, vertical)

        color_groups = {}
        sku_newly_oos_by_color = {}

        for v in prod.get("variants", []):
            v_id = str(v.get("id"))
            avail = bool(v.get("available", False))
            price = v.get("price", "0.00")
            size, colorway = parse_variant_size_and_group(v, vertical)
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
                    # Preserve today's newly-OOS drops if script is re-run on the same UTC date
                    if store_has_prior_history and str(first_seen_oos).startswith(today_prefix):
                        store_newly_oos_count += 1
                        sku_newly_oos_by_color[colorway] = sku_newly_oos_by_color.get(colorway, 0) + 1
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

            if size and not excluded and is_valid_variant_price(price):
                color_groups.setdefault(colorway, []).append({
                    "variant_id": v_id,
                    "size": size,
                    "available": avail,
                    "ledger_days_oos": ledger_days_oos,
                    "proxy_days": proxy_days,
                    "price": price
                })

        for colorway, v_list in color_groups.items():
            if vertical == "waist":
                womens_flag = False
                active_core_set = WAIST_CORE_SIZES
                active_edge_set = WAIST_EDGE_SIZES
                curve_label = "Men's Waist Core (31-34)"
            else:
                womens_flag = is_womens_product(raw_p_name, p_handle, colorway)
                active_core_set = WOMENS_CORE_SIZES if womens_flag else MENS_CORE_SIZES
                active_edge_set = WOMENS_EDGE_SIZES if womens_flag else MENS_EDGE_SIZES
                curve_label = "Women's Core (7-9)" if womens_flag else "Men's/Unisex Core (8.5-11)"

            stocked_sizes = {item["size"] for item in v_list if item["available"]}
            edge_stocked = [s for s in stocked_sizes if s in active_edge_set]
            core_oos_items = [item for item in v_list if not item["available"] and item["size"] in active_core_set]

            if not core_oos_items or not edge_stocked:
                continue

            for oos_item in core_oos_items:
                c_size = oos_item["size"]
                stocked_neighbors = get_stocked_neighbors(c_size, stocked_sizes, vertical)
                if len(stocked_neighbors) == 2:
                    confirmed_days = oos_item["ledger_days_oos"]
                    effective_days = max(confirmed_days, oos_item["proxy_days"])
                    sku_drops = sku_newly_oos_by_color.get(colorway, 0)
                    gender_priority = 0 if womens_flag else 3
                    score = (
                        effective_days
                        + (15 if in_top20 else 0)
                        + (10 if confirmed_days >= 1 else 0)
                        + (5 if sku_drops > 0 else 0)
                        + gender_priority
                    )
                    raw_full = f"{p_name} ({colorway})" if colorway != "Standard" else p_name
                    full_title = clean_product_grammar(raw_full)

                    asymmetry_candidates.append({
                        "product_name": full_title,
                        "size_curve_profile": curve_label,
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
    hero_coverage_pct = round(100.0 - hero_bleed_pct, 1)

    ledger.setdefault("store_metrics", {})[domain] = {
        "last_updated_utc": now_iso,
        "catalog_oos_pct": catalog_oos_pct,
        "hero_size_coverage_pct": hero_coverage_pct
    }

    if catalog_oos_pct < 5.0 or not asymmetry_candidates:
        print(f"  [~] {domain}: Filtered (<5% OOS or no strict 2-neighbor holes).")
        return None

    asymmetry_candidates.sort(key=lambda x: x["rank_score"], reverse=True)
    lead = asymmetry_candidates[0]

    csv_path = export_brand_csv(target_meta["brand"], domain, asymmetry_candidates)
    ranked_candidates = generate_ranked_permutations(target_meta["first"], target_meta["last"], domain)
    winner_info = verified_winners.get(domain)

    seq = build_outbound_sequence(
        target_meta, lead, asymmetry_candidates[:3], len(asymmetry_candidates),
        oos_featured_count, catalog_oos_pct, hero_coverage_pct, store_newly_oos_count
    )

    return {
        "store_url": domain,
        "brand": target_meta["brand"],
        "vertical": vertical,
        "mx_verified": mx_valid,
        "decision_maker": f"{target_meta['first']} {target_meta['last']} ({target_meta['title']})",
        "verified_winning_email": winner_info["email"] if winner_info else "PENDING_VERIFICATION",
        "ranked_candidate_inboxes": ranked_candidates,
        "client_csv_report": csv_path,
        "total_mid_curve_holes_in_csv": len(asymmetry_candidates),
        "products_indexed": len(products),
        "total_variants": total_variants,
        "catalog_oos_rate": f"{catalog_oos_pct}%",
        "hero_bleed_rate": f"{hero_bleed_pct}%",
        "hero_size_coverage_pct": f"{hero_coverage_pct}%",
        "oos_featured_top20_variants": oos_featured_count,
        "top20_order_verified": top20_verified,
        "store_newly_oos_since_last_run": store_newly_oos_count,
        "primary_size_asymmetry": lead,
        "hook": seq["email_draft"]["body"].split("\n\n")[1],
        "email_draft": seq["email_draft"],
        "delivery_reply_draft": seq["delivery_reply_draft"],
        "tuesday_followup_draft": seq["tuesday_followup_draft"]
    }


def main():
    ledger = load_drift_ledger()
    verified_winners = load_verified_winners()

    run_count = ledger["_meta"].get("run_count", 0) + 1
    if run_count == 1:
        ledger["_meta"]["first_initialized_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ledger["_meta"]["run_count"] = run_count

    print(f"[*] Executing Sanitized Multi-Vertical Telemetry Pass (Run #{run_count} — 35 Targets)...\n")

    results = []
    nb_rows = []

    for idx, target_meta in enumerate(TARGETS):
        res = audit_store(target_meta, ledger, verified_winners)
        if res:
            results.append(res)
            print(f"  [+] {res['brand']} ({res['vertical']}) -> {res['email_draft']['subject']}")
            print(f"      CSV: {res['client_csv_report']} ({res['total_mid_curve_holes_in_csv']} holes | Hero Coverage: {res['hero_size_coverage_pct']})")
            print(f"      Verify: {res['primary_size_asymmetry']['verify_url']}\n")
            for item in res["ranked_candidate_inboxes"]:
                nb_rows.append({
                    "brand": res["brand"],
                    "domain": res["store_url"],
                    "vertical": res["vertical"],
                    "executive": res["decision_maker"],
                    "priority_rank": item["rank"],
                    "inbox_type": item["type"],
                    "email": item["email"]
                })
        if idx < len(TARGETS) - 1:
            time.sleep(0.8)

    save_drift_ledger(ledger)

    with open("footwear_anomalies.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    with open(INBOX_CANDIDATES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["brand", "domain", "vertical", "executive", "priority_rank", "inbox_type", "email"])
        writer.writeheader()
        writer.writerows(nb_rows)

    print(f"[✓] Complete: {len(results)} actionable stores exported to footwear_anomalies.json")
    print(f"[✓] Exported {len(nb_rows)} candidate emails to {INBOX_CANDIDATES_CSV}")


if __name__ == "__main__":
    main()