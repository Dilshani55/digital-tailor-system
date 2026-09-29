# ── Ease allowance rules (PROJECT ASSUMPTIONS — not verified against a published table) ──
# Circumference ease added to the body measurement, in cm. Used by drafting/ease.py.
# Stretch-knit (negative ease) drafting is not implemented and is rejected by the engine.

EASE_RULES = {
    "woven": {"bust_cm": 10.0, "waist_cm": 8.0, "hip_cm": 10.0},
    "knit":  {"bust_cm": 6.0,  "waist_cm": 4.0, "hip_cm": 6.0},
}

# Fit preference adjusts circumferential ease (cm)
FIT_EASE_DELTA = {
    "close": -2.0,
    "standard": 0.0,
    "loose": 3.0,
}
