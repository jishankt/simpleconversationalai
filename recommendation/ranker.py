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
    def rank_candidates(self, assessments: List[AssessmentResult], requirements: Dict[str, Any], raw_message: str = "") -> List[Tuple[NormalizedProduct, float, Dict[str, Any]]]:
        """
        Ranks eligible candidate products using dynamic scoring based on customer stated priorities:
        use case, volume, portability, speed, and preferred features.
        """
        msg_l = (raw_message or "").lower()
        req_keys_str = " ".join(str(k) + ":" + str(v) for k, v in requirements.items()).lower()
        combined_text = f"{msg_l} {req_keys_str}"

        # ── Detect Customer Priorities Dynamically ───────────────────────────
        is_portability_priority = any(k in combined_text for k in ["portable", "portability", "compact", "lightweight", "light", "travel", "carry", "mobile", "small footprint", "transport", "flight case", "limited space"])
        is_speed_priority = any(k in combined_text for k in ["speed", "fast", "faster", "fastest", "quick", "seconds", "throughput", "rapid"])
        is_volume_priority = any(k in combined_text for k in ["high volume", "volume", "700", "500", "600", "800", "busy", "capacity", "unattended", "continuous", "heavy", "production"])
        is_quality_priority = any(k in combined_text for k in ["quality", "image quality", "resolution", "fine art", "600 dpi", "color", "skin tone", "archival"])

        # Determine dynamic weights based on stated priorities
        weights = {
            "use_case": 25.0,
            "volume": 20.0,
            "portability": 15.0,
            "speed": 15.0,
            "preferred_features": 15.0,
            "size_fit": 10.0,
        }
        if is_portability_priority:
            weights["portability"] = 35.0
            weights["volume"] = 10.0
        if is_speed_priority:
            weights["speed"] = 35.0
            weights["volume"] = 10.0
        if is_volume_priority:
            weights["volume"] = 35.0
            weights["portability"] = 10.0
        if is_quality_priority:
            weights["use_case"] = 35.0

        ranked = []
        for item in assessments:
            p = item.product
            specs = p.verified
            p_name_l = p.name.lower()
            p_desc_l = ((p.description or "") + " " + (p.comparison_highlights or "") + " " + " ".join(specs.applications or [])).lower()

            score_factors = {}
            score = 0.0

            # 1. Use Case Alignment
            req_app = str(requirements.get("application") or "")
            req_cat = str(requirements.get("category") or "")
            use_case_pts = 0.0
            if "photo booth" in combined_text or "booth" in combined_text or "event" in combined_text:
                if p.category == "photo_booth":
                    use_case_pts = 100.0
                elif "dye-sub" in p_desc_l:
                    use_case_pts = 80.0
                else:
                    use_case_pts = 30.0
            elif "fine art" in combined_text or "gallery" in combined_text or "studio" in combined_text:
                if p.category == "photo_fine_art":
                    use_case_pts = 100.0
                elif p.category == "photo_booth" and "cx-02w" in p.id:
                    use_case_pts = 85.0
                else:
                    use_case_pts = 50.0
            elif "cad" in combined_text or "technical" in combined_text:
                use_case_pts = 100.0 if p.category == "technical_cad" else 20.0
            else:
                use_case_pts = 80.0
            score_factors["use_case"] = round(use_case_pts * (weights["use_case"] / 100.0), 1)
            score += score_factors["use_case"]

            # 2. Volume Alignment
            vol_val = requirements.get("event_volume") or requirements.get("daily_volume")
            vol_pts = 50.0
            if isinstance(vol_val, (int, float)) and vol_val >= 500:
                if "cy-02" in p.id.lower() or "cy02" in p.id.lower():
                    vol_pts = 100.0  # 700 prints/roll
                elif "cx-02" in p.id.lower() or "cx02" in p.id.lower():
                    vol_pts = 75.0   # 400 prints/roll
                elif "cz-01" in p.id.lower():
                    vol_pts = 40.0   # 150 prints/roll
                elif "production" in p_name_l or "5700" in p.id or "p9500" in p.id or "am-c4000" in p.id:
                    vol_pts = 100.0
            elif is_volume_priority:
                if "cy-02" in p.id or "production" in p_name_l or "5700" in p.id:
                    vol_pts = 100.0
                elif "cx-02" in p.id or "am-c550" in p.id:
                    vol_pts = 70.0
                else:
                    vol_pts = 40.0
            else:
                vol_pts = 70.0
            score_factors["volume"] = round(vol_pts * (weights["volume"] / 100.0), 1)
            score += score_factors["volume"]

            # 3. Portability Alignment
            port_pts = 50.0
            if "cz-01" in p.id:
                port_pts = 100.0  # 5.8 kg ultra-compact
            elif "cx-02" in p.id and "cx-02w" not in p.id:
                port_pts = 80.0   # 12 kg portable
            elif "cx-02w" in p.id:
                port_pts = 65.0   # 14 kg
            elif "cy-02" in p.id:
                port_pts = 45.0   # 18 kg high-capacity
            elif "p700" in p.id or "ds-530" in p.id or "am-c550" in p.id or "t3100" in p.id:
                port_pts = 70.0   # compact desktop
            else:
                port_pts = 30.0   # large floor-standing
            score_factors["portability"] = round(port_pts * (weights["portability"] / 100.0), 1)
            score += score_factors["portability"]

            # 4. Speed Alignment
            speed_pts = 50.0
            if "cx-02" in p.id and "cx-02w" not in p.id:
                speed_pts = 95.0  # 9.8s high-speed 4x6
            elif "cy-02" in p.id:
                speed_pts = 85.0  # 12.4s high-speed 4x6
            elif "cz-01" in p.id:
                speed_pts = 70.0  # 18.8s 4x6
            elif "cx-02w" in p.id:
                speed_pts = 70.0  # 33.4s 8x10
            elif "t5700d" in p.id or "am-c4000" in p.id:
                speed_pts = 95.0
            else:
                speed_pts = 60.0
            score_factors["speed"] = round(speed_pts * (weights["speed"] / 100.0), 1)
            score += score_factors["speed"]

            # 5. Preferred Features Alignment
            feat_pts = 50.0
            if any(k in combined_text for k in ["ribbon rewind", "rewind"]):
                feat_pts = 100.0 if ("cx-02" in p.id or "cx-02w" in p.id) else 20.0
            elif any(k in combined_text for k in ["gloss", "matte", "finishing", "luster"]):
                feat_pts = 100.0 if p.category in ("photo_booth", "photo_fine_art") else 40.0
            elif any(k in combined_text for k in ["grey calibration", "gray calibration"]):
                feat_pts = 100.0 if "cx-02w" in p.id else 30.0
            elif any(k in combined_text for k in ["dual roll", "two rolls"]):
                feat_pts = 100.0 if "t5700d" in p.id else 20.0
            elif any(k in combined_text for k in ["heat-free", "line head"]):
                feat_pts = 100.0 if "am-c" in p.id else 30.0
            else:
                feat_pts = 70.0
            score_factors["preferred_features"] = round(feat_pts * (weights["preferred_features"] / 100.0), 1)
            score += score_factors["preferred_features"]

            # 6. Size Fit (Exact vs Over-width)
            size_pts = 80.0
            if "print_size" in item.matched:
                size_pts = 100.0
            score_factors["size_fit"] = round(size_pts * (weights["size_fit"] / 100.0), 1)
            score += score_factors["size_fit"]

            score_factors["applied_weights"] = dict(weights)
            ranked.append((p, round(score, 1), score_factors))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked


product_ranker = ProductRanker()
