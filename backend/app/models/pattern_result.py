from mongoengine import (
    Document, ReferenceField, ListField, DictField,
    FloatField, StringField, DateTimeField, BooleanField,
)
from datetime import datetime, timezone
from app.models.session import Session

class PatternResult(Document):
    meta = {'collection': 'pattern_results', 'indexes': [('session_id', '-generated_at')]}

    session_id = ReferenceField(Session, required=True)
    pattern_coordinates = ListField(DictField(), default=list)
    yardage_metres = FloatField(default=0.0)
    nesting_summary = DictField(default=dict)
    project_name = StringField(max_length=80)             # optional design / project name given by the user
    drafting_info = DictField(default=dict)               # block, ease, construction notes saved at generation (PDF source)
    width_estimates = ListField(DictField(), default=list)   # one entry per standard width (36"/45"/60"), for results and PDF
    garment_type = StringField(default="blouse")
    selected_fabric_id = StringField(default="cotton-poplin")
    selected_fabric_name = StringField(default="Cotton Poplin")
    fabric_selection_snapshot = DictField(default=dict)  # source sample and server-recomputed user preference comparison
    validation_report = DictField(default=dict)
    base_block = DictField(default=dict)             # base block stage (drafting values, ease, geometry)
    design_spec = DictField(default=dict)            # canonical confirmed design used for this pattern
    measurements_snapshot = DictField(default=dict)  # validated canonical-cm measurements used for this pattern
    validation_passed = BooleanField(default=True)
    generation_time_sec = FloatField(default=None)  # measured wall-clock time of engine.generate(); None for older records
    generated_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
