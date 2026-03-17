import json
import re
from pathlib import Path
from typing import List, Dict, Tuple

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
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

SUITE_FEATURE_PATTERNS = [
    (r"\bfully renovated suites?\b", "Fully Renovated Suites"),
    (r"\bnewly renovated suites?\b", "Newly Renovated Suites"),
    (r"\brenovated suites?\b", "Renovated Suites"),
    (r"\bspacious suites?\b", "Spacious Suites"),
    (r"\bfreshly painted units?\b", "Freshly Painted Units"),
    (r"\bopen-concept modern kitchens?\b", "Open-concept Modern Kitchens"),
    (r"\bopen-concept kitchens?\b", "Open-concept Kitchens"),
    (r"\bchrome accents\b", "Chrome Accents"),
    (r"\bbreakfast bars?\b", "Breakfast Bars"),
    (r"\blaminate countertops?\b", "Laminate Countertops"),
    (r"\bhard surface countertops?\b", "Hard Surface Countertops"),
    (r"\bgranite countertops?\b", "Granite Countertops"),
    (r"\bover-?mount sinks?\b", "Over-mount Sinks"),
    (r"\bundermount double sinks?\b", "Undermount Double Sinks"),
    (r"\bundermount sinks?\b", "Undermount Sinks"),
    (r"\btiled backsplashes?\b", "Tiled Backsplashes"),
    (r"\bstainless steel appliances?\b", "Stainless Steel Appliances"),
    (r"\bstainless steel refrigerator\b", "Stainless Steel Refrigerator"),
    (r"\bfridge\b", "Fridge"),
    (r"\brefrigerator\b", "Refrigerator"),
    (r"\bstove\b", "Stove"),
    (r"\bmicrowave\b", "Microwave"),
    (r"\bdishwasher available in select(?:ed)? units?\b", "Dishwasher Available in Select Units"),
    (r"\bdishwasher\b", "Dishwasher"),
    (r"\bupgraded bathroom fixtures\b", "Upgraded Bathroom Fixtures"),
    (r"\bnew mirrors\b", "New Mirrors"),
    (r"\bnew vanities\b", "New Vanities"),
    (r"\bnewly finished flooring\b", "Newly Finished Flooring"),
    (r"\bnew flooring\b", "New Flooring"),
    (r"\bnew bathroom tiles\b", "New Bathroom Tiles"),
    (r"\bnew kitchen and bathroom tiles\b", "New Kitchen and Bathroom Tiles"),
    (r"\bnew light fixtures\b", "New Light Fixtures"),
    (r"\bnew hardware fixtures\b", "New Hardware Fixtures"),
    (r"\bair conditioning\b", "Air Conditioning"),
    (r"\blarge brightly lit windows\b", "Large Brightly Lit Windows"),
    (r"\bprivate balconies\b", "Private Balconies"),
    (r"\bbalconies\b", "Balconies"),
    (r"\bbalcony\b", "Balcony"),
    (r"\bhardwood flooring\b", "Hardwood Flooring"),
    (r"\bhardwood floors\b", "Hardwood Floors"),
    (r"\bceramics\b", "Ceramics"),
    (r"\bfully renovated bathrooms?\b", "Fully Renovated Bathrooms"),
    (r"\bfully renovated kitchens?\b", "Fully Renovated Kitchens"),
    (r"\brenovated kitchen\b", "Renovated Kitchen"),
    (r"\brenovated bathroom\b", "Renovated Bathroom"),
    (r"\bnew bathrooms?\b", "New Bathrooms"),
    (r"\bupdated kitchen\b", "Updated Kitchen"),
    (r"\bupdated kitchens?\b", "Updated Kitchens"),
    (r"\b1\.5 bathrooms? available on select units?\b", "1.5 Bathrooms Available on Select Units"),
]

PARKING_PATTERNS = [
    (r"\bindoor and outdoor parking\b", "Indoor and Outdoor Parking"),
    (r"\bindoor/outdoor parking\b", "Indoor and Outdoor Parking"),
    (r"\bindoor parking\b", "Indoor Parking"),
    (r"\boutdoor parking\b", "Outdoor Parking"),
    (r"\bunderground parking\b", "Underground Parking"),
    (r"\bunderground garage\b", "Underground Parking"),
    (r"\bcovered parking\b", "Covered Parking"),
    (r"\bcovered parking available\b", "Covered Parking"),
    (r"\bvisitor parking\b", "Visitor Parking"),
    (r"\bvisitor parking available\b", "Visitor Parking"),
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

AMENITY_HEADINGS = [
    "Our Amenities",
    "Amenities",
    "Property Amenities",
    "Building Amenities",
    "Everything you need, all in one place",
]

STOP_WORDS = {
    "Suites",
    "Location",
    "Gallery",
    "Contact",
    "Neighbourhood",
    "Neighborhood",
    "Floor Plans",
    "Virtual Tour",
    "Availability",
    "Map",
}


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


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def read_urls(file_path: str) -> List[str]:
    lines = Path(file_path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def expand_subpage_urls(base_url: str) -> List[str]:
    base = base_url.strip().rstrip("/")
    paths = ["", "/amenities", "/suites", "/location"]
    return [base + path for path in paths]


def fetch_property_pages(base_url: str) -> Dict[str, str]:
    pages = {}
    for url in expand_subpage_urls(base_url):
        try:
            print(f"  -> fetching {url}")
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                pages[url] = response.text
        except Exception as e:
            print(f"     failed {url}: {e}")
    return pages


def extract_page_title(soup: BeautifulSoup) -> str:
    if soup.title:
        title = clean_text(soup.title.get_text(" ", strip=True))
        title = re.sub(r"^Home\s*\|\s*", "", title, flags=re.I)
        return title
    h1 = soup.find("h1")
    if h1:
        return clean_text(h1.get_text(" ", strip=True))
    return ""


def extract_meta_description(soup: BeautifulSoup) -> str:
    tag = soup.find("meta", attrs={"name": "description"})
    if tag and tag.get("content"):
        return clean_text(tag["content"])
    return ""


def get_lines_from_soup(soup: BeautifulSoup) -> List[str]:
    return [clean_text(x) for x in soup.stripped_strings if clean_text(x)]


def get_phone(text: str) -> str:
    match = re.search(r"(?:\+?1[\s\-]?)?\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}", text)
    return match.group(0) if match else ""


def extract_phone_from_soup(soup: BeautifulSoup) -> str:
    tel_link = soup.select_one('a[href^="tel:"]')
    if tel_link:
        href = tel_link.get("href", "")
        phone = href.replace("tel:", "").strip()
        return phone
    return ""


def detect_manager_name_from_soup(soup: BeautifulSoup, base_url: str) -> str:
    html = str(soup).lower()
    base = base_url.lower()
    if "sterling-karamar" in html or "sterling karamar" in html or "karamar" in base:
        return "Sterling Karamar"
    if "hazelview" in html or "hazelview" in base:
        return "Hazelview Properties"
    return ""


def get_address_city_province(lines: List[str]) -> Tuple[str, str, str]:
    joined = "\n".join(lines)

    pattern = re.compile(
        r"([0-9][^\n,]*?(?:Street|St\.|Road|Rd\.|Drive|Dr\.|Avenue|Ave\.|Boulevard|Blvd\.|Lane|Ln\.|Court|Ct\.|Crescent|Circle|Terrace|Place|Way)[^\n,]*),?\s*\n?([A-Za-z .'-]+),\s*(ON|AB|BC|MB|NB|NL|NS|PE|QC|SK)\s*[A-Z0-9 ]*",
        flags=re.I,
    )
    m = pattern.search(joined)
    if m:
        address = clean_text(m.group(1))
        city = clean_text(m.group(2))
        prov = PROVINCE_MAP.get(m.group(3).upper(), m.group(3).upper())
        return address, city, prov

    for i in range(len(lines) - 1):
        if re.search(r"\b(ON|AB|BC|MB|NB|NL|NS|PE|QC|SK)\b", lines[i + 1]):
            if re.search(r"\d", lines[i]):
                address = clean_text(lines[i].rstrip(","))
                city_match = re.search(r"([A-Za-z .'-]+),\s*(ON|AB|BC|MB|NB|NL|NS|PE|QC|SK)", lines[i + 1])
                if city_match:
                    city = clean_text(city_match.group(1))
                    prov = PROVINCE_MAP.get(city_match.group(2).upper(), city_match.group(2).upper())
                    return address, city, prov

    return "", "", ""


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


def extract_suite_types_from_text(text: str) -> List[str]:
    text = normalize_suite_type_text(text)

    found = []
    for pattern, label in SUITE_TYPE_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            found.append(label)

    return unique_keep_order(found)


def extract_suite_types_from_suites_page(soup: BeautifulSoup) -> List[str]:
    title = extract_page_title(soup)
    meta = extract_meta_description(soup)
    text = f"{title}\n{meta}"
    return extract_suite_types_from_text(text)


def normalize_suite_features(items: List[str]) -> List[str]:
    items = unique_keep_order(items)

    if "Open-concept Kitchens" in items and "Open-concept Modern Kitchens" in items:
        items = [x for x in items if x != "Open-concept Kitchens"]

    if "Stainless Steel Appliances" in items:
        items = [x for x in items if x not in {
            "Stainless Steel Refrigerator", "Refrigerator", "Fridge", "Stove", "Microwave"
        }]

    if "Dishwasher Available in Select Units" in items and "Dishwasher" in items:
        items = [x for x in items if x != "Dishwasher"]

    if "Hardwood Flooring" in items and "Hardwood Floors" in items:
        items = [x for x in items if x != "Hardwood Floors"]

    if "Private Balconies" in items and "Balconies" in items:
        items = [x for x in items if x != "Balconies"]

    return items


def get_suite_features(text: str) -> List[str]:
    found = []
    for pattern, label in SUITE_FEATURE_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            found.append(label)
    return normalize_suite_features(found)


def extract_location_description(soup: BeautifulSoup) -> str:
    paragraphs = soup.select("div.dmNewParagraph p")
    for p in paragraphs:
        text = clean_text(p.get_text(" ", strip=True))
        if len(text) > 100:
            return text

    meta = extract_meta_description(soup)
    if meta:
        return meta

    lines = get_lines_from_soup(soup)
    for line in lines:
        if len(line) > 100:
            return line

    return ""


def extract_amenities_from_selector(soup: BeautifulSoup) -> List[str]:
    candidates = []

    selectors = [
        "li",
        ".amenities li",
        ".amenity li",
        ".dmRespCol li",
        ".dmNewParagraph li",
        ".dmNewParagraph p",
        ".dmRespCol p",
    ]

    for selector in selectors:
        for el in soup.select(selector):
            text = clean_text(el.get_text(" ", strip=True))
            if not text:
                continue
            if len(text) > 120:
                continue
            if text in STOP_WORDS:
                continue
            candidates.append(text)

    cleaned = []
    for item in candidates:
        low = item.lower()
        if low.startswith("welcome to "):
            continue
        if low.startswith("your new "):
            continue
        if item in {"Amenities", "Property Amenities", "Building Amenities"}:
            continue
        cleaned.append(item)

    return unique_keep_order(cleaned)


def extract_amenities_from_text(lines: List[str]) -> List[str]:
    start_idx = None
    for i, line in enumerate(lines):
        if line in AMENITY_HEADINGS:
            start_idx = i + 1
            break

    if start_idx is None:
        return []

    items = []
    for line in lines[start_idx:start_idx + 80]:
        if line in STOP_WORDS:
            break
        if len(line) > 120:
            continue
        if line.lower().startswith("welcome to "):
            continue
        if line.lower().startswith("your new "):
            continue
        items.append(line)

    return unique_keep_order(items)


def normalize_parking(items: List[str]) -> List[str]:
    items = unique_keep_order(items)

    if "Indoor and Outdoor Parking" in items:
        items = [x for x in items if x not in {"Indoor Parking", "Outdoor Parking"}]

    if "Tenant and Visitor Parking" in items:
        items = [x for x in items if x not in {"Tenant Parking", "Visitor Parking"}]

    return items


def extract_parking_from_amenities(amenities: List[str]) -> List[str]:
    found = []
    amenity_text = "\n".join(amenities).lower()

    for pattern, label in PARKING_PATTERNS:
        if re.search(pattern, amenity_text, flags=re.I):
            found.append(label)

    return normalize_parking(found)


def get_parking(text: str, amenities: List[str]) -> List[str]:
    found = []
    combined = "\n".join(amenities) + "\n" + text

    for pattern, label in PARKING_PATTERNS:
        if re.search(pattern, combined, flags=re.I):
            found.append(label)

    return normalize_parking(found)


def remove_parking_from_amenities(amenities: List[str], parking: List[str]) -> List[str]:
    if not parking:
        return amenities

    cleaned = []
    parking_labels = {p.lower() for p in parking}

    for item in amenities:
        low = item.lower().strip()
        if low in parking_labels:
            continue

        exact_parking = False
        for _, label in PARKING_PATTERNS:
            if low == label.lower():
                exact_parking = True
                break

        if not exact_parking:
            cleaned.append(item)

    return unique_keep_order(cleaned)


def get_utilities(text: str) -> List[str]:
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


def parse_property_from_pages(base_url: str, pages: Dict[str, str]) -> Dict:
    if not pages:
        raise ValueError("No pages could be fetched")

    base = base_url.strip().rstrip("/")

    soups = {url: BeautifulSoup(html, "lxml") for url, html in pages.items()}

    home_soup = soups.get(base) or soups.get(base + "/") or next(iter(soups.values()))
    suites_soup = soups.get(base + "/suites")
    location_soup = soups.get(base + "/location")
    amenities_soup = soups.get(base + "/amenities")

    all_lines = []
    all_text_parts = []

    for soup in soups.values():
        lines = get_lines_from_soup(soup)
        all_lines.extend(lines)
        all_text_parts.append("\n".join(lines))

    combined_text = "\n".join(all_text_parts)

    title = extract_page_title(home_soup)
    phone = extract_phone_from_soup(home_soup) or get_phone(combined_text)
    manager = detect_manager_name_from_soup(home_soup, base_url)
    address, city, province = get_address_city_province(all_lines)

    post_content = extract_meta_description(home_soup)
    if not post_content and location_soup:
        post_content = extract_location_description(location_soup)

    suite_types = []
    if suites_soup:
        suite_types = extract_suite_types_from_suites_page(suites_soup)
    if not suite_types:
        suite_types = extract_suite_types_from_text(combined_text)

    suite_features = get_suite_features(combined_text)

    amenities = []
    if amenities_soup:
        amenities = extract_amenities_from_selector(amenities_soup)

    if not amenities:
        amenities = extract_amenities_from_text(all_lines)

    parking = extract_parking_from_amenities(amenities)
    if not parking:
        parking = get_parking(combined_text, amenities)

    amenities = remove_parking_from_amenities(amenities, parking)
    utilities = get_utilities(combined_text)
    location_description = extract_location_description(location_soup) if location_soup else ""

    return {
        "url": base_url.strip(),
        "post_title": title,
        "post_content": post_content,
        "property_type": "Apartment",
        "property_manager_name": manager,
        "property_manager_phone": phone,
        "property_manager_website": base_url.strip(),
        "address": f"{address}, {city}" if address and city else address,
        "province": province,
        "city_name": city,
        "suite_types": suite_types,
        "suite_features": suite_features,
        "amenities": amenities,
        "utilities_included": utilities,
        "parking": parking,
        "location_description": location_description,
        "pages_scraped": list(pages.keys()),
    }


def main():
    base_urls = read_urls("urls.txt")
    results = []

    for base_url in base_urls:
        try:
            print(f"Scraping property: {base_url}")
            pages = fetch_property_pages(base_url)
            data = parse_property_from_pages(base_url, pages)
            results.append(data)
        except Exception as e:
            print(f"FAILED: {base_url} -> {e}")
            results.append({
                "url": base_url,
                "post_title": "",
                "post_content": "",
                "property_type": "Apartment",
                "property_manager_name": "",
                "property_manager_phone": "",
                "property_manager_website": base_url,
                "address": "",
                "province": "",
                "city_name": "",
                "suite_types": [],
                "suite_features": [],
                "amenities": [],
                "utilities_included": [],
                "parking": [],
                "location_description": "",
                "pages_scraped": [],
                "error": str(e),
            })

    Path("properties.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print("Saved -> properties.json")


if __name__ == "__main__":
    main()