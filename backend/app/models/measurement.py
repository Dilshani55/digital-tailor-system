from mongoengine import Document, ReferenceField, FloatField, StringField, DateTimeField, DictField, IntField
from datetime import datetime, timezone
from app.models.user import User

class MeasurementProfile(Document):
    meta = {'collection': 'measurements', 'indexes': [('user_id', '-created_at')]}

    user_id = ReferenceField(User, required=True)
    client_name = StringField(default="Customer Profile")
    email = StringField()
    notes = StringField(default="No notes.")

    # ALL *_cm fields hold CANONICAL centimetres (see app/logic/measurement_schema.py).
    # Core circumference / stature — required to create a profile.
    bust_cm = FloatField(required=True)
    waist_cm = FloatField(required=True)
    hip_cm = FloatField(required=True)
    height_cm = FloatField(required=True)

    # Drafting measurements. None == not measured. There are NO defaults on purpose:
    # a missing measurement must never be silently replaced by an invented value.
    neck_cm = FloatField()
    shoulder_cm = FloatField()           # shoulder length
    across_back_cm = FloatField()
    back_waist_length_cm = FloatField()
    armhole_cm = FloatField()            # legacy alias, kept equal to armhole_depth_cm
    armhole_depth_cm = FloatField()
    garment_length_cm = FloatField()
    bicep_cm = FloatField()
    sleeve_cm = FloatField()             # sleeve length
    wrist_cm = FloatField()

    # Fabric type/stretch + required fit
    fabric_type = StringField(default="woven")       # woven | knit | stretch-knit
    fit_preference = StringField(default="standard") # close | standard | loose

    # What the user actually entered, per field: {field: {"value": number, "unit": "cm"|"in"}}
    original_values = DictField(default=dict)
    # Unit of the most recent submission (informational; per-field units are in original_values)
    unit = StringField(default="cm")
    measurement_schema_version = IntField(default=1)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
