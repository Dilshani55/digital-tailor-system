"""SYNTHETIC observations and judgements, used only to exercise the algorithm in tests.

These values are NOT empirical textile findings, expert opinions or production data.
"""


def research_data():
    criteria = [
        {"id": "air", "label": "Air permeability", "unit": "test-unit", "protocol": "synthetic test protocol",
         "objective": "benefit", "source": "Synthetic test fixture", "preference_source": "Synthetic test preference"},
        {"id": "mass", "label": "Areal density", "unit": "g/m2", "protocol": "synthetic mass protocol",
         "objective": "cost", "source": "Synthetic test fixture", "preference_source": "Synthetic test preference"},
    ]
    samples = []
    for fid, label, values in (("cotton-jersey-knit", "Synthetic jersey J1", (3, 1)),
                               ("french-terry-knit", "Synthetic terry T1", (1, 3))):
        samples.append({"fabric_id": fid, "sample_id": fid + "-test", "label": label,
                        "values": {c["id"]: {"value": value, "unit": c["unit"], "protocol": c["protocol"],
                                             "source": "Synthetic observation, not real fabric data"}
                                   for c, value in zip(criteria, values)}})
    return {"schema_version": 1, "profiles": [{"id": "synthetic-knit-test", "source": "Synthetic test study",
            "design": {"garment_type": "t-shirt", "neckline_type": "round-neck",
                       "sleeve_length": "short-sleeve", "sleeve_style": "regular-sleeve"},
            "fit_preference": "standard", "criteria": criteria,
            "experts": [{"id": "synthetic-expert", "source": "Synthetic judgement, not a real expert",
                         "matrix": [[1, 1], [1, 1]]}], "samples": samples}]}
