"""
Requirement-Aware Product Reranker for Kepler Tech Conversational AI.
Reranks retrieved catalog products using structured requirements:
- Category matching
- Print size / drawing size compatibility (A0, A1, A2, 24", 36", 44")
- Scanner / MFP necessity
- Daily print / scan volume
- Color mode (photo, technical CAD, monochrome)
"""

import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger("rag.reranker")


class RequirementReranker:
    """Reranks product candidates according to customer requirements."""

    def rerank(
        self,
        candidates: List[Dict[str, Any]],
        requirements: Dict[str, Any],
        limit: int = 4,
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        if not requirements:
            return candidates[:limit]

        scored_candidates = []
        for prod in candidates:
            score = float(prod.get("similarity_score", 0.5))
            prod_text = (
                f"{prod.get('name', '')} {prod.get('description', '')} "
                f"{prod.get('category', '')} {prod.get('width', '')} "
                f"{prod.get('intended_usage', '')}"
            ).lower()

            # 1. Print size / Drawing size requirement
            req_size = requirements.get("print_size") or requirements.get("max_size") or requirements.get("size")
            if req_size:
                size_str = str(req_size).lower()
                # A0 = 36", A1 = 24", A2 = 17"
                if "a0" in size_str:
                    if "36" in prod_text or "a0" in prod_text or "44" in prod_text:
                        score += 0.35
                    elif "24" in prod_text or "a1" in prod_text:
                        score -= 0.30  # Incompatible with A0
                elif "a1" in size_str:
                    if "24" in prod_text or "a1" in prod_text or "36" in prod_text or "a0" in prod_text:
                        score += 0.30
                elif "photo" in size_str or "4x6" in size_str:
                    if any(t in prod_text for t in ["d1000", "cx-02", "photo", "surelab", "d500"]):
                        score += 0.35

            # 2. Scanner / MFP requirement
            scan_req = requirements.get("scan_required") or requirements.get("needs_scanner") or requirements.get("scanner")
            if scan_req is True or (isinstance(scan_req, str) and scan_req.lower() in ("yes", "true", "required")):
                if any(m in prod_text for m in ["mfp", "scan", "scanner", "all-in-one", "copier", "t5400m", "t3100m"]):
                    score += 0.40
                else:
                    score -= 0.25  # Doesn't have scanner
            elif scan_req is False or (isinstance(scan_req, str) and scan_req.lower() in ("no", "false")):
                if "mfp" not in prod_text:
                    score += 0.10

            # 3. Category match
            req_cat = requirements.get("category")
            if req_cat:
                req_cat_lower = str(req_cat).lower()
                prod_cat_lower = str(prod.get("category", "")).lower()
                if "scanner" in req_cat_lower:
                    if "scanner" in prod_cat_lower or "scanner" in prod_text:
                        score += 0.35
                    else:
                        score -= 0.40
                elif "printer" in req_cat_lower or "technical" in req_cat_lower or "cad" in req_cat_lower:
                    if "printer" in prod_cat_lower or "printer" in prod_text:
                        score += 0.25

            # 4. Daily Volume
            volume = requirements.get("daily_volume") or requirements.get("volume")
            if volume:
                try:
                    vol_num = int(re.sub(r"[^\d]", "", str(volume)))
                    if vol_num >= 50:
                        # High volume production
                        if any(hv in prod_text for hv in ["production", "heavy duty", "high speed", "t5400", "t5100", "ds-900", "ds-870"]):
                            score += 0.25
                    else:
                        # Entry / medium volume
                        if any(lv in prod_text for lv in ["compact", "desktop", "entry", "t3100", "ds-770"]):
                            score += 0.15
                except (ValueError, TypeError):
                    pass

            scored_candidates.append((score, prod))

        # Sort by updated score descending
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_candidates[:limit]]


requirement_reranker = RequirementReranker()
