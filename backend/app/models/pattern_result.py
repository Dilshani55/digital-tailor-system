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
    design_spec = DictField(default=dict)            # canonical confirmed design used for this pattern
    measurements_snapshot = DictField(default=dict)  # validated canonical-cm measurements used for this pattern
    validation_passed = BooleanField(default=True)
    generated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
