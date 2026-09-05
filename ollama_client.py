"""
Ollama HTTP Client for conversational generation.
Communicates with http://localhost:11434/api/generate with fallback simulation
adhering strictly to prompt rules when Ollama is offline.
"""

import requests
import json
import logging
from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TIMEOUT_SECONDS

logger = logging.getLogger("ollama_client")


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, default_model: str = DEFAULT_MODEL):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    def check_health(self) -> dict:
        """Checks if Ollama is running and retrieves list of installed models."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                return {
                    "online": True,
                    "models": models,
                    "model_available": self.default_model in models,
                    "active_model": self.default_model,
                    "base_url": self.base_url
                }
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")

        return {
            "online": False,
            "models": [],
            "model_available": False,
            "active_model": self.default_model,
            "base_url": self.base_url,
            "message": "Ollama service offline. Rule-based simulation engine active."
        }

    def generate(self, prompt: str, model: str = None, options: dict = None) -> dict:
        """
        Sends generation request to Ollama /api/generate.
        If Ollama is unreachable, uses fallback engine adhering to prompt guidelines.
        """
        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False
        }
        if options:
            payload["options"] = options

        endpoint = f"{self.base_url}/api/generate"

        try:
            # Use tuple (connect_timeout, read_timeout)
            resp = requests.post(endpoint, json=payload, timeout=(1.5, TIMEOUT_SECONDS))
            if resp.status_code == 200:
                data = resp.json()
                response_text = data.get("response", "").strip()
                return {
                    "success": True,
                    "response": response_text,
                    "source": "ollama",
                    "model": target_model,
                    "total_duration": data.get("total_duration", 0)
                }
            else:
                logger.warning(f"Ollama returned HTTP {resp.status_code}: {resp.text}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ollama connection error: {e}. Utilizing prompt-aligned simulator.")

        # Fallback simulation if Ollama instance is not currently serving the request
        simulated_response = self._simulate_assistant_response(prompt)
        return {
            "success": True,
            "response": simulated_response,
            "source": "simulation_engine",
            "model": f"{target_model} (simulation)",
            "note": "Generated via local fallback simulator because Ollama service is not responding."
        }

    def _simulate_assistant_response(self, prompt: str) -> str:
        """
        Fallback generator aligned with https://www.keplertechllc.com/:
        - Natural, helpful, concise (1-3 sentences)
        - 1 question per turn
        - Strictly adheres to prompt guidelines and commercial rules
        """
        lower = prompt.lower()

        # Extract latest customer message
        customer_msg = ""
        if "Customer:" in prompt:
            lines = [l for l in prompt.split("\n") if l.strip().startswith("Customer:")]
            if lines:
                customer_msg = lines[-1].replace("Customer:", "").strip().lower()

        # Greetings
        if any(w in customer_msg for w in ["hi", "hello", "hey", "good morning", "good afternoon"]) and len(customer_msg.split()) < 5:
            return "Hello! Welcome to Kepler Tech LLC. How can I assist you with your printing solutions or consumable needs today?\n\n[Options: Printers | Scanners | Consumables]"

        # Product Comparisons (Section D Compliance)
        if any(w in customer_msg for w in ["compare", "vs", "versus", "difference between"]):
            if ("t3100" in customer_msg and "t5100" in customer_msg) or ("24" in customer_msg and "36" in customer_msg and "plotter" in customer_msg):
                return (
                    "The Epson SureColor T3100 is a compact 24-inch (A1) plotter suitable for desktop use in smaller studios, "
                    "whereas the SureColor T5100 accommodates full 36-inch (A0) drawings with a standard floor stand and roll feed. "
                    "Does your firm require 36-inch wide drawings, or is 24-inch A1 sufficient for your plans?"
                )
            if ("cx-02" in customer_msg or "cx02" in customer_msg) and ("cy-02" in customer_msg or "cy02" in customer_msg):
                return (
                    "The Citizen CX-02 is an ultra-portable 12 kg dye-sub printer with ribbon rewind for mobile event photography, "
                    "while the heavy-duty Citizen CY-02 features a high-capacity 700-print roll to minimize changeovers in fixed booths. "
                    "Are you running a mobile event business or a permanent high-traffic photo booth?"
                )
            if ("c4000" in customer_msg or "am-c4000" in customer_msg) and ("c550" in customer_msg or "am-c550" in customer_msg):
                return (
                    "The Epson WorkForce AM-C4000 is an A3 enterprise MFP printing at 40 ppm with a 5,150-sheet capacity and optional booklet finisher, "
                    "whereas the AM-C550 provides faster 55 ppm printing in a compact A4 footprint. "
                    "Do your office workflows require A3 document printing, or is fast A4 handling your main priority?"
                )
            if ("p700" in customer_msg and "p900" in customer_msg) or ("13" in customer_msg and "17" in customer_msg and "photo" in customer_msg):
                return (
                    "Both printers feature the 10-color UltraChrome PRO10 ink set with no black switching, "
                    "but the P700 prints up to 13 inches (A3+) using 25ml cartridges, while the P900 prints up to 17 inches (A2+) with 50ml tanks. "
                    "What is the largest paper size you intend to produce for your portfolio or gallery exhibits?"
                )
            if ("ifa 11" in customer_msg or "ifa11" in customer_msg) and ("ifa 13" in customer_msg or "ifa13" in customer_msg):
                return (
                    "Innova IFA 11 Photo Cotton Rag 315gsm features an ultra-smooth matte surface for crisp photographic detail, "
                    "whereas Innova IFA 13 Cold Press offers a traditional rough watercolor texture for tactile fine art replicas. "
                    "Which surface texture best complements your artwork or photography?"
                )

        # Detailed Technical Specifications Inquiries
        if any(w in customer_msg for w in ["spec", "specs", "specification", "resolution", "dpi", "print speed", "technical detail"]):
            if "t3100" in customer_msg or ("24" in customer_msg and "plotter" in customer_msg):
                return "The Epson SureColor T3100 offers 2400 x 1200 dpi resolution, produces an A1 CAD print in 34 seconds, and uses archival UltraChrome XD2 pigment inks (up to 80ml). Would you like details on paper roll loading or network connectivity?"
            if "t5100" in customer_msg or ("36" in customer_msg and "plotter" in customer_msg):
                return "The Epson SureColor T5100 supports 36-inch media at 2400 x 1200 dpi, prints an A1 drawing in 31 seconds, and includes a heavy-duty floor stand with catch basket. What type of technical drawings or maps will you primarily print?"
            if "p900" in customer_msg or "p700" in customer_msg:
                return "The Epson SureColor P900 produces gallery-grade prints up to 17 inches wide at 5760 x 1440 dpi with 10-color UltraChrome PRO10 inks including Violet and Carbon Black mode. Are you printing on roll media or fine art cut sheets?"
            if "am-c4000" in customer_msg or "c4000" in customer_msg:
                return "The Epson WorkForce Enterprise AM-C4000 delivers 40 ppm using Heat-Free PrecisionCore technology, holds up to 5,150 sheets, and supports single-pass duplex scanning at 120 ipm. Do you require stapling or booklet-making finishing accessories?"
            if "f100" in customer_msg or "sc-f100" in customer_msg:
                return "The Epson SureColor SC-F100 is an A4 desktop dye-sublimation printer featuring refillable 140ml ink bottles and UltraChrome DS inks, designed for personalized gifts, mugs, and small promotional items. What type of merchandise are you planning to sublimate?"
            if "f500" in customer_msg or "sc-f500" in customer_msg:
                return "The Epson SureColor SC-F500 is a 24-inch dye-sublimation roll printer using refillable UltraChrome DS ink tanks, ideal for sportswear, soft signage, and apparel printing. Are you printing roll textiles or cut-sheet transfers?"
            if "cx-02" in customer_msg:
                return "The Citizen CX-02 weighs 12 kg, produces a 4x6 print in 13.8 seconds, supports both glossy and matte finishes from the same roll, and features ribbon rewind to prevent media waste. Will this printer be integrated into a mobile flight case or a desktop kiosk?"

        # Contact / Hours / Location from https://www.keplertechllc.com/
        if any(w in customer_msg for w in ["hour", "time", "timing", "open", "working hours"]):
            return "Our office is open Monday through Friday from 8:30 AM to 5:30 PM, and Saturday from 8:30 AM to 1:00 PM (closed on Sunday). What equipment or media are you looking for today?"

        if any(w in customer_msg for w in ["where", "location", "address", "dubai", "office"]):
            return "We are located at D79, Khalid Bin Waleed Road, Office No. 1, Abdulla Al Awar Building in Dubai, and provide fast delivery across the UAE and Middle East. How may I help with your project?"

        if any(w in customer_msg for w in ["phone", "contact", "call", "email", "whatsapp"]):
            return "You can reach our team at +971 4 323 1008 or +971 55 835 8586, and by email at info@keplertech.ae or sales@keplertech.ae. What type of printing or consumable requirement do you have?"

        # CAD / Technical Plotters (Epson SureColor T-Series)
        if any(w in customer_msg for w in ["cad", "gis", "blueprint", "architect", "engineering", "plotter"]):
            return "For technical CAD and architectural drawings, high line precision and fast output are essential. What maximum paper width do you require, such as 24-inch (A1) or 36-inch (A0)?"

        if "a1" in customer_msg or "24 inch" in customer_msg or "24-inch" in customer_msg:
            return "An A1 24-inch technical plotter like the Epson SureColor T3100 series provides high-precision line accuracy with UltraChrome XD2 pigment inks. Would you prefer a desktop model or a floor stand with a catch basket?"

        if "a0" in customer_msg or "36 inch" in customer_msg or "36-inch" in customer_msg:
            return "For 36-inch A0 technical drawings, the Epson SureColor T5100 and T5400 series deliver high-speed, smudge-resistant printing for busy engineering teams. Do you also require an integrated large-format scanner for plan revisions?"

        # Photo & Fine Art (Epson SureColor P-Series & Citizen Dye-Sub)
        if any(w in customer_msg for w in ["photo", "fine art", "gallery", "photography", "portrait"]):
            if any(w in customer_msg for w in ["booth", "event", "instant", "passport"]):
                return "For instant event photography and photo booths, our Citizen CX-02 and CY-02 dye-sublimation printers produce durable, laminated prints in seconds. What print sizes do you need to offer, such as 4x6 or 6x8 inches?"
            return "For gallery-grade photography and fine art reproductions, our Epson SureColor P-Series printers feature up to 12-color UltraChrome PRO ink sets for unmatched tonal gradation. Are you looking for a compact desktop model like the P700/P900 or a 24-to-44 inch production printer?"

        # High-Speed Office / Enterprise (WorkForce Enterprise AM-C4000 / AM-C550)
        if any(w in customer_msg for w in ["office", "copier", "enterprise", "workforce", "business printer", "high volume"]):
            return "For corporate and high-volume office workflows, the Epson WorkForce Enterprise AM-C4000 and AM-C550 deliver 40 to 55 ppm using Heat-Free PrecisionCore technology with minimal maintenance. Do you need advanced finishing options such as stapling or booklet making?"

        # Fine Art Media & Paper (Innova Art / Olmec)
        if any(w in customer_msg for w in ["paper", "media", "cotton rag", "canvas", "luster", "lustre", "pearl", "innova", "olmec"]):
            return "We supply premium media including Innova Photo Cotton Rag 315gsm, Cold Press Natural White, and Olmec Photo Lustre and Pearl papers. Which surface finish and weight best match your artwork or photography?"

        # Consumables / Inks / Maintenance Boxes
        if any(w in customer_msg for w in ["ink", "cartridge", "maintenance box", "printhead", "ribbon", "consumable", "supplies", "tank"]):
            if "f100" in customer_msg or "sc-f100" in customer_msg:
                return "For the Epson SureColor SC-F100, we supply genuine 140ml UltraChrome DS dye-sublimation ink bottles (T49N series: Cyan, Magenta, Yellow, Black) and the C13S210125 maintenance box. Are you looking to order a complete CMYK set or specific replacement colors?"
            if "f500" in customer_msg or "sc-f500" in customer_msg:
                return "For the Epson SureColor SC-F500, we supply 140ml UltraChrome DS dye-sublimation inks (T49N series) and the C13S210057 desktop maintenance box. Are you printing roll media or sheet transfers?"
            if "p900" in customer_msg or "sc-p900" in customer_msg:
                return "For the Epson SureColor SC-P900, we supply genuine 10-color UltraChrome PRO10 ink cartridges (T47A series, 50ml) and the C12C935711 maintenance tank. Are you looking for individual replacement shades or a complete cartridge set?"
            if "p700" in customer_msg or "sc-p700" in customer_msg:
                return "For the Epson SureColor SC-P700, we supply genuine 10-color UltraChrome PRO10 ink cartridges and the C12C935711 maintenance tank. Which ink channels do you need to replenish?"
            if "t3100" in customer_msg or "t5100" in customer_msg:
                return "For the Epson SureColor T3100 and T5100 CAD plotters, we supply genuine UltraChrome XD2 archival pigment inks (T40C standard / T40D high-capacity) and the C13S210057 maintenance box. Do you need high-capacity 80ml black or 50ml color cartridges?"
            if "t3400" in customer_msg or "t5400" in customer_msg:
                return "For the Epson SureColor T3400 and T5400, we supply UltraChrome XD2 inks (T41R 110ml / T41F 350ml) and the C13S210057 maintenance box. What cartridge capacities best fit your monthly CAD volume?"
            if "p7500" in customer_msg or "p9500" in customer_msg:
                return "For the Epson SureColor SC-P7500 and SC-P9500, we supply 12-color UltraChrome PRO12 700ml high-capacity ink cartridges (T44J series) and the C13S210115 borderless maintenance tank. Are you looking for photographic or fine art media profiles as well?"
            if any(m in customer_msg for m in ["p6000", "p7000", "p8000", "p9000"]):
                return "For the Epson SureColor P6000/P7000/P8000/P9000 series, we supply genuine UltraChrome HD and HDX 350ml (T824) and 700ml (T804) ink cartridges and the C13T699700 maintenance box. Which cartridge size suits your production workflow?"
            if "am-c4000" in customer_msg or "c4000" in customer_msg:
                return "For the Epson WorkForce Enterprise AM-C4000, we supply genuine high-yield T08H series ink cartridges (Black, Cyan, Magenta, Yellow) and the C12C937181 maintenance box. Do you require black or color replacement cartridges?"
            if "am-c550" in customer_msg or "c550" in customer_msg or "am-c400" in customer_msg:
                return "For the Epson WorkForce Enterprise AM-C550 and AM-C400, we supply genuine high-yield ink supplies and the C12C937201 maintenance box. Which items do you need to replenish?"
            if "cx-02" in customer_msg or "cx02" in customer_msg:
                return "For the Citizen CX-02 digital photo printer, we supply genuine Citizen CX-02 dye-sub media packs (4x6 and 6x8 paper with matching ribbon rolls) and thermal head cleaning pens. Which print dimensions are you configuring for your setup?"
            if "cy-02" in customer_msg or "cy02" in customer_msg:
                return "For the Citizen CY-02, we supply genuine CY-MS46 (4x6) and CY-MS68 (6x8) media packs with ribbon and carry bags. What event print sizes are you preparing for?"
            if "cz-01" in customer_msg or "cz01" in customer_msg:
                return "For the Citizen CZ-01, we supply genuine 4x6 (CZ-MS46) and 4.5x8 (CZ-MS458) dye-sub media packs and travel carry cases. Will this printer be used for on-location mobile events?"
            return "We supply genuine Epson UltraChrome ink cartridges, Citizen dye-sub print media packs, and Epson maintenance boxes. Which printer model do you currently operate?"

        # Software (Mirage / AirCastPro / Adobe)
        if any(w in customer_msg for w in ["mirage", "software", "rip", "aircastpro", "workflow"]):
            return "We offer Mirage by DINAX for professional RIP and color management workflows, as well as AirCastPro wireless print servers for event photography. Which printers are you planning to connect with the software?"

        # Troubleshooting
        if any(w in customer_msg for w in ["error", "jam", "line", "streak", "head", "clog", "faint", "not working", "blurry"]):
            return "To troubleshoot print quality issues, we recommend first performing an automated nozzle check and head cleaning through the printer utility menu. Have you already tested a nozzle check pattern?"

        # Endings
        if any(w in customer_msg for w in ["thank you", "thanks", "bye", "goodbye", "that's all", "that is all"]):
            return "Thank you for contacting Kepler Tech LLC! Please feel free to reach out whenever you need further assistance with your printing equipment or media."

        # Default discovery
        return "I would be glad to help you find the ideal printing solution from Kepler Tech LLC. Could you tell me what specific print applications or workload you are looking to support?"
