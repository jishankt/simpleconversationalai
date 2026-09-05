"""
Verified Ground Truth Knowledge Base for Kepler Tech LLC.
Extracted from https://www.keplertechllc.com/.
Used for zero-hallucination verification and factual response grounding.
"""

COMPANY_PROFILE = {
    "name": "Kepler Tech LLC",
    "business_type": "Dubai's #1 Printer, Inkjet Media & Consumables Supplier & Authorized Distributor",
    "address": "D79, Khalid Bin Waleed Road, Office No. 1, Abdulla Al Awar Building, Dubai, United Arab Emirates",
    "phones": ["+971 4 323 1008", "+971 55 835 8586"],
    "emails": ["sales@keplertech.ae", "info@keplertech.ae"],
    "hours": {
        "weekdays": "Monday – Friday: 8:30 AM to 5:30 PM",
        "saturday": "Saturday: 8:30 AM to 1:00 PM",
        "sunday": "Closed"
    },
    "service_regions": "United Arab Emirates and fast delivery across Middle East"
}

# Verified Products & Hardware Catalog
VERIFIED_PRODUCTS = {
    "cad_plotters": [
        {
            "brand": "Epson",
            "series": "SureColor T-Series",
            "model": "Epson SureColor T3100 / T3100N",
            "category": "Technical CAD/GIS Plotter",
            "size": "24-inch (A1)",
            "ink": "UltraChrome XD2 pigment ink (Black, Cyan, Magenta, Yellow)",
            "resolution": "2400 x 1200 dpi",
            "intended_use": "Architectural blueprints, line drawings, engineering CAD/GIS, construction plans",
            "features": "Compact desktop or stand option, wireless printing, high line accuracy, fast A1 print in 34 seconds."
        },
        {
            "brand": "Epson",
            "series": "SureColor T-Series",
            "model": "Epson SureColor T5100",
            "category": "Technical CAD/GIS Plotter",
            "size": "36-inch (A0)",
            "ink": "UltraChrome XD2 pigment ink",
            "resolution": "2400 x 1200 dpi",
            "intended_use": "Large-format AEC plans, full-size blueprints, municipal maps",
            "features": "Floor stand included, roll and cut-sheet feed, auto-switching, Wi-Fi Direct."
        },
        {
            "brand": "Epson",
            "series": "SureColor T-Series",
            "model": "Epson SureColor T5400 / T5400M",
            "category": "Technical CAD/GIS Multifunction Plotter",
            "size": "36-inch (A0)",
            "ink": "UltraChrome XD2 high-capacity cartridges (up to 350ml)",
            "resolution": "2400 x 1200 dpi",
            "intended_use": "High-volume architectural firms, construction site offices requiring scan-to-print/email",
            "features": "Integrated 36-inch scanner on M-series, borderless printing, high security PCL/HP-GL support."
        }
    ],
    "photo_fine_art": [
        {
            "brand": "Epson",
            "series": "SureColor P-Series",
            "model": "Epson SureColor P700",
            "category": "Professional Photo Printer",
            "size": "13-inch (A3+)",
            "ink": "UltraChrome PRO10 (10 colors with Violet, dedicated Photo and Matte Black channels)",
            "intended_use": "Fine art photographers, gallery proofs, portrait studios",
            "features": "Carbon Black Mode for D-Max, roll paper unit included, touch screen."
        },
        {
            "brand": "Epson",
            "series": "SureColor P-Series",
            "model": "Epson SureColor P900",
            "category": "Professional Photo Printer",
            "size": "17-inch (A2+)",
            "ink": "UltraChrome PRO10 (10 colors with Violet)",
            "intended_use": "Exhibition printing, photographic portfolios, graphic artists",
            "features": "Ultra-compact footprint, sheet feeder and roll media support."
        },
        {
            "brand": "Epson",
            "series": "SureColor P-Series",
            "model": "Epson SureColor P7500 / P9500",
            "category": "Production Fine Art & Proofing Printer",
            "size": "24-inch (P7500) / 44-inch (P9500)",
            "ink": "UltraChrome PRO12 (12 colors with Orange, Green, Violet)",
            "intended_use": "Commercial photo labs, contract proofing, museum reproductions",
            "features": "PrecisionCore MicroTFP printhead, 99% Pantone coverage, SpectroProofer option."
        }
    ],
    "office_enterprise": [
        {
            "brand": "Epson",
            "series": "WorkForce Enterprise",
            "model": "Epson WorkForce Enterprise AM-C4000",
            "category": "Enterprise Color Multifunction Inkjet Copier",
            "speed": "40 ppm (ISO)",
            "capacity": "5,150-sheet maximum paper capacity",
            "intended_use": "Corporate departments, government entities, educational campuses",
            "features": "PrecisionCore Heat-Free technology, dual-head single-pass duplex scanning up to 120 ipm, stapling & booklet finisher, low power consumption."
        },
        {
            "brand": "Epson",
            "series": "WorkForce Enterprise",
            "model": "Epson WorkForce AM-C550",
            "category": "Compact High-Speed A4 Color MFP",
            "speed": "55 ppm (ISO)",
            "intended_use": "Fast-paced office workgroups needing rapid first page out",
            "features": "10.1-inch color touchscreen, Energy Star qualified, high-yield ink cartridges."
        },
        {
            "brand": "Epson",
            "series": "WorkForce Pro",
            "model": "Epson WorkForce Pro WF-C879R D3TWFC",
            "category": "A3 Multifunction Business Inkjet",
            "yield": "Up to 86,000 mono / 50,000 color pages per Replaceable Ink Pack System (RIPS)",
            "intended_use": "Mid-to-large offices seeking low intervention and ultra-high yields",
            "features": "DURABrite Pro pigment inks, 4-tray paper feeding, rear bypass feed."
        }
    ],
    "dye_sub_photo": [
        {
            "brand": "Citizen",
            "model": "Citizen CX-02 / CX-02S",
            "category": "Dye-Sublimation Event Photo Printer",
            "sizes": "4x6, 6x8 inches (ribbon + media rolls)",
            "intended_use": "Event photography, photo booths, retail kiosks, passport and ID studios",
            "features": "Ultra-compact and lightweight (12kg), ribbon rewind function, glossy and matte finishes without changing paper, fast 13-second 4x6 print."
        },
        {
            "brand": "Citizen",
            "model": "Citizen CY-02",
            "category": "High-Capacity Dye-Sublimation Photo Printer",
            "sizes": "4x6, 5x7, 6x8 inches (700 prints per roll)",
            "intended_use": "Fixed photo booths, amusement parks, high-volume event operators",
            "features": "Heavy-duty steel chassis, drop-in paper loading, high reliability."
        }
    ],
    "fine_art_media": [
        {
            "brand": "Innova Art",
            "code": "IFA 11",
            "name": "Innova Photo Cotton Rag 315gsm",
            "surface": "Ultra smooth natural white, 100% cotton, acid-free and lignin-free",
            "intended_use": "Archival fine art reproductions, museum exhibitions, high-end portfolios"
        },
        {
            "brand": "Innova Art",
            "code": "IFA 13",
            "name": "Innova Cold Press Rough Textured Natural White 315gsm",
            "surface": "Traditional rough watercolor texture, natural white, 100% cotton",
            "intended_use": "Fine art watercolor reproductions, limited edition prints"
        },
        {
            "brand": "Olmec",
            "code": "OLM 68",
            "name": "Olmec Photo Lustre Lightweight 190gsm",
            "surface": "Resin-coated softly stippled lustre finish, instant dry",
            "intended_use": "Commercial photo printing, school portraits, proofs"
        },
        {
            "brand": "Olmec",
            "code": "OLM 70",
            "name": "Olmec Photo Pearl Premium 310gsm",
            "surface": "Heavyweight resin-coated microporous pearl with silky sheen",
            "intended_use": "Wedding albums, studio photography, exhibition prints"
        }
    ],
    "software": [
        {
            "name": "Mirage by DINAX",
            "type": "Professional RIP & Print Workflow Software",
            "benefits": "Precise color management, automated nesting, soft-proofing, seamless Photoshop & Illustrator plugin."
        },
        {
            "name": "AirCastPro",
            "type": "Wireless Photo Print Server",
            "benefits": "Instant Apple AirPrint and Android printing directly to Citizen and DNP dye-sub printers for event photo booths."
        }
    ]
}


def get_verified_facts_summary() -> str:
    """Returns a dense factual summary of verified products to ground the AI model."""
    summary_lines = [
        "VERIFIED KEPLER TECH HARDWARE & MEDIA CATALOG:",
        "- CAD/GIS Plotters: Epson SureColor T3100 (24-in A1 desktop/stand), T5100 (36-in A0 stand), T5400/T5400M (36-in with MFP scanner). Pigment XD2 inks.",
        "- Fine Art & Photo: Epson SureColor P700 (13-in A3+ PRO10), P900 (17-in A2+ PRO10), P7500 (24-in PRO12 12-color), P9500 (44-in PRO12 12-color).",
        "- Enterprise Office: Epson WorkForce Enterprise AM-C4000 (40 ppm Heat-Free, 5,150 sheets), AM-C550 (55 ppm A4), WF-C879R (RIPS up to 86k mono / 50k color).",
        "- Dye-Sub Photo Booths: Citizen CX-02 (compact 12kg, 4x6 / 6x8 in 13s, ribbon rewind), CY-02 (700 prints/roll high-capacity).",
        "- Fine Art Paper: Innova IFA 11 (Cotton Rag 315gsm smooth), IFA 13 (Cold Press Rough 315gsm), Olmec OLM 68 (Lustre 190gsm), OLM 70 (Pearl 310gsm).",
        "- Software: Mirage by DINAX (RIP workflow), AirCastPro (wireless print server for photo booths).",
        "- Office: D79, Khalid Bin Waleed Rd, Dubai. Mon-Fri 8:30AM-5:30PM, Sat 8:30AM-1PM. Tel: +971 4 323 1008. Email: sales@keplertech.ae."
    ]
    return "\n".join(summary_lines)
