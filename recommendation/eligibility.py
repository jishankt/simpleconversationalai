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

        # ── 1. Print Size Gate ───────────────────────────────────────────────
        req_size = requirements.get("print_size")
        if req_size:
            if req_size in ("A0", "36-inch"):
                if specs.max_width_mm is not None:
                    if specs.max_width_mm >= 914:
                        matched.append("print_size")
                    else:
                        failed.append("print_size")
                        is_eligible = False
                        rejection_reason = f"Maximum print width ({specs.max_width_label or specs.max_width_mm}) is smaller than required A0 (36-inch)."
                else:
                    unknown.append("print_size")
            elif req_size in ("A1", "24-inch"):
                if specs.max_width_mm is not None:
                    if specs.max_width_mm >= 610:
                        matched.append("print_size")
                    else:
                        failed.append("print_size")
                        is_eligible = False
                        rejection_reason = f"Maximum print width ({specs.max_width_label or specs.max_width_mm}) is smaller than required A1 (24-inch)."
                else:
                    unknown.append("print_size")

        # ── 2. Scanner Gate (Strict 3-valued logic) ───────────────────────────
        req_scan = requirements.get("scan_required")
        if req_scan is not None:
            if req_scan is True:
                if specs.has_scanner is True:
                    matched.append("scan_required")
                elif specs.has_scanner is False:
                    failed.append("scan_required")
                    is_eligible = False
                    rejection_reason = "Product does not have an integrated scanner (customer requires scanning)."
                else:
                    unknown.append("scan_required")
            elif req_scan is False:
                # Customer does NOT need scanner
                if specs.has_scanner is False or specs.has_scanner is None or specs.has_scanner is True:
                    # Print-only printers or multifunction printers are both technically capable of printing,
                    # but standalone print-only units match perfectly.
                    matched.append("scan_required")

        # ── 3. Application Match ─────────────────────────────────────────────
        req_app = requirements.get("application")
        if req_app:
            if any(req_app.lower() in app.lower() for app in specs.applications):
                matched.append("application")

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
