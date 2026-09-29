import csv
import io
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.pattern_result import PatternResult
from app.models.research_record import ResearchRecord, METRICS_INTEGRITY_VERSION
from app.logic.research_metrics import (
    load_model_evaluation, compute_feature_corrections, mean_or_none,
)

research_bp = Blueprint("research", __name__)


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

    try:
        pattern = PatternResult.objects(id=pattern_id).first()
    except Exception:
        return jsonify({"error": "Invalid pattern_id format"}), 400

    if not pattern:
        return jsonify({"error": "Pattern not found"}), 404

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
        feedback_score = int(score),
        feedback_comment = comment,
        metrics_integrity_version = METRICS_INTEGRITY_VERSION,
    )
    record.save()

    return jsonify({"message": "Usability survey feedback recorded successfully", "record_id": str(record.id)}), 201


# ── GET RESEARCH METRICS SUMMARY ──────────────────────────────────────────────
@research_bp.route("/metrics", methods=["GET"])
@jwt_required()
def get_research_metrics():
    records = list(ResearchRecord.objects.all())
    model_eval = load_model_evaluation()

    if not records and not model_eval.get("available"):
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
                "participant": r.user_id.full_name,
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
        # No baseline layout is defined yet, so no fabric saving can be claimed.
        "avg_fabric_savings": None,
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
    records = ResearchRecord.objects.all()

    # Create an in-memory string buffer for CSV
    si = io.StringIO()
    cw = csv.writer(si)

    # Blank cell == not measured (or a legacy record whose value cannot be trusted).
    cw.writerow([
        "Record ID", "Participant Name", "Garment Type", "Baseline Yardage (m)",
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
            r.user_id.full_name,
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

def make_response(content):
    return Response(content)
