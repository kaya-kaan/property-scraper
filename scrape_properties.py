#python scrape_properties.py

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
}

TIMEOUT = 30

REALSTAR_PAGE_RULES = {
    "main": {
        "suffixes": [""],
        "keywords": [],
    },
    "floorplans": {
        "suffixes": ["/brochure"],
        "keywords": [
            "floor plans",
            "floorplans",
            "brochure",
            "suites",
            "available units",
        ],
    },
    "amenities": {
        "suffixes": ["/amenities"],
        "keywords": [
            "amenities",
            "community amenities",
            "apartment amenities",
            "building amenities",
        ],
    },
}

HAZELVIEW_PAGE_RULES = {
    "main": {
        "suffixes": [""],
        "keywords": [],
    },
}

DEFAULT_PAGE_RULES = {
    "main": {
        "suffixes": [""],
        "keywords": [],
    },
}

IGNORE_LINK_KEYWORDS = [
    "privacy",
    "cookie",
    "login",
    "sign in",
    "resident portal",
    "applicant",
    "careers",
    "corporate",
    "contact us",
    "facebook",
    "instagram",
    "linkedin",
    "youtube",
    "x.com",
    "twitter",
    "mailto:",
    "tel:",
]

OUTPUT_FILE = "raw_collected_properties.json"
INPUT_FILE = "urls.txt"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def detect_provider(url: str) -> str:
    netloc = urlparse(url).netloc.lower()

    if netloc.endswith("realstar.ca"):
        return "realstar"
    if netloc.endswith("hazelviewproperties.com"):
        return "hazelview"

    return "generic"


def page_rules_for_provider(provider: str) -> Dict[str, Dict[str, List[str]]]:
    if provider == "realstar":
        return REALSTAR_PAGE_RULES
    if provider == "hazelview":
        return HAZELVIEW_PAGE_RULES
    return DEFAULT_PAGE_RULES




def fetch_html(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=HEADERS["User-Agent"],
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/",
            }
        )
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        html = page.content()
        print(f"Fetched with browser: {url}")
        browser.close()
        return html

def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def extract_title(soup: BeautifulSoup) -> str:
    if soup.title:
        return clean(soup.title.get_text(" ", strip=True))
    return ""


def extract_meta_description(soup: BeautifulSoup) -> str:
    tag = soup.find("meta", attrs={"name": "description"})
    if tag and tag.get("content"):
        return clean(tag["content"])
    return ""


def extract_visible_text(soup: BeautifulSoup) -> str:
    parts = []
    for tag in soup.find_all(string=True):
        parent = tag.parent.name if tag.parent else ""
        if parent in {"script", "style", "noscript"}:
            continue
        text = clean(tag)
        if text:
            parts.append(text)
    return "\n".join(parts)


def extract_json_ld(soup: BeautifulSoup) -> List[dict]:
    items = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                items.extend([x for x in data if isinstance(x, dict)])
            elif isinstance(data, dict):
                items.append(data)
        except Exception:
            continue
    return items


def extract_headings(soup: BeautifulSoup) -> Dict[str, List[str]]:
    return {
        "h1": [clean(x.get_text(" ", strip=True)) for x in soup.find_all("h1") if clean(x.get_text(" ", strip=True))],
        "h2": [clean(x.get_text(" ", strip=True)) for x in soup.find_all("h2") if clean(x.get_text(" ", strip=True))],
        "h3": [clean(x.get_text(" ", strip=True)) for x in soup.find_all("h3") if clean(x.get_text(" ", strip=True))],
    }


def same_domain(url1: str, url2: str) -> bool:
    return urlparse(url1).netloc.lower() == urlparse(url2).netloc.lower()


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    cleaned = parsed._replace(fragment="")
    url = cleaned.geturl()
    return url.rstrip("/")


def should_ignore_link(href: str, text: str) -> bool:
    blob = f"{href} {text}".lower()
    return any(keyword in blob for keyword in IGNORE_LINK_KEYWORDS)


def extract_links(soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
    links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = clean(a.get("href", ""))
        text = clean(a.get_text(" ", strip=True))

        if not href:
            continue
        if href.startswith("#"):
            continue

        full_url = urljoin(base_url, href)
        full_url = normalize_url(full_url)

        if not same_domain(base_url, full_url):
            continue
        if should_ignore_link(full_url, text):
            continue

        key = (full_url, text.lower())
        if key in seen:
            continue
        seen.add(key)

        links.append({
            "text": text,
            "href": full_url,
        })

    return links


def fetch_page_data(url: str) -> Dict:
    html = fetch_html(url)
    soup = soup_from_html(html)

    return {
        "url": normalize_url(url),
        "title": extract_title(soup),
        "meta_description": extract_meta_description(soup),
        "html": html,
        "text": extract_visible_text(soup),
        "json_ld": extract_json_ld(soup),
        "headings": extract_headings(soup),
        "links": extract_links(soup, url),
    }


def try_suffixes(base_url: str, suffixes: List[str]) -> Optional[Dict]:
    last_error = None

    for suffix in suffixes:
        candidate = normalize_url(base_url.rstrip("/") + suffix)
        print(f"Trying: {candidate}")
        try:
            return fetch_page_data(candidate)
        except Exception as e:
            print(f"Failed: {candidate} -> {repr(e)}")
            last_error = e

    if last_error:
        raise RuntimeError(f"All suffix attempts failed for {base_url}: {repr(last_error)}")

    return None


def score_link_candidate(link: Dict[str, str], keywords: List[str]) -> int:
    blob = f"{link.get('text', '')} {link.get('href', '')}".lower()
    score = 0
    for keyword in keywords:
        if keyword.lower() in blob:
            score += 1
    return score


def find_best_link_page(main_page: Dict, role_name: str, keywords: List[str]) -> Optional[Dict]:
    candidates = []
    for link in main_page.get("links", []):
        score = score_link_candidate(link, keywords)
        if score > 0:
            candidates.append((score, link["href"]))

    candidates.sort(reverse=True)

    tried = set()
    for _, url in candidates:
        if url in tried:
            continue
        tried.add(url)
        try:
            return fetch_page_data(url)
        except Exception:
            continue

    return None


def discover_pages_for_property(base_url: str, provider: str) -> Dict[str, Dict]:
    page_rules = page_rules_for_provider(provider)
    pages = {}

    # Main page
    main_page = try_suffixes(base_url, page_rules["main"]["suffixes"])
    if not main_page:
        raise RuntimeError(f"Could not fetch main page for {base_url}")
    pages["main"] = main_page

    # Other roles
    for role_name, rule in page_rules.items():
        if role_name == "main":
            continue

        page = None
        try:
            page = try_suffixes(base_url, rule["suffixes"])
        except Exception as e:
            print(f"Suffix discovery failed for {role_name}: {repr(e)}")

        if not page and rule["keywords"]:
            page = find_best_link_page(main_page, role_name, rule["keywords"])

        if page:
            pages[role_name] = page
        else:
            pages[role_name] = {
                "url": "",
                "title": "",
                "meta_description": "",
                "html": "",
                "text": "",
                "json_ld": [],
                "headings": {"h1": [], "h2": [], "h3": []},
                "links": [],
                "error": f"Could not find page for role: {role_name}",
            }

    return pages


def collect_property(base_url: str) -> Dict:
    base_url = normalize_url(base_url)
    provider = detect_provider(base_url)
    pages = discover_pages_for_property(base_url, provider)

    return {
        "base_url": base_url,
        "provider": provider,
        "page_rules_used": page_rules_for_provider(provider),
        "pages": pages,
    }


def read_urls(file_path: str) -> List[str]:
    lines = Path(file_path).read_text(encoding="utf-8").splitlines()
    return [clean(line) for line in lines if clean(line) and not clean(line).startswith("#")]


def main():
    urls = read_urls(INPUT_FILE)
    results = []

    for url in urls:
        try:
            print(f"Collecting: {url}")
            result = collect_property(url)
            results.append(result)
        except Exception as e:
            provider = detect_provider(url)
            print(f"FAILED: {url} -> {e}")
            results.append({
                "base_url": url,
                "provider": provider,
                "page_rules_used": page_rules_for_provider(provider),
                "pages": {},
                "error": str(e),
            })

    Path(OUTPUT_FILE).write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
