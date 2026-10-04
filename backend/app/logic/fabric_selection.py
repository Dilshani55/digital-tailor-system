"""Drafting compatibility followed by data-dependent crisp AHP/TOPSIS ranking."""

import math
import re

from app.logic.block_selection import select_drafting_block
from app.logic.fabric_mcda import RankingDataError
from app.logic.fabric_recommendation import FABRIC_KNOWLEDGE_BASE
from app.logic.fabric_research import DESIGN_FIELDS, check_dataset, load_research_data, rank_profile
from app.logic.published_fabrics import rank_user_samples, sample_fabric, study_for_garment, study_metadata

METHOD = "AHP-weighted TOPSIS (crisp multi-criteria decision analysis)"

# Legacy catalogue classifications: only construction supports an engine constraint.
# Ordinal drape is retained for clients, but NEVER used as measured ranking data.
TRAITS = {
    "cotton-poplin": ("woven", 2, "opaque"), "linen-blend": ("woven", 2, "opaque"),
    "rayon": ("woven", 4, "opaque"), "cotton-jersey-knit": ("knit", 4, "opaque"),
    "silk-chiffon": ("woven", 5, "sheer"), "cotton-twill": ("woven", 1, "opaque"),
    "satin": ("woven", 4, "opaque"), "crepe-de-chine": ("woven", 4, "semi-opaque"),
    "georgette": ("woven", 5, "semi-sheer"), "french-terry-knit": ("knit", 2, "opaque"),
}


def _gsm(fabric):
    text = ((fabric.get("technical_details") or {}).get("typical_gsm_range")) or ""
    match = re.search(r"(\d+)\s*[–-]\s*(\d+)\s*GSM", text)
    return {"min": int(match.group(1)), "max": int(match.group(2))} if match else None


def compatibility(garment_type, construction):
    """An engine support constraint, not a universal textile suitability claim."""
    if garment_type == "t-shirt" and construction != "knit":
        return False, "This system drafts T-shirts on its knit block; choose a knit fabric."
    if garment_type == "blouse" and construction != "woven":
        return False, "This system drafts blouses on its woven block; choose a woven fabric."
    return True, ""


def fabric_construction(fabric_id):
    if fabric_id in TRAITS:
        return TRAITS[fabric_id][0]
    from app.logic.published_fabrics import get_published_fabric
    fabric = get_published_fabric(fabric_id)
    return fabric["construction"] if fabric else None


def _apply_ranking(candidates, result):
    for row in candidates:
        scored = result["results"][row["id"]]
        row.update(topsis_closeness=scored["closeness"], research_sample=scored["sample"],
                   ranking_details={k: v for k, v in scored.items() if k != "sample"})
    if not result["discriminating"]:
        return
    candidates.sort(key=lambda row: (-row["topsis_closeness"], row["id"]))
    rank, previous = 0, None
    for position, row in enumerate(candidates, 1):
        coefficient = row["topsis_closeness"]
        if previous is None or not math.isclose(previous, coefficient, rel_tol=0, abs_tol=1e-10):
            rank = position
        previous = coefficient
        row.update(rank=rank, recommended=rank == 1,
                   recommendation_status="Top ranked sample" if rank == 1 else "Ranked sample",
                   explanation=f"Rank {rank}; relative TOPSIS closeness {coefficient:.3f}. Applies to sample {row['research_sample']['sample_id']} and your chosen priorities.")


def recommend_for_design(attributes, fit_preference="standard", *, research_data=None, data_path=None, user_preferences=None):
    attrs = dict(attributes or {})
    garment = attrs.get("garment_type") or "blouse"
    fit = fit_preference if fit_preference in ("close", "standard", "loose") else "standard"
    design = {key: attrs.get(key) for key in DESIGN_FIELDS}
    rows = []
    for fid, fabric in FABRIC_KNOWLEDGE_BASE.items():
        construction, drape, opacity = TRAITS[fid]
        ok, reason = compatibility(garment, construction)
        warnings = []
        if opacity in ("sheer", "semi-sheer"):
            warnings.append("Check this sample's opacity: a lining or camisole may be needed; the pattern has no lining pieces.")
        block = select_drafting_block(garment, construction)
        rows.append({**{k: v for k, v in fabric.items() if k != "recommendation_rules"},
                     "construction": construction, "fabric_type": construction,
                     "drape_level": drape, "opacity": opacity, "gsm_range": _gsm(fabric),
                     "properties_basis": "Generic catalogue descriptions; not measured sample data.",
                     "compatible": ok, "incompatible_reason": reason or None,
                     "drafting_block": block["block_label"] if ok else None,
                     "recommendation_score": None, "score_reasons": [], "topsis_closeness": None,
                     "rank": None, "recommended": False, "warnings": warnings,
                     "recommendation_status": "Compatible — unranked" if ok else "Not compatible",
                     "explanation": f"Supported by this system's {garment} drafting block. Select the actual fabric sample yourself."
                                    if ok else reason})
    candidates = [r for r in rows if r["compatible"]]
    status = "awaiting_data"
    message = "Fabric sample data and recorded expert comparisons are not available for this design and fit. Choose a compatible fabric below."
    audit = None
    published = None
    published_rows = []
    try:
        data = research_data if research_data is not None else load_research_data(data_path)
        check_dataset(data)
        profile = next((p for p in data["profiles"] if p["design"] == design and p["fit_preference"] == fit), None)
        if profile is not None:
            result = rank_profile(profile, [r["id"] for r in candidates])
            audit = result["audit"]
            status = "ranked" if result["discriminating"] else "indistinguishable"
            message = "Ranking compares the identified samples using recorded criteria and expert judgements."
            if status == "indistinguishable":
                message = "The recorded criteria do not distinguish these samples. Choose a compatible fabric below."
            _apply_ranking(candidates, result)
        elif research_data is None and not data["profiles"]:
            study = study_for_garment(garment)
            if study:
                published = study_metadata(study)
                published_rows = [sample_fabric(study, sample) for sample in study["samples"]]
                status = "awaiting_preferences"
                message = "Published measurements are available. Set your fabric goals and importance choices to compare these samples."
                if user_preferences is not None:
                    try:
                        result = rank_user_samples(study, user_preferences, design=design, fit=fit)
                    except RankingDataError as exc:
                        status, message = "invalid_preferences", str(exc)
                    else:
                        audit = result["audit"]
                        status = "ranked" if result["discriminating"] else "indistinguishable"
                        message = "Published samples compared using your preferences. Select a sample and view its measured values and source."
                        if not result["discriminating"]:
                            message = "These properties do not distinguish the samples. No ranking is assigned."
                        _apply_ranking(published_rows, result)
    except RankingDataError as exc:
        status = "invalid_data"
        message = "The research data is incomplete or inconsistent. Ranking is unavailable; choose a compatible fabric below."
        audit = {"data_error": str(exc)}
    if status != "ranked":
        candidates.sort(key=lambda row: row["name"])
    picked = [r for r in published_rows + candidates if r["recommended"]]
    return {"method": METHOD, "ranking_status": status, "ranking_message": message,
            "ranking_audit": audit, "published_study": published, "design": design, "fit_preference": fit,
            "recommended_ids": [r["id"] for r in picked],
            "fabrics": published_rows + candidates + [r for r in rows if not r["compatible"]],
            "note": "TOPSIS closeness is a relative comparison, not a fit probability or validation result. Generic catalogue properties are not used for ranking."}
