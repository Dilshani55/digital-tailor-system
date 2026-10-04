"""Research profiles: recorded judgements and identified, comparable fabric samples."""

import json
from pathlib import Path

from app.logic.fabric_mcda import RankingDataError, group_ahp, number, topsis

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "fabric_research.json"
DESIGN_FIELDS = ("garment_type", "neckline_type", "sleeve_length", "sleeve_style")


def text_field(record, key):
    value = record.get(key) if isinstance(record, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise RankingDataError(f"A recorded {key} is required.")
    return value.strip()


def load_research_data(path=None):
    try:
        with Path(path or DEFAULT_DATA_PATH).open(encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise RankingDataError("The fabric research data file cannot be read.") from exc
    check_dataset(data)
    return data


def check_dataset(data):
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("profiles"), list):
        raise RankingDataError("Fabric research data needs schema_version 1 and a profiles list.")
    ids, contexts = set(), set()
    for profile in data["profiles"]:
        pid = text_field(profile, "id")
        if pid in ids:
            raise RankingDataError("Research profile IDs must be unique.")
        ids.add(pid)
        design = profile.get("design")
        if not isinstance(design, dict) or set(design) != set(DESIGN_FIELDS):
            raise RankingDataError("Each research profile needs all four confirmed design attributes.")
        from app.logic.feature_schema import validate_attributes
        clean, errors = validate_attributes(design)
        if errors or clean != design:
            raise RankingDataError("Research profile design must use supported canonical attributes.")
        fit = profile.get("fit_preference")
        if fit not in ("close", "standard", "loose"):
            raise RankingDataError("Research profile fit_preference must be close, standard or loose.")
        context = tuple(design[k] for k in DESIGN_FIELDS) + (fit,)
        if context in contexts:
            raise RankingDataError("Only one research profile may match each design and fit.")
        contexts.add(context)


def rank_profile(profile, candidate_ids):
    """Require complete candidate coverage; a partial dataset cannot imply a catalogue winner."""
    text_field(profile, "source")
    criteria = profile.get("criteria")
    if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10:
        raise RankingDataError("A profile needs 2–10 explicitly defined criteria.")
    criterion_ids = [text_field(c, "id") for c in criteria]
    if len(set(criterion_ids)) != len(criteria):
        raise RankingDataError("Criterion IDs must be unique.")
    directions = []
    for criterion in criteria:
        for key in ("label", "unit", "protocol", "source", "preference_source"):
            text_field(criterion, key)
        objective = criterion.get("objective")
        if objective not in ("benefit", "cost", "target"):
            raise RankingDataError("A criterion objective must be benefit, cost or target.")
        if objective == "target":
            number(criterion.get("target"), "Criterion target")
        directions.append("cost" if objective == "target" else objective)

    experts = profile.get("experts")
    if not isinstance(experts, list) or not experts:
        raise RankingDataError("A profile needs recorded expert pairwise comparisons.")
    expert_ids = [text_field(e, "id") for e in experts]
    if len(set(expert_ids)) != len(experts):
        raise RankingDataError("Expert pseudonyms must be unique.")
    for expert in experts:
        text_field(expert, "source")
        matrix = expert.get("matrix")
        if not isinstance(matrix, list) or len(matrix) != len(criteria):
            raise RankingDataError("Expert matrix order must match the ordered criteria.")
    ahp = group_ahp([e["matrix"] for e in experts])

    samples = profile.get("samples")
    if not isinstance(samples, list):
        raise RankingDataError("Identified fabric samples are required.")
    ids = [text_field(sample, "fabric_id") for sample in samples]
    sample_ids = [text_field(sample, "sample_id") for sample in samples]
    if len(set(ids)) != len(ids) or len(set(sample_ids)) != len(samples):
        raise RankingDataError("Each catalogue candidate needs one unique, identified sample.")
    if set(ids) != set(candidate_ids):
        raise RankingDataError("Comparable sample data is required for every compatible catalogue fabric.")
    decision_matrix = []
    for sample in samples:
        text_field(sample, "label")
        observations = sample.get("values")
        if not isinstance(observations, dict) or set(observations) != set(criterion_ids):
            raise RankingDataError("Each sample needs observations for exactly the same criteria.")
        row = []
        for criterion in criteria:
            observation = observations[criterion["id"]]
            text_field(observation, "source")
            for key in ("unit", "protocol"):
                if not isinstance(observation, dict) or observation.get(key) != criterion[key]:
                    raise RankingDataError(f"Sample {criterion['id']} uses a different {key}.")
            value = number(observation.get("value"), "Sample observation")
            row.append(abs(value - criterion["target"]) if criterion["objective"] == "target" else value)
        decision_matrix.append(row)
    ranking = topsis(decision_matrix, ahp["weights"], directions)
    audit = {"profile_id": profile["id"], "profile_source": profile["source"],
             "criteria": criteria, "expert_sources": [{"id": e["id"], "source": e["source"]} for e in experts],
             "ahp": ahp, "decision_matrix": decision_matrix, "sample_order": sample_ids,
             "ideal": ranking["ideal"], "negative_ideal": ranking["negative_ideal"],
             "column_norms": ranking["column_norms"]}
    return {"discriminating": ranking["discriminating"], "audit": audit,
            "results": {sample["fabric_id"]: {**row, "sample": sample}
                        for sample, row in zip(samples, ranking["alternatives"])}}
