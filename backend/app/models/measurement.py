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
    # Every measurement is optional on the profile: which ones a pattern needs depends on the confirmed
    # design (config/measurement_requirements.json). Nothing is ever defaulted.
    bust_cm = FloatField()
    waist_cm = FloatField()
    hip_cm = FloatField()
    height_cm = FloatField()

    # Drafting measurements. None == not measured. There are NO defaults on purpose:
    # a missing measurement must never be silently replaced by an invented value.
    neck_cm = FloatField()
    shoulder_cm = FloatField()           # shoulder length
    across_back_cm = FloatField()
    back_waist_length_cm = FloatField()
    armhole_cm = FloatField()            # legacy alias, kept equal to armhole_depth_cm
    armhole_depth_cm = FloatField()
    garment_length_cm = FloatField()
    bicep_cm = FloatField()              # upper arm around
    sleeve_cm = FloatField()             # sleeve length
    wrist_cm = FloatField()              # legacy (a long sleeve's sleeve end)

    # schema version 3 (drafting method of docs/pattern-drafting-method.md). Old profiles simply lack them:
    # the wizard then asks for the missing ones, nothing is estimated.
    shoulder_width_cm = FloatField()     # shoulder tip to shoulder tip, across the back
    shoulder_to_bust_cm = FloatField()
    bust_point_distance_cm = FloatField()
    waist_to_hip_cm = FloatField()
    sleeve_end_cm = FloatField()         # around the arm where the sleeve ends
    neck_width_cm = FloatField()         # design value: full neckline width
    front_neck_depth_cm = FloatField()   # design value
    back_neck_depth_cm = FloatField()    # design value

    # Fabric type/stretch + required fit
    fabric_type = StringField(default="woven")       # woven | knit | stretch-knit
    fit_preference = StringField(default="standard") # close | standard | loose

    # What the user actually entered, per field: {field: {"value": number, "unit": "cm"|"in"}}
    original_values = DictField(default=dict)
    # Unit of the most recent submission (informational; per-field units are in original_values)
    unit = StringField(default="cm")
    measurement_schema_version = IntField(default=1)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
