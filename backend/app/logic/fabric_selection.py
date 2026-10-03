"""
Design-aware, RULE-BASED fabric recommendation (not machine-learned).

Input: the user-confirmed design (garment type, neckline, sleeve length, sleeve style) and the fit.
Output: every catalogue fabric with
    compatible        can the drafting engine draft this design in this fabric? (hard rule)
    score / reasons   explainable rule deltas (each reason names the rule)
    warnings          e.g. a sheer fabric needs a lining the engine does not draft
    recommended       True for the 2-4 best compatible fabrics
Fabric properties come from the author-compiled knowledge base in fabric_recommendation.py; the
structured traits below (construction, drape level, opacity) are the author's classification of the same
fabrics — general textile knowledge, not measured values.
"""

import re

from app.logic.block_selection import select_drafting_block
from app.logic.fabric_recommendation import FABRIC_KNOWLEDGE_BASE

METHOD = "Rule-based fabric recommendation (deterministic rules, not machine-learned)"

# Author-compiled traits per fabric: construction, drape level (1 very low .. 5 very high), opacity.
TRAITS = {
    "cotton-poplin":      ("woven", 2, "opaque"),
    "linen-blend":        ("woven", 2, "opaque"),
    "rayon":              ("woven", 4, "opaque"),
    "cotton-jersey-knit": ("knit", 4, "opaque"),
    "silk-chiffon":       ("woven", 5, "sheer"),
    "cotton-twill":       ("woven", 1, "opaque"),
    "satin":              ("woven", 4, "opaque"),
    "crepe-de-chine":     ("woven", 4, "semi-opaque"),
    "georgette":          ("woven", 5, "semi-sheer"),
    "french-terry-knit":  ("knit", 2, "opaque"),
}

MIN_RECOMMENDED, MAX_RECOMMENDED = 2, 4
RECOMMEND_THRESHOLD = 60


def _gsm(fabric):
    text = ((fabric.get("technical_details") or {}).get("typical_gsm_range")) or ""
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)\s*GSM", text)
    return {"min": int(m.group(1)), "max": int(m.group(2))} if m else None


def compatibility(garment_type, construction):
    """(compatible, reason) — the same block rule the drafting engine uses."""
    if garment_type == "t-shirt" and construction != "knit":
        return False, "A T-shirt is drafted on the knit block (stretch assumed); a woven fabric would not fit."
    if garment_type == "blouse" and construction != "woven":
        return False, "A blouse is drafted on the woven block with darts; a knit fabric is not compatible."
    return True, ""


def _score(fid, fabric, attrs, fit):
    construction, drape, opacity = TRAITS[fid]
    weight = fabric["weight"]
    style, length = attrs.get("sleeve_style"), attrs.get("sleeve_length")
    score, reasons, warnings = 60, [], []

    def rule(delta, text):
        nonlocal score
        score += delta
        reasons.append({"delta": delta, "reason": text})

    if style == "puff-sleeve":
        if drape <= 3 and weight in ("Light", "Medium"):
            rule(+15, "Puff sleeve: a crisp light/medium fabric holds the gathered cap up.")
        elif drape >= 4:
            rule(-10, "Puff sleeve: a very fluid fabric lets the gathers collapse.")
        if weight == "Heavy":
            rule(-10, "Puff sleeve: heavy fabric makes bulky gathers.")

    garment = attrs.get("garment_type")
    if garment == "blouse" and 2 <= drape <= 4:
        rule(+5, "Blouse: medium drape suits a darted woven bodice.")
    if garment == "t-shirt" and construction == "knit":
        if weight == "Medium":
            rule(+10, "Knit top: medium-weight jersey is the usual T-shirt fabric.")
        elif weight == "Heavy":
            rule(-5, "Knit top: heavy knit is warm for everyday tops.")

    if attrs.get("neckline_type") in ("square-neck", "v-neck") and drape <= 3:
        rule(+5, "Square/V neckline: a fabric with body keeps the neckline edges straight.")
    if length == "sleeveless" and fabric["breathability"].startswith(("High", "Very High")):
        rule(+5, "Sleeveless: breathable fabric suits a warm-weather top.")
    if fit == "close" and fabric["stretch"] in ("Slight Stretch", "Stretchable"):
        rule(+5, "Close fit: a little stretch adds comfort.")
    if fit == "loose" and drape >= 4:
        rule(+5, "Loose fit: a fluid fabric drapes softly.")

    if opacity == "sheer":
        rule(-15, "Sheer fabric: needs a lining, which this pattern does not include.")
        warnings.append("Sheer — a lining would be needed; the pattern has no lining pieces.")
    elif opacity == "semi-sheer":
        rule(-5, "Semi-sheer fabric: may need a lining or camisole.")
        warnings.append("Semi-sheer — may need a lining or camisole.")
    return max(0, min(100, score)), reasons, warnings


def recommend_for_design(attributes, fit_preference="standard"):
    """Ranked catalogue for a confirmed design. Never invents availability, price or stock."""
    attrs = dict(attributes or {})
    garment = attrs.get("garment_type") or "blouse"
    fit = fit_preference if fit_preference in ("close", "standard", "loose") else "standard"
    rows = []
    for fid, fabric in FABRIC_KNOWLEDGE_BASE.items():
        construction, drape, opacity = TRAITS[fid]
        ok, why_not = compatibility(garment, construction)
        score, reasons, warnings = _score(fid, fabric, attrs, fit)
        block = select_drafting_block(garment, construction)
        rows.append({
            **{k: fabric[k] for k in ("id", "name", "local_image", "simple_description", "feel", "weight", "stretch",
                                      "breathability", "drape", "advantages", "limitations", "care_instructions",
                                      "sewing_difficulty", "technical_details", "best_garment_uses",
                                      "climate_suitability", "reference_source", "image_license")},
            "construction": construction, "drape_level": drape, "opacity": opacity, "gsm_range": _gsm(fabric),
            "compatible": ok, "incompatible_reason": why_not or None,
            "drafting_block": block["block_label"] if ok else None,
            "fabric_type": construction,
            "recommendation_score": score if ok else None,
            "score_reasons": reasons if ok else [],
            "warnings": warnings,
            "recommended": False,
        })
    compatible = sorted((r for r in rows if r["compatible"]), key=lambda r: (-r["recommendation_score"], r["name"]))
    picked = [r for r in compatible if r["recommendation_score"] >= RECOMMEND_THRESHOLD][:MAX_RECOMMENDED]
    if len(picked) < MIN_RECOMMENDED:
        picked = compatible[:MIN_RECOMMENDED]
    for r in picked:
        r["recommended"] = True
    for r in rows:
        if not r["compatible"]:
            r["recommendation_status"] = "Not compatible"
        elif r["recommended"]:
            r["recommendation_status"] = "Recommended"
        else:
            r["recommendation_status"] = "Also compatible"
        if r["compatible"]:
            best = max(r["score_reasons"], key=lambda x: x["delta"], default=None)
            r["explanation"] = (best["reason"] if best and best["delta"] > 0
                                else f"Compatible with the {garment.replace('-', ' ')} block; no specific advantage for this design.")
        else:
            r["explanation"] = r["incompatible_reason"]
    ordered = picked + [r for r in compatible if not r["recommended"]] + [r for r in rows if not r["compatible"]]
    return {
        "method": METHOD,
        "design": {k: attrs.get(k) for k in ("garment_type", "neckline_type", "sleeve_length", "sleeve_style")},
        "fit_preference": fit,
        "recommended_ids": [r["id"] for r in picked],
        "fabrics": ordered,
        "note": "Fabric properties are an author-compiled classification of general textile knowledge; "
                "no availability, price or stock information is held.",
    }
