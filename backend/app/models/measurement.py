from mongoengine import Document, ReferenceField, FloatField, StringField, DateTimeField
from datetime import datetime, timezone
from app.models.user import User

class MeasurementProfile(Document):
    meta = {'collection': 'measurements'}

    user_id = ReferenceField(User, required=True)
    client_name = StringField(default="Customer Profile")
    bust_cm = FloatField(required=True)
    waist_cm = FloatField(required=True)
    hip_cm = FloatField(required=True)
    height_cm = FloatField(required=True)
    fabric_type = StringField(default="woven")
    unit = StringField(default="cm")
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
