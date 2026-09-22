import re
import dns.resolver
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

PROBE_PATHS = [
    "",
    "/pages/contact",
    "/pages/contact-us",
    "/pages/help",
    "/policies/terms-of-service",
    "/policies/privacy-policy"
]

PRIORITY_PREFIXES = [
    "operations", "ops", "merchandising", "customerexperience", 
    "customerservice", "info", "team", "hello", "support"
]

EXCLUDED_DOMAINS = {
    "adr.org",
    "adrservices.com",
    "wixpress.com",
    "sentry.io",
    "shopify.com",
    "myshopify.com",
    "karllagerfeld.com",
    "example.com"
}

EXCLUDED_PREFIXES = {
    "kvkk",
    "privacy",
    "demands",
    "membership",
    "legal",
    "compliance",
    "abuse",
    "security"
}

def check_mx_record(domain: str) -> bool:
    """Verifies that the target domain has active Mail Exchange (MX) records."""
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        return len(answers) > 0
    except Exception:
        return False

def is_valid_operational_email(email: str) -> bool:
    """Filters out arbitration desks, legal departments, and tracking artifacts."""
    email_lower = email.lower()
    
    # Reject media file false positives
    if any(email_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"]):
        return False
        
    parts = email_lower.split('@')
    if len(parts) != 2:
        return False
        
    prefix, domain = parts[0], parts[1]

    if domain in EXCLUDED_DOMAINS:
        return False

    if any(noise in domain for noise in ["sentry", "wixpress", "shopify"]):
        return False

    if any(prefix.startswith(bad_prefix) for bad_prefix in EXCLUDED_PREFIXES):
        return False

    return True

def extract_emails_from_html(html_content: str) -> set:
    """Finds all emails within an HTML document, filtering out noise and non-operational addresses."""
    raw_matches = re.findall(EMAIL_REGEX, html_content)
    return {email.lower() for email in raw_matches if is_valid_operational_email(email)}

def harvest_brand_email(target_url: str) -> str:
    """
    Crawls storefront paths and returns the highest-priority verified email.
    Verifies active MX records prior to returning.
    """
    base_url = target_url.rstrip('/')
    found_emails = set()

    for path in PROBE_PATHS:
        url = urljoin(base_url, path)
        try:
            res = requests.get(url, headers=HEADERS, timeout=8)
            if res.status_code == 200:
                emails = extract_emails_from_html(res.text)
                found_emails.update(emails)
                # Early exit if a high-priority prefix is discovered
                if any(any(email.startswith(p) for p in PRIORITY_PREFIXES) for email in emails):
                    break
        except Exception:
            continue

    if not found_emails:
        return ""

    # Sort: check priority operational prefixes first
    for prefix in PRIORITY_PREFIXES:
        for email in found_emails:
            if email.startswith(prefix):
                domain = email.split('@')[-1]
                if check_mx_record(domain):
                    return email

    # Fall back to any email that passes validation and MX verification
    for email in found_emails:
        domain = email.split('@')[-1]
        if check_mx_record(domain):
            return email

    return ""

if __name__ == "__main__":
    test_targets = [
        "https://stio.com",
        "https://freeflyapparel.com",
        "https://studs.com",
        "https://fashionnova.com"
    ]
    
    print("[*] Testing sanitized lead enrichment engine...")
    for target in test_targets:
        verified_email = harvest_brand_email(target)
        print(f"[+] Target: {target} -> Resolved: {verified_email if verified_email else 'Filtered / No Valid Endpoint'}")