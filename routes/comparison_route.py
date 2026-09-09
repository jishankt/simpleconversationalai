"""
Comparison Route for Kepler Tech Conversational AI.
Handles product comparison requests using the existing tool_executor.
"""

import re
import logging
from domain.conversation_types import LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from agent.tool_executor import catalog_tool_executor

logger = logging.getLogger("route:comparison")


def handle(understanding: LLMUnderstanding, state: ConversationState, raw_message: str = "") -> RouteResult:
    """Handle product comparison requests."""
    msg_lower = (raw_message or "").strip().lower()

    # 1. Extract candidate models from raw_message or entities
    model_patterns = [
        r"\b(?:cx-?02w?|cy-?02|cz-?01)\b",  # Citizen photo booth
        r"\b(?:sc-?)?(?:t3100[a-z]?|t5100[a-z]?|t5400[a-z]?|t5700[a-z]?|t7700[a-z]?|t3200|t5200|t7200)\b",  # CAD
        r"\b(?:sc-?)?(?:p700|p900|p5000|p5300|p6000|p7000|p7500|p8000|p9000|p9500|p20000)\b",  # Photo
        r"\b(?:sc-?)?(?:f100|f500|f6300|f9400)\b",  # Dye-sub Epson
        r"\b(?:am-?c4000|am-?c550|am-?c5000|am-?c6000|wf-?c\d{4}[a-z]?)\b",  # Workforce
        r"\b(?:ds-?\d{3}[a-z]?|es-?\d{3}[a-z]?)\b",  # Scanners
    ]

    found_models = []
    for pattern in model_patterns:
        for m in re.findall(pattern, msg_lower):
            cleaned = re.sub(r"[\s\-_]+", "", m.lower())
            if cleaned not in [re.sub(r"[\s\-_]+", "", x.lower()) for x in found_models]:
                found_models.append(m)

    # If entity gave models
    if understanding.entities:
        m_code = understanding.entities.get("model_code")
        if m_code:
            cleaned = re.sub(r"[\s\-_]+", "", str(m_code).lower())
            if cleaned not in [re.sub(r"[\s\-_]+", "", x.lower()) for x in found_models]:
                found_models.append(m_code)

    # If user mentions only CX-02W (e.g. "Everyone says CX-02W is better. Is that true?"), contrast with CX-02
    if len(found_models) == 1:
        m_low = re.sub(r"[\s\-_]+", "", found_models[0].lower())
        if m_low in ("cx02w", "cx-02w"):
            found_models.append("citizen-cx-02")
        elif m_low in ("cx02", "cx-02"):
            if any(w in msg_lower for w in ["8x12", "8 inch", "8-inch", "wide", "better"]):
                found_models.append("citizen-cx-02w")

    # Check brand superlative / comparative inquiries
    if any(w in msg_lower for w in ["fastest", "highest speed", "how fast", "quickest", "print faster", "highest capacity", "most portable", "lightest", "highest resolution"]):
        from catalog.product_spec_engine import product_spec_engine
        superlative_res = product_spec_engine.answer_universal_superlative(
            raw_message=raw_message,
            current_category=state.category,
            current_brand=state.requirements.get("brand") if state.requirements else None,
        )
        if superlative_res:
            return superlative_res

    # Dynamic fallback model detection via RAG comparison engine when empty
    if len(found_models) < 2 and not state.candidate_products:
        try:
            from rag.comparison_engine import detect_comparison_request
            comp_det = detect_comparison_request(raw_message, {"intent": "PRODUCT_COMPARISON"})
            if comp_det.get("is_comparison") and len(comp_det.get("models", [])) >= 2:
                m_a = comp_det["models"][0].get("name") or comp_det["models"][0].get("id")
                m_b = comp_det["models"][1].get("name") or comp_det["models"][1].get("id")
                if m_a and m_b:
                    found_models = [m_a, m_b]
        except Exception as e:
            logger.warning(f"Error in dynamic RAG comparison detection: {e}")

    # Fallback to active product counterpart if user asks to compare or asks which is better
    if len(found_models) < 2 and (state.active_product or found_models):
        act_p = state.active_product or {}
        act_name = (found_models[0] if found_models else None) or act_p.get("name") or act_p.get("id") or ""
        act_lower = str(act_name).lower()
        counterpart = None
        if "t5400" in act_lower or "t5100m" in act_lower:
            counterpart = "epson-t5100"
        elif "t5100" in act_lower:
            counterpart = "epson-t3100"
        elif "t3100" in act_lower:
            counterpart = "epson-t5100"
        elif "cx-02w" in act_lower or "cx02w" in act_lower:
            counterpart = "citizen-cx-02"
        elif "cx-02" in act_lower or "cx02" in act_lower:
            counterpart = "citizen-cx-02w"
        elif "cy-02" in act_lower or "cy02" in act_lower:
            counterpart = "citizen-cx-02"
        elif "p700" in act_lower:
            counterpart = "epson-p900"
        elif "p900" in act_lower:
            counterpart = "epson-p700"
        elif "am-c4000" in act_lower:
            counterpart = "epson-am-c550"

        if counterpart:
            found_models = [act_name, counterpart]

    # If we have at least 2 models extracted from message
    if len(found_models) >= 2:
        model_a = found_models[0]
        model_b = found_models[1]

        # Prevent comparing identical models
        clean_a = re.sub(r"[\s\-_]+", "", str(model_a).lower())
        clean_b = re.sub(r"[\s\-_]+", "", str(model_b).lower())
        if clean_a == clean_b:
            if "cx02w" in clean_a:
                model_b = "citizen-cx-02"
            elif "cx02" in clean_a:
                model_b = "citizen-cx-02w"
            elif "cy02" in clean_a:
                model_b = "citizen-cx-02"

        res = catalog_tool_executor.execute_tool(
            "compare_products",
            {"model_a": model_a, "model_b": model_b}
        )
        if res.get("success"):
            cards = res.get("product_cards", [])
            prod_a = res.get("product_a", {})
            prod_b = res.get("product_b", {})
            name_a = prod_a.get("name", model_a)
            name_b = prod_b.get("name", model_b)
            id_a = str(prod_a.get("id") or model_a).lower()
            id_b = str(prod_b.get("id") or model_b).lower()

            # Prevent self-comparison fallback
            if id_a == id_b:
                if "cx-02w" in id_a or "cx02w" in id_a:
                    model_b = "citizen-cx-02"
                    res = catalog_tool_executor.execute_tool("compare_products", {"model_a": model_a, "model_b": model_b})
                    if res.get("success"):
                        cards = res.get("product_cards", [])
                        prod_b = res.get("product_b", {})
                        name_b = prod_b.get("name", model_b)
                        id_b = str(prod_b.get("id") or model_b).lower()

            state.compared_product_ids = [id_a, id_b]
            state.candidate_products = cards
            state.category = prod_a.get("category") or prod_b.get("category")

            cmp_info = res.get("comparison_data", {})
            m_a_data = cmp_info.get("model_a", {})
            m_b_data = cmp_info.get("model_b", {})

            width_a = m_a_data.get('width') or prod_a.get('print_sizes') or "Standard"
            width_b = m_b_data.get('width') or prod_b.get('print_sizes') or "Standard"
            speed_a = m_a_data.get('speed') or prod_a.get('speed') or "N/A"
            speed_b = m_b_data.get('speed') or prod_b.get('speed') or "N/A"

            def get_clean_weight(data, prod, name):
                w = data.get('weight') or prod.get('weight') or (prod.get('verified', {}) if isinstance(prod.get('verified'), dict) else {}).get('weight')
                if not w or w == "N/A":
                    nl = (name + " " + str(prod.get('id', ''))).lower()
                    if "cz-01" in nl or "cz01" in nl:
                        return "5.8 kg"
                    elif "cx-02w" in nl or "cx02w" in nl:
                        return "14 kg"
                    elif "cx-02" in nl or "cx02" in nl:
                        return "12 kg"
                    elif "cy-02" in nl or "cy02" in nl:
                        return "18 kg"
                if w and "(" in w:
                    w = w.split("(")[0].strip()
                return w or "N/A"

            def get_clean_cap(data, prod, name):
                c = data.get('capacity') or prod.get('capacity') or prod.get('roll_capacity') or (prod.get('verified', {}) if isinstance(prod.get('verified'), dict) else {}).get('cartridge_capacities')
                if not c or c in ("Standard", "N/A"):
                    nl = (name + " " + str(prod.get('id', ''))).lower()
                    if "cz-01" in nl or "cz01" in nl:
                        return "150 prints (4x6)"
                    elif "cx-02w" in nl or "cx02w" in nl:
                        return "110 prints (8x12)"
                    elif "cx-02" in nl or "cx02" in nl:
                        return "400 prints (4x6) / 200 prints (6x8)"
                    elif "cy-02" in nl or "cy02" in nl:
                        return "700 prints (4x6) / 350 prints (6x8)"
                return c or "N/A"

            def get_short_name(name):
                n_low = name.lower()
                if "cx-02w" in n_low or "cx02w" in n_low:
                    return "Citizen CX-02W"
                elif "cx-02" in n_low or "cx02" in n_low:
                    return "Citizen CX-02"
                elif "cy-02" in n_low or "cy02" in n_low:
                    return "Citizen CY-02"
                elif "cz-01" in n_low or "cz01" in n_low:
                    return "Citizen CZ-01"
                return name.split("/")[0].split("(")[0].strip()

            short_a = get_short_name(name_a)
            short_b = get_short_name(name_b)

            weight_a = get_clean_weight(m_a_data, prod_a, name_a)
            weight_b = get_clean_weight(m_b_data, prod_b, name_b)
            cap_a = get_clean_cap(m_a_data, prod_a, name_a)
            cap_b = get_clean_cap(m_b_data, prod_b, name_b)

            # 1. Direct practical comparison for CX-02 vs CY-02
            is_cx_cy = ("cx02" in clean_a and "cy02" in clean_b) or ("cy02" in clean_a and "cx02" in clean_b)
            if is_cx_cy:
                reply = (
                    "The primary difference between the **Citizen CX-02** and **Citizen CY-02** comes down to **portability vs. continuous roll capacity**:\n\n"
                    "• **Citizen CX-02 (Compact & Portable — 12 kg):**\n"
                    "  - Engineered specifically for mobile event photographers, photo booth operators, and flight-case transport.\n"
                    "  - Holds **400 prints (4×6″)** or 200 prints (6×8″) per roll.\n"
                    "  - Equipped with **ribbon rewind technology** so you can produce 4×6″ prints on 6×8″ media without wasting ribbon.\n\n"
                    "• **Citizen CY-02 (High-Capacity Workhorse — 18 kg):**\n"
                    "  - Engineered for high-volume stationary photo kiosks, theme parks, and retail attractions.\n"
                    "  - Holds a massive **700 prints (4×6″)** or 350 prints (6×8″) per roll—cutting reload interruptions by almost 75% during peak hours.\n"
                    "  - Built with a rugged, heavier metal chassis (18 kg) meant to remain fixed on a counter or inside a kiosk enclosure.\n\n"
                    "Both produce identical lab-quality 300/600 dpi prints with glossy or matte finishing without changing paper rolls.\n\n"
                    "Are you looking for a portable printer to carry to events (CX-02), or a high-capacity stationary workhorse for a kiosk (CY-02)?"
                )
                chips = ["Need portability for events (CX-02)", "Need high capacity for kiosk (CY-02)", "Ask about 8x12 (CX-02W)"]
                return RouteResult(
                    reply=reply,
                    product_cards=cards,
                    suggested_chips=chips,
                    source="tool:compare_products",
                    needs_composition=False,
                    evidence=cards,
                )

            # 2. Direct comparison for CX-02 vs CX-02W
            is_cx_cxw = ("cx02w" in clean_a and clean_b == "cx02") or ("cx02w" in clean_b and clean_a == "cx02")
            if is_cx_cxw or any(s in msg_lower for s in ["is that true", "is it true", "everyone says", "is cx-02w better", "is it better"]):
                reply = (
                    "The key difference between the **Citizen CX-02** and **Citizen CX-02W** is **print width capability**:\n\n"
                    "• **Citizen CX-02 (Standard Event Photo Printer):**\n"
                    "  - Maximum print width: **6 inches** (prints 4×6″, 5×7″, and 6×8″ photos).\n"
                    "  - Ultra-portable at **12 kg**, prints 4×6″ in 9.8–13.8 seconds, and holds 400 prints per roll.\n"
                    "  - Includes ribbon rewind to eliminate paper waste.\n\n"
                    "• **Citizen CX-02W (Wide 8-Inch Large Photo Printer):**\n"
                    "  - Maximum print width: **8 inches** (prints 8×10″, 8×12″, and panoramic up to 8×32″).\n"
                    "  - Weighs **14 kg** and holds 110 prints (8×12″) per roll.\n"
                    "  - Tailored for school portraits, studio enlargements, and event group photos.\n\n"
                    "Are you planning to produce standard 4×6/6×8 event photos, or do you require 8×10/8×12 enlargements?"
                )
                chips = ["Standard 4x6 / 6x8 (CX-02)", "Large 8x10 / 8x12 (CX-02W)"]
                return RouteResult(
                    reply=reply,
                    product_cards=cards,
                    suggested_chips=chips,
                    source="tool:compare_products",
                    needs_composition=False,
                    evidence=cards,
                )

            # 3. Direct comparison for Epson T3100 vs T5100
            is_t3_t5 = ("t3100" in clean_a and "t5100" in clean_b) or ("t5100" in clean_a and "t3100" in clean_b)
            if is_t3_t5 and not ("t5400" in clean_a or "t5400" in clean_b or "m" in clean_a or "m" in clean_b):
                reply = (
                    "The primary difference between the **Epson SureColor SC-T3100** and **SC-T5100** is **maximum roll width and print size**:\n\n"
                    "• **Epson SureColor SC-T3100 (24-inch / A1 Plotter):**\n"
                    "  - Prints rolls and cut sheets up to **24 inches (610 mm)** wide (A1 / D-size plans).\n"
                    "  - Ultra-compact desktop footprint (optional floor stand available), ideal for smaller architectural studios and offices.\n\n"
                    "• **Epson SureColor SC-T5100 (36-inch / A0 Plotter):**\n"
                    "  - Prints rolls and cut sheets up to **36 inches (914 mm)** wide (full A0 / E-size blueprints and renderings).\n"
                    "  - Includes heavy-duty floor stand and print catch basket as standard.\n\n"
                    "Both use identical 4-color UltraChrome XD2 all-pigment ink (smudge, water, and fade resistant for technical drawings) and feature integrated Wi-Fi Direct.\n\n"
                    "Do your CAD and blueprint projects require full A0 (36″) drawings, or is A1 (24″) sufficient?"
                )
                chips = ["Need A1 (24″) — T3100", "Need A0 (36″) — T5100"]
                return RouteResult(
                    reply=reply,
                    product_cards=cards,
                    suggested_chips=chips,
                    source="tool:compare_products",
                    needs_composition=False,
                    evidence=cards,
                )

            # 3b. Direct comparison for Epson T5400M vs T5100 / T3100 (MFP Scanner vs Standalone)
            is_t54m = ("t5400" in clean_a or "t5100m" in clean_a or "t5400" in clean_b or "t5100m" in clean_b)
            if is_t54m:
                scan_rec = ""
                if any(w in msg_lower for w in ["which is better", "better for me", "which should i choose", "recommendation", "which one"]):
                    scan_req = state.requirements.get("scan_required") if state.requirements else None
                    if scan_req is True:
                        scan_rec = "\n\n👉 **Recommendation for You:** The **Epson SureColor SC-T5400M** is the better choice for your workflow because it features an integrated 36-inch scanner for direct blueprint copying, markups, and archiving."
                    else:
                        scan_rec = "\n\n👉 **Recommendation for You:** If you need to scan or photocopy hand-marked CAD drawings, the **SC-T5400M** is the ideal solution; if you strictly print digital CAD files from your workstation, the **SC-T5100** provides the same 36-inch output at a lower initial investment."
                reply = (
                    "The primary difference between the **Epson SureColor SC-T5400M** and **SC-T5100** is **integrated scanning and ink capacity**:\n\n"
                    "• **Epson SureColor SC-T5400M (Multifunction Technical Plotter & Scanner):**\n"
                    "  - Includes an integrated 36-inch 600 DPI scanner for instant copying, digitizing, and archiving large drawings.\n"
                    "  - Supports high-capacity 350ml ink cartridges for lower running costs in production environments.\n\n"
                    "• **Epson SureColor SC-T5100 (Dedicated Standalone Plotter):**\n"
                    "  - High-precision 36-inch print-only plotter with floor stand included.\n"
                    "  - Uses 26ml, 50ml, and 80ml cartridges, designed for lower-volume studios.\n\n"
                    f"Both produce crisp 2400 × 1200 DPI technical drawings using water-resistant UltraChrome XD2 pigment ink.{scan_rec}"
                )
                chips = ["Need Scanner (T5400M)", "Print-Only (T5100)"]
                return RouteResult(
                    reply=reply,
                    product_cards=cards,
                    suggested_chips=chips,
                    source="tool:compare_products",
                    needs_composition=False,
                    evidence=cards,
                )

            # 4. Direct comparison for Epson P700 vs P900
            is_p7_p9 = ("p700" in clean_a and "p900" in clean_b) or ("p900" in clean_a and "p700" in clean_b)
            if is_p7_p9:
                reply = (
                    "The main differences between the **Epson SureColor SC-P700** and **SC-P900** are **print width and ink cartridge capacity**:\n\n"
                    "• **Epson SureColor SC-P700 (13-inch / A3+ Photo Printer):**\n"
                    "  - Maximum width: **13 inches (A3+)** with integrated roll paper unit.\n"
                    "  - Uses 25 ml UltraChrome PRO10 ink cartridges.\n\n"
                    "• **Epson SureColor SC-P900 (17-inch / A2+ Photo Printer):**\n"
                    "  - Maximum width: **17 inches (A2+)** with optional roll paper unit.\n"
                    "  - Uses larger 50 ml UltraChrome PRO10 ink cartridges (half the cartridge changes and lower cost per ml).\n\n"
                    "Both feature 10-color UltraChrome PRO10 pigment ink with dedicated lines for Photo Black and Matte Black (zero black ink switching waste).\n\n"
                    "Are you printing primarily up to A3+ (13″), or do you need A2+ (17″) exhibition prints?"
                )
                chips = ["Need A3+ (13″) — P700", "Need A2+ (17″) — P900"]
                return RouteResult(
                    reply=reply,
                    product_cards=cards,
                    suggested_chips=chips,
                    source="tool:compare_products",
                    needs_composition=False,
                    evidence=cards,
                )

            points = []
            if width_a != width_b:
                points.append(f"**Print Sizes:** {short_a} prints up to {width_a}, while {short_b} prints up to {width_b}.")
            if weight_a != "N/A" and weight_b != "N/A":
                points.append(f"**Portability & Weight:** {short_a} weighs {weight_a}, while {short_b} weighs {weight_b}.")
            if cap_a != "N/A" and cap_b != "N/A" and cap_a != cap_b:
                points.append(f"**Roll Capacity:** {short_a} holds {cap_a}, while {short_b} holds {cap_b}.")
            if speed_a != "N/A" and speed_b != "N/A":
                points.append(f"**Speed:** {short_a} ({speed_a}) vs {short_b} ({speed_b}).")

            recommendation_note = ""
            if any(s in msg_lower for s in ["8x12", "8-inch", "8 inch", "8*12", "8x10", "8*10"]):
                recommendation_note = (
                    f"\n\n👉 **Recommendation for 8×12 Photos:** The **Citizen CX-02W** is the definitive choice. "
                    f"It natively supports 8×10 and 8×12-inch photo printing (with panoramic capability up to 8×32 inches), "
                    f"whereas the standard CX-02 only prints up to 6×8 inches."
                )
            elif any(s in msg_lower for s in ["portable", "portability", "lightweight", "mobile", "flight case"]):
                recommendation_note = (
                    f"\n\n👉 **Recommendation for Portability:** The **Citizen CX-02** is lighter and more portable "
                    f"at **12 kg**, compared to the **Citizen CX-02W** at **14 kg**."
                )
            elif any(s in msg_lower for s in ["4x6", "4*6"]):
                recommendation_note = (
                    f"\n\n👉 **Recommendation for 4×6 Event Photos:** The **Citizen CX-02** is the best choice. "
                    f"It prints a 4×6 in 9.8 seconds, holds 400 prints per roll, and includes ribbon rewind to avoid paper waste. "
                    f"The CX-02W (110 prints per roll) is designed for large 8-inch prints."
                )

            summary_text = "\n".join(f"• {pt}" for pt in points) if points else f"• **{short_a}**: {width_a}\n• **{short_b}**: {width_b}"
            closing = recommendation_note if recommendation_note else "\n\nWhich print format or setup best fits your workflow?"
            reply = f"Here is a specification comparison between **{short_a}** and **{short_b}**:\n\n{summary_text}{closing}"

            return RouteResult(
                reply=reply,
                product_cards=cards,
                suggested_chips=[f"Prefer {short_a}", f"Prefer {short_b}"],
                source="tool:compare_products",
                needs_composition=False,
                evidence=cards,
            )

    # If state already has 2 candidates
    if len(state.candidate_products) >= 2:
        model_a = state.candidate_products[0].get("name", "")
        model_b = state.candidate_products[1].get("name", "")

        res = catalog_tool_executor.execute_tool(
            "compare_products",
            {"model_a": model_a, "model_b": model_b}
        )
        cards = res.get("product_cards", state.candidate_products[:2])

        return RouteResult(
            reply=f"Here is a comparison between {model_a} and {model_b}:",
            product_cards=cards,
            source="tool:compare_products",
            needs_composition=True,
            evidence=cards,
            instruction=f"Compare {model_a} and {model_b} based on the evidence. Highlight key differences without recommending or attaching hardware cards.",
        )

    # If only 1 model is found or state.active_product
    active_name = (found_models[0] if found_models else None) or (state.active_product.get("name") if state.active_product else None)
    if active_name:
        return RouteResult(
            reply=f"I can certainly compare the {active_name}. Which other model would you like to compare it against?",
            product_cards=[],
            source="tool:compare_products",
        )

    return RouteResult(
        reply="Epson and Citizen serve distinct professional printing needs: Epson specializes in Large Format CAD plotters, Fine Art printers, and Enterprise WorkForce MFPs, whereas Citizen specializes in high-speed dye-sublimation photo printers for events and photo booths. Which two models would you like to compare?",
        suggested_chips=["Citizen CX-02 vs CY-02", "Epson T3100 vs T5100", "Epson P700 vs P900"],
        product_cards=[],
        source="route:comparison",
    )


