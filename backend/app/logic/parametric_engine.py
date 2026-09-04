import math
from app.logic.ease_rules import apply_ease, get_neckline_depth, get_sleeve_length


class ParametricEngine:
    """
    Generates 2D garment pattern block coordinates from body measurements
    and detected garment features, following Winifred Aldrich's
    Metric Pattern Cutting for Women's Wear (5th Edition) standards.

    All measurements and coordinates are in centimetres (cm).
    Origin point (0, 0) is always top-left of each pattern piece.
    """

    def __init__(self, measurements, features):
        """
        Args:
            measurements (dict): body measurements from MeasurementProfile
                                 {bust_cm, waist_cm, hip_cm, height_cm, fabric_type}
            features     (dict): detected garment features from YOLOv8
                                 {neckline, sleeves, darts, seams, garment_type}
        """
        self.raw          = measurements
        self.features     = features
        self.fabric_type  = measurements.get("fabric_type", "woven")
        self.garment_type = features.get("garment_type", "blouse")

        # Apply ease allowance
        self.eased = apply_ease(measurements, self.fabric_type)

        # Derived measurements (Aldrich formulas)
        self._compute_derived()


    def _compute_derived(self):
        """Computes all derived measurements used across pattern pieces."""
        e = self.eased

        # Half measurements (pattern is drafted for half the body)
        self.half_bust  = e["bust_cm"]  / 2
        self.half_waist = e["waist_cm"] / 2
        self.half_hip   = e["hip_cm"]   / 2

        # Quarter measurements (used for front/back split)
        self.quarter_bust  = e["bust_cm"]  / 4
        self.quarter_waist = e["waist_cm"] / 4
        self.quarter_hip   = e["hip_cm"]   / 4

        # Body length proportions (Aldrich Chapter 2 formulas)
        height = e["height_cm"]
        self.back_neck_to_waist = height * 0.2413    # ~39cm for 162cm height
        self.waist_to_hip       = height * 0.1173    # ~19cm
        self.nape_to_hip        = self.back_neck_to_waist + self.waist_to_hip

        # Shoulder and armhole
        self.shoulder_width   = (self.half_bust / 4) + e["shoulder"]
        self.armhole_depth    = (self.half_bust / 4) + 5.0
        self.back_width       = (self.half_bust / 6) + 5.5
        self.front_width      = (self.half_bust / 6) + 4.0

        # Neck measurements
        self.back_neck_width  = (self.half_bust / 6) - 1.0
        self.back_neck_rise   = 2.0
        self.front_neck_depth = get_neckline_depth(
                                    self.features.get("neckline", "round neck"))

        # Dart
        self.dart_width       = 2.5 if self.features.get("darts") != "no dart" else 0.0


    # ── BACK BODICE ───────────────────────────────────────────────────────────
    def draft_back_bodice(self):
        """
        Drafts the back bodice block.
        Returns ordered list of (x, y) coordinate points in cm.
        Label key is included for each point for the PDF guide.
        """
        e   = self.eased
        bw  = self.back_neck_to_waist
        qb  = self.quarter_bust
        qw  = self.quarter_waist
        ad  = self.armhole_depth

        # ── Construction lines ────────────────────────────────────────────────
        A = (0, 0)
        B = (0, ad)
        C = (0, bw)
        D = (0, bw + self.waist_to_hip)

        # ── Width lines ───────────────────────────────────────────────────────
        A1 = (self.back_neck_width, 0)
        B1 = (qb, ad)
        C1 = (qw + self.dart_width / 2, bw)
        D1 = (self.quarter_hip, bw + self.waist_to_hip)

        # ── Shoulder point ────────────────────────────────────────────────────
        shoulder_rise = self.shoulder_width * math.tan(math.radians(18))
        SP = (self.shoulder_width, shoulder_rise)

        # ── Back neck curve (3 control points) ───────────────────────────────
        A2 = (0, self.back_neck_rise)            # left of neckline
        A3 = (self.back_neck_width * 0.5, 0.5)  # curve control

        # ── Armhole curve (simplified 3-point arc) ────────────────────────────
        arm_mid_x = qb - (qb - self.back_width) / 2
        arm_mid_y = ad - (ad - shoulder_rise) / 2
        ARM_MID   = (arm_mid_x, arm_mid_y)

        # ── Dart construction (back waist dart) ───────────────────────────────
        dart_x     = qw / 2
        dart_top   = (dart_x, bw - 8.0)    # dart point (8cm above waist)
        dart_left  = (dart_x - self.dart_width / 2, bw)
        dart_right = (dart_x + self.dart_width / 2, bw)

        # ── Assemble pattern piece as ordered polygon ─────────────────────────
        piece = {
            "name": "Back Bodice",
            "seam_allowance_cm": 1.5,
            "points": {
                "A":  A,    # nape of neck
                "A1": A1,   # neck shoulder end
                "A2": A2,   # neck curve
                "A3": A3,   # neck curve control
                "SP": SP,   # shoulder point
                "ARM_MID": ARM_MID,
                "B1": B1,   # bust line side
                "B":  B,    # bust line centre back
                "C":  C,    # waist centre back
                "D":  D,    # hip centre back
                "D1": D1,   # hip side
                "C1": C1,   # waist side
                "DART_TOP":   dart_top,
                "DART_LEFT":  dart_left,
                "DART_RIGHT": dart_right
            },
            "outline": [
                A2, A3, A1, SP, ARM_MID, B1,
                D1, C1, dart_right, dart_top, dart_left,
                C, D, B, A2
            ],
            "grain_line": {
                "start": (qb / 2, ad),
                "end":   (qb / 2, bw)
            }
        }
        return piece


    # ── FRONT BODICE ──────────────────────────────────────────────────────────
    def draft_front_bodice(self):
        """
        Drafts the front bodice block.
        Front is wider than back to accommodate bust shaping.
        """
        e   = self.eased
        bw  = self.back_neck_to_waist
        qb  = self.quarter_bust
        qw  = self.quarter_waist
        ad  = self.armhole_depth

        A  = (0, self.front_neck_depth)   # centre front neck
        B  = (0, ad)                       # bust line centre front
        C  = (0, bw)                       # waist centre front
        D  = (0, bw + self.waist_to_hip)   # hip centre front

        front_bust = qb + 0.5
        B1 = (front_bust, ad)
        C1 = (qw + self.dart_width / 2, bw)
        D1 = (self.quarter_hip + 0.5, bw + self.waist_to_hip)

        shoulder_rise = self.shoulder_width * math.tan(math.radians(15))
        SP = (self.shoulder_width, shoulder_rise)

        A_top = (0, 0)                              # top of centre front
        A1    = (self.back_neck_width + 0.5, 0)    # shoulder end of neckline

        arm_mid_x = front_bust - (front_bust - self.front_width) / 2
        arm_mid_y = ad - (ad - shoulder_rise) / 2
        ARM_MID   = (arm_mid_x, arm_mid_y)

        dart_apex_x = qb * 0.55     # bust point approximately
        dart_apex_y = ad + 2.0
        dart_angle  = 12.0          # degrees
        dart_length = 8.0

        dart_left  = (
            dart_apex_x - dart_length * math.sin(math.radians(dart_angle / 2)),
            dart_apex_y + dart_length * math.cos(math.radians(dart_angle / 2))
        )
        dart_right = (
            dart_apex_x + dart_length * math.sin(math.radians(dart_angle / 2)),
            dart_apex_y + dart_length * math.cos(math.radians(dart_angle / 2))
        )
        DART_APEX = (dart_apex_x, dart_apex_y)

        neck_curve = (
            A1[0] * 0.3,
            self.front_neck_depth * 0.7
        )

        piece = {
            "name": "Front Bodice",
            "seam_allowance_cm": 1.5,
            "points": {
                "A_TOP":    A_top,
                "A":        A,
                "A1":       A1,
                "NECK_CRV": neck_curve,
                "SP":       SP,
                "ARM_MID":  ARM_MID,
                "B1":       B1,
                "B":        B,
                "C":        C,
                "D":        D,
                "D1":       D1,
                "C1":       C1,
                "DART_APEX":  DART_APEX,
                "DART_LEFT":  dart_left,
                "DART_RIGHT": dart_right
            },
            "outline": [
                A_top, A1, neck_curve, A, B, C, D,
                D1, C1, dart_right, DART_APEX, dart_left,
                B1, ARM_MID, SP, A_top
            ],
            "grain_line": {
                "start": (qb / 2, ad),
                "end":   (qb / 2, bw)
            }
        }
        return piece


    # ── SLEEVE ────────────────────────────────────────────────────────────────
    def draft_sleeve(self):
        """
        Drafts the sleeve block.
        Returns None if garment is sleeveless.
        """
        sleeve_type = self.features.get("sleeves", "short sleeve")

        if sleeve_type == "sleeveless":
            return None

        sleeve_length = get_sleeve_length(sleeve_type)
        sleeve_head   = self.armhole_depth * 0.75
        sleeve_width  = self.half_bust / 2 + 3.0

        CROWN = (sleeve_width / 2, 0)
        UL = (0,             sleeve_head)   # underarm left
        UR = (sleeve_width,  sleeve_head)   # underarm right

        taper = 3.0 if sleeve_type == "long sleeve" else 1.0
        HL    = (taper,                  sleeve_length)
        HR    = (sleeve_width - taper,   sleeve_length)

        CROWN_L = (sleeve_width * 0.25, sleeve_head * 0.3)
        CROWN_R = (sleeve_width * 0.75, sleeve_head * 0.3)

        is_single = (sleeve_type == "single sleeve" or self.features.get("neckline") == "one-shoulder")
        piece = {
            "name": "Sleeve (single sleeve)" if is_single else f"Sleeve ({sleeve_type})",
            "cut_count": 1 if is_single else 2,
            "seam_allowance_cm": 1.5,
            "length_cm": sleeve_length,
            "width_cm":  sleeve_width,
            "points": {
                "CROWN":   CROWN,
                "UL":      UL,
                "UR":      UR,
                "HL":      HL,
                "HR":      HR,
                "CROWN_L": CROWN_L,
                "CROWN_R": CROWN_R
            },
            "outline": [
                CROWN, CROWN_R, UR, HR, HL, UL, CROWN_L, CROWN
            ],
            "grain_line": {
                "start": (sleeve_width / 2, sleeve_head),
                "end":   (sleeve_width / 2, sleeve_length)
            }
        }
        return piece


    # ── GENERATE FULL PATTERN ─────────────────────────────────────────────────
    def generate(self):
        """
        Generates the complete pattern block for the garment.
        Returns a dict with all pattern pieces and construction notes.
        """
        back   = self.draft_back_bodice()
        front  = self.draft_front_bodice()
        sleeve = self.draft_sleeve()

        pieces = [back, front]
        if sleeve:
            pieces.append(sleeve)

        for piece in pieces:
            outline = piece["outline"]
            xs = [p[0] for p in outline]
            ys = [p[1] for p in outline]
            piece["bounding_box"] = {
                "width_cm":  round(max(xs) - min(xs), 2),
                "height_cm": round(max(ys) - min(ys), 2)
            }

        notes = self._build_notes()

        return {
            "garment_type":   self.garment_type,
            "fabric_type":    self.fabric_type,
            "pattern_pieces": pieces,
            "measurements_used": {
                "raw":   self.raw,
                "eased": {
                    "bust_cm":   round(self.eased["bust_cm"],  2),
                    "waist_cm":  round(self.eased["waist_cm"], 2),
                    "hip_cm":    round(self.eased["hip_cm"],   2),
                    "height_cm": round(self.eased["height_cm"],2)
                }
            },
            "construction_notes": notes
        }


    def _build_notes(self):
        """Returns tailor construction notes based on features."""
        notes = [
            f"All seam allowances: 1.5 cm unless stated.",
            f"Fabric type: {self.fabric_type} — "
            f"ease applied: bust +{self.eased['bust_cm'] - self.raw['bust_cm']:.1f} cm, "
            f"waist +{self.eased['waist_cm'] - self.raw['waist_cm']:.1f} cm.",
            f"Neckline: {self.features.get('neckline', 'round neck')} — "
            f"depth {self.front_neck_depth:.1f} cm from centre front.",
            f"Sleeves: {self.features.get('sleeves', 'short sleeve')} — "
            f"length {get_sleeve_length(self.features.get('sleeves', 'short sleeve')):.1f} cm.",
        ]

        if self.dart_width > 0:
            notes.append(
                f"Dart: {self.features.get('darts', 'bust dart')} — "
                f"width {self.dart_width:.1f} cm."
            )
        else:
            notes.append("No darts — suitable for stretch-knit or T-shirt constructions.")

        if self.fabric_type == "stretch-knit":
            notes.append(
                "IMPORTANT: Negative ease applied. Cut fabric on the bias "
                "or with greatest stretch going around the body."
            )

        return notes
