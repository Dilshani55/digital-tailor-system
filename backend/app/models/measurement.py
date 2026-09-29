from mongoengine import Document, ReferenceField, FloatField, StringField, DateTimeField
from datetime import datetime, timezone
from app.models.user import User

class MeasurementProfile(Document):
    meta = {'collection': 'measurements'}

    user_id = ReferenceField(User, required=True)
    client_name = StringField(default="Customer Profile")
    email = StringField()
    notes = StringField(default="No notes.")

    # Core circumference / stature (engine still uses hip + height)
    bust_cm = FloatField(required=True)
    waist_cm = FloatField(required=True)
    hip_cm = FloatField(required=True)
    height_cm = FloatField(required=True)

    # Locked drafting measurements (workflow step 4)
    neck_cm = FloatField(default=36.0)
    shoulder_cm = FloatField(default=12.0)           # shoulder length
    across_back_cm = FloatField(default=34.0)
    back_waist_length_cm = FloatField(default=40.0)
    armhole_cm = FloatField(default=20.0)            # legacy alias
    armhole_depth_cm = FloatField(default=20.0)
    garment_length_cm = FloatField(default=65.0)
    bicep_cm = FloatField(default=28.0)
    sleeve_cm = FloatField(default=55.0)             # sleeve length
    wrist_cm = FloatField(default=16.0)

    # Fabric type/stretch + required fit
    fabric_type = StringField(default="woven")       # woven | knit | stretch-knit
    fit_preference = StringField(default="standard") # close | standard | loose

    unit = StringField(default="cm")
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
