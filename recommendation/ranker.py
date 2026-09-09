"""
Deterministic Product Ranker.
Scores candidate products based on explicit Python rules, never by LLM intuition.
Application match: 30
Print size match: 25
Scanner match: 20
Usage / Volume: 15
Optional features: 10
"""
from typing import List, Dict, Any, Tuple
from recommendation.eligibility import AssessmentResult
from catalog.schema import NormalizedProduct


class ProductRanker:
    def rank_candidates(self, assessments: List[AssessmentResult], requirements: Dict[str, Any]) -> List[Tuple[NormalizedProduct, float, Dict[str, Any]]]:
        """
        Ranks eligible candidate products using deterministic weighted scoring.
        """
        ranked = []
        for item in assessments:
            score = 0.0
            score_breakdown = {}
            p = item.product
            specs = p.verified

            # 1. Application Match (30 pts)
            req_app = requirements.get("application")
            if req_app and "application" in item.matched:
                score += 30.0
                score_breakdown["application"] = 30.0
            elif not req_app:
                # Neutral base credit if no specific application required
                score += 20.0
                score_breakdown["application"] = 20.0

            # 2. Print Size Match (25 pts)
            req_size = requirements.get("print_size")
            if req_size and "print_size" in item.matched:
                # If exact size match vs larger capability
                score += 25.0
                score_breakdown["print_size"] = 25.0

            # 3. Scanner Requirement (20 pts)
            req_scan = requirements.get("scan_required")
            if req_scan is True and specs.has_scanner is True:
                score += 20.0
                score_breakdown["scanner"] = 20.0
            elif req_scan is False and specs.has_scanner is False:
                # Ideal fit for print-only
                score += 20.0
                score_breakdown["scanner"] = 20.0
            elif req_scan is False and specs.has_scanner is True:
                # Over-specified but eligible
                score += 10.0
                score_breakdown["scanner"] = 10.0

            # 4. Daily Volume / Workload (15 pts)
            raw_vol = requirements.get("daily_volume")
            req_vol = raw_vol
            if isinstance(raw_vol, (int, float)):
                req_vol = "high" if raw_vol >= 100 else ("medium" if raw_vol >= 20 else "low")
            elif isinstance(raw_vol, str):
                import re
                num_match = re.search(r"\b(\d+)\b", raw_vol)
                if num_match:
                    n = int(num_match.group(1))
                    req_vol = "high" if n >= 100 else ("medium" if n >= 20 else "low")
                elif raw_vol.lower() in ("high", "medium", "low"):
                    req_vol = raw_vol.lower()

            p_name_l = p.name.lower()
            if req_vol == "high":
                if "am-c4000" in p_name_l or "production" in p_name_l or "5700" in p.id or "p9500" in p.id:
                    score += 15.0
                    score_breakdown["volume"] = 15.0
                elif any(k in p_name_l for k in ["am-c550", "enterprise", "high-speed", "ds-870", "ds-970"]):
                    score += 10.0
                    score_breakdown["volume"] = 10.0
                elif any(k in p_name_l for k in ["ds-70", "ds-80w", "mobile"]):
                    score += 0.0
                    score_breakdown["volume"] = 0.0
                elif "350ml" in (specs.cartridge_capacities or ""):
                    score += 15.0
                    score_breakdown["volume"] = 15.0
                else:
                    score += 5.0
                    score_breakdown["volume"] = 5.0
            elif req_vol in ("low", "medium"):
                if "c550" in p_name_l or "am-c550" in p_name_l or "desktop" in (specs.footprint or "").lower() or "t3100" in p.id or "t5100" in p.id or "ds-530" in p_name_l or "f100" in p.id:
                    score += 15.0
                    score_breakdown["volume"] = 15.0
                elif any(k in p_name_l for k in ["am-c4000", "production", "enterprise"]):
                    # Over-capacity for low/medium workload
                    score += 5.0
                    score_breakdown["volume"] = 5.0
                else:
                    score += 10.0
                    score_breakdown["volume"] = 10.0
            else:
                score += 5.0
                score_breakdown["volume"] = 5.0

            # 5. Optional Features & Connectivity (10 pts)
            if "Wi-Fi" in specs.connectivity:
                score += 5.0
            if "Ethernet" in specs.connectivity:
                score += 5.0

            # 6. Brand Match Bonus (15 pts)
            req_brand = requirements.get("brand")
            if req_brand and (req_brand.lower() in (p.brand or "").lower() or req_brand.lower() in (p.name or "").lower()):
                score += 15.0
                score_breakdown["brand"] = 15.0

            ranked.append((p, score, score_breakdown))


        # Sort descending by score
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked


product_ranker = ProductRanker()
