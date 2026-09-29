import math
from app.logic.ease_rules import apply_ease, get_neckline_depth, get_sleeve_length
from app.logic.block_selection import select_drafting_block


def calculate_shoelace_area(points):
    """
    Computes polygon area using Gauss's Shoelace formula.
    points: list of (x, y) tuples or lists
    """
    if not points or len(points) < 3:
        return 0.0
    n = len(points)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = points[i][0], points[i][1]
        x2, y2 = points[j][0], points[j][1]
        area += x1 * y2
        area -= x2 * y1
    return abs(area) / 2.0


class ParametricEngine:
    """
    Generates 2D garment pattern block coordinates from body measurements
    and confirmed garment features, following Winifred Aldrich's
    Metric Pattern Cutting for Women's Wear standards.

    All measurements and coordinates are in centimetres (cm).
    Origin point (0, 0) is always top-left of each pattern piece.
    """

    def __init__(self, measurements, features):
        """
        Args:
            measurements (dict): body measurements from MeasurementProfile
            features     (dict): confirmed CAD features {neckline, sleeves, ...}
        """
        self.raw          = measurements
        self.features     = features
        self.fabric_type  = measurements.get("fabric_type", "woven")
        self.garment_type = features.get("garment_type", "blouse")
        self.fit_preference = measurements.get("fit_preference", "standard")

        # Step 5 — drafting method selection
        self.block = select_drafting_block(self.garment_type, self.fabric_type)

        # Apply ease (fabric + fit)
        self.eased = apply_ease(
            measurements, self.fabric_type, self.fit_preference
        )

        # Derived measurements (Aldrich + locked user measurements)
        self._compute_derived()


    def _compute_derived(self):
        """Computes all derived measurements used across pattern pieces."""
        e = self.eased
        raw = self.raw

        # Half measurements (pattern is drafted for half the body)
        self.half_bust  = e["bust_cm"]  / 2
        self.half_waist = e["waist_cm"] / 2
        self.half_hip   = e["hip_cm"]   / 2

        # Quarter measurements (used for front/back split)
        self.quarter_bust  = e["bust_cm"]  / 4
        self.quarter_waist = e["waist_cm"] / 4
        self.quarter_hip   = e["hip_cm"]   / 4

        # Back waist length — prefer locked measurement
        height = e["height_cm"]
        locked_bwl = raw.get("back_waist_length_cm") or e.get("back_waist_length_cm")
        if locked_bwl:
            self.back_neck_to_waist = float(locked_bwl)
        else:
            self.back_neck_to_waist = height * 0.2413

        self.waist_to_hip = height * 0.1173
        self.nape_to_hip  = self.back_neck_to_waist + self.waist_to_hip

        # Garment length / crop hem (from high shoulder / nape toward hem)
        locked_len = raw.get("garment_length_cm") or e.get("garment_length_cm")
        if locked_len:
            self.garment_length = float(locked_len)
        elif self.block["is_crop"]:
            self.garment_length = self.back_neck_to_waist * 0.72
        else:
            self.garment_length = self.nape_to_hip

        # Shoulder — prefer locked shoulder length
        locked_shoulder = raw.get("shoulder_cm") or e.get("shoulder_cm")
        if locked_shoulder:
            self.shoulder_width = float(locked_shoulder) + e["shoulder"]
        else:
            self.shoulder_width = (self.half_bust / 4) + e["shoulder"]

        # Armhole depth — prefer locked measurement
        locked_ad = raw.get("armhole_depth_cm") or raw.get("armhole_cm") or e.get("armhole_depth_cm")
        if locked_ad:
            self.armhole_depth = float(locked_ad)
        else:
            self.armhole_depth = (self.half_bust / 4) + 5.0

        # Across-back / front widths
        locked_ab = raw.get("across_back_cm") or e.get("across_back_cm")
        if locked_ab:
            # across-back is full width; half-block uses half
            self.back_width = float(locked_ab) / 2.0
            self.front_width = self.back_width - 1.0
        else:
            self.back_width  = (self.half_bust / 6) + 5.5
            self.front_width = (self.half_bust / 6) + 4.0

        # Neck — prefer locked neck circumference
        locked_neck = raw.get("neck_cm") or e.get("neck_cm")
        if locked_neck:
            # Aldrich: back neck width ≈ neck/5 − small constant (half-body)
            self.back_neck_width = max(5.5, (float(locked_neck) / 5.0) - 0.2)
        else:
            self.back_neck_width = (self.half_bust / 6) - 1.0
        self.back_neck_rise   = 2.0
        self.front_neck_depth = get_neckline_depth(
            self.features.get("neckline", "round neck")
        )

        # Sleeve inputs
        self.bicep_cm = float(raw.get("bicep_cm") or e.get("bicep_cm") or (self.half_bust / 2 + 3.0))
        self.wrist_cm = float(raw.get("wrist_cm") or e.get("wrist_cm") or 16.0)
        self.user_sleeve_cm = raw.get("sleeve_cm") or e.get("sleeve_cm")

        # Darts — woven blocks only; knit / t-shirt / crop knit: no darts
        feature_darts = self.features.get("darts", "bust dart")
        if self.block["allow_darts"] and feature_darts != "no dart":
            self.dart_width = 2.5
        else:
            self.dart_width = 0.0

        sleeve_type = self.features.get("sleeves", "short sleeve")
        self.block["add_armhole_facing"] = (sleeve_type == "sleeveless")
        self.block["add_neckband"] = bool(
            self.block.get("add_neckband") and self.block["is_knit_block"]
        )

    # ── BACK BODICE ───────────────────────────────────────────────────────────
    def draft_back_bodice(self):
        """
        Drafts the back bodice block.
        Returns ordered list of (x, y) coordinate points in cm.
        Label key is included for each point for the PDF guide.
        """
        bw  = self.back_neck_to_waist
        qb  = self.quarter_bust
        qw  = self.quarter_waist
        ad  = self.armhole_depth
        hem_y = max(ad + 2.0, min(self.garment_length, self.nape_to_hip + 5.0))

        # ── Construction lines ────────────────────────────────────────────────
        A = (0, 0)
        B = (0, ad)
        C = (0, bw) if bw <= hem_y else (0, hem_y)
        D = (0, hem_y)

        # ── Width lines ───────────────────────────────────────────────────────
        A1 = (self.back_neck_width, 0)
        B1 = (qb, ad)
        C1 = (qw + self.dart_width / 2, min(bw, hem_y))
        # Hem width: blouse/T use hip or bust; crop uses bust/waist blend
        if self.block["is_crop"] or hem_y <= bw + 2:
            hem_w = max(qw, qb * 0.95)
        else:
            hem_w = self.quarter_hip
        D1 = (hem_w, hem_y)

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

        # ── Dart construction (back waist dart) — woven only ──────────────────
        dart_x     = qw / 2
        dart_top   = (dart_x, min(bw, hem_y) - 8.0)
        dart_left  = (dart_x - self.dart_width / 2, min(bw, hem_y))
        dart_right = (dart_x + self.dart_width / 2, min(bw, hem_y))

        outline = [A2, A3, A1, SP, ARM_MID, B1, D1]
        if self.dart_width > 0 and bw <= hem_y + 0.1:
            outline.extend([C1, dart_right, dart_top, dart_left])
        outline.extend([C if bw <= hem_y else D, D, B, A2])

        piece = {
            "name": "Back Bodice",
            "block_type": self.block["block_label"],
            "cut_count": 1,
            "cut_on_fold": True,
            "seam_allowance_cm": 1.5,
            "points": {
                "A":  A,
                "A1": A1,
                "A2": A2,
                "A3": A3,
                "SP": SP,
                "ARM_MID": ARM_MID,
                "B1": B1,
                "B":  B,
                "C":  C,
                "D":  D,
                "D1": D1,
                "C1": C1,
                "DART_TOP":   dart_top,
                "DART_LEFT":  dart_left,
                "DART_RIGHT": dart_right
            },
            "outline": outline,
            "grain_line": {
                "start": (qb / 2, ad),
                "end":   (qb / 2, max(ad + 1.0, hem_y - 2.0))
            }
        }
        return piece


    # ── FRONT BODICE ──────────────────────────────────────────────────────────
    def draft_front_bodice(self):
        """
        Drafts the front bodice block.
        Front is wider than back to accommodate bust shaping.
        """
        bw  = self.back_neck_to_waist
        qb  = self.quarter_bust
        qw  = self.quarter_waist
        ad  = self.armhole_depth
        hem_y = max(ad + 2.0, min(self.garment_length, self.nape_to_hip + 5.0))

        A  = (0, self.front_neck_depth)
        B  = (0, ad)
        C  = (0, bw) if bw <= hem_y else (0, hem_y)
        D  = (0, hem_y)

        front_bust = qb + 0.5
        B1 = (front_bust, ad)
        C1 = (qw + self.dart_width / 2, min(bw, hem_y))
        if self.block["is_crop"] or hem_y <= bw + 2:
            hem_w = max(qw, front_bust * 0.95)
        else:
            hem_w = self.quarter_hip + 0.5
        D1 = (hem_w, hem_y)

        shoulder_rise = self.shoulder_width * math.tan(math.radians(15))
        SP = (self.shoulder_width, shoulder_rise)

        A_top = (0, 0)
        A1    = (self.back_neck_width + 0.5, 0)

        arm_mid_x = front_bust - (front_bust - self.front_width) / 2
        arm_mid_y = ad - (ad - shoulder_rise) / 2
        ARM_MID   = (arm_mid_x, arm_mid_y)

        dart_apex_x = qb * 0.55
        dart_apex_y = ad + 2.0
        dart_angle  = 12.0
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

        neckline_type = self.features.get("neckline", "round neck")
        if neckline_type in ("sweetheart neck", "sweetheart-neck"):
            neck_curve = (A1[0] * 0.45, self.front_neck_depth * 0.40)
        elif neckline_type in ("square neck", "square-neck"):
            neck_curve = (A1[0], self.front_neck_depth)
        else:
            neck_curve = (A1[0] * 0.3, self.front_neck_depth * 0.7)

        outline = [A_top, A1, neck_curve, A, B]
        if bw <= hem_y:
            outline.append(C)
        outline.append(D)
        outline.append(D1)
        if self.dart_width > 0:
            outline.extend([C1, dart_right, DART_APEX, dart_left])
        outline.extend([B1, ARM_MID, SP, A_top])

        piece = {
            "name": "Front Bodice",
            "block_type": self.block["block_label"],
            "cut_count": 1,
            "cut_on_fold": True,
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
            "outline": outline,
            "grain_line": {
                "start": (qb / 2, ad),
                "end":   (qb / 2, max(ad + 1.0, hem_y - 2.0))
            }
        }
        return piece


    # ── SLEEVE ────────────────────────────────────────────────────────────────
    def draft_sleeve(self):
        """
        Drafts the sleeve block based on Winifred Aldrich pattern construction formulas.
        Supports 7 parametric geometry families:
        1. Standard Set-in: cap, short, elbow, three-quarter, long, single
        2. Volume & Gathers: puff, bishop, balloon, lantern (+ wrist cuff band)
        3. Flared & Radial: bell, flared, cape, butterfly, ruffle, tiered
        4. Hybrid Puff & Taper: leg-o'-mutton
        5. Cut-out & Slit: cold shoulder, slit
        6. Bodice-Integrated: batwing, kimono
        Returns None if garment is sleeveless, or a piece dict (or list of piece dicts).
        """
        sleeve_type = self.features.get("sleeves", "short sleeve")

        if sleeve_type == "sleeveless":
            return None

        # Prefer user sleeve length measurement when provided
        if self.user_sleeve_cm:
            sleeve_length = float(self.user_sleeve_cm)
        else:
            sleeve_length = get_sleeve_length(sleeve_type)

        is_puff = (sleeve_type in ("puff sleeve", "puff-sleeve"))
        is_bell = (sleeve_type in [
            "bell sleeve", "flared sleeve", "ruffle sleeve", "tiered sleeve",
            "bell-sleeve", "flutter-sleeve",
        ])
        is_bishop = (sleeve_type in [
            "bishop sleeve", "balloon sleeve", "lantern sleeve", "bishop-sleeve",
        ])
        is_leg_mutton = (sleeve_type == "leg-o'-mutton sleeve")
        is_cap = (sleeve_type in ["cap sleeve", "petal sleeve", "cap-length"])
        is_cape = (sleeve_type in ["cape sleeve", "butterfly sleeve"])
        is_cold_shoulder = (sleeve_type in ["cold shoulder sleeve", "slit sleeve"])
        is_batwing = (sleeve_type in ["batwing sleeve", "kimono sleeve", "kimono-sleeve", "dolman-sleeve"])

        # Sleeve cap depth and bicep width — prefer locked bicep measurement
        bicep_width = max(self.bicep_cm / 2.0 + 2.0, self.half_bust / 2)

        if is_cap:
            sleeve_head = self.armhole_depth * 0.50
            sleeve_width = bicep_width + 1.5
        elif is_puff or is_leg_mutton:
            sleeve_head = self.armhole_depth * 0.90
            sleeve_width = bicep_width + 6.0
        elif is_bishop:
            sleeve_head = self.armhole_depth * 0.75
            sleeve_width = bicep_width + 7.5
        elif is_batwing:
            sleeve_head = self.armhole_depth * 1.30
            sleeve_width = bicep_width + 10.0
        else:
            sleeve_head = self.armhole_depth * 0.75
            sleeve_width = bicep_width + 3.0

        CROWN = (sleeve_width / 2, 0)
        UL = (0, sleeve_head)
        UR = (sleeve_width, sleeve_head)

        # Crown arch control points
        crown_arch_y = sleeve_head * (0.20 if (is_puff or is_leg_mutton) else 0.30)
        CROWN_L = (sleeve_width * 0.25, crown_arch_y)
        CROWN_R = (sleeve_width * 0.75, crown_arch_y)

        # Lower hem points according to style geometry
        if is_bell:
            # Aldrich Slash-and-Spread elbow flare
            elbow_y = min(32.0, sleeve_length * 0.55)
            EL = (1.5, elbow_y)
            ER = (sleeve_width - 1.5, elbow_y)
            flare_amount = 8.0
            HL = (-flare_amount, sleeve_length)
            HR = (sleeve_width + flare_amount, sleeve_length)
            points = {
                "CROWN": CROWN, "UL": UL, "UR": UR,
                "EL": EL, "ER": ER, "HL": HL, "HR": HR,
                "CROWN_L": CROWN_L, "CROWN_R": CROWN_R
            }
            outline = [CROWN, CROWN_R, UR, ER, HR, HL, EL, UL, CROWN_L, CROWN]

        elif is_cape:
            # Wide circular drape
            flare_amount = 10.0
            HL = (-flare_amount, sleeve_length)
            HR = (sleeve_width + flare_amount, sleeve_length)
            HEM_C = (sleeve_width / 2, sleeve_length + 3.0)
            points = {
                "CROWN": CROWN, "UL": UL, "UR": UR,
                "HL": HL, "HR": HR, "HEM_C": HEM_C,
                "CROWN_L": CROWN_L, "CROWN_R": CROWN_R
            }
            outline = [CROWN, CROWN_R, UR, HR, HEM_C, HL, UL, CROWN_L, CROWN]

        elif is_leg_mutton:
            # Wide bicep tapering dramatically to narrow wrist
            wrist_taper = 6.5
            HL = (wrist_taper, sleeve_length)
            HR = (sleeve_width - wrist_taper, sleeve_length)
            elbow_y = sleeve_length * 0.55
            EL = (2.0, elbow_y)
            ER = (sleeve_width - 2.0, elbow_y)
            points = {
                "CROWN": CROWN, "UL": UL, "UR": UR,
                "EL": EL, "ER": ER, "HL": HL, "HR": HR,
                "CROWN_L": CROWN_L, "CROWN_R": CROWN_R
            }
            outline = [CROWN, CROWN_R, UR, ER, HR, HL, EL, UL, CROWN_L, CROWN]

        elif is_cold_shoulder:
            # Cutout notch at the sleeve crown
            taper = 3.5 if sleeve_length > 40 else 1.5
            HL = (taper, sleeve_length)
            HR = (sleeve_width - taper, sleeve_length)
            CUTOUT_L = (sleeve_width * 0.35, sleeve_head * 0.40)
            CUTOUT_R = (sleeve_width * 0.65, sleeve_head * 0.40)
            points = {
                "CROWN": CROWN, "UL": UL, "UR": UR,
                "HL": HL, "HR": HR, "CROWN_L": CROWN_L, "CROWN_R": CROWN_R,
                "CUTOUT_L": CUTOUT_L, "CUTOUT_R": CUTOUT_R
            }
            outline = [CROWN_R, UR, HR, HL, UL, CROWN_L, CUTOUT_L, CUTOUT_R, CROWN_R]

        elif is_bishop:
            # Full body gathered into wrist cuff
            gather_ease = 4.0
            HL = (-gather_ease, sleeve_length)
            HR = (sleeve_width + gather_ease, sleeve_length)
            points = {
                "CROWN": CROWN, "UL": UL, "UR": UR,
                "HL": HL, "HR": HR,
                "CROWN_L": CROWN_L, "CROWN_R": CROWN_R
            }
            outline = [CROWN, CROWN_R, UR, HR, HL, UL, CROWN_L, CROWN]

        else:
            # Standard set-in sleeve — taper toward wrist when long
            if sleeve_length > 45.0:
                wrist_half = max(self.wrist_cm / 2.0 + 1.0, 4.0)
                taper = max(0.0, (sleeve_width - wrist_half * 2) / 2.0)
            elif sleeve_length > 30.0:
                taper = 2.0
            elif is_puff:
                taper = 2.0
            else:
                taper = 1.0

            HL = (taper, sleeve_length)
            HR = (sleeve_width - taper, sleeve_length)
            points = {
                "CROWN": CROWN, "UL": UL, "UR": UR,
                "HL": HL, "HR": HR,
                "CROWN_L": CROWN_L, "CROWN_R": CROWN_R
            }
            outline = [CROWN, CROWN_R, UR, HR, HL, UL, CROWN_L, CROWN]

        is_single = (sleeve_type == "single sleeve" or self.features.get("neckline") == "one-shoulder")
        main_piece = {
            "name": "Sleeve (single sleeve)" if is_single else f"Sleeve ({sleeve_type})",
            "cut_count": 1 if is_single else 2,
            "seam_allowance_cm": 1.5,
            "length_cm": sleeve_length,
            "width_cm": sleeve_width,
            "points": points,
            "outline": outline,
            "grain_line": {
                "start": (sleeve_width / 2, sleeve_head),
                "end": (sleeve_width / 2, sleeve_length)
            }
        }

        # For Bishop and Balloon sleeves, draft an accompanying wrist cuff piece
        if is_bishop:
            cuff_width = max(self.wrist_cm + 2.0, 18.0)
            cuff_height = 5.0
            cuff_piece = {
                "name": "Sleeve Wrist Cuff",
                "cut_count": 2,
                "seam_allowance_cm": 1.0,
                "length_cm": cuff_height,
                "width_cm": cuff_width,
                "points": {
                    "TL": (0, 0),
                    "TR": (cuff_width, 0),
                    "BR": (cuff_width, cuff_height),
                    "BL": (0, cuff_height)
                },
                "outline": [
                    (0, 0), (cuff_width, 0), (cuff_width, cuff_height), (0, cuff_height), (0, 0)
                ],
                "grain_line": {
                    "start": (cuff_width / 2, 0),
                    "end": (cuff_width / 2, cuff_height)
                }
            }
            return [main_piece, cuff_piece]

        return main_piece

    def draft_neckband(self):
        """Simple rectangular neckband for knit T-shirt constructions."""
        if not self.block.get("add_neckband"):
            return None
        neck = float(self.raw.get("neck_cm") or 36.0)
        band_len = neck * 0.85
        band_h = 3.0
        return {
            "name": "Neckband",
            "cut_count": 1,
            "cut_on_fold": False,
            "seam_allowance_cm": 0.7,
            "points": {
                "TL": (0, 0), "TR": (band_len, 0),
                "BR": (band_len, band_h), "BL": (0, band_h),
            },
            "outline": [(0, 0), (band_len, 0), (band_len, band_h), (0, band_h), (0, 0)],
            "grain_line": {
                "start": (band_len / 2, 0),
                "end": (band_len / 2, band_h),
            },
        }

    def draft_armhole_facing(self):
        """Armhole facing strip for sleeveless garments."""
        if not self.block.get("add_armhole_facing"):
            return None
        # Approximate armhole perimeter from depth + width
        facing_len = self.armhole_depth * 2.2 + self.back_width
        facing_w = 4.0
        return {
            "name": "Armhole Facing",
            "cut_count": 2,
            "cut_on_fold": False,
            "seam_allowance_cm": 0.7,
            "points": {
                "TL": (0, 0), "TR": (facing_len, 0),
                "BR": (facing_len, facing_w), "BL": (0, facing_w),
            },
            "outline": [(0, 0), (facing_len, 0), (facing_len, facing_w), (0, facing_w), (0, 0)],
            "grain_line": {
                "start": (facing_len / 2, 0),
                "end": (facing_len / 2, facing_w),
            },
        }


    # ── GENERATE FULL PATTERN ─────────────────────────────────────────────────
    def generate(self):
        """
        Generates the complete pattern block for the garment.
        Returns a dict with all pattern pieces and construction notes.
        """
        back   = self.draft_back_bodice()
        front  = self.draft_front_bodice()
        sleeve = self.draft_sleeve()
        neckband = self.draft_neckband()
        facing = self.draft_armhole_facing()

        pieces = [back, front]
        if sleeve:
            if isinstance(sleeve, list):
                pieces.extend(sleeve)
            else:
                pieces.append(sleeve)
        if neckband:
            pieces.append(neckband)
        if facing:
            pieces.append(facing)

        for piece in pieces:
            outline = piece["outline"]
            xs = [p[0] for p in outline]
            ys = [p[1] for p in outline]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            piece["bounding_box"] = {
                "width_cm":  round(max_x - min_x, 2),
                "height_cm": round(max_y - min_y, 2)
            }

            if "cut_on_fold" not in piece:
                piece["cut_on_fold"] = (piece["name"] in ["Back Bodice", "Front Bodice"])
            if "cut_count" not in piece:
                piece["cut_count"] = 1 if piece["cut_on_fold"] else 2
            if "seam_allowance_cm" not in piece:
                piece["seam_allowance_cm"] = 1.5

            poly_area = calculate_shoelace_area(outline)
            piece["polygon_area_cm2"] = round(poly_area, 2)

        notes = self._build_notes()

        return {
            "garment_type":   self.garment_type,
            "fabric_type":    self.fabric_type,
            "drafting_block": self.block,
            "pattern_pieces": pieces,
            "measurements_used": {
                "raw":   self.raw,
                "eased": {
                    "bust_cm":   round(self.eased["bust_cm"],  2),
                    "waist_cm":  round(self.eased["waist_cm"], 2),
                    "hip_cm":    round(self.eased["hip_cm"],   2),
                    "height_cm": round(self.eased["height_cm"],2),
                    "fit_preference": self.fit_preference,
                },
                "derived": {
                    "back_waist_length_cm": round(self.back_neck_to_waist, 2),
                    "armhole_depth_cm": round(self.armhole_depth, 2),
                    "shoulder_width_cm": round(self.shoulder_width, 2),
                    "across_back_half_cm": round(self.back_width, 2),
                    "garment_length_cm": round(self.garment_length, 2),
                }
            },
            "construction_notes": notes
        }


    def _build_notes(self):
        """Returns tailor construction notes based on features."""
        notes = [
            f"Drafting block: {self.block['block_label']} "
            f"(garment={self.garment_type}, fabric={self.fabric_type}).",
            f"All seam allowances: 1.5 cm unless stated.",
            f"Fabric type: {self.fabric_type} — "
            f"ease applied: bust +{self.eased['bust_cm'] - self.raw['bust_cm']:.1f} cm, "
            f"waist +{self.eased['waist_cm'] - self.raw['waist_cm']:.1f} cm "
            f"(fit: {self.fit_preference}).",
            f"Neckline: {self.features.get('neckline', 'round neck')} — "
            f"depth {self.front_neck_depth:.1f} cm from centre front.",
            f"Sleeves: {self.features.get('sleeves', 'short sleeve')} — "
            f"length {get_sleeve_length(self.features.get('sleeves', 'short sleeve')) if not self.user_sleeve_cm else float(self.user_sleeve_cm):.1f} cm.",
            f"Garment length used: {self.garment_length:.1f} cm.",
        ]

        if self.dart_width > 0:
            notes.append(
                f"Dart: {self.features.get('darts', 'bust dart')} — "
                f"width {self.dart_width:.1f} cm."
            )
        else:
            notes.append("No darts — knit block or stretch construction.")

        if self.block.get("add_neckband"):
            notes.append("Include knit neckband — stretch greatest around the neck.")
        if self.block.get("add_armhole_facing"):
            notes.append("Sleeveless: include armhole facing pieces.")

        if self.fabric_type == "stretch-knit":
            notes.append(
                "IMPORTANT: Negative ease applied. Cut fabric on the bias "
                "or with greatest stretch going around the body."
            )

        return notes
