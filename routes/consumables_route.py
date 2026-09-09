"""
Consumables Route for Kepler Tech Conversational AI.
Handles consumable/ink queries with full-word exact matching,
color-specific filtering, and color clarification prompts when ink color is unspecified.
"""

import logging
import re
from domain.conversation_types import LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from agent.tool_executor import catalog_tool_executor

logger = logging.getLogger("route:consumables")

# Known ink colors in Epson / professional printing
KNOWN_COLORS = [
    "black", "photo black", "matte black", "cyan", "magenta", "yellow", 
    "light cyan", "light magenta", "gray", "grey", "light gray", "light grey",
    "violet", "orange", "green", "red", "vivid magenta", "vivid light magenta"
]


def handle(understanding: LLMUnderstanding, state: ConversationState, raw_message: str = "") -> RouteResult:
    """Handle consumable queries — find inks/cartridges/ribbons with color specificity."""
    entities = understanding.entities
    model_code = entities.get("model_code")
    raw_lower = (raw_message or "").lower().strip()

    # 1. Direct Consumable SKU Match (e.g., customer asks for "C13T40D140" or "C13S210057")
    direct_sku_match = re.search(r"\b(c1[23][a-z0-9]{5,8}|c13s\d+|c12c\d+|ifa\s*\d+|olm\s*\d+)\b", raw_lower)
    if direct_sku_match:
        sku = direct_sku_match.group(1).upper()
        res_sku = catalog_tool_executor.execute_tool("get_product_specs", {"product_identifier": sku})
        if res_sku.get("success"):
            item = res_sku.get("product", {})
            card = catalog_tool_executor.format_card(item, card_type="consumable")
            p_name = item.get("name", sku)
            state.active_printer_for_consumables = None
            return RouteResult(
                reply=f"Here is the verified genuine consumable for **{p_name}** (SKU: {sku}):",
                consumable_cards=[card],
                source="tool:get_direct_consumable_sku",
            )

    # 2. Extract Colors if customer mentioned any (or retrieve saved color from previous turn)
    extracted_colors = []
    for color in sorted(KNOWN_COLORS, key=lambda c: len(c), reverse=True):
        if re.search(r"\b" + re.escape(color) + r"\b", raw_lower):
            # Avoid duplicate sub-strings (e.g., "black" inside "photo black")
            if not any(color in ec for ec in extracted_colors):
                extracted_colors.append(color)

    if extracted_colors:
        state.requested_ink_color = extracted_colors[0]
    elif state.requested_ink_color:
        extracted_colors = [state.requested_ink_color]

    # 3. Determine target printer / hardware model with exact full-word matching
    target = None
    m = None
    from catalog.product_resolver import resolve_canonical_id, normalize_model_identifier
    raw_canon = resolve_canonical_id(raw_message)
    has_pronoun_ref = bool(re.search(r"\b(?:this|that|it|its|these|those)\b", raw_lower))

    # If pronoun is used and an active product exists, the pronoun refers to that active product!
    if has_pronoun_ref and state.active_product:
        target = state.active_product.get("name") or state.active_product.get("sku")
    elif raw_canon:
        target = raw_canon
    elif raw_message and re.search(r"\b(?:sc-?)?(?:[tpf]\d{3,4}[a-z]?|ds-?\d{3,5}[a-z]?|cx-?\d{1,2}w?|cy-?\d{1,2}|cz-?\d{1,2}|am-?c\d{3,4}|wf-?c\d{3,5}[a-z]?|12000xl|f100|f500)\b", raw_lower):
        m = re.search(r"\b(?:sc-?)?(?:[tpf]\d{3,4}[a-z]?|ds-?\d{3,5}[a-z]?|cx-?\d{1,2}w?|cy-?\d{1,2}|cz-?\d{1,2}|am-?c\d{3,4}|wf-?c\d{3,5}[a-z]?|12000xl|f100|f500)\b", raw_lower)
        if m:
            target = m.group(0).upper()
    elif model_code:
        # Validate model_code against user's actual text to avoid hallucinated LLM entities
        cand_norm = normalize_model_identifier(model_code)
        msg_norm = re.sub(r"[^a-z0-9]", "", raw_lower)
        if cand_norm and cand_norm in msg_norm:
            target = resolve_canonical_id(model_code) or model_code

    # If asking generally for ink ("i want to buy a ink", "need ink", "i want ink") without explicit model code, do not assume previous active product
    has_model_mention = bool(target or m)
    is_general_ink_req = not has_model_mention and not has_pronoun_ref and bool(re.search(r"\b(?:ink|inks|cartridge|cartridges|toner|ribbon)\b", raw_lower))
    if not is_general_ink_req:
        # Prioritize the printer actively discussed in consumables flow first!
        if not target and state.active_printer_for_consumables:
            target = state.active_printer_for_consumables
        elif not target and state.active_product:
            target = state.active_product.get("name") or state.active_product.get("sku")

    # If no printer identified, ask user for the exact model
    if not target:
        state.category = "consumable"
        state.awaiting_field = "printer_model"
        state.candidate_products = []
        return RouteResult(
            reply="Which printer or scanner model do you need consumables for?",
            suggested_chips=["SC-P900", "SC-T3100", "SC-F100", "SC-P700", "WF-C20600"],
            product_cards=[],
            consumable_cards=[],
            source="route:consumables:ask_model",
            needs_composition=False,
        )

    # Clean composite target string (e.g. "CX-02, CX-02S" or "CX-02 / CX-02S" -> extract primary model like "CX-02")
    if target:
        m_primary = re.search(r"\b(?:sc-?)?(?:[tpf]\d{3,4}[a-z]?|ds-?\d{3,5}[a-z]?|cx-?\d{1,2}w?|cy-?\d{1,2}|cz-?\d{1,2}|am-?c\d{3,4}|wf-?c\d{3,5}[a-z]?|12000xl|f100|f500)\b", str(target), re.IGNORECASE)
        if m_primary:
            target = m_primary.group(0).upper()

    # Cache active printer for follow-up questions
    state.active_printer_for_consumables = target


    # 4. Fetch compatible consumables via tool executor
    res = catalog_tool_executor.execute_tool(
        "get_compatible_consumables",
        {"printer_identifier": target, "limit": 16}
    )
    all_consumables = res.get("consumable_cards", [])
    product_cards = res.get("product_cards", [])
    printer_name = res.get("printer_name") or target

    if not all_consumables:
        return RouteResult(
            reply=f"I could not locate verified consumables for '{target}' in our catalog. Please contact sales@keplertech.ae for specialty sourcing.",
            source="tool:get_compatible_consumables",
        )

    # 5. Filter by color if color was specified
    if extracted_colors:
        state.awaiting_field = None
        state.requested_ink_color = None  # Clear once fulfilled
        matched_color_cards = []
        for c in all_consumables:
            c_text = (c.get("name", "") + " " + c.get("description", "")).lower()
            if any(re.search(r"\b" + re.escape(clr) + r"\b", c_text) for clr in extracted_colors):
                matched_color_cards.append(c)

        if matched_color_cards:
            colors_formatted = ", ".join([c.title() for c in extracted_colors[:-1]]) + (" and " if len(extracted_colors) > 1 else "") + extracted_colors[-1].title()
            plural = "inks" if len(extracted_colors) > 1 or len(matched_color_cards) > 1 else "ink"
            return RouteResult(
                reply=f"Here are the genuine **{colors_formatted}** {plural} for {printer_name}:",
                product_cards=[],
                consumable_cards=matched_color_cards,
                source="tool:get_compatible_consumables_by_color",
                needs_composition=False,
            )

    # Extract ONLY the genuine colors that this printer's consumables actually have
    COLOR_CANDIDATES = [
        "Photo Black", "Matte Black", "Light Black", "Light Light Black",
        "Light Cyan", "Light Magenta", "Vivid Magenta", "Vivid Light Magenta",
        "Dark Grey", "Light Grey", "Grey", "Gray",
        "Black", "Cyan", "Magenta", "Yellow", "Violet", "Orange", "Green", "Red"
    ]
    available_ink_colors = []
    for c in all_consumables:
        c_name_l = c.get("name", "").lower()
        if any(k in c_name_l for k in ["ink", "cartridge", "tank", "pack", "bottle"]):
            for clr in COLOR_CANDIDATES:
                if re.search(r"\b" + re.escape(clr.lower()) + r"\b", c_name_l):
                    if clr not in available_ink_colors:
                        available_ink_colors.append(clr)
                    break

    is_citizen_dyesub = any(b in printer_name.lower() for b in ["citizen", "cx-02", "cx02", "cy-02", "cz-01", "cx-02w"]) or any(b in str(target).lower() for b in ["citizen", "cx-02", "cx02", "cy-02", "cz-01", "cx-02w"])
    is_epson_dyesub = any(b in printer_name.lower() for b in ["sc-f100", "sc-f500", "f100", "f500"]) or any(b in str(target).lower() for b in ["sc-f100", "sc-f500", "f100", "f500"])
    user_wanted_printer_card = any(k in raw_lower for k in ["show me the", "printer and its inks", "printer and inks", "and the printer", "show the printer"])
    hw_cards_to_show = product_cards if user_wanted_printer_card else []

    is_ink_cartridge_question = any(w in raw_lower for w in ["does it use ink", "use ink cartridges", "use cartridges", "use ink", "need ink", "have ink", "liquid ink", "use ribbon"])

    # For Citizen dye-sub photo printers: they use paper/ribbon rolls, NEVER ask for ink colors
    if is_citizen_dyesub:
        items_list = "\n".join([f"• **{c.get('name')}** (SKU: `{c.get('sku')}`)" for c in all_consumables])
        if is_ink_cartridge_question:
            reply = (
                f"No, the **{printer_name}** does not use liquid ink cartridges. It is a thermal dye-sublimation photo printer that uses all-in-one ribbon and paper media sets (each pack includes both the photo paper roll and the thermal ribbon).\n\n"
                f"Here are the genuine compatible media sets:\n\n{items_list}\n\n"
                f"*(Each media pack produces instant-dry, smudge-proof lab quality prints with glossy or matte finish without changing paper).*"
            )
        else:
            reply = (
                f"Here are the genuine compatible photo media sets for **{printer_name}**:\n\n"
                f"{items_list}\n\n"
                f"*(Note: Citizen media packs include both the dye-sub paper roll and matching thermal ribbon).*"
            )
        return RouteResult(
            reply=reply,
            product_cards=hw_cards_to_show,
            consumable_cards=all_consumables,
            source="tool:get_compatible_consumables",
        )

    # For Epson dye-sublimation printers (SC-F100, SC-F500): use 140ml UltraChrome DS bottles & maintenance box
    if is_epson_dyesub:
        items_list = "\n".join([f"• **{c.get('name')}** (SKU: `{c.get('sku')}`)" for c in all_consumables])
        if is_ink_cartridge_question:
            reply = (
                f"The **{printer_name}** uses genuine Epson 140ml UltraChrome DS dye-sublimation ink bottles (T49N series) and a maintenance box, rather than traditional sealed cartridges.\n\n"
                f"Here are the verified genuine inks and consumables:\n\n{items_list}"
            )
        else:
            reply = (
                f"Here are the genuine compatible inks and consumables for **{printer_name}**:\n\n"
                f"{items_list}\n\n"
                f"*(Uses genuine 140ml UltraChrome DS ink refill bottles for Black, Cyan, Magenta, and Yellow, along with the dedicated maintenance box).*"
            )
        return RouteResult(
            reply=reply,
            product_cards=hw_cards_to_show,
            consumable_cards=all_consumables,
            source="tool:get_compatible_consumables",
        )

    # For inkjet printers when asked if it uses ink cartridges
    if is_ink_cartridge_question and not is_dyesub:
        items_list = "\n".join([f"• **{c.get('name')}** (SKU: `{c.get('sku')}`)" for c in all_consumables[:6]])
        colors_display = ", ".join(available_ink_colors) if available_ink_colors else "genuine ink cartridges"
        reply = (
            f"Yes, the **{printer_name}** uses genuine ink cartridges ({colors_display}).\n\n"
            f"Here are the verified compatible consumables:\n\n{items_list}"
        )
        return RouteResult(
            reply=reply,
            product_cards=hw_cards_to_show,
            consumable_cards=all_consumables[:6],
            source="tool:get_compatible_consumables",
        )

    # If user specifically asks for replacement ink or says "buy ink", ask for color if multiple exist:
    is_asking_all_or_compatible = any(w in raw_lower for w in ["what consumables", "which consumables", "compatible with", "media compatible", "all consumables", "show consumables", "what ink does it use", "what inks does it use"])
    if len(available_ink_colors) >= 2 and not extracted_colors and not is_asking_all_or_compatible and any(b in raw_lower for b in ["buy ink", "need ink", "order ink", "refill", "cartridge"]):
        state.awaiting_field = "ink_color"
        colors_display = ", ".join(available_ink_colors)
        return RouteResult(
            reply=f"Which ink color do you need for the **{printer_name}**? ({colors_display})",
            suggested_chips=available_ink_colors[:6] + ["All Colors"],
            product_cards=hw_cards_to_show,
            consumable_cards=all_consumables[:6],
            source="route:consumables:ask_color",
            needs_composition=False,
        )

    # Default: Return verified compatible consumables / media with clean bullet points
    items_list = "\n".join([f"• **{c.get('name')}** (SKU: `{c.get('sku')}`)" for c in all_consumables[:6]])
    reply = f"Here are the verified genuine consumables and media for **{printer_name}**:\n\n{items_list}"

    return RouteResult(
        reply=reply,
        product_cards=hw_cards_to_show,
        consumable_cards=all_consumables[:6],
        source="tool:get_compatible_consumables",
    )

