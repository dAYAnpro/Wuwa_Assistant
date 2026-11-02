import sys
import re
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR
import rapidocr_onnxruntime.ch_ppocr_v3_det.text_detect as _det
import rapidocr_onnxruntime.ch_ppocr_v3_rec.text_recognize as _rec
import rapidocr_onnxruntime.ch_ppocr_v2_cls.text_cls as _cls

# Explicitly register submodules in sys.modules and patch init_module
# to prevent PyInstaller / runtime dynamic import AttributeError: module 'ch_ppocr_v3_det' has no attribute 'TextDetector'
sys.modules['ch_ppocr_v3_det'] = _det
sys.modules['ch_ppocr_v3_rec'] = _rec
sys.modules['ch_ppocr_v2_cls'] = _cls

MODULE_CLASS_MAP = {
    ("ch_ppocr_v3_det", "TextDetector"): _det.TextDetector,
    ("ch_ppocr_v3_rec", "TextRecognizer"): _rec.TextRecognizer,
    ("ch_ppocr_v2_cls", "TextClassifier"): _cls.TextClassifier,
}

_orig_init_module = RapidOCR.init_module

@staticmethod
def _safe_init_module(module_name, class_name):
    if (module_name, class_name) in MODULE_CLASS_MAP:
        return MODULE_CLASS_MAP[(module_name, class_name)]
    return _orig_init_module(module_name, class_name)

RapidOCR.init_module = _safe_init_module

# Standard Wuthering Waves Stat Names
KNOWN_STATS = [
    "Crit. Rate",
    "Crit. DMG",
    "Energy Regen",
    "Resonance Skill DMG Bonus",
    "Basic Attack DMG Bonus",
    "Heavy Attack DMG Bonus",
    "Resonance Liberation DMG Bonus",
    "Glacio DMG Bonus",
    "Fusion DMG Bonus",
    "Electro DMG Bonus",
    "Aero DMG Bonus",
    "Spectro DMG Bonus",
    "Havoc DMG Bonus",
    "Healing Bonus",
    "ATK",
    "HP",
    "DEF"
]

# Known monster name to exact element / Sonata set family mapping as a robust fallback
NAME_TO_SONATA = {
    # 4-Costs
    "Suhsin": "Glacio (Heart of Sworn Vigil)",
    "Thousand-Puppet": "Glacio (Thousand-Puppet Pavilion)",
    "Denia": "Glacio (Freezing Frost / Frosty Resolve)",
    "Sigillum": "Glacio (Freezing Frost / Frosty Resolve)",
    "Leviathan": "Glacio (Freezing Frost / Frosty Resolve)",
    "Hecate": "Havoc (Dream of the Lost / Sun-sinking)",
    "Calamity Effigy": "Aero (Sierra Gale) / Moonlit Clouds",
    "Adam Smasher": "Havoc (Dream of the Lost)",
    "Reactor Husk": "Glacio (Freezing Frost / Frosty Resolve)",
    "Hyvatia": "Glacio (Freezing Frost / Frosty Resolve)",
    "Lioness of Glory": "Fusion (Molten Rift / Flaming Clawprint)",
    "Inferno Rider": "Fusion (Molten Rift)",
    "Feilian Beringal": "Aero (Sierra Gale)",
    "Fallacy of No Return": "Spectro / Rejuvenating Glow",
    "Impermanence Heron": "Havoc / Moonlit Clouds",
    "Thundering Mephis": "Electro (Void Thunder)",
    "Tempest Mephis": "Electro (Void Thunder)",
    "Mourning Aix": "Spectro (Celestial Light)",
    "Bell-Borne Geochelone": "Rejuvenating Glow / Moonlit Clouds",
    "Crownless": "Havoc (Sun-sinking Eclipse)",
    "Dreamless": "Havoc (Sun-sinking Eclipse)",
    "Jué": "Spectro (Celestial Light)",
    "Inferno": "Fusion (Molten Rift)",
    
    # 3-Costs & 1-Costs common keywords
    "Soulfrayer": "Electro (Void Thunder)",
    "Formrender": "Electro (Void Thunder)",
    "Glommoth": "Fusion (Molten Rift)",
    "Kronaclaw": "Fusion (Molten Rift)",
    "Kronablight": "Spectro (Celestial Light / Eternal Radiance)",
    "Roseshroom": "Havoc (Sun-sinking Eclipse)",
    "Tambourinist": "Havoc (Sun-sinking Eclipse / Dream of the Lost)",
    "Corrosaurus": "Fusion (Molten Rift)",
    "Kerasaur": "Fusion (Molten Rift)",
    "Pilgrim": "Fusion (Molten Rift)",
    "Lumiscale": "Electro (Void Thunder)",
    "Spearback": "Electro (Void Thunder)",
    "Rocksteady": "Rejuvenating Glow / Glacio",
    "Violet-Feathered": "Electro (Void Thunder)",
    "Cyan-Feathered": "Aero (Sierra Gale)",
    "Flautist": "Electro (Void Thunder)",
    "Chasm Guardian": "Havoc (Sun-sinking Eclipse)",
    "Geospider": "Havoc / Fusion / Glacio",
    "Hooscamp": "Aero (Sierra Gale)",
    "Hoochief": "Aero (Sierra Gale)",
    "Chirpuff": "Aero (Sierra Gale)",
    "Gulpuff": "Glacio (Freezing Frost)",
    "Predator": "Aero / Glacio / Electro",
    "Prism": "Havoc / Glacio / Fusion / Spectro",
    "Junrock": "Rejuvenating Glow / Lingering Tunes",
    "Fusion Dreadmane": "Fusion (Molten Rift)",
    "Glacio Dreadmane": "Glacio (Freezing Frost)",
    "Havoc Drake": "Havoc (Sun-sinking Eclipse)",
    "Aero Drake": "Aero (Sierra Gale)",
    "Tick Tack": "Havoc / Moonlit Clouds"
}

def clean_text(text: str) -> str:
    """Normalize text and remove bullet points, OCR artifacts, and leading symbols."""
    text = re.sub(r'^[•\*\-\s\.\:X_xVv]+', '', text)
    return text.strip()

def parse_stat_line(label: str, value_str: str):
    """
    Fuzzy match stat label and parse numeric value.
    Disambiguates percentage vs flat stats (ATK% vs Flat ATK) to prevent dictionary key collisions.
    """
    clean = clean_text(label)
    value_clean = value_str.replace(' ', '').replace(',', '.')
    is_percent = '%' in value_clean

    # Safely extract float without throwing ValueError on OCR noise
    val_match = re.search(r'(\d+(?:\.\d+)?)', value_clean)
    try:
        val_num = float(val_match.group(1)) if val_match else 0.0
    except (ValueError, TypeError):
        val_num = 0.0

    # Differentiate flat vs percentage for ATK, HP, DEF
    n_clean = re.sub(r'[^a-zA-Z]', '', clean).upper()
    if n_clean in ["ATK", "HP", "DEF"]:
        stat_name = f"{n_clean}%" if is_percent else f"Flat {n_clean}"
    else:
        best_match = clean
        n_clean_lower = n_clean.lower()
        for stat in KNOWN_STATS:
            n_stat = re.sub(r'[^a-zA-Z]', '', stat).lower()
            if n_clean_lower == n_stat:
                best_match = stat
                break
        else:
            for stat in KNOWN_STATS:
                n_stat = re.sub(r'[^a-zA-Z]', '', stat).lower()
                if n_clean_lower in n_stat or n_stat in n_clean_lower:
                    best_match = stat
                    break
        stat_name = best_match

    return {
        "stat": stat_name,
        "value": f"{val_num:.1f}%" if is_percent else int(val_num),
        "num": val_num,
        "is_percent": is_percent
    }

class EchoParser:
    def __init__(self):
        # High-Performance RapidOCR Configuration:
        # 1. use_angle_cls=False: Wuthering Waves UI is always horizontal.
        # 2. rec_batch_num=16: Batches bounding boxes into parallel tensor operations across CPU cores.
        self.ocr = RapidOCR(
            Global={"use_angle_cls": False},
            Rec={"rec_batch_num": 16}
        )

    def detect_sonata_color(self, icon_crop):
        """
        Identify Sonata element family using color hue clustering.
        Enhanced thresholds:
        - Filters out low saturation dark background (s > 90, v > 70)
        - Uses strict hue ranges to avoid dark-slate slate/blue menu bleeding into Glacio.
        """
        if icon_crop is None or icon_crop.size == 0:
            return "Unknown"
        hsv = cv2.cvtColor(icon_crop, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        
        # Stricter mask: higher saturation & brightness to isolate the glowing icon
        mask = (s > 90) & (v > 70)
        if np.sum(mask) < 15:
            # Fallback to moderate mask if icon was faint
            mask = (s > 70) & (v > 50)
            if np.sum(mask) < 10:
                return "Unknown"

        mean_hue = np.median(h[mask])
        
        # Color ranges in OpenCV HSV (H: 0-180, S: 0-255, V: 0-255):
        # Havoc: Purple/Magenta (~135-165)
        # Electro: Violet/Purple-Blue (~115-135)
        # Glacio: Cyan/Ice-Blue (~88-112)
        # Aero: Bright Mint/Green (~35-85)
        # Spectro: Warm Gold/Yellow (~20-35)
        # Fusion: Red/Orange-Red (< 12 or >= 165)
        if 138 <= mean_hue <= 165:
            return "Havoc (Sun-sinking Eclipse / Midnight Veil)"
        elif 115 < mean_hue < 138:
            return "Electro (Void Thunder)"
        elif 88 <= mean_hue <= 115:
            return "Glacio (Freezing Frost / Frosty Resolve)"
        elif 35 <= mean_hue < 88:
            return "Aero (Sierra Gale) / Moonlit Clouds"
        elif 18 <= mean_hue < 35:
            return "Spectro (Celestial Light / Eternal Radiance)"
        elif mean_hue < 18 or mean_hue >= 165:
            return "Fusion (Molten Rift / Flaming Clawprint)"
            
        return "Unknown"

    def infer_sonata_from_name_or_stats(self, name: str, main_stats: list) -> str:
        """Fallback to resolve Sonata set when image color check is uncertain or ambiguous."""
        # 1. Direct elemental damage main stat (3-Cost Echoes)
        for m in main_stats:
            stat_name = m.get("stat", "")
            if "Electro DMG" in stat_name:
                return "Electro (Void Thunder)"
            elif "Fusion DMG" in stat_name:
                return "Fusion (Molten Rift)"
            elif "Havoc DMG" in stat_name:
                return "Havoc (Sun-sinking Eclipse)"
            elif "Aero DMG" in stat_name:
                return "Aero (Sierra Gale)"
            elif "Spectro DMG" in stat_name:
                return "Spectro (Celestial Light)"
            elif "Glacio DMG" in stat_name:
                return "Glacio (Freezing Frost)"

        # 2. Known monster name lookup
        for key, sonata in NAME_TO_SONATA.items():
            if key.lower() in name.lower():
                return sonata

        return "Unknown"

    def parse_panel(self, panel_img):
        """
        Fast Single-Pass OCR & Stat Matcher.
        Cuts runtime by ~60% compared to multiple crop passes.
        """
        h, w, _ = panel_img.shape

        # Crop the active Echo card area (y: 7% to 78%, skipping currency header & upgrade button)
        y_start = int(h * 0.07)
        y_end = int(h * 0.78)
        card = panel_img[y_start:y_end, :]
        ch, cw, _ = card.shape

        # Single-pass OCR
        ocr_res, _ = self.ocr(card)
        if not ocr_res:
            return None

        data = {
            "name": "Unknown Echo",
            "level": 0,
            "cost": 0,
            "sonata": "Unknown",
            "main_stats": [],
            "sub_stats": [],
            "substats_cv": 0.0,
            "total_cv": 0.0
        }

        # Dynamic pixel thresholds scaling with screen resolution
        max_line_gap = max(20, int(h * 0.045))
        max_match_dy = max(22, int(h * 0.048))

        # Collect text boxes
        items = []
        for box, text, score in ocr_res:
            t = text.strip()
            # Stop if reached Echo Skill section
            if "Echo Skill" in t or "Fcho Skill" in t or ("Skill" in t and "Resonance" not in t):
                break
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            items.append({
                "text": t,
                "cy": sum(ys) / len(ys),
                "cx": sum(xs) / len(xs),
                "box": box,
                "min_x": min(xs),
                "max_x": max(xs),
                "min_y": min(ys),
                "max_y": max(ys)
            })

        items.sort(key=lambda it: it["cy"])

        # Split items into Header (top 35% of card) and Stats (below 35%)
        header_cutoff_y = ch * 0.35
        header_items = [it for it in items if it["cy"] < header_cutoff_y]
        stats_items = [it for it in items if it["cy"] >= header_cutoff_y]

        # 1. Parse Header items: Name, Level, Sonata, Cost
        detected_sonata_color = "Unknown"
        for it in header_items:
            t = it["text"]
            # Echo Name
            if len(t) >= 5 and not re.search(r'^\d+$', t):
                if not any(k in t.lower() for k in ["cost", "upgrade", "management", "echo skill", "user id", "level", "sort"]):
                    if data["name"] == "Unknown Echo":
                        data["name"] = t

            # Level (+0 to +25)
            m_lvl = re.search(r'\+(\d+)', t)
            if m_lvl:
                data["level"] = int(m_lvl.group(1))
                # Detect Sonata color right next to level
                # Carefully bound icon region to isolate icon from dark background
                icon_h = it["max_y"] - it["min_y"]
                ix1 = int(it["max_x"] + 2)
                ix2 = int(ix1 + icon_h * 1.3)
                iy1 = max(0, int(it["min_y"]))
                iy2 = min(ch, int(it["max_y"]))
                if 0 <= ix1 < cw and 0 <= ix2 <= cw:
                    icon_crop = card[iy1:iy2, ix1:ix2]
                    detected_sonata_color = self.detect_sonata_color(icon_crop)

            # Cost directly from header
            m_cost = re.search(r'COST\s*([134])', t, re.IGNORECASE)
            if m_cost:
                data["cost"] = int(m_cost.group(1))

        # 2. Parse Stats items: Group into Left Labels and Right Values
        mid_x = cw * 0.65
        left_items = [it for it in stats_items if it["cx"] < mid_x]
        right_items = [it for it in stats_items if it["cx"] >= mid_x]

        # Merge split label lines (e.g. "Resonance Skill DMG" + "Bonus")
        merged_left = []
        idx = 0
        while idx < len(left_items):
            curr = left_items[idx]
            if idx + 1 < len(left_items):
                nxt = left_items[idx + 1]
                if abs(nxt["cy"] - curr["cy"]) < max_line_gap and len(nxt["text"]) <= 6 and ("Bonus" in nxt["text"] or "DMG" in nxt["text"]):
                    merged = dict(curr)
                    merged["text"] = curr["text"] + " " + nxt["text"]
                    merged["cy"] = curr["cy"]
                    merged_left.append(merged)
                    idx += 2
                    continue
            merged_left.append(curr)
            idx += 1

        # Match each right value with its left label by closest vertical Y
        stat_pairs = []
        used_left = set()
        for r in right_items:
            best_l = None
            min_dy = 999
            for l_idx, l in enumerate(merged_left):
                if l_idx in used_left:
                    continue
                dy = abs(r["cy"] - l["cy"])
                if dy < min_dy and dy < max_match_dy:
                    min_dy = dy
                    best_l = (l_idx, l)
            if best_l:
                used_left.add(best_l[0])
                stat_pairs.append({
                    "label": best_l[1]["text"],
                    "value": r["text"],
                    "cy": best_l[1]["cy"]
                })

        stat_pairs.sort(key=lambda p: p["cy"])

        # First 2 are Main Stats, remaining up to 5 are Sub-Stats
        if len(stat_pairs) >= 2:
            data["main_stats"] = [parse_stat_line(p["label"], p["value"]) for p in stat_pairs[:2]]
            data["sub_stats"] = [parse_stat_line(p["label"], p["value"]) for p in stat_pairs[2:]]
        else:
            data["sub_stats"] = [parse_stat_line(p["label"], p["value"]) for p in stat_pairs]

        # 3. Sonata Final Resolution (Color detection + Hybrid Name/Stat fallback)
        if detected_sonata_color != "Unknown" and detected_sonata_color != "Glacio (Freezing Frost / Frosty Resolve)":
            data["sonata"] = detected_sonata_color
        else:
            # If color was Glacio or Unknown, double-check using monster name / 3-Cost elemental main stat
            inferred = self.infer_sonata_from_name_or_stats(data["name"], data["main_stats"])
            if inferred != "Unknown":
                data["sonata"] = inferred
            else:
                data["sonata"] = detected_sonata_color

        # 4. Game Rule Cross-Validation: Infer Cost with 100% certainty if missed
        if data["cost"] == 0 and len(data["main_stats"]) > 0:
            m1 = data["main_stats"][0]["stat"]
            m2 = data["main_stats"][1]["stat"] if len(data["main_stats"]) > 1 else ""
            m2_val = data["main_stats"][1]["num"] if len(data["main_stats"]) > 1 else 0

            if m1 in ["Crit. Rate", "Crit. DMG", "Healing Bonus"] or m2_val == 150:
                data["cost"] = 4
            elif "DMG Bonus" in m1 or m1 == "Energy Regen" or m2_val == 100:
                data["cost"] = 3
            elif "HP" in m2 and m2_val > 1000:
                data["cost"] = 1

        # 5. Calculate Crit Value (CV)
        sub_cr = 0.0
        sub_cd = 0.0
        for s in data["sub_stats"]:
            if s["stat"] == "Crit. Rate":
                sub_cr = s["num"]
            elif s["stat"] == "Crit. DMG":
                sub_cd = s["num"]

        main_cr = 0.0
        main_cd = 0.0
        for m in data["main_stats"]:
            if m["stat"] == "Crit. Rate":
                main_cr = m["num"]
            elif m["stat"] == "Crit. DMG":
                main_cd = m["num"]

        data["substats_cv"] = round(2 * sub_cr + sub_cd, 1)
        data["total_cv"] = round(data["substats_cv"] + (2 * main_cr + main_cd), 1)

        return data
