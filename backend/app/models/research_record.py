from mongoengine import Document, ReferenceField, DictField, FloatField, IntField, StringField, DateTimeField
from datetime import datetime, timezone
from app.models.user import User
from app.models.session import Session
from app.models.pattern_result import PatternResult

class ResearchRecord(Document):
    meta = {'collection': 'research_records'}

    user_id = ReferenceField(User, required=True)
    session_id = ReferenceField(Session)
    pattern_id = ReferenceField(PatternResult)
    
    corrections_made = DictField(default=dict)
    correction_rate = FloatField(default=0.0) # percentage of fields corrected by user
    ai_confidence_avg = FloatField(default=0.91)
    
    processing_time_sec = FloatField(default=0.85) # image analysis time
    pattern_generation_time_sec = FloatField(default=0.45) # CAD calculation time
    
    baseline_yardage_m = FloatField(default=2.5)
    optimized_yardage_m = FloatField(default=0.0)
    fabric_savings_m = FloatField(default=0.0)
    layout_efficiency = FloatField(default=0.0)
    
    feedback_score = IntField(min_value=1, max_value=5) # 1-5 stars usability survey
    feedback_comment = StringField()
    
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
