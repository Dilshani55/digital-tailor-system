from mongoengine import Document, ReferenceField, StringField, DateTimeField
from datetime import datetime, timezone
from app.models.user import User
from app.models.design_image import DesignImage
from app.models.measurement import MeasurementProfile

class Session(Document):
    meta = {'collection': 'sessions'}

    user_id = ReferenceField(User, required=True)
    image_id = ReferenceField(DesignImage)
    measurement_id = ReferenceField(MeasurementProfile)
    status = StringField(default="processing")
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
