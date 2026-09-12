"""
Catalogue Resolver for Kepler Tech SalesAI.
Resolves customer text to approved catalogue entries for:
- Exact model detail queries
- Approved model comparisons
Enforces strict 41-catalogue membership.
"""
import re
from typing import Optional, List, Dict, Any, Tuple
from catalog.catalogue_loader import catalogue_loader


def find_mentioned_catalogue_products(text: str) -> List[Dict[str, Any]]:
    """
    Identifies which of the 41 approved catalogue products are mentioned in the text.
    Returns matching catalogue products.
    """
    if not text:
        return []

    text_lower = text.lower()
    all_products = catalogue_loader.get_all()
    matched = []

    # Sort products by model family length descending so 'SC-T3700DE' matches before 'SC-T3700D'
    sorted_prods = sorted(all_products, key=lambda p: len(p["id"]), reverse=True)

    seen_ids = set()
    for p in sorted_prods:
        pid = p["id"]
        fam = p.get("model_family", "").lower()
        disp = p.get("display_name", "").lower()

        # Specific variations of model patterns
        patterns = [
            re.escape(pid),
            re.escape(fam),
            re.escape(fam.replace("sc-", "").replace("wf-", "").replace("em-", "").replace("am-", "")),
        ]

        found = False
        for pat in patterns:
            if len(pat) >= 4 and re.search(rf"\b{pat}\b", text_lower):
                found = True
                break

        if found and pid not in seen_ids:
            seen_ids.add(pid)
            matched.append(p)

    return matched


def build_model_detail_response(product: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """Builds verified description, specs, and card for an exact model inquiry."""
    from catalog.catalogue_filter import catalogue_filter
    card = catalogue_filter._format_card(product, product.get("subcategory"), {})
    
    name = product.get("display_name")
    cat = product.get("catalogue", "").replace("_", " ").title()
    subcat = product.get("subcategory", "").replace("_", " ").title()
    width = product.get("max_width_inches")
    functions = "/".join([f.title() for f in (product.get("functions") or ["Print"])])
    scanner = "Includes integrated scanner" if product.get("scanner_integrated") else "Dedicated print-only"
    
    reply = (
        f"Here are the verified specifications for the **{name}** from our official {cat} catalogue:\n\n"
        f"• **Category:** {cat} ({subcat})\n"
        f"• **Functions:** {functions} ({scanner})\n"
    )
    if width:
        reply += f"• **Maximum Print Width:** {width:.0f} inches\n"
    if product.get("paper_size"):
        reply += f"• **Paper Formats:** {product['paper_size'].upper()}\n"
    if product.get("dual_roll"):
        reply += "• **Dual Roll:** Automatic dual-roll media switching supported\n"
    if product.get("spectro"):
        reply += "• **Spectrophotometer:** Integrated inline colour calibration\n"

    reply += f"\n*(Verified from official catalogue: {product.get('source_catalogue')})*"

    return reply, [card]


def build_approved_comparison_response(products: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """Compares two or more approved catalogue products based on verified specifications."""
    from catalog.catalogue_filter import catalogue_filter
    cards = [catalogue_filter._format_card(p, p.get("subcategory"), {}) for p in products[:3]]
    
    p1 = products[0]
    p2 = products[1]
    
    reply = (
        f"### Catalogue Comparison: **{p1['display_name']}** vs **{p2['display_name']}**\n\n"
        f"| Feature | {p1['display_name']} | {p2['display_name']} |\n"
        f"| :--- | :--- | :--- |\n"
        f"| **Catalogue** | {p1.get('catalogue', '').replace('_', ' ').title()} | {p2.get('catalogue', '').replace('_', ' ').title()} |\n"
        f"| **Functions** | {'/'.join(p1.get('functions', ['Print']))} | {'/'.join(p2.get('functions', ['Print']))} |\n"
        f"| **Scanner** | {'Integrated' if p1.get('scanner_integrated') else 'No'} | {'Integrated' if p2.get('scanner_integrated') else 'No'} |\n"
        f"| **Max Width** | {p1.get('max_width_inches', 'N/A')}″ | {p2.get('max_width_inches', 'N/A')}″ |\n"
        f"| **Dual Roll** | {'Yes' if p1.get('dual_roll') else 'No'} | {'Yes' if p2.get('dual_roll') else 'No'} |\n"
    )
    
    return reply, cards
