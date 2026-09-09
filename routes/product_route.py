"""
Product Route for Kepler Tech Conversational AI.
Handles product search and product specification queries
using the existing tool_executor infrastructure.
"""

import re
import logging
from domain.conversation_types import LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from agent.tool_executor import catalog_tool_executor

logger = logging.getLogger("route:product")


def handle(understanding: LLMUnderstanding, state: ConversationState,
           raw_message: str = "") -> RouteResult:
    """Handle product search, product spec queries, and brochure downloads."""
    msg_lower = (raw_message or "").strip().lower()

    # ── Unsupported Competitor Brands Guardrail ───────────────────────────
    unsupported = [b for b in ["canon", "hp", "designjet", "imageprograf", "brother", "xerox", "ricoh", "kyocera", "konica"] if re.search(rf"\b{b}\b", msg_lower)]
    if unsupported and not any(k in msg_lower for k in ["epson", "citizen", "innova", "olmec"]):
        brand_name = unsupported[0].title()
        if brand_name.lower() == "hp":
            brand_name = "HP"
        return RouteResult(
            reply=f"I don’t have verified information about {brand_name} equipment, as Kepler Tech LLC is an authorized distributor and partner specializing in Epson and Citizen commercial printing and scanning hardware. I would be glad to recommend an authorized model that matches your printing requirements!",
            suggested_chips=["View Large Format Plotters", "Photo Printers", "Office Enterprise MFPs"],
            source="route:unsupported_brand"
        )

    # ── Universal Product Attribute / Superlative Engine ────────────────
    from catalog.product_spec_engine import product_spec_engine
    superlative_res = product_spec_engine.answer_universal_superlative(
        raw_message=raw_message,
        current_category=state.category,
        current_brand=state.requirements.get("brand") if state.requirements else None,
    )
    if superlative_res:
        return superlative_res

    # ── Product Brochure / Datasheet Request ─────────────────────────────
    is_brochure_query = any(b in msg_lower for b in [
        "brochure", "brosure", "broucher", "brousher", "broshur", "brocher",
        "datasheet", "data sheet", "specsheet", "spec sheet",
        "download pdf", "pdf link", "give brochure", "send brochure",
        "give the brosure", "give the brochure", "product sheet", "technical sheet",
        "catalog pdf", "brochure link"
    ])
    if is_brochure_query:
        from catalog.brochure_resolver import brochure_resolver
        brochures = brochure_resolver.resolve_for_conversation(state, raw_message)
        if brochures:
            lines = ["Here are the official product data sheets from Kepler Tech LLC:"]
            cards = []
            from catalog.price_resolver import price_resolver
            from catalog.repository import catalog_repository
            for b in brochures:
                b_name = b.get("name", "Product")
                pdf_url = b.get("pdf", "")
                web_url = b.get("url", "")
                lines.append(f"• 📄 **[{b_name} — Product Data Sheet (PDF)]({pdf_url})**")
                if web_url:
                    lines.append(f"  🌐 [View {b_name} on Kepler Tech]({web_url})")

                # Match normalized product for high-res images and complete specs
                matched_prod = None
                b_aliases = [re.sub(r"[\s\-_/]+", "", a.lower()) for a in b.get("aliases", [])]
                for p in catalog_repository.get_all():
                    p_id_norm = re.sub(r"[\s\-_/]+", "", p.id.lower())
                    p_name_norm = re.sub(r"[\s\-_/]+", "", p.name.lower())
                    if p_id_norm in b_aliases or any(a in p_id_norm for a in b_aliases) or any(a in p_name_norm for a in b_aliases):
                        matched_prod = p
                        break

                if matched_prod:
                    card = catalog_tool_executor.format_card(matched_prod.to_dict(), card_type="hardware")
                    card["pdf_url"] = pdf_url
                    card["brochure_url"] = pdf_url
                    cards.append(card)
                else:
                    alias = b.get("aliases", [b_name])[0].upper()
                    price_info = price_resolver.get_price_info(identifier=alias, prod={"name": b_name})
                    cards.append({
                        "id": b.get("name", ""),
                        "name": b_name,
                        "title": b_name,
                        "sku": alias,
                        "price": price_info.get("price"),
                        "price_formatted": price_info.get("price_str", "Price on Request"),
                        "price_str": price_info.get("price_str", "Price on Request"),
                        "vat_note": price_info.get("vat_note", ""),
                        "currency": "AED",
                        "image": "https://www.keplertechllc.com/wp-content/uploads/2023/05/Kepler-Logo-.png",
                        "image_url": "https://www.keplertechllc.com/wp-content/uploads/2023/05/Kepler-Logo-.png",
                        "url": web_url or pdf_url,
                        "pdf_url": pdf_url,
                        "brochure_url": pdf_url,
                        "badge": "Data Sheet PDF",
                        "card_type": "hardware",
                        "description": f"Official verified product data sheet for {b_name}.",
                        "has_consumables": False,
                    })
            lines.append("\nYou can download the complete technical specifications directly using the PDF links above. Please let me know if you would like information on genuine consumables, media rolls, or warranty support!")
            return RouteResult(
                reply="\n".join(lines),
                product_cards=cards,
                source="tool:get_brochure",
                needs_composition=False,
            )
        else:
            return RouteResult(
                reply="I'd be happy to provide the official product data sheet! Which specific printer model do you need the brochure for (e.g., Citizen CX-02, CY-02, Epson P700, or T3100)?",
                suggested_chips=["Citizen CX-02 Data Sheet", "Citizen CY-02 Data Sheet", "Epson P700 Data Sheet", "Epson T3100 Data Sheet"],
                source="tool:get_brochure",
            )

    entities = understanding.entities
    model_code = entities.get("model_code")
    from catalog.product_resolver import resolve_canonical_id, normalize_model_identifier
    canonical_id = resolve_canonical_id(raw_message)
    if canonical_id:
        model_code = canonical_id
    elif model_code:
        cand_norm = normalize_model_identifier(model_code)
        msg_norm = re.sub(r"[^a-z0-9]", "", msg_lower)
        if not cand_norm or cand_norm not in msg_norm:
            model_code = None
    if not model_code and raw_message:
        m = re.search(r"\b(?:sc-?)?([tpf]\d{3,4}[a-z]?|ds-?\d{3,5}[a-z]?|cx-?\d{2}w?|cy-?\d{2}|cz-?\d{2}|am-?c\d{3,4}|wf-?c\d{3,4}[a-z]?|12000xl|f100|f500)\b", raw_message.lower())
        if m:
            model_code = m.group(0).upper()

    # ── Specific product spec query ──────────────────────────────────────
    if model_code:
        # Check single-attribute answer first
        from catalog.product_spec_engine import product_spec_engine
        from catalog.repository import catalog_repository
        single_attr_res = product_spec_engine.answer_single_attribute(model_code, raw_message)
        if single_attr_res:
            p_obj = catalog_repository.get_by_id(model_code)
            if p_obj:
                state.active_product = p_obj.to_dict()
                state.candidate_products = single_attr_res.product_cards
            return single_attr_res

        # Retrieve rich specs from universal product_spec_engine
        detailed_specs = product_spec_engine.get_product_detailed_specs(model_code, raw_message)

        res = catalog_tool_executor.execute_tool(
            "get_product_specs", {"product_identifier": model_code}
        )
        if res.get("success") or detailed_specs:
            product = (detailed_specs.get("product") if detailed_specs else None) or res.get("product", {})
            cards = [detailed_specs["product_card"]] if (detailed_specs and detailed_specs.get("product_card")) else res.get("product_cards", [])
            state.active_product = product
            state.candidate_products = cards
            if not state.category:
                p_name_l = product.get("name", "").lower()
                if any(x in p_name_l for x in ["sc-t", "surecolor t", "cad", "plotter"]):
                    state.category = "technical_cad"
                elif any(x in p_name_l for x in ["sc-p", "surecolor p", "photo"]):
                    state.category = "photo_fine_art"
                elif any(x in p_name_l for x in ["workforce", "am-c", "copier"]):
                    state.category = "office_enterprise"
                elif any(x in p_name_l for x in ["ds-", "workforce ds", "scanner"]):
                    state.category = "scanner"
                elif any(x in p_name_l for x in ["cx-", "cy-"]):
                    state.category = "photo_booth"

            p_name = product.get("name", model_code)
            p_url = product.get("website_url") or product.get("web_url") or f"https://www.keplertechllc.com/product/{product.get('id', '')}/"
            desc = product.get("description") or product.get("intended_usage") or "genuine verified equipment from Kepler Tech LLC"
            price_str = cards[0].get("price_formatted") if cards else (product.get("price_formatted") or "Price on Request")
            vat = cards[0].get("vat_note") if cards else (product.get("vat_note") or "")

            q_lower = (raw_message or "").lower()
            if any(w in q_lower for w in ["technology", "inkjet", "thermal", "dye sub", "dyesub", "type of printer"]):
                is_citizen = any(c in p_name.lower() for c in ["citizen", "cx-02", "cx02", "cz-01", "cz01", "cy-02", "cy02"])
                tech = product.get("ink_technology") or product.get("verified", {}).get("ink_technology") or ("Dye-Sublimation Thermal Transfer" if is_citizen else "PrecisionCore MicroTFP")
                if "inkjet" in q_lower:
                    if is_citizen:
                        reply = f"Regarding [{p_name}]({p_url}): No, it is not an inkjet printer. The {p_name} utilizes professional **{tech}** technology using ribbon and paper rolls for lab-grade, instant-dry photo prints."
                    else:
                        reply = f"Yes, [{p_name}]({p_url}) uses professional **{tech}** inkjet technology."
                else:
                    reply = f"The [{p_name}]({p_url}) operates on professional **{tech}** technology."
            elif any(k in q_lower for k in ["price", "cost", "how much", "rate"]):
                reply = f"The [{p_name}]({p_url}) is officially listed at **{price_str}** {vat}. Here are the verified specifications — {desc.rstrip('.')}."
            elif detailed_specs and any(w in q_lower for w in ["spec", "specs", "specification", "specifications", "detail", "details", "description", "full description", "overview", "what is", "about", "tell me about"]):
                reply = detailed_specs["reply"]
            elif detailed_specs and not any(w in q_lower for w in ["recommend", "options", "suggest"]):
                reply = detailed_specs["reply"]
            else:
                reply = f"Here are the verified specifications for [{p_name}]({p_url}) — {desc.rstrip('.')}."

            consumable_cards = []
            if any(w in q_lower for w in ["ink", "inks", "cartridge", "cartridges", "consumable", "consumables", "ribbon", "paper roll", "supplies"]):
                cons_res = catalog_tool_executor.execute_tool(
                    "get_compatible_consumables", {"printer_identifier": model_code or product.get("name", "")}
                )
                if cons_res.get("success"):
                    consumable_cards = cons_res.get("consumable_cards", [])

            return RouteResult(
                reply=reply,
                product_cards=cards,
                consumable_cards=consumable_cards,
                source="tool:get_product_specs",
                needs_composition=False,
                evidence=[product],
            )
        else:
            return RouteResult(
                reply=f"I don’t have verified information about '{model_code}' in our authorized Kepler Tech catalog. Would you like me to recommend an authorized Epson or Citizen model that matches your printing needs?",
                suggested_chips=["View Large Format Plotters", "Photo Printers", "Office Enterprise MFPs"],
                source="route:unverified_product",
            )

    # ── Product question on active product ───────────────────────────────
    if state.active_product and not model_code:
        # Check if the user is genuinely asking a question about the active product or making a new inquiry
        is_question_about_active = any(w in (raw_message or "").lower().split() for w in ["it", "this", "its", "that", "speed", "size", "width", "ink", "scanner", "resolution", "specs", "specifications", "how", "what", "does", "can", "price", "cost", "much", "rate"])
        
        if is_question_about_active:
            from catalog.product_spec_engine import product_spec_engine
            active_id = state.active_product.get("id") or state.active_product.get("name")
            single_attr_res = product_spec_engine.answer_single_attribute(active_id, raw_message)
            if single_attr_res:
                return single_attr_res

            product = state.active_product
            p_name = product.get("name", "")
            width = product.get("width", "")
            speed = product.get("speed", "")
            ink = product.get("ink_technology") or product.get("verified", {}).get("ink_technology", "")
            price_str = product.get("price_formatted") or (f"AED {product.get('price'):,.2f}" if product.get("price") else "Price on Request")
            vat = product.get("vat_note") or ("(Excl. VAT)" if (product.get("price") or "AED" in str(price_str)) else "")
            q_lower = (raw_message or "").lower()
            
            reply_parts = [f"Regarding the {p_name}:"]
            if any(k in q_lower for k in ["price", "cost", "how much", "rate"]):
                reply_parts.append(f"The official standard list price is **{price_str}** {vat}.")
            
            if any(w in q_lower for w in ["scanner", "scan", "scanning"]):
                has_scan = product.get("has_scanner") or product.get("verified", {}).get("has_scanner") or ("m" in product.get("id", "").lower() and "t5400" in product.get("id", "").lower())
                if has_scan:
                    reply_parts.append(f"Yes, the {p_name} includes an integrated high-performance scanner for direct scanning, copying, and archiving.")
                else:
                    reply_parts.append(f"No, the {p_name} is a dedicated print-only model without a built-in scanner.")

            if any(w in q_lower for w in ["technology", "inkjet", "thermal", "dye sub", "dyesub", "type of printer"]):
                is_citizen = any(c in p_name.lower() for c in ["citizen", "cx-02", "cx02", "cz-01", "cz01", "cy-02", "cy02"])
                tech = ink or ("Dye-Sublimation Thermal Transfer" if is_citizen else "PrecisionCore MicroTFP")
                if "inkjet" in q_lower:
                    if is_citizen:
                        reply_parts.append(f"No, the {p_name} is not an inkjet printer; it utilizes professional **{tech}** technology with ribbon and paper rolls for lab-grade, instant-dry photo output.")
                    else:
                        reply_parts.append(f"Yes, the {p_name} uses professional **{tech}** inkjet technology.")
                else:
                    reply_parts.append(f"Printing technology: **{tech}**.")

            if any(w in q_lower for w in ["feature", "features", "driver", "benefit", "what can it do"]):
                headings = product.get("feature_headings", [])
                if headings:
                    clean_h = [h for h in headings if not h.lower().startswith("discover") and not h.lower().startswith("product")][:4]
                    reply_parts.append(f"Key features include: {', '.join(clean_h or headings[:4])}.")

            if width and any(w in q_lower for w in ["size", "width", "dimensions", "large", "print size"]):
                reply_parts.append(f"It supports print sizes up to {width}.")
            if speed and any(w in q_lower for w in ["speed", "fast", "ppm", "seconds"]):
                reply_parts.append(f"Print speed: {speed}.")
            
            if any(w in q_lower for w in ["why", "reason", "why this", "advantage", "why choose"]):
                reason = product.get("comparison_highlights") or product.get("recommendation_reason") or product.get("intended_usage") or product.get("description", "")
                reply_parts.append(f"It was recommended because: {reason.rstrip('.')}.")
            
            if any(w in q_lower for w in ["spec", "specs", "specification", "specifications", "description", "overview", "detail", "details", "website"]):
                from catalog.product_spec_engine import product_spec_engine
                detailed = product_spec_engine.get_product_detailed_specs(product.get("id", product.get("sku", "")))
                if detailed:
                    return RouteResult(
                        reply=detailed["reply"],
                        product_cards=[detailed["product_card"]],
                        source="tool:get_product_specs",
                        needs_composition=False,
                        evidence=[product],
                    )

            if len(reply_parts) == 1:
                # General question fallback with verified description
                desc = product.get("description") or product.get("full_description", "")[:250]
                reply_parts.append(desc.rstrip("."))
            
            reply = " ".join(reply_parts)

            cards_to_show = state.candidate_products[:1] if state.candidate_products else [catalog_tool_executor.format_card(product)]
            return RouteResult(
                reply=reply,
                product_cards=cards_to_show,
                source="tool:get_product_specs",
                needs_composition=False,
                evidence=[product],
                instruction=f"Answer the customer's question about {p_name} using the verified specifications: width={width}, speed={speed}, ink={ink}, price={price_str}.",
            )
        else:
            # Active product was from a previous unrelated turn; clear and re-route
            state.active_product = None

    # ── General Website / Specifications Catalog Inquiry ─────────────────
    is_general_spec_lookup = any(phrase in msg_lower for phrase in [
        "description and specifications", "specifications and description",
        "product description", "product specifications", "product specs",
        "find the product description", "find product description",
        "go the website", "go to the website", "go to website",
        "from website", "from the website", "on the website", "check the website",
        "check website", "website specifications"
    ]) or ("specifications" in msg_lower and any(w in msg_lower for w in ["find", "get", "show", "give", "can you", "ai can", "proper answer"]))

    if is_general_spec_lookup and not model_code and not state.active_product:
        return RouteResult(
            reply="Yes, absolutely! I can retrieve verified product descriptions, detailed technical specifications, official PDF datasheets, and live pricing directly from the official Kepler Tech LLC website for any authorized Epson or Citizen model.\n\nWhich product or equipment would you like specifications for?\n• **CAD & Technical Plotters:** Epson SureColor SC-T3100, SC-T5100, SC-T5400M, SC-T5700D\n• **Photo & Fine Art:** Citizen CX-02, CY-02, CZ-01, Epson SureColor P700, P900, P7500\n• **Document Scanners:** Epson WorkForce DS-530II, DS-800WN, Expression 12000XL\n• **Enterprise Office MFPs:** Epson WorkForce Enterprise AM-C4000, AM-C550\n\nYou can specify any model name or code to view its verified overview and specifications!",
            suggested_chips=["Citizen CX-02 Specs", "Epson T5400M Specs", "Epson DS-530II Specs", "Epson AM-C4000 Specs"],
            source="route:product_spec_lookup_prompt",
        )

    is_general_price_query = any(k in msg_lower for k in ["what is the price", "what does it cost", "how much is it", "how much does it cost", "how much", "tell me the price", "what is price"]) and not model_code and not state.active_product and not any(d in msg_lower for d in ["discount", "bargain", "negotiat"])
    if is_general_price_query and not any(w in msg_lower for w in ["recommend", "suggest", "options", "looking for", "want to buy"]):
        return RouteResult(
            reply="Official standard list rates are available for all equipment in our catalog. Which specific model would you like pricing for (e.g., Citizen CX-02, Epson SC-T3100, Epson P700, or DS-530II)?",
            suggested_chips=["Citizen CX-02 Price", "Epson T3100 Price", "Epson P700 Price", "Epson DS-530II Price"],
            source="route:product:price_inquiry",
        )

    # ── Catalog search and Grounded Recommendation ──────────────────────
    from catalog.repository import catalog_repository
    from recommendation.eligibility import eligibility_engine
    from recommendation.ranker import product_ranker
    from recommendation.evidence_builder import build_recommendation_evidence
    from conversation.requirement_extractor import requirement_extractor

    # Extract any fresh requirement updates/corrections from the message
    extracted = requirement_extractor.extract_and_validate(raw_message, state)
    if extracted:
        state.requirements.update(extracted)

    if understanding.requirement_updates:
        for rk, rv in understanding.requirement_updates.items():
            if rv is not None and rv != "":
                if rk == "daily_volume" and isinstance(rv, (int, float)):
                    rv = int(rv)
                state.requirements[rk] = rv
    if understanding.entities:
        for ek in ["print_size", "scan_required", "daily_volume", "speed"]:
            val = understanding.entities.get(ek)
            if val is not None and val != "":
                if ek == "daily_volume" and isinstance(val, (int, float)):
                    val = int(val)
                state.requirements[ek] = val

    # 1. Fetch category candidates
    req_brand = state.requirements.get("brand")
    all_cat_products = catalog_repository.get_by_category(state.category) if state.category else catalog_repository.get_all()
    if req_brand and not any(req_brand.lower() in (p.brand or "").lower() or req_brand.lower() in p.name.lower() for p in all_cat_products):
        # Current category has no models for the requested brand (e.g. Citizen in photo_fine_art)
        brand_prods = [p for p in catalog_repository.get_all() if req_brand.lower() in (p.brand or "").lower() or req_brand.lower() in p.name.lower()]
        if brand_prods:
            all_cat_products = brand_prods
            if brand_prods[0].category:
                state.category = brand_prods[0].category
    elif not all_cat_products:
        all_cat_products = catalog_repository.get_all()


    if req_brand == "Citizen" and state.category == "photo_booth":
        req_size = state.requirements.get("print_size", "")
        if any(w in str(req_size).lower() for w in ["large", "wide", "8x12", "8x10", "a0", "a1", "24-inch", "44-inch"]):
            state.requirements["print_size"] = "8x12 inches"
        elif any(w in str(req_size).lower() for w in ["compact", "small", "mini", "4x6", "5x7", "6x8", "a4", "a3", "a3+"]):
            state.requirements["print_size"] = "4x6 inches"

    # 2. Hard Eligibility Filter
    eligible_assessments = eligibility_engine.filter_candidates(all_cat_products, state.requirements)


    # 3. Deterministic Python Ranking
    ranked_tuples = product_ranker.rank_candidates(eligible_assessments, state.requirements)

    if ranked_tuples:
        top_product, top_score, _ = ranked_tuples[0]

        # ── Double-Check Verification Guard ─────────────────────────
        # Double check 1: Brand compliance
        if req_brand and req_brand.lower() not in (top_product.brand or "").lower() and req_brand.lower() not in top_product.name.lower():
            logger.warning(f"Double check: {top_product.name} violates brand {req_brand}. Finding brand match.")
            for p, score, _ in ranked_tuples:
                if req_brand.lower() in (p.brand or "").lower() or req_brand.lower() in p.name.lower():
                    top_product = p
                    break

        # Double check 2: Category consistency (Never recommend CAD plotter for photo inquiry)
        if ("photo" in (state.category or "").lower() or "booth" in (state.category or "").lower()) and "cad" in (top_product.category or "").lower():
            logger.warning(f"Double check: CAD product {top_product.name} blocked for photo category.")
            photo_candidates = catalog_repository.get_by_category("photo_booth" if req_brand == "Citizen" else "photo_fine_art")
            if photo_candidates:
                top_product = photo_candidates[0]

        state.active_product = top_product.to_dict()
        
        # Build cards
        cards = []
        for p, score, _ in ranked_tuples[:4]:
            cards.append(p.to_dict())
        state.candidate_products = cards

        # 4. Build Grounded Evidence Object
        evidence = [build_recommendation_evidence(top_product, state.requirements, top_score, ["print_size", "scan_required", "application", "daily_volume"])]
        
        cat_name = state.category.replace("_", " ") if state.category else "equipment"
        top_url = top_product.source.website_url or f"https://www.keplertechllc.com/product/{top_product.id}/"
        top_desc = top_product.description or top_product.comparison_highlights or "engineered for reliable, high-precision performance"
        top_highlights = top_product.comparison_highlights
        if not top_highlights and top_desc:
            # Extract first clean human sentence without raw spec dumping
            first_sent = [s.strip() for s in re.split(r'(?<=[.!?])\s+', top_desc) if len(s.strip()) > 15 and not s.startswith("Discover") and "Product Data Sheet" not in s and "Printing Technology:" not in s]
            top_highlights = first_sent[0] if first_sent else top_desc[:120].rstrip(".")

        # Natural, non-robotic formulation tailored to the context
        is_citizen_large = req_brand == "Citizen" and "cx-02w" in top_product.id.lower()
        if is_citizen_large:
            reply = (
                f"For large-format photo printing with Citizen, the top choice is the **[{top_product.name}]({top_url})** — "
                f"{top_highlights.rstrip('.')}. It supports professional **8×10 and 8×12-inch** photo formats (with panoramic prints up to 8×32″). "
                f"*(Note: Citizen specialized dye-sub printers go up to 8×12″; if your workflow requires 24-inch or 44-inch wide gallery rolls, our authorized Epson SureColor P-Series covers those larger formats).* "
                f"You can explore the verified specifications below:"
            )
        elif req_brand == "Citizen":
            reply = f"For compact Citizen photo printing, the recommended model is the **[{top_product.name}]({top_url})** — {top_highlights.rstrip('.')}. Here are the verified specifications and data sheet:"
        elif any(w in (raw_message or "").lower() for w in ["sorry", "instead", "actually", "switch"]):
            reply = f"Understood! For your updated requirements, here is the recommended option: **[{top_product.name}]({top_url})** — {top_highlights.rstrip('.')}. You can explore the verified specifications below:"
        else:
            reply = f"Based on your requirements, the recommended model is the **[{top_product.name}]({top_url})** — {top_highlights.rstrip('.')}. You can explore the verified specifications and official data sheet below:"

        # Prevent duplicate verbatim loop or honor explicit alternative requests
        is_alt_request = any(k in (raw_message or "").lower() for k in [
            "show another", "show another one", "another option", "other option",
            "next option", "different option", "alternative", "another one", "show other"
        ])
        is_repeat_turn = bool(state.last_assistant_response and reply.strip() == state.last_assistant_response.strip())
        is_same_active = bool(state.active_product and top_product.id == (state.active_product.get("id") or state.active_product.get("name")))

        if is_alt_request or is_repeat_turn or (is_alt_request and is_same_active):
            if len(ranked_tuples) > 1:
                alt_product, alt_score, _ = ranked_tuples[1]
                alt_url = alt_product.source.website_url or f"https://www.keplertechllc.com/product/{alt_product.id}/"
                alt_desc = alt_product.description or alt_product.comparison_highlights or "reliable high-performance option"
                alt_highlights = alt_product.comparison_highlights
                if not alt_highlights and alt_desc:
                    first_sent = [s.strip() for s in re.split(r'(?<=[.!?])\s+', alt_desc) if len(s.strip()) > 15 and not s.startswith("Discover") and "Product Data Sheet" not in s and "Printing Technology:" not in s]
                    alt_highlights = first_sent[0] if first_sent else alt_desc[:120].rstrip(".")
                reply = f"Another excellent option matching your criteria is the **[{alt_product.name}]({alt_url})** — {alt_highlights.rstrip('.')}. You can explore the verified specifications below:"
                top_product = alt_product
                state.active_product = alt_product.to_dict()
                cards = [catalog_tool_executor.format_card(alt_product.to_dict(), card_type="hardware")]
                evidence = [alt_product]
            else:
                reply = f"To confirm for your requirements, the **[{top_product.name}]({top_url})** remains the optimal match — {top_highlights.rstrip('.')}. Would you like to check genuine consumables, media rolls, or download the official data sheet?"



        return RouteResult(
            reply=reply,
            product_cards=cards[:1] if len(cards) == 1 or not state.category else cards,
            source="recommendation:grounded_engine",
            needs_composition=False,
            evidence=evidence,
        )
    else:
        state.candidate_products = []
        req_details = []
        if state.requirements.get("print_size"):
            req_details.append(f"print size {state.requirements['print_size']}")
        if state.requirements.get("scan_required") is True:
            req_details.append("integrated scanner")
        elif state.requirements.get("scan_required") is False:
            req_details.append("print-only (no scanner)")
        if state.requirements.get("brand"):
            req_details.append(f"brand {state.requirements['brand']}")
        criteria_str = f" ({', '.join(req_details)})" if req_details else ""
        return RouteResult(
            reply=f"None of our authorized Kepler Tech models simultaneously satisfy all your specified requirements{criteria_str}. Rather than suggesting an incompatible unit, please let me know if you would like to adjust your size or scanner preferences, or contact our sales team at sales@keplertechllc.com for customized equipment options.",
            product_cards=[],
            suggested_chips=["Adjust Requirements", "View All Plotters", "Contact Sales Team"],
            source="recommendation:honest_rejection",
        )

