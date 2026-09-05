"""
Scraper script for Kepler Tech LLC (https://www.keplertechllc.com/).
Extracts product titles, technical specs, categories, and descriptions.
"""

import sys
import json
import os
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

PRODUCT_URLS = [
    "https://www.keplertechllc.com/product/citizen-cx-02-photo-printer/",
    "https://www.keplertechllc.com/product/citizen-cy-02-photo-printer/",
    "https://www.keplertechllc.com/product/citizen-cz-01-photo-printer/",
    "https://www.keplertechllc.com/product/epson-surecolor-p700-13-photo-printer/",
    "https://www.keplertechllc.com/product/epson-surecolor-p900-17-inch-photo-printer/",
    "https://www.keplertechllc.com/product/epson-workforce-enterprise-am-c4000-printer/",
    "https://www.keplertechllc.com/product/epson-wf-am-c550-a4-multifunction-printer/",
    "https://www.keplertechllc.com/product/epson-sc-t5700d-technical-printer/"
]


def fetch_and_parse_product(url: str) -> dict:
    """Fetches a product page and extracts structured data."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.content, "html.parser")
        
        # Title
        title_el = soup.find("h1", class_="product_title") or soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else url.split("/")[-2]

        # SKU
        sku_el = soup.find("span", class_="sku")
        sku = sku_el.get_text(strip=True) if sku_el else ""

        # Description
        desc_el = soup.find("div", class_="woocommerce-product-details__short-description")
        desc = desc_el.get_text(strip=True) if desc_el else ""

        # Specs Table / Tab
        specs = {}
        for row in soup.select("table.shop_attributes tr, .woocommerce-Tabs-panel--additional_information tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                specs[th.get_text(strip=True)] = td.get_text(strip=True)

        return {
            "title": title,
            "url": url,
            "sku": sku,
            "description": desc,
            "specs": specs
        }
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None


if __name__ == "__main__":
    print("Scraping sample product pages from keplertechllc.com...")
    results = []
    for url in PRODUCT_URLS:
        p = fetch_and_parse_product(url)
        if p:
            print(f"  Scraped: {p['title']}")
            results.append(p)
    print(f"Done. Scraped {len(results)} live products.")
