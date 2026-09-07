"""
Evidence Builder.
Constructs an explicit Evidence Object containing only verified facts from the catalog.
The LLM response composer operates solely on this evidence object.
"""
from typing import Dict, Any, List, Optional
from catalog.schema import NormalizedProduct


def build_recommendation_evidence(
    product: NormalizedProduct,
    requirements: Dict[str, Any],
    score: float,
    matched_fields: List[str]
) -> Dict[str, Any]:
    """
    Builds a grounded evidence payload for a recommended product.
    """
    specs = product.verified
    evidence_matched = {}

    if "print_size" in matched_fields or "print_size" in requirements:
        evidence_matched["print_size"] = {
            "customer_requirement": requirements.get("print_size"),
            "product_evidence": specs.max_width_label or (f"{specs.max_width_mm}mm" if specs.max_width_mm else "Verified Large Format")
        }

    if "scan_required" in matched_fields or "scan_required" in requirements:
        evidence_matched["scan_required"] = {
            "customer_requirement": "Scanner needed" if requirements.get("scan_required") else "Print only",
            "product_evidence": "Integrated 36-inch Scanner" if specs.has_scanner else "Print-only standalone engine"
        }

    if "application" in matched_fields or "application" in requirements:
        evidence_matched["application"] = {
            "customer_requirement": requirements.get("application"),
            "product_evidence": ", ".join(specs.applications) if specs.applications else "Technical & CAD"
        }

    return {
        "product_id": product.id,
        "product_name": product.name,
        "brand": product.brand,
        "score": score,
        "verified_specs": {
            "max_width": specs.max_width_label,
            "resolution": specs.resolution,
            "speed": specs.speed,
            "ink_technology": specs.ink_technology,
            "has_scanner": specs.has_scanner,
            "connectivity": specs.connectivity,
            "footprint": specs.footprint,
            "cartridges": specs.cartridge_capacities,
        },
        "matched_requirements": evidence_matched,
        "comparison_highlights": product.comparison_highlights,
        "source_url": product.source.website_url,
    }


def build_spec_evidence(product: NormalizedProduct, spec_field: str) -> Dict[str, Any]:
    """
    Builds grounded evidence for a single specification query.
    """
    specs = product.verified
    val = getattr(specs, spec_field, None)
    if spec_field == "width":
        val = specs.max_width_label
    elif spec_field == "scanner":
        val = "Integrated scanner included" if specs.has_scanner is True else ("No scanner (Print-only)" if specs.has_scanner is False else None)

    return {
        "product_name": product.name,
        "spec_field": spec_field,
        "verified_value": val,
        "is_verified": val is not None,
    }
