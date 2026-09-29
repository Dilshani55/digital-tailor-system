from mongoengine import Document, ReferenceField, DictField, FloatField, IntField, StringField, DateTimeField
from datetime import datetime, timezone
from app.models.user import User
from app.models.session import Session
from app.models.pattern_result import PatternResult

# Records written before the research-integrity cleanup lack the
# metrics_integrity_version field and load with the default (1). Version-1 rows
# may contain values invented by earlier code (confidence 0.91, times 0.82/0.38 s,
# 2.5 m baseline, ...), so only feedback_score / feedback_comment / user / date
# are trusted from them.
METRICS_INTEGRITY_VERSION = 2


class ResearchRecord(Document):
    meta = {'collection': 'research_records', 'indexes': ['user_id', 'pattern_id']}

    user_id = ReferenceField(User, required=True)
    session_id = ReferenceField(Session)
    pattern_id = ReferenceField(PatternResult)

    # Every measured field defaults to None == "not measured". Never a made-up value.
    corrections_made = DictField(default=dict)     # {head: {predicted, confirmed}}
    correction_rate = FloatField(default=None)     # % of classifier heads the user changed
    ai_confidence_avg = FloatField(default=None)   # mean top-1 softmax confidence (classifier)

    processing_time_sec = FloatField(default=None)          # image analysis time (not yet measured)
    pattern_generation_time_sec = FloatField(default=None)  # drafting time (not yet measured)

    baseline_yardage_m = FloatField(default=None)   # no baseline layout is defined yet
    optimized_yardage_m = FloatField(default=None)
    fabric_savings_m = FloatField(default=None)
    layout_efficiency = FloatField(default=None)

    feedback_score = IntField(min_value=1, max_value=5) # 1-5 stars usability survey
    feedback_comment = StringField()

    metrics_integrity_version = IntField(default=1)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
