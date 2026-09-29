from mongoengine import (
    Document, ReferenceField, ListField, DictField,
    FloatField, StringField, DateTimeField, BooleanField,
)
from datetime import datetime, timezone
from app.models.session import Session

class PatternResult(Document):
    meta = {'collection': 'pattern_results'}

    session_id = ReferenceField(Session, required=True)
    pattern_coordinates = ListField(DictField(), default=list)
    yardage_metres = FloatField(default=0.0)
    nesting_summary = DictField(default=dict)
    garment_type = StringField(default="blouse")
    selected_fabric_id = StringField(default="cotton-poplin")
    selected_fabric_name = StringField(default="Cotton Poplin")
    validation_report = DictField(default=dict)
    validation_passed = BooleanField(default=True)
    generated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
