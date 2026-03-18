#python scrape_properties.py

import json
import re
from pathlib import Path
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

SUBPAGES = {
    "home": "",
    "amenities": "/amenities",
    "suites": "/suites",
    "location": "/location",
}

PROVINCE_MAP = {
    "ON": "Ontario",
    "Ontario": "Ontario",
    "AB": "Alberta",
    "Alberta": "Alberta",
    "BC": "British Columbia",
    "British Columbia": "British Columbia",
    "MB": "Manitoba",
    "Manitoba": "Manitoba",
    "NB": "New Brunswick",
    "New Brunswick": "New Brunswick",
    "NL": "Newfoundland and Labrador",
    "Newfoundland and Labrador": "Newfoundland and Labrador",
    "NS": "Nova Scotia",
    "Nova Scotia": "Nova Scotia",
    "PE": "Prince Edward Island",
    "Prince Edward Island": "Prince Edward Island",
    "QC": "Quebec",
    "Quebec": "Quebec",
    "SK": "Saskatchewan",
    "Saskatchewan": "Saskatchewan",
}

SUITE_TYPE_PATTERNS = [
    (r"\bbachelor\b", "Bachelor"),
    (r"\bstudio\b", "Studio"),
    (r"\bone bedroom plus den\b|\b1[\s-]?bedroom plus den\b", "One Bedroom Plus Den"),
    (r"\bone bedroom\b|\b1[\s-]?bedroom\b", "One Bedroom"),
    (r"\btwo bedroom\b|\b2[\s-]?bedroom\b", "Two Bedroom"),
    (r"\bthree bedroom\b|\b3[\s-]?bedroom\b", "Three Bedroom"),
    (r"\bfour bedroom\b|\b4[\s-]?bedroom\b", "Four Bedroom"),
]

PARKING_PATTERNS = [
    (r"\bindoor and outdoor parking\b", "Indoor and Outdoor Parking"),
    (r"\bindoor/outdoor parking\b", "Indoor and Outdoor Parking"),
    (r"\bindoor parking\b", "Indoor Parking"),
    (r"\boutdoor parking\b", "Outdoor Parking"),
    (r"\bunderground parking\b", "Underground Parking"),
    (r"\bunderground garage\b", "Underground Parking"),
    (r"\bcovered parking\b", "Covered Parking"),
    (r"\bvisitor parking\b", "Visitor Parking"),
    (r"\btenant parking\b", "Tenant Parking"),
    (r"\bguest parking\b", "Guest Parking"),
    (r"\btenant and visitor parking\b", "Tenant and Visitor Parking"),
    (r"\bparking available\b", "Parking Available"),
    (r"\bsurface parking\b", "Surface Parking"),
    (r"\bgarage parking\b", "Garage Parking"),
    (r"\bon-site parking\b", "On-Site Parking"),
]

UTILITY_PATTERNS = [
    (r"\bheat\b", "Heat"),
    (r"\bhydro\b", "Hydro"),
    (r"\bwater\b", "Water"),
    (r"\bhot water\b", "Hot Water"),
    (r"\belectricity\b", "Electricity"),
]


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        item = clean_text(str(item))
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def read_urls(file_path: str) -> List[str]:
    lines = Path(file_path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def build_subpage_urls(base_url: str) -> Dict[str, str]:
    base = base_url.strip().rstrip("/")
    return {name: base + suffix for name, suffix in SUBPAGES.items()}


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def extract_visible_text(soup: BeautifulSoup) -> str:
    lines = [clean_text(x) for x in soup.stripped_strings if clean_text(x)]
    return "\n".join(lines)


def extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        title = clean_text(h1.get_text(" ", strip=True))
        if title:
            return title

    if soup.title:
        title = clean_text(soup.title.get_text(" ", strip=True))
        title = re.sub(r"^Home\s*\|\s*", "", title, flags=re.I)
        return title

    return ""


def extract_meta_description(soup: BeautifulSoup) -> str:
    tag = soup.find("meta", attrs={"name": "description"})
    if tag and tag.get("content"):
        return clean_text(tag["content"])
    return ""


def extract_phone(text: str, soup: BeautifulSoup) -> str:
    tel_link = soup.select_one('a[href^="tel:"]')
    if tel_link:
        href = tel_link.get("href", "")
        phone = href.replace("tel:", "").strip()
        if phone:
            return phone

    match = re.search(r"(?:\+?1[\s\-]?)?\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}", text)
    return match.group(0) if match else ""


def detect_manager_name(combined_text: str, base_url: str) -> str:
    low_text = combined_text.lower()
    low_url = base_url.lower()

    if "sterling karamar" in low_text or "sterling-karamar" in low_text or "karamar" in low_url:
        return "Sterling Karamar"
    if "hazelview" in low_text or "hazelview" in low_url:
        return "Hazelview Properties"

    return ""


def extract_address_city_province(combined_text: str) -> Dict[str, str]:
    text = combined_text

    pattern = re.compile(
        r"([0-9][^\n,]*?(?:Street|St\.|Road|Rd\.|Drive|Dr\.|Avenue|Ave\.|Boulevard|Blvd\.|Lane|Ln\.|Court|Ct\.|Crescent|Circle|Terrace|Place|Way)[^\n,]*)"
        r",?\s+([A-Za-z .'-]+),\s*(ON|AB|BC|MB|NB|NL|NS|PE|QC|SK)\b",
        flags=re.I,
    )

    match = pattern.search(text)
    if match:
        address = clean_text(match.group(1))
        city = clean_text(match.group(2))
        province = PROVINCE_MAP.get(match.group(3).upper(), match.group(3).upper())
        return {
            "address": f"{address}, {city}",
            "city_name": city,
            "province": province,
        }

    return {
        "address": "",
        "city_name": "",
        "province": "",
    }


def normalize_suite_type_text(text: str) -> str:
    text = text.lower()

    replacements = [
        (r"\bone and two-bedroom\b", "one bedroom two bedroom"),
        (r"\bone and two bedroom\b", "one bedroom two bedroom"),
        (r"\btwo and three-bedroom\b", "two bedroom three bedroom"),
        (r"\btwo and three bedroom\b", "two bedroom three bedroom"),
        (r"\bthree and four-bedroom\b", "three bedroom four bedroom"),
        (r"\bthree and four bedroom\b", "three bedroom four bedroom"),
        (r"\b1 and 2-bedroom\b", "1 bedroom 2 bedroom"),
        (r"\b1 and 2 bedroom\b", "1 bedroom 2 bedroom"),
        (r"\b2 and 3-bedroom\b", "2 bedroom 3 bedroom"),
        (r"\b2 and 3 bedroom\b", "2 bedroom 3 bedroom"),
        (r"\b3 and 4-bedroom\b", "3 bedroom 4 bedroom"),
        (r"\b3 and 4 bedroom\b", "3 bedroom 4 bedroom"),
        (r"\b1, 2,? ?& 3-bedroom\b", "1 bedroom 2 bedroom 3 bedroom"),
        (r"\b1, 2,? and 3-bedroom\b", "1 bedroom 2 bedroom 3 bedroom"),
        (r"\b1, 2,? ?& 3 bedroom\b", "1 bedroom 2 bedroom 3 bedroom"),
        (r"\b1, 2,? and 3 bedroom\b", "1 bedroom 2 bedroom 3 bedroom"),
        (r"\b1, 2, 3-bedroom\b", "1 bedroom 2 bedroom 3 bedroom"),
        (r"\b1, 2, 3 bedroom\b", "1 bedroom 2 bedroom 3 bedroom"),
        (r"\bstudio, 1, 2,? ?& 3-bedroom\b", "studio 1 bedroom 2 bedroom 3 bedroom"),
        (r"\bstudio, 1, 2,? and 3-bedroom\b", "studio 1 bedroom 2 bedroom 3 bedroom"),
        (r"\bstudio, 1, 2,? ?& 3 bedroom\b", "studio 1 bedroom 2 bedroom 3 bedroom"),
        (r"\bstudio, 1, 2,? and 3 bedroom\b", "studio 1 bedroom 2 bedroom 3 bedroom"),
        (r"\bbachelor, 1 and 2-bedroom\b", "bachelor 1 bedroom 2 bedroom"),
        (r"\bbachelor, 1 and 2 bedroom\b", "bachelor 1 bedroom 2 bedroom"),
        (r"\bbachelor, one and two-bedroom\b", "bachelor one bedroom two bedroom"),
        (r"\bbachelor, one and two bedroom\b", "bachelor one bedroom two bedroom"),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)

    return text


def extract_suite_types(text: str) -> List[str]:
    text = normalize_suite_type_text(text)
    found = []

    for pattern, label in SUITE_TYPE_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            found.append(label)

    return unique_keep_order(found)


def extract_parking(text: str) -> List[str]:
    found = []
    for pattern, label in PARKING_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            found.append(label)
    return unique_keep_order(found)


def extract_utilities(text: str) -> List[str]:
    found = []
    lower = text.lower()

    explicit_context = (
        "utilities included" in lower
        or ("included" in lower and "heat" in lower)
        or ("included" in lower and "water" in lower)
        or ("included" in lower and "hydro" in lower)
    )

    if explicit_context:
        for pattern, label in UTILITY_PATTERNS:
            if re.search(pattern, lower, flags=re.I):
                found.append(label)

    return unique_keep_order(found)


def light_extract_fields(base_url: str, pages: Dict[str, Dict]) -> Dict:
    home = pages.get("home", {})
    home_soup = soup_from_html(home.get("html", "")) if home.get("html") else BeautifulSoup("", "lxml")

    combined_text = "\n".join(
        page.get("text", "") for page in pages.values() if page.get("text")
    )

    title = extract_title(home_soup)
    meta_description = extract_meta_description(home_soup)
    phone = extract_phone(combined_text, home_soup)
    manager = detect_manager_name(combined_text, base_url)
    addr = extract_address_city_province(combined_text)
    suite_types = extract_suite_types(combined_text)
    parking = extract_parking(combined_text)
    utilities = extract_utilities(combined_text)

    return {
        "post_title": title,
        "post_content": meta_description,
        "property_type": "Apartment",
        "property_manager_name": manager,
        "property_manager_phone": phone,
        "property_manager_website": base_url,
        "address": addr["address"],
        "province": addr["province"],
        "city_name": addr["city_name"],
        "suite_types": suite_types,
        "suite_features": [],
        "amenities": [],
        "utilities_included": utilities,
        "parking": parking,
    }


def scrape_property(base_url: str) -> Dict:
    page_urls = build_subpage_urls(base_url)
    pages = {}

    for page_name, page_url in page_urls.items():
        try:
            print(f"  -> fetching {page_url}")
            html = fetch_html(page_url)
            soup = soup_from_html(html)
            text = extract_visible_text(soup)

            pages[page_name] = {
                "url": page_url,
                "html": html,
                "text": text,
                "title": extract_title(soup),
                "meta_description": extract_meta_description(soup),
            }
        except Exception as e:
            print(f"     failed {page_url}: {e}")
            pages[page_name] = {
                "url": page_url,
                "html": "",
                "text": "",
                "title": "",
                "meta_description": "",
                "error": str(e),
            }

    extracted = light_extract_fields(base_url, pages)

    return {
        "url": base_url,
        "pages": pages,
        "scraped_fields": extracted,
    }


def main():
    base_urls = read_urls("urls.txt")
    results = []

    for base_url in base_urls:
        try:
            print(f"Scraping property: {base_url}")
            results.append(scrape_property(base_url))
        except Exception as e:
            print(f"FAILED: {base_url} -> {e}")
            results.append({
                "url": base_url,
                "pages": {},
                "scraped_fields": {},
                "error": str(e),
            })

    Path("properties_raw.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print("Saved -> properties_raw.json")


if __name__ == "__main__":
    main()