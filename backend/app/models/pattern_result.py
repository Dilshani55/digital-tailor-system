from mongoengine import Document, ReferenceField, ListField, DictField, FloatField, StringField, DateTimeField
from datetime import datetime, timezone
from app.models.session import Session

class PatternResult(Document):
    meta = {'collection': 'pattern_results'}

    session_id = ReferenceField(Session, required=True)
    pattern_coordinates = ListField(DictField(), default=list)
    yardage_metres = FloatField(default=0.0)
    garment_type = StringField(default="blouse")
    generated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
