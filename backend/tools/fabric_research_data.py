"""Create a blank data-collection template or validate a recorded fabric study.

Run from the repository root with backend/venv/Scripts/python.exe. No database
or server is needed. This tool never invents observations or expert responses.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.logic.fabric_mcda import RankingDataError  # noqa: E402
from app.logic.fabric_research import load_research_data, rank_profile  # noqa: E402
from app.logic.fabric_selection import TRAITS, compatibility  # noqa: E402
from app.logic.published_fabrics import load_studies, study_metadata  # noqa: E402


def template(garment):
    criteria = [{"id": "air_permeability", "label": "Air permeability", "unit": "", "protocol": "",
                 "objective": None, "source": "", "preference_source": ""},
                {"id": "areal_density", "label": "Areal density", "unit": "g/m2", "protocol": "",
                 "objective": None, "source": "", "preference_source": ""}]
    return {"schema_version": 1, "profiles": [{"id": "", "source": "",
            "design": {"garment_type": garment, "neckline_type": "round-neck",
                       "sleeve_length": "short-sleeve", "sleeve_style": "regular-sleeve"},
            "fit_preference": "standard", "criteria": criteria,
            "experts": [{"id": "", "source": "", "matrix": [[1, None], [None, 1]]}],
            "samples": [{"fabric_id": fid, "sample_id": "", "label": "",
                         "values": {c["id"]: {"value": None, "unit": c["unit"], "protocol": "", "source": ""}
                                    for c in criteria}}
                        for fid, trait in TRAITS.items() if compatibility(garment, trait[0])[0]]}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--template", choices=("t-shirt", "blouse"), help="Print a blank collection template as JSON")
    mode.add_argument("--validate", type=Path, help="Validate all profiles and print their calculated results")
    mode.add_argument("--published", action="store_true", help="Validate the shipped published measurements and list their sources")
    args = parser.parse_args()
    if args.template:
        print(json.dumps(template(args.template), indent=2, ensure_ascii=False))
        return 0
    try:
        if args.published:
            studies = load_studies()
            print(json.dumps({"valid": True, "studies": [study_metadata(s) for s in studies]}, indent=2))
            return 0
        data = load_research_data(args.validate)
        if not data["profiles"]:
            raise RankingDataError("No expert profiles are recorded; use --published to check the default user-preference dataset.")
        summaries = []
        for profile in data["profiles"]:
            candidates = [fid for fid, trait in TRAITS.items() if compatibility(profile["design"]["garment_type"], trait[0])[0]]
            result = rank_profile(profile, candidates)
            summaries.append({"profile_id": profile["id"], "weights": result["audit"]["ahp"]["weights"],
                              "consistency_ratio": result["audit"]["ahp"]["consistency_ratio"],
                              "discriminating": result["discriminating"],
                              "samples": [{"sample_id": r["sample"]["sample_id"], "closeness": r["closeness"]}
                                          for r in result["results"].values()]})
        print(json.dumps({"valid": True, "profiles": summaries}, indent=2))
        return 0
    except RankingDataError as exc:
        print(f"Research data not ready: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
