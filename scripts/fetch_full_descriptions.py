"""
Scraper script to fetch full verified product descriptions, specifications,
and feature highlights from Kepler Tech LLC product pages.
Saves to data/verified_descriptions.json.
"""

import json
import os
import re
import time
import urllib.request
from bs4 import BeautifulSoup
from typing import Dict, Any

PRODUCTS_TO_SCRAPE = {
    "citizen-cz-01": "https://www.keplertechllc.com/product/citizen-cz-01-photo-printer/",
    "citizen-cx-02": "https://www.keplertechllc.com/product/citizen-cx-02-photo-printer/",
    "citizen-cy-02": "https://www.keplertechllc.com/product/citizen-cy-02-photo-printer/",
    "citizen-cx-02w": "https://www.keplertechllc.com/product/citizen-cx-02w-large-photo-printer/",
    "epson-am-c4000": "https://www.keplertechllc.com/product/epson-workforce-enterprise-am-c4000-printer/",
    "epson-am-c550": "https://www.keplertechllc.com/product/epson-wf-am-c550-a4-multifunction-printer/",
    "epson-t3100": "https://www.keplertechllc.com/product/epson-surecolor-sc-t3100-wireless-printer-with-stand/",
    "epson-t5100": "https://www.keplertechllc.com/product/epson-surecolor-sc-t5100-large-format-printer/",
    "epson-t5400m": "https://www.keplertechllc.com/product/epson-surecolor-sc-t5100m-plotter-printer/",
    "epson-t5700d": "https://www.keplertechllc.com/product/epson-sc-t5700d-technical-printer/",
    "epson-p700": "https://www.keplertechllc.com/product/epson-surecolor-p700-13-photo-printer/",
    "epson-p900": "https://www.keplertechllc.com/product/epson-surecolor-sc-p900-printer-with-roll-adapter/",
    "epson-p7500": "https://www.keplertechllc.com/product/epson-surecolor-sc-p7500-large-format-printer/",
    "epson-sc-f100": "https://www.keplertechllc.com/product/epson-surecolor-sc-f100-printer/",
    "epson-sc-f500": "https://www.keplertechllc.com/product/epson-surecolor-sc-f500-dye-sublimation-printer/",
    "epson-ds-530ii": "https://www.keplertechllc.com/product/epson-workforce-ds-530ii-color-duplex-document-scanner/",
    "epson-expression-12000xl": "https://www.keplertechllc.com/product/epson-expression-12000xl-photo-scanner/",
    "epson-ds-800wn": "https://www.keplertechllc.com/product/epson-workforce-ds-800wn-document-scanner/",
    "epson-ds-900wn": "https://www.keplertechllc.com/product/epson-workforce-ds-900wn-high-speed-network-document-scanner/"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def clean_text(text: str) -> str:
    """Cleans excess whitespace and trims."""
    if not text:
        return ""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def scrape_product(pid: str, url: str) -> Dict[str, Any]:
    print(f"Fetching {pid} from {url}...")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        soup = BeautifulSoup(html, "html.parser")

        # 1. Page title / Product title
        title_el = soup.find("h1", class_="product_title") or soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else ""

        # 2. Short description
        short_desc_el = soup.find("div", class_="woocommerce-product-details__short-description")
        short_desc = clean_text(short_desc_el.get_text(separator="\n", strip=True)) if short_desc_el else ""

        # 3. Description Tab
        desc_el = soup.find("div", id="tab-description") or soup.find("div", class_="woocommerce-Tabs-panel--description")
        full_desc = ""
        headings = []
        paragraphs = []
        if desc_el:
            # Extract section headings
            for h in desc_el.find_all(["h2", "h3", "h4"]):
                ht = h.get_text(strip=True)
                if ht and ht not in headings:
                    headings.append(ht)
            full_desc = clean_text(desc_el.get_text(separator="\n", strip=True))

        # 4. Specification Tab
        spec_el = soup.find("div", id="tab-specification") or soup.find("div", class_="woocommerce-Tabs-panel--specification") or soup.find("div", id="tab-additional_information")
        specs_text = ""
        specs_table = {}
        if spec_el:
            specs_text = clean_text(spec_el.get_text(separator="\n", strip=True))
            for row in spec_el.find_all("tr"):
                th = row.find(["th", "td"])
                tds = row.find_all("td")
                if th and len(tds) > 0:
                    k = th.get_text(strip=True)
                    v = tds[-1].get_text(strip=True)
                    if k and v:
                        specs_table[k] = v

        # 5. Image URL
        img_el = soup.find("div", class_="woocommerce-product-gallery__image")
        img_url = ""
        if img_el:
            a_tag = img_el.find("a")
            if a_tag and a_tag.get("href"):
                img_url = a_tag["href"]
            else:
                img_tag = img_el.find("img")
                if img_tag and img_tag.get("src"):
                    img_url = img_tag["src"]

        safe_title = title.encode("ascii", "replace").decode("ascii")
        print(f"  -> Title: {safe_title}")
        print(f"  -> Full Desc Length: {len(full_desc)} chars | Headings: {len(headings)}")
        print(f"  -> Specs Length: {len(specs_text)} chars")

        return {
            "id": pid,
            "url": url,
            "title": title,
            "image_url": img_url,
            "short_description": short_desc,
            "full_description": full_desc,
            "feature_headings": headings,
            "specifications_text": specs_text,
            "specifications_table": specs_table
        }
    except Exception as e:
        print(f"  ERROR fetching {pid}: {e}")
        return {
            "id": pid,
            "url": url,
            "error": str(e)
        }


def main():
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    out_path = os.path.join(out_dir, "verified_descriptions.json")

    results = {}
    for pid, url in PRODUCTS_TO_SCRAPE.items():
        data = scrape_product(pid, url)
        results[pid] = data
        time.sleep(0.5)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nSuccessfully saved {len(results)} product descriptions to {out_path}!")


if __name__ == "__main__":
    main()
