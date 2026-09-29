import csv
import hashlib
import io
from flask import Blueprint, request, jsonify, Response, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.pattern_result import PatternResult
from app.models.research_record import ResearchRecord, METRICS_INTEGRITY_VERSION
from app.models.fabric_comparison import FabricComparison, ESTIMATE_SOURCES
from app.logic.nesting_algorithm import estimate_fabric, NestingError, STANDARD_FABRIC_WIDTHS
from app.logic.research_metrics import (
    load_model_evaluation, compute_feature_corrections, mean_or_none, summarize_fabric_comparisons,
)

research_bp = Blueprint("research", __name__)


def _researcher_emails():
    raw = current_app.config.get("RESEARCHER_EMAILS") or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _is_researcher(user_id):
    """Only accounts listed in RESEARCHER_EMAILS may read study-wide data (default: nobody)."""
    allowed = _researcher_emails()
    if not allowed:
        return False
    user = User.objects(id=user_id).first()
    return bool(user and user.email.lower() in allowed)


def _pseudonym(user):
    """Stable anonymous label for a participant - names and e-mails never leave the server."""
    return "P-" + hashlib.sha256(str(user.id).encode("utf-8")).hexdigest()[:6]


def _forbidden():
    return jsonify({"error": "Study-wide research data is only available to researcher accounts.",
                    "error_code": "RESEARCHER_ONLY"}), 403


def _owns(pattern, user_id):
    try:
        return str(pattern.session_id.user_id.id) == str(user_id)
    except Exception:
        return False


def _trusted(record, field):
    """
    Value of a measured field, or None for legacy (pre-cleanup) records, whose
    measured fields may have been filled with invented defaults by older code.
    """
    if getattr(record, "metrics_integrity_version", 1) < METRICS_INTEGRITY_VERSION:
        return None
    return getattr(record, field, None)


# ── POST SUBMIT FEEDBACK ──────────────────────────────────────────────────────
@research_bp.route("/feedback", methods=["POST"])
@jwt_required()
def submit_feedback():
    current_user_id = get_jwt_identity()
    user = User.objects(id=current_user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}
    pattern_id = data.get("pattern_id")
    score = data.get("feedback_score")
    comment = data.get("feedback_comment", "")

    if not pattern_id or not score:
        return jsonify({"error": "pattern_id and feedback_score are required"}), 400
    if isinstance(score, bool) or not isinstance(score, (int, float, str)) \
            or not str(score).strip().isdigit() or not 1 <= int(score) <= 5:
        return jsonify({"error": "feedback_score must be a whole number from 1 to 5",
                        "error_code": "INVALID_SCORE"}), 400
    if not isinstance(comment, str) or len(comment) > 2000:
        return jsonify({"error": "feedback_comment must be text of at most 2000 characters"}), 400

    try:
        pattern = PatternResult.objects(id=pattern_id).first()
    except Exception:
        return jsonify({"error": "Invalid pattern_id format"}), 400

    if not pattern:
        return jsonify({"error": "Pattern not found"}), 404
    if not _owns(pattern, current_user_id):
        return jsonify({"error": "Unauthorized"}), 403

    # Record only what was actually measured / stored by the pipeline.
    session = pattern.session_id
    image = getattr(session, "image_id", None)
    predictions = ((getattr(image, "garment_attributes", None) or {}).get("predictions")) or {}
    confirmed = getattr(image, "confirmed_attributes", None) or {}
    # Real correction data: the classifier's stored prediction vs. the user's confirmed value.
    corrections, correction_rate = compute_feature_corrections(predictions, confirmed)

    # Mean top-1 classifier confidence, only if the classifier actually ran.
    ai_conf = getattr(image, "confidence_score", None) if predictions else None

    # Yardage / efficiency exactly as the pipeline stored them, or None.
    # No baseline layout is defined yet, so baseline and savings stay None.
    opt_yardage = pattern.yardage_metres if (pattern.yardage_metres or 0) > 0 else None
    layout_eff = (pattern.nesting_summary or {}).get("utilisation_percent")

    record = ResearchRecord(
        user_id = user,
        session_id = session,
        pattern_id = pattern,
        corrections_made = corrections,
        correction_rate = correction_rate,
        ai_confidence_avg = ai_conf,
        optimized_yardage_m = opt_yardage,
        layout_efficiency = layout_eff,
        processing_time_sec = getattr(image, "analysis_time_sec", None) if image else None,
        pattern_generation_time_sec = getattr(pattern, "generation_time_sec", None),
        feedback_score = int(score),
        feedback_comment = comment,
        metrics_integrity_version = METRICS_INTEGRITY_VERSION,
    )
    record.save()

    return jsonify({"message": "Usability survey feedback recorded successfully", "record_id": str(record.id)}), 201


# ── TRADITIONAL vs SYSTEM FABRIC ESTIMATE (evaluation instrument) ─────────────
def _ref_id(document, field):
    """Id of a reference without loading the referenced document (no extra query per row)."""
    ref = document._data.get(field)
    return str(getattr(ref, "id", ref)) if ref is not None else None


def _comparison_json(c):
    return {
        "comparison_id": str(c.id),
        "pattern_id": _ref_id(c, "pattern_id"),
        "fabric_width_cm": c.fabric_width_cm,
        "cutting_mode": c.cutting_mode,
        "system_cutting_mode": c.system_cutting_mode,
        "system_purchase_m": c.system_purchase_m,
        "system_layout_length_cm": c.system_layout_length_cm,
        "system_utilisation_percent": c.system_utilisation_percent,
        "traditional_estimate_m": c.traditional_estimate_m,
        "estimate_source": c.estimate_source,
        "estimator_label": c.estimator_label,
        "notes": c.notes,
        "difference_m": c.difference_m,
        "relative_difference_percent": c.relative_difference_percent,
        "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
    }


def _bad(message, code="INVALID_COMPARISON"):
    return jsonify({"error": message, "error_code": code}), 400


@research_bp.route("/fabric-comparisons", methods=["POST"])
@jwt_required()
def create_fabric_comparison():
    """
    Record a traditional (e.g. tailor's) fabric estimate for one of the user's patterns. The
    system's estimate for the same width and cutting mode is recomputed here by the real nesting
    code (the stored pattern is not changed), so both numbers describe the same situation.
    """
    current_user_id = get_jwt_identity()
    user = User.objects(id=current_user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _bad("Request body must be a JSON object.")

    try:
        pattern = PatternResult.objects(id=str(data.get("pattern_id", "")).strip("<>")).first()
    except Exception:
        return _bad("Invalid pattern_id format")
    if not pattern:
        return jsonify({"error": "Pattern not found"}), 404
    if not _owns(pattern, current_user_id):
        return jsonify({"error": "Unauthorized"}), 403
    if getattr(pattern, "validation_passed", True) is False:
        return jsonify({"error": "This pattern failed geometric validation, so it has no fabric estimate to compare.",
                        "error_code": "PATTERN_NOT_VALID"}), 422

    width = data.get("fabric_width_cm")
    if isinstance(width, bool) or not isinstance(width, (int, float)) or width not in STANDARD_FABRIC_WIDTHS:
        return _bad(f"fabric_width_cm must be one of {', '.join(str(w) for w in STANDARD_FABRIC_WIDTHS)}.")
    mode = data.get("cutting_mode", "auto")
    if mode not in ("auto", "folded", "open"):
        return _bad("cutting_mode must be auto, folded or open.")
    trad = data.get("traditional_estimate_m")
    if isinstance(trad, bool) or not isinstance(trad, (int, float)) or not 0.1 <= trad <= 20:
        return _bad("traditional_estimate_m must be a number of metres between 0.1 and 20.")
    source = data.get("estimate_source")
    if source not in ESTIMATE_SOURCES:
        return _bad(f"estimate_source must be one of: {', '.join(ESTIMATE_SOURCES)}.")
    label = (data.get("estimator_label") or "").strip()
    notes = (data.get("notes") or "").strip()
    if len(label) > 40 or len(notes) > 500:
        return _bad("estimator_label is limited to 40 characters and notes to 500.")

    fabric_type = (getattr(pattern, "measurements_snapshot", None) or {}).get("fabric_type", "woven")
    try:
        nesting = estimate_fabric(pattern.pattern_coordinates, width, mode, fabric_type)
    except NestingError as err:
        return jsonify({"error": err.message, "error_code": err.error_code, "nesting_failed": True}), 422

    comparison = FabricComparison(
        user_id=user, pattern_id=pattern, fabric_width_cm=float(width), cutting_mode=mode,
        system_cutting_mode=nesting["cutting_mode"],
        system_purchase_m=nesting["purchasing_recommended_m"],
        system_layout_length_cm=nesting["fabric_length_cm"],
        system_utilisation_percent=nesting.get("utilisation_percent"),
        traditional_estimate_m=float(trad), estimate_source=source,
        estimator_label=label or None, notes=notes or None,
    )
    comparison.save()
    return jsonify(_comparison_json(comparison)), 201


@research_bp.route("/fabric-comparisons", methods=["GET"])
@jwt_required()
def list_fabric_comparisons():
    """The caller's own comparisons, optionally for one pattern."""
    user = User.objects(id=get_jwt_identity()).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    query = {"user_id": user}
    pattern_id = request.args.get("pattern_id")
    if pattern_id:
        try:
            pattern = PatternResult.objects(id=pattern_id.strip("<>")).first()
        except Exception:
            return _bad("Invalid pattern_id format")
        if not pattern:
            return jsonify({"error": "Pattern not found"}), 404
        query["pattern_id"] = pattern
    items = FabricComparison.objects(**query).order_by("-created_at")
    return jsonify({"comparisons": [_comparison_json(c) for c in items]}), 200


@research_bp.route("/fabric-comparisons/<comparison_id>", methods=["DELETE"])
@jwt_required()
def delete_fabric_comparison(comparison_id):
    try:
        c = FabricComparison.objects(id=comparison_id.strip("<>")).first()
    except Exception:
        return _bad("Invalid comparison_id format")
    if not c:
        return jsonify({"error": "Comparison not found"}), 404
    if _ref_id(c, "user_id") != str(get_jwt_identity()):
        return jsonify({"error": "Unauthorized"}), 403
    c.delete()
    return jsonify({"message": "Comparison deleted"}), 200


def _comparison_rows():
    return [{"traditional_m": c.traditional_estimate_m, "system_m": c.system_purchase_m,
             "source": c.estimate_source, "pattern_id": _ref_id(c, "pattern_id")}
            for c in FabricComparison.objects.all()]


# ── GET RESEARCH METRICS SUMMARY ──────────────────────────────────────────────
@research_bp.route("/metrics", methods=["GET"])
@jwt_required()
def get_research_metrics():
    if not _is_researcher(get_jwt_identity()):
        return _forbidden()
    records = list(ResearchRecord.objects.all())
    model_eval = load_model_evaluation()
    fabric_comparison = summarize_fabric_comparisons(_comparison_rows())

    if not records and not model_eval.get("available") and fabric_comparison is None:
        return jsonify({
            "available": False,
            "message": "No research data available"
        }), 200

    total_patterns = len(records)
    total_participants = len(set(str(r.user_id.id) for r in records))
    legacy_excluded = sum(
        1 for r in records if getattr(r, "metrics_integrity_version", 1) < METRICS_INTEGRITY_VERSION
    )

    def avg(field):
        return mean_or_none([_trusted(r, field) for r in records])

    def count(field):
        return sum(1 for r in records if _trusted(r, field) is not None)

    def total_time(r):
        a, b = _trusted(r, "processing_time_sec"), _trusted(r, "pattern_generation_time_sec")
        return None if a is None or b is None else a + b

    def rnd(v, n):
        return None if v is None else round(v, n)

    feedback_list = []
    for r in records:
        if r.feedback_comment:
            feedback_list.append({
                "participant": _pseudonym(r.user_id),
                "score": r.feedback_score,
                "comment": r.feedback_comment,
                "date": r.created_at.strftime("%Y-%m-%d")
            })

    return jsonify({
        "available": True,
        "total_participants": total_participants,
        "total_patterns": total_patterns,
        "legacy_records_excluded_from_measured_fields": legacy_excluded,
        # Held-out test-split evaluation of the classifier, read from the genuine
        # training log (null-safe: {"available": False, ...} if the file is absent).
        "model_evaluation": model_eval,
        # Legacy keys kept for client compatibility. They are NOT measured from
        # participant data (per-user accuracy/precision/recall/F1 do not exist), so null.
        "ai_accuracy": None,
        "precision": None,
        "recall": None,
        "f1_score": None,
        "avg_ai_confidence": rnd(avg("ai_confidence_avg"), 4),
        "avg_correction_rate": rnd(avg("correction_rate"), 1),
        "correction_rate_n": count("correction_rate"),
        # A single "saving" figure is not claimed; the entered traditional estimates are summarised
        # descriptively in fabric_comparison (None until someone records one).
        "avg_fabric_savings": None,
        "fabric_comparison": fabric_comparison,
        "avg_processing_time": rnd(mean_or_none([total_time(r) for r in records]), 2),  # None until timed
        # Survey scores are genuine user input, valid for legacy records too.
        "usability_score": rnd(mean_or_none([r.feedback_score for r in records]), 1),
        "usability_score_n": sum(1 for r in records if r.feedback_score is not None),
        "feedbacks": feedback_list
    }), 200


# ── GET EXPORT RESEARCH DATA TO CSV ───────────────────────────────────────────
@research_bp.route("/export/csv", methods=["GET"])
@jwt_required()
def export_research_csv():
    if not _is_researcher(get_jwt_identity()):
        return _forbidden()
    records = ResearchRecord.objects.all()

    # Create an in-memory string buffer for CSV
    si = io.StringIO()
    cw = csv.writer(si)

    # Blank cell == not measured (or a legacy record whose value cannot be trusted).
    cw.writerow([
        "Record ID", "Participant (anonymous id)", "Garment Type", "Baseline Yardage (m)",
        "Optimized Yardage (m)", "Fabric Savings (m)", "Layout Efficiency (%)",
        "AI Feature Correction Rate (%)", "Processing Time (s)",
        "Feedback Usability Score", "Feedback Comment", "Date Created"
    ])

    def cell(v):
        return "" if v is None else v

    for r in records:
        garment = r.pattern_id.garment_type if r.pattern_id else "N/A"
        proc, gen = _trusted(r, "processing_time_sec"), _trusted(r, "pattern_generation_time_sec")
        cw.writerow([
            str(r.id),
            _pseudonym(r.user_id),
            garment,
            cell(_trusted(r, "baseline_yardage_m")),
            cell(_trusted(r, "optimized_yardage_m")),
            cell(_trusted(r, "fabric_savings_m")),
            cell(_trusted(r, "layout_efficiency")),
            cell(_trusted(r, "correction_rate")),
            cell(proc + gen if proc is not None and gen is not None else None),
            r.feedback_score,
            r.feedback_comment,
            r.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=research_metrics_export.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@research_bp.route("/export/fabric-comparisons.csv", methods=["GET"])
@jwt_required()
def export_fabric_comparisons_csv():
    """Raw traditional-vs-system rows for the thesis analysis (researchers only, pseudonymised)."""
    if not _is_researcher(get_jwt_identity()):
        return _forbidden()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Comparison ID", "Participant (anonymous id)", "Pattern ID", "Garment Type",
                 "Fabric Width (cm)", "Requested Cutting Mode", "System Cutting Mode",
                 "System Layout Length (cm)", "System Recommended Purchase (m)", "System Utilisation (%)",
                 "Traditional Estimate (m)", "Estimate Source", "Estimator Label",
                 "Difference (m, traditional - system)", "Relative Difference (% of traditional)", "Date"])
    for c in FabricComparison.objects.all().order_by("created_at"):
        cw.writerow([str(c.id), _pseudonym(c.user_id), str(c.pattern_id.id), c.pattern_id.garment_type,
                     c.fabric_width_cm, c.cutting_mode, c.system_cutting_mode, c.system_layout_length_cm,
                     c.system_purchase_m, "" if c.system_utilisation_percent is None else c.system_utilisation_percent,
                     c.traditional_estimate_m, c.estimate_source, c.estimator_label or "",
                     c.difference_m, c.relative_difference_percent, c.created_at.strftime("%Y-%m-%d %H:%M:%S")])
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=fabric_comparisons.csv"
    output.headers["Content-type"] = "text/csv"
    return output


def make_response(content):
    return Response(content)
