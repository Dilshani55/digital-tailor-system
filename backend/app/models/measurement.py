from mongoengine import Document, ReferenceField, FloatField, StringField, DateTimeField
from datetime import datetime, timezone
from app.models.user import User

class MeasurementProfile(Document):
    meta = {'collection': 'measurements'}

    user_id = ReferenceField(User, required=True)
    client_name = StringField(default="Customer Profile")
    email = StringField()
    notes = StringField(default="No notes.")
    
    bust_cm = FloatField(required=True)
    waist_cm = FloatField(required=True)
    hip_cm = FloatField(required=True)
    height_cm = FloatField(required=True)
    
    # Extra tailoring metrics
    shoulder_cm = FloatField(default=12.0)
    neck_cm = FloatField(default=36.0)
    armhole_cm = FloatField(default=20.0)
    sleeve_cm = FloatField(default=55.0)
    garment_length_cm = FloatField(default=65.0)
    
    fabric_type = StringField(default="woven")
    unit = StringField(default="cm")
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
