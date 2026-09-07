"""
Catalog Repository & Normalizer.
Loads and unifies raw catalog data into NormalizedProduct models with strict 3-valued logic.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from catalog.schema import NormalizedProduct, VerifiedSpecs, ProductSource

logger = logging.getLogger("catalog:repository")


class CatalogRepository:
    def __init__(self, corpus_path: Optional[str] = None, products_path: Optional[str] = None):
        base_dir = Path(__file__).parent.parent / "data"
        self.corpus_path = Path(corpus_path) if corpus_path else base_dir / "kepler_product_corpus.json"
        self.products_path = Path(products_path) if products_path else base_dir / "products.json"
        
        self.products_by_id: Dict[str, NormalizedProduct] = {}
        self.products_by_category: Dict[str, List[NormalizedProduct]] = {}
        self._load_and_normalize()

    def _load_and_normalize(self):
        """Loads and normalizes all products into canonical models."""
        # 1. Load kepler_product_corpus.json if available
        if self.corpus_path.exists():
            try:
                with open(self.corpus_path, "r", encoding="utf-8") as f:
                    corpus_data = json.load(f)
                    for item in corpus_data:
                        norm = self._normalize_corpus_item(item)
                        if norm:
                            self.products_by_id[norm.id] = norm
            except Exception as e:
                logger.error(f"Error loading corpus {self.corpus_path}: {e}")

        # 2. Enrich and link with high-res verified images and URLs from products.json
        if self.products_path.exists():
            try:
                with open(self.products_path, "r", encoding="utf-8") as f:
                    products_data = json.load(f)
                    for item in products_data:
                        sku = str(item.get("sku") or item.get("_id") or "").upper()
                        name_l = item.get("name", "").lower()
                        img = item.get("image_url") or item.get("image")
                        web_url = item.get("website_url") or item.get("web_url")
                        consumables = item.get("consumables", [])

                        # Match against normalized products
                        for p in self.products_by_id.values():
                            p_match = False
                            if p.id in ("epson-am-c4000",) and ("am-c4000" in name_l or "am-c400" in name_l):
                                p_match = True
                            elif p.id in ("epson-am-c550",) and ("am-c550" in name_l):
                                p_match = True
                            elif p.id in ("epson-t3100",) and ("t3100" in name_l or "t3100" in sku.lower()):
                                p_match = True
                            elif p.id in ("epson-t5100",) and ("t5100" in name_l or "t5100" in sku.lower()):
                                p_match = True
                            elif p.id in ("epson-t5400m",) and ("t5400" in name_l or "t5100m" in name_l or "t5400m" in sku.lower()):
                                p_match = True
                            elif p.id in ("epson-t5700d",) and ("t5700" in name_l or "t3700" in name_l):
                                p_match = True
                            elif p.id in ("epson-p700",) and ("p700" in name_l and "7000" not in name_l and "7500" not in name_l):
                                p_match = True
                            elif p.id in ("epson-p900",) and ("p900" in name_l and "9000" not in name_l and "9500" not in name_l):
                                p_match = True
                            elif p.id in ("epson-p7500-p9500", "epson-p9500") and ("p9500" in name_l or "p7500" in name_l):
                                p_match = True
                            elif p.id in ("citizen-cx-02",) and ("cx-02" in name_l or "cx02" in name_l):
                                p_match = True
                            elif p.id in ("citizen-cy-02",) and ("cy-02" in name_l or "cy02" in name_l):
                                p_match = True
                            elif p.id in ("epson-sc-f100", "epson-f100") and ("f100" in name_l):
                                p_match = True
                            elif p.id in ("epson-sc-f500", "epson-f500") and ("f500" in name_l):
                                p_match = True

                            if p_match:
                                if sku and not p.sku and not sku.startswith("EPSON-"):
                                    p.sku = sku
                                if img and not p.image_url:
                                    p.image_url = img
                                if web_url and not p.source.website_url:
                                    p.source.website_url = web_url
                                if consumables and not p.consumables:
                                    p.consumables = consumables
            except Exception as e:
                logger.error(f"Error enriching products {self.products_path}: {e}")

        # Explicit verified image fallbacks for all primary catalog items
        VERIFIED_HARDWARE_MEDIA = {
            "epson-am-c4000": {
                "sku": "C11CJ43402BY",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2023/06/WorkForce-Enterprise%E2%80%8B-AM-C4000%E2%80%8B.webp",
                "website_url": "https://www.keplertechllc.com/product/epson-workforce-enterprise-am-c4000-printer/",
                "consumables": ["C13T08H100", "C13T08H200", "C13T08H300", "C13T08H400", "C12C937181"]
            },
            "epson-am-c550": {
                "sku": "C11CJ92401",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2025/01/Epson-WorkForce-AM-C550-A4-Color-Multifunction-Printer.webp",
                "website_url": "https://www.keplertechllc.com/product/epson-wf-am-c550-a4-multifunction-printer/",
                "consumables": ["C13T08Q140", "C13T08Q240", "C13T08Q340", "C13T08Q440", "C12C937201"]
            },
            "epson-t3100": {
                "sku": "C11CF11301A0",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2023/08/Epson-SureColor-SC-T3100-%E2%80%93-Wireless-Printer-With-Stand.webp",
                "website_url": "https://www.keplertechllc.com/product/epson-surecolor-sc-t3100-wireless-printer-with-stand/",
                "consumables": ["C13T40D140", "C13T40D240", "C13T40D340", "C13T40D440", "C13S210055"]
            },
            "epson-t5100": {
                "sku": "C11CF12301A0",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2023/08/Epson-SureColor-SC-T5100-Printer.webp",
                "website_url": "https://www.keplertechllc.com/product/epson-surecolor-sc-t5100-large-format-printer/",
                "consumables": ["C13T40D140", "C13T40D240", "C13T40D340", "C13T40D440", "C13S210055"]
            },
            "epson-t5400m": {
                "sku": "C11CH65301A0",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2026/01/SC-T5100M.webp",
                "website_url": "https://www.keplertechllc.com/product/epson-surecolor-sc-t5100m-plotter-printer/",
                "consumables": ["C13T41F540", "C13T41F240", "C13T41F340", "C13T41F440", "C13S210055"]
            },
            "epson-t5700d": {
                "sku": "C11CH81301A0",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2024/01/SC-T5700DM-Printer.webp",
                "website_url": "https://www.keplertechllc.com/product/epson-sc-t5700d-technical-printer/",
                "consumables": ["C13T50U100", "C13T50U200", "C13T50U300", "C13T50U400", "C13S210115"]
            },
            "epson-p700": {
                "sku": "C11CH38401",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2023/03/Epson-P7000-Printer-1.webp",
                "website_url": "https://www.keplertechllc.com/product/epson-surecolor-p700-13-photo-printer/",
                "consumables": ["C13T46S100", "C13T46S200", "C13T46S300", "C13T46S400", "C12C935711"]
            },
            "epson-p900": {
                "sku": "C11CH37401",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2023/04/Epson-P900-Printer-2.webp",
                "website_url": "https://www.keplertechllc.com/product/epson-surecolor-sc-p900-photo-printer/",
                "consumables": ["C13T47A100", "C13T47A200", "C13T47A300", "C13T47A400", "C12C935711"]
            },
            "epson-p7500-p9500": {
                "sku": "C11CH13301A0",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2023/03/Epson-P7500-Printer.webp",
                "website_url": "https://www.keplertechllc.com/product/epson-surecolor-sc-p7500-large-format-printer/",
                "consumables": ["C13T44J140", "C13T44J240", "C13T44J340", "C13T44J440", "C13T699700"]
            },
            "citizen-cx-02": {
                "sku": "CX02-PHOTO",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2023/03/Citizen-CX-02-Photo-Printer-Dubai.webp",
                "website_url": "https://www.keplertechllc.com/product/citizen-cx-02-photo-printer/",
                "consumables": ["CX2.4x6", "CX2.6x8"]
            },
            "citizen-cy-02": {
                "sku": "CY02-PHOTO",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2023/04/Citizen-CY-02-Photo-Printer.webp",
                "website_url": "https://www.keplertechllc.com/product/citizen-cy-02-photo-printer/",
                "consumables": ["CY02Bag"]
            },
            "epson-sc-f100": {
                "sku": "C11CJ80301",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2023/07/Epson-F100.webp",
                "website_url": "https://www.keplertechllc.com/product/epson-surecolor-sc-f100-printer/",
                "consumables": ["C13T49N100", "C13T49N200", "C13T49N300", "C13T49N400", "C13S210125"]
            },
            "epson-sc-f500": {
                "sku": "C11CJ17301A0",
                "image_url": "https://www.keplertechllc.com/wp-content/uploads/2026/04/epson-SC-F500.jpg.jpeg",
                "website_url": "https://www.keplertechllc.com/product/epson-surecolor-sc-f500-dye-sublimation-printer/",
                "consumables": ["C13T49N100", "C13T49N200", "C13T49N300", "C13T49N400", "C13S210055"]
            }
        }

        for pid, media_info in VERIFIED_HARDWARE_MEDIA.items():
            if pid in self.products_by_id:
                prod = self.products_by_id[pid]
                if media_info.get("sku"):
                    prod.sku = media_info["sku"]
                if media_info.get("image_url"):
                    prod.image_url = media_info["image_url"]
                if media_info.get("website_url"):
                    prod.source.website_url = media_info["website_url"]
                if media_info.get("consumables"):
                    prod.consumables = media_info["consumables"]


        # 3. Index standalone scanners from products.json if not already in corpus
        if self.products_path.exists():
            try:
                with open(self.products_path, "r", encoding="utf-8") as f:
                    products_data = json.load(f)
                    for item in products_data:
                        cat_item = item.get("category", "")
                        name = item.get("name", "")
                        sku = str(item.get("sku") or item.get("_id") or "")
                        if cat_item == "Scanner" or ("scanner" in name.lower() and "ink" not in cat_item.lower() and "ribbon" not in name.lower()):
                            p_id = f"epson-{sku.lower()}" if sku else f"scanner-{len(self.products_by_id)}"
                            if p_id not in self.products_by_id and not any(p.name == name for p in self.products_by_id.values()):
                                specs = VerifiedSpecs(
                                    has_scanner=True,
                                    applications=["Document Scanning", "Archiving", "Business Invoices"],
                                    media_handling="ADF / Flatbed Document Scanner",
                                )
                                norm_scanner = NormalizedProduct(
                                    id=p_id,
                                    brand="Epson",
                                    model=name.split()[0] if name else "Epson Scanner",
                                    name=name,
                                    category="scanner",
                                    verified=specs,
                                    source=ProductSource(website_url=item.get("website_url") or item.get("web_url")),
                                    image_url=item.get("image_url") or item.get("image"),
                                    description=item.get("description") or "Official high-precision document scanner from Kepler Tech LLC.",
                                    consumables=item.get("consumables", []),
                                )
                                self.products_by_id[norm_scanner.id] = norm_scanner
            except Exception as e:
                logger.error(f"Error indexing scanners from {self.products_path}: {e}")

        # Index by category
        self.products_by_category = {}
        for p in self.products_by_id.values():
            self.products_by_category.setdefault(p.category, []).append(p)
        logger.info(f"Loaded {len(self.products_by_id)} normalized products across {len(self.products_by_category)} categories.")


    def _normalize_corpus_item(self, item: Dict) -> Optional[NormalizedProduct]:
        p_id = item.get("id")
        if not p_id:
            return None

        # Determine category
        cat_raw = item.get("category", "").lower()
        if "booth" in cat_raw or "dyesub" in cat_raw or "dye_sub" in cat_raw or "citizen" in p_id or "f100" in p_id or "f500" in p_id:
            category = "photo_booth"
        elif "cad" in cat_raw or "plotter" in cat_raw:
            category = "technical_cad"
        elif "photo" in cat_raw or "fine_art" in cat_raw or "art" in cat_raw:
            category = "photo_fine_art"
        elif "office" in cat_raw or "enterprise" in cat_raw:
            category = "office_enterprise"
        elif "scanner" in cat_raw:
            category = "scanner"
        elif "paper" in cat_raw or "media" in cat_raw:
            category = "media_paper"
        elif "software" in cat_raw or "server" in cat_raw:
            category = "software"
        elif "ink" in cat_raw or "cartridge" in cat_raw or "consumable" in cat_raw:
            category = "consumable"
        else:
            category = "technical_cad"


        # Width calculation
        width_str = item.get("width", "")
        max_width_mm = None
        max_width_label = width_str if width_str else None
        if "36" in width_str or "a0" in width_str.lower():
            max_width_mm = 914
            max_width_label = "36-inch (A0)"
        elif "24" in width_str or "a1" in width_str.lower():
            max_width_mm = 610
            max_width_label = "24-inch (A1)"
        elif "17" in width_str or "a2" in width_str.lower():
            max_width_mm = 432
            max_width_label = "17-inch (A2+)"
        elif "13" in width_str or "a3" in width_str.lower():
            max_width_mm = 329
            max_width_label = "13-inch (A3+)"
        elif "44" in width_str:
            max_width_mm = 1118
            max_width_label = "44-inch Production"

        # Scanner: strict 3-valued logic (True / False / None)
        name_desc = (item.get("name", "") + " " + item.get("media_handling", "") + " " + item.get("comparison_highlights", "")).lower()
        if "integrated scanner" in name_desc or "scanner included" in name_desc or "multifunction" in name_desc or "mfp" in name_desc:
            has_scanner = True
        elif "print only" in name_desc or "standalone plotter" in name_desc or "desktop plotter" in name_desc or "dual-roll production plotter" in name_desc or p_id in ("epson-t3100", "epson-t5100", "epson-t5700d", "epson-p700", "epson-p900", "citizen-cx-02"):
            has_scanner = False
        else:
            has_scanner = None

        # Connectivity
        conn_raw = item.get("connectivity", "")
        connectivity = []
        if "wi-fi" in conn_raw.lower() or "wifi" in conn_raw.lower():
            connectivity.append("Wi-Fi")
        if "ethernet" in conn_raw.lower() or "gigabit" in conn_raw.lower() or "network" in conn_raw.lower():
            connectivity.append("Ethernet")
        if "usb" in conn_raw.lower():
            connectivity.append("USB")

        # Applications
        apps = []
        intended = item.get("intended_usage", "").lower()
        if "cad" in intended or "architecture" in intended or "drawings" in intended or "blueprint" in intended:
            apps.extend(["CAD", "Architecture", "Engineering", "Blueprints"])
        if "gis" in intended or "map" in intended:
            apps.append("GIS & Maps")
        if "photo" in intended or "gallery" in intended or "fine art" in intended:
            apps.extend(["Photography", "Fine Art", "Gallery Proofing"])
        if "event" in intended or "booth" in intended:
            apps.extend(["Photo Booth", "Event Printing"])

        specs = VerifiedSpecs(
            max_width_mm=max_width_mm,
            max_width_label=max_width_label,
            has_scanner=has_scanner,
            resolution=item.get("max_resolution"),
            speed=item.get("speed"),
            ink_technology=item.get("ink_technology"),
            connectivity=connectivity,
            applications=apps,
            cartridge_capacities=item.get("cartridge_capacities"),
            media_handling=item.get("media_handling"),
            footprint=item.get("footprint"),
        )

        return NormalizedProduct(
            id=p_id,
            brand=item.get("brand", "Epson"),
            model=item.get("name", "").split()[0] if item.get("name") else p_id,
            name=item.get("name", p_id),
            category=category,
            verified=specs,
            source=ProductSource(website_url=item.get("source_url")),
            comparison_highlights=item.get("comparison_highlights"),
            description=item.get("intended_usage"),
        )

    def get_by_id(self, product_id: str) -> Optional[NormalizedProduct]:
        return self.products_by_id.get(product_id)

    def get_all(self) -> List[NormalizedProduct]:
        return list(self.products_by_id.values())

    def get_by_category(self, category: str) -> List[NormalizedProduct]:
        return self.products_by_category.get(category, [])


# Singleton catalog repository
catalog_repository = CatalogRepository()
