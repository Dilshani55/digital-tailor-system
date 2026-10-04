"""Within-study comparisons of published measurements and live user judgements.

The papers provide observations, not user priorities or a garment-fit validation.
No source values, protocols or candidate sets are accepted from the client.
"""
import copy
import hashlib
import json
from pathlib import Path

from app.logic.fabric_mcda import RankingDataError, ahp_weights, number, topsis
from app.logic.fabric_research import text_field

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "published_fabric_samples.json"
SAATY_CHOICES = (1/9, 1/7, 1/5, 1/3, 1, 3, 5, 7, 9)


def load_studies():
    try:
        raw = DATA_PATH.read_bytes()
        data = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise RankingDataError("Published sample data cannot be read.") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("studies"), list):
        raise RankingDataError("Published sample schema is invalid.")
    ids, fabric_ids = set(), set()
    for study in data["studies"]:
        sid = text_field(study, "id")
        if sid in ids or study.get("construction") not in ("knit", "woven"):
            raise RankingDataError("Each published study needs a unique ID and construction.")
        ids.add(sid)
        for key in ("title", "citation", "url", "scope_note", "composition"):
            text_field(study, key)
        criteria = study.get("criteria", [])
        keys = [text_field(c, "id") for c in criteria]
        if len(keys) != 3 or len(set(keys)) != len(keys):
            raise RankingDataError("Published studies need three unique criteria.")
        for c in criteria:
            for key in ("label", "unit", "protocol", "table"):
                text_field(c, key)
            if {g.get("value") for g in c.get("goal_options", [])} != {"cost", "benefit"}:
                raise RankingDataError("Each published criterion needs explicit preference directions.")
        samples = study.get("samples", [])
        sample_ids = set()
        if len(samples) < 2:
            raise RankingDataError("A study needs at least two identified samples.")
        for sample in samples:
            fid, sample_id = text_field(sample, "fabric_id"), text_field(sample, "sample_id")
            if fid in fabric_ids or sample_id in sample_ids:
                raise RankingDataError("Published sample identities must be unique.")
            fabric_ids.add(fid)
            sample_ids.add(sample_id)
            for key in ("label", "structure"):
                text_field(sample, key)
            if set(sample.get("values", {})) != set(keys):
                raise RankingDataError("All study samples need the same complete criteria.")
            for c in criteria:
                obs = sample["values"][c["id"]]
                for key in ("source", "source_url", "table"):
                    text_field(obs, key)
                if obs.get("unit") != c["unit"] or obs.get("protocol") != c["protocol"]:
                    raise RankingDataError("Within-study observation units and protocols must agree.")
                number(obs.get("value"), "Published observation")
        study["data_sha256"] = hashlib.sha256(raw).hexdigest()
    return data["studies"]


def study_for_garment(garment):
    construction = {"t-shirt": "knit", "blouse": "woven"}.get(garment)
    return next((s for s in load_studies() if s["construction"] == construction), None)


def study_metadata(study):
    return {**{k: v for k, v in study.items() if k != "samples"}, "sample_count": len(study["samples"])}


def sample_fabric(study, sample):
    """Only reported properties; unknown stretch/drape/care are not inferred."""
    return {"id": sample["fabric_id"], "name": sample["label"],
            "construction": study["construction"], "fabric_type": study["construction"],
            "research_sample": copy.deepcopy(sample), "study_id": study["id"],
            "source_url": study["url"], "reference_source": study["citation"],
            "simple_description": f"{study['composition']}; {sample['structure']}. Identified published sample.",
            "properties_basis": "Published measurements of this identified sample only.",
            "technical_details": {"construction": sample["structure"], "composition_note": study["composition"]},
            "compatible": True, "recommended": False, "recommendation_score": None,
            "topsis_closeness": None, "rank": None, "score_reasons": [], "warnings": [],
            "recommendation_status": "Published sample — unranked",
            "explanation": "Set your preferences to compare the samples. Fabric stretch and garment fit were not tested here."}


def get_published_fabric(fabric_id):
    if not isinstance(fabric_id, str):
        return None
    for study in load_studies():
        for sample in study["samples"]:
            if sample["fabric_id"] == fabric_id.strip().lower():
                return sample_fabric(study, sample)
    return None


def rank_user_samples(study, preferences, *, design, fit):
    if not isinstance(preferences, dict) or set(preferences) != {"study_id", "goals", "comparisons"}:
        raise RankingDataError("Choose a goal for every property and answer all three comparisons.")
    if preferences["study_id"] != study["id"]:
        raise RankingDataError("These preferences belong to another study. Set them for this design again.")
    criteria = copy.deepcopy(study["criteria"])
    keys = [c["id"] for c in criteria]
    goals = preferences["goals"]
    if not isinstance(goals, dict) or set(goals) != set(keys) or any(v not in ("cost", "benefit") for v in goals.values()):
        raise RankingDataError("Choose lighter/heavier, airflow/thickness and insulation goals explicitly.")
    comparisons = preferences["comparisons"]
    if not isinstance(comparisons, list) or len(comparisons) != 3:
        raise RankingDataError("Answer all three importance comparisons.")
    pairs = {(keys[i], keys[j]): (i, j) for i in range(3) for j in range(i+1, 3)}
    matrix = [[1.0 for _ in keys] for _ in keys]
    seen = set()
    for comparison in comparisons:
        if not isinstance(comparison, dict) or set(comparison) != {"left", "right", "ratio"}:
            raise RankingDataError("Each comparison needs the two properties and their importance ratio.")
        pair = (text_field(comparison, "left"), text_field(comparison, "right"))
        if pair not in pairs or pair in seen:
            raise RankingDataError("Each ordered property pair must be answered exactly once.")
        seen.add(pair)
        ratio = number(comparison["ratio"], "Importance ratio")
        if not any(abs(ratio - choice) < 1e-9 for choice in SAATY_CHOICES):
            raise RankingDataError("Choose an importance level from the provided scale.")
        i, j = pairs[pair]
        matrix[i][j], matrix[j][i] = ratio, 1/ratio
    try:
        ahp = ahp_weights(matrix)
    except RankingDataError as exc:
        raise RankingDataError("Your importance choices contradict each other. Review the three comparisons and try again. " + str(exc)) from exc
    for criterion in criteria:
        criterion.update(objective=goals[criterion["id"]], preference_source="Current user's explicit choices")
    samples = study["samples"]
    values = [[s["values"][key]["value"] for key in keys] for s in samples]
    ranking = topsis(values, ahp["weights"], [goals[key] for key in keys])
    audit = {"profile_id": study["id"], "profile_source": study["citation"], "source_url": study["url"],
             "data_sha256": study["data_sha256"], "weight_source": "user_preferences",
             "preferences": copy.deepcopy(preferences), "design": dict(design), "fit_preference": fit,
             "criteria": criteria, "ahp": {**ahp, "matrix": matrix}, "decision_matrix": values,
             "sample_order": [s["sample_id"] for s in samples],
             "ideal": ranking["ideal"], "negative_ideal": ranking["negative_ideal"],
             "column_norms": ranking["column_norms"], "scope_note": study["scope_note"]}
    return {"audit": audit, "discriminating": ranking["discriminating"],
            "results": {s["fabric_id"]: {**row, "sample": copy.deepcopy(s)}
                        for s, row in zip(samples, ranking["alternatives"])}}
