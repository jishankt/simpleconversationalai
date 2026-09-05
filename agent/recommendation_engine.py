"""Conservative requirement matching and recommendation ranking.

Search results are not automatically recommendations.  A product is only
presented as a strong match when critical customer requirements are verified by
catalog evidence.  Unknown data remains unknown.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class ProductAssessment:
    product: Dict[str, Any]
    score: float
    matched: List[str]
    failed: List[str]
    unknown: List[str]
    confidence: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data


def _norm(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(v) for v in value)
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _blob(product: Dict[str, Any]) -> str:
    fields: List[str] = []
    for key in (
        "name", "sku", "category", "description", "width", "max_width",
        "print_width", "intended_usage", "features", "tags", "scanner",
        "has_scanner", "scan_capable", "ink_technology", "technology",
    ):
        value = product.get(key)
        if value not in (None, "", [], {}):
            fields.append(_norm(value))
    return " ".join(fields)


def _width_requirement_matches(product: Dict[str, Any], requested: Any) -> Optional[bool]:
    """Return True/False/None for verified match / verified failure / unknown."""
    req = _norm(requested)
    width = _norm(
        product.get("width")
        or product.get("max_width")
        or product.get("max_media_width")
        or product.get("print_width")
    )
    if not width:
        return None

    aliases = {
        "a1": ("a1", "24", "610"),
        "24": ("a1", "24", "610"),
        "a0": ("a0", "36", "914"),
        "36": ("a0", "36", "914"),
        "44": ("44", "1118", "b0"),
        "b0": ("44", "1118", "b0"),
    }
    wanted: Tuple[str, ...] = ()
    for key, vals in aliases.items():
        if key in req:
            wanted = vals
            break
    if not wanted:
        return req in width if req else None
    return any(v in width for v in wanted)


def _scan_requirement_matches(product: Dict[str, Any], requested: Any) -> Optional[bool]:
    req = requested
    if isinstance(req, str):
        low = req.strip().lower()
        if low in {"yes", "true", "required", "need", "scanner", "mfp"}:
            req = True
        elif low in {"no", "false", "print only", "not required"}:
            req = False
        else:
            return None
    if not isinstance(req, bool):
        return None

    for key in ("has_scanner", "scanner", "scan_capable", "mfp"):
        value = product.get(key)
        if isinstance(value, bool):
            return value is req
        if isinstance(value, str):
            low = value.strip().lower()
            if low in {"yes", "true", "included", "built-in", "integrated"}:
                return req is True
            if low in {"no", "false", "not included", "print only"}:
                return req is False

    text = _blob(product)
    has_positive = bool(re.search(r"\b(scanner|scanning|scan|mfp|copier|copy)\b", text))
    if has_positive and req is True:
        return True
    # Crucial: lack of scanner words is UNKNOWN, never evidence for print-only.
    return None


def _text_requirement_matches(product: Dict[str, Any], value: Any, synonyms: Optional[Iterable[str]] = None) -> Optional[bool]:
    text = _blob(product)
    wanted = [_norm(value)] if value not in (None, "") else []
    if synonyms:
        wanted.extend(_norm(v) for v in synonyms)
    wanted = [v for v in wanted if v]
    if not wanted:
        return None
    return True if any(v in text for v in wanted) else None


def assess_product(product: Dict[str, Any], category: Optional[str], requirements: Dict[str, Any]) -> ProductAssessment:
    matched: List[str] = []
    failed: List[str] = []
    unknown: List[str] = []
    score = 0.0

    # Category itself is soft evidence because catalog category labels can vary.
    if category:
        cat_tokens = {
            "technical_cad": ("cad", "technical", "plotter", "surecolor t", "large format"),
            "photo_fine_art": ("photo", "fine art", "surecolor p", "gallery"),
            "office_enterprise": ("office", "workforce", "enterprise", "multifunction"),
            "photo_booth": ("photo", "dye", "citizen", "booth"),
            "scanner": ("scanner", "scan"),
            "consumable": ("ink", "cartridge", "media", "consumable"),
        }.get(category, (category.replace("_", " "),))
        if any(t in _blob(product) for t in cat_tokens):
            matched.append("category")
            score += 1.0

    for field, value in requirements.items():
        if value in (None, "", [], {}):
            continue

        result: Optional[bool]
        weight = 1.0
        critical = False

        if field == "print_size":
            result = _width_requirement_matches(product, value)
            weight = 3.0
            critical = category == "technical_cad"
        elif field == "scan_required":
            result = _scan_requirement_matches(product, value)
            weight = 3.0
            critical = bool(value)
        elif field in {"application", "intended_usage", "workflow"}:
            syns: List[str] = []
            low = _norm(value)
            if "architect" in low:
                syns = ["cad", "technical drawing", "blueprint"]
            elif "cad" in low:
                syns = ["technical drawing", "blueprint", "architect"]
            elif "photo" in low:
                syns = ["photography", "fine art", "gallery"]
            result = _text_requirement_matches(product, value, syns)
            weight = 2.0
        elif field in {"scanner_type", "document_type"}:
            result = _text_requirement_matches(product, value)
            weight = 2.0
        elif field in {"daily_volume", "usage_level", "workload"}:
            # Do not guess capacity from marketing language. Match only explicit text.
            result = _text_requirement_matches(product, value)
            weight = 1.0
        else:
            result = _text_requirement_matches(product, value)
            weight = 1.0

        if result is True:
            matched.append(field)
            score += weight
        elif result is False:
            failed.append(field)
            score -= weight * 2
        else:
            unknown.append(field)
            if critical:
                score -= 0.5

    if failed:
        confidence = "LOW"
    else:
        critical_unknowns = [u for u in unknown if u in {"print_size", "scan_required"}]
        if not critical_unknowns and len(matched) >= 2:
            confidence = "HIGH"
        elif matched:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

    return ProductAssessment(
        product=product,
        score=score,
        matched=matched,
        failed=failed,
        unknown=unknown,
        confidence=confidence,
    )


def rank_products(products: List[Dict[str, Any]], category: Optional[str], requirements: Dict[str, Any], limit: int = 4) -> List[ProductAssessment]:
    assessments = [assess_product(p, category, requirements) for p in products]
    # Verified failures go last. Stable sort preserves retriever relevance for ties.
    assessments.sort(key=lambda a: (bool(a.failed), -a.score))
    return assessments[:limit]


def recommendation_intro(assessments: List[ProductAssessment], category: Optional[str]) -> str:
    if not assessments:
        return "I couldn't find a verified catalog match for those requirements."

    best = assessments[0]
    cat = (category or "product").replace("_", " ")
    if best.confidence == "HIGH" and not best.failed:
        return f"Based on the requirements you've given me, these are the strongest verified {cat} matches in our catalog."
    if best.confidence == "MEDIUM" and not best.failed:
        return f"I found some {cat} candidates that match part of your requirements, but some product details are not verified in the catalog, so I won't claim a perfect match."
    return f"I found catalog candidates for {cat}, but I don't have enough verified evidence to call one a reliable match yet."
