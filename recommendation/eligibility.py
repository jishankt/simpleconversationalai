"""
Hard Eligibility Engine for Kepler Tech Catalog.
Enforces binary eligibility filtering:
  - Critical mismatches act as strict gates (FAILED -> excluded).
  - Unknown specifications are explicitly marked UNKNOWN (never assumed True or False).
  - True matches are marked MATCHED.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from catalog.schema import NormalizedProduct


@dataclass
class AssessmentResult:
    product: NormalizedProduct
    is_eligible: bool
    matched: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    unknown: List[str] = field(default_factory=list)
    rejection_reason: Optional[str] = None


class EligibilityEngine:
    def assess_product(self, product: NormalizedProduct, requirements: Dict[str, Any]) -> AssessmentResult:
        """
        Assesses whether a product satisfies all critical customer requirements.
        """
        matched = []
        failed = []
        unknown = []
        is_eligible = True
        rejection_reason = None

        specs = product.verified

        # ── 0. Hardware Type Gate ───────────────────────────────────────────
        if product.category in ("media_paper", "software", "consumable"):
            return AssessmentResult(
                product=product,
                is_eligible=False,
                failed=["hardware_type"],
                rejection_reason=f"Product is {product.category}, not a printing/scanning hardware device."
            )

        # ── 1. Print Size Gate ───────────────────────────────────────────────
        req_size = requirements.get("print_size")
        if req_size:
            import re
            m_metric = re.search(r"\b(\d+(?:\.\d+)?)\s*(cm|m|meter|metre|metter|mm)\b", str(req_size).lower())
            if m_metric:
                val = float(m_metric.group(1))
                unit = m_metric.group(2)
                mm = val * 1000 if unit in ("m", "meter", "metre", "metter") else (val * 10 if unit == "cm" else val)
                if mm >= 841:
                    req_size = "A0"
                elif mm >= 594:
                    req_size = "A1"
                elif mm >= 420:
                    req_size = "A2"
                elif mm >= 297:
                    req_size = "A3+"
                elif mm >= 210:
                    req_size = "A4"

            if req_size in ("A0", "36-inch"):
                if specs.max_width_mm is not None:
                    if specs.max_width_mm >= 914:
                        matched.append("print_size")
                    else:
                        failed.append("print_size")
                        is_eligible = False
                        rejection_reason = f"Maximum print width ({specs.max_width_label or specs.max_width_mm}) is smaller than required A0 (36-inch)."
                else:
                    failed.append("print_size")
                    is_eligible = False
                    rejection_reason = "Product does not support A0 (36-inch) wide-format printing."
            elif req_size in ("A1", "24-inch"):
                if specs.max_width_mm is not None:
                    if specs.max_width_mm >= 610:
                        matched.append("print_size")
                    else:
                        failed.append("print_size")
                        is_eligible = False
                        rejection_reason = f"Maximum print width ({specs.max_width_label or specs.max_width_mm}) is smaller than required A1 (24-inch)."
                else:
                    failed.append("print_size")
                    is_eligible = False
                    rejection_reason = "Product does not support A1 (24-inch) wide-format printing."
            elif req_size in ("A2+", "A2", "17-inch"):
                if specs.max_width_mm is not None:
                    if specs.max_width_mm >= 432:
                        matched.append("print_size")
                    else:
                        failed.append("print_size")
                        is_eligible = False
                        rejection_reason = f"Maximum print width ({specs.max_width_label or specs.max_width_mm}) is smaller than required A2 (17-inch)."
                else:
                    matched.append("print_size")
            elif req_size in ("A3+", "A3", "13-inch"):
                if specs.max_width_mm is not None:
                    if specs.max_width_mm >= 329:
                        matched.append("print_size")
                    else:
                        failed.append("print_size")
                        is_eligible = False
                        rejection_reason = f"Maximum print width ({specs.max_width_label or specs.max_width_mm}) is smaller than required A3 (13-inch)."
                else:
                    matched.append("print_size")
            elif req_size in ("A4", "A4 Desktop", "a4"):
                if specs.max_width_mm is not None:
                    if specs.max_width_mm >= 210:
                        matched.append("print_size")
                    else:
                        failed.append("print_size")
                        is_eligible = False
                        rejection_reason = f"Maximum print width ({specs.max_width_label or specs.max_width_mm}) is smaller than required A4."
                elif specs.max_width_label and "a4" in specs.max_width_label.lower():
                    matched.append("print_size")
                else:
                    matched.append("print_size")
            elif any(s in str(req_size).lower() for s in ["8x10", "8x12", "8x10 inches", "8x12 inches", "8 inch", "8-inch"]):
                if specs.max_width_mm is not None:
                    if specs.max_width_mm >= 203:
                        matched.append("print_size")
                    else:
                        failed.append("print_size")
                        is_eligible = False
                        rejection_reason = f"Product maximum width ({specs.max_width_label or specs.max_width_mm}) cannot print 8x12-inch photos."
                elif specs.max_width_label and ("8x12" in specs.max_width_label or "8x10" in specs.max_width_label):
                    matched.append("print_size")
                else:
                    failed.append("print_size")
                    is_eligible = False
            elif any(s in str(req_size).lower() for s in ["4x6", "5x7", "6x8", "4x6 inches", "6x8 inches"]):
                if "photo" in product.category or "dye_sub" in product.category or (specs.max_width_mm and specs.max_width_mm >= 152):
                    matched.append("print_size")
            elif any(s in str(req_size).lower() for s in ["compact desktop", "compact", "small", "desktop"]):
                # Compact desktop matches desktop models across photo, booth, CAD
                if specs.max_width_mm is None or specs.max_width_mm <= 610:
                    matched.append("print_size")



        # ── 2. Scanner Gate (Strict logic) ───────────────────────────────────
        req_scan = requirements.get("scan_required")
        if req_scan is not None:
            if req_scan is True:
                if specs.has_scanner is True:
                    matched.append("scan_required")
                else:
                    failed.append("scan_required")
                    is_eligible = False
                    rejection_reason = "Product does not have an integrated scanner (customer requires scanning)."
            elif req_scan is False:
                # Customer explicitly does NOT want a scanner (print-only requested)
                if specs.has_scanner is False or specs.has_scanner is None:
                    matched.append("scan_required")
                else:
                    failed.append("scan_required")
                    is_eligible = False
                    rejection_reason = "Product includes an integrated scanner (customer specified print only / no scanner)."

        # ── 3. Application Match ─────────────────────────────────────────────
        req_app = requirements.get("application")
        if req_app:
            if any(req_app.lower() in app.lower() for app in specs.applications):
                matched.append("application")

        # ── 4. Brand Gate ────────────────────────────────────────────────────
        req_brand = requirements.get("brand")
        if req_brand:
            p_brand = (product.brand or "").lower()
            p_name = (product.name or "").lower()
            if req_brand.lower() in p_brand or req_brand.lower() in p_name:
                matched.append("brand")
            else:
                failed.append("brand")
                is_eligible = False
                rejection_reason = f"Product brand ({product.brand}) does not match requested brand ({req_brand})."


        return AssessmentResult(
            product=product,
            is_eligible=is_eligible,
            matched=matched,
            failed=failed,
            unknown=unknown,
            rejection_reason=rejection_reason
        )

    def filter_candidates(self, products: List[NormalizedProduct], requirements: Dict[str, Any]) -> List[AssessmentResult]:
        results = []
        for p in products:
            res = self.assess_product(p, requirements)
            if res.is_eligible:
                results.append(res)
        return results


eligibility_engine = EligibilityEngine()
