from mongoengine import Document, ReferenceField, StringField, DictField, FloatField, DateTimeField
from datetime import datetime, timezone
from app.models.user import User

class DesignImage(Document):
    meta = {'collection': 'design_images'}

    user_id = ReferenceField(User, required=True)
    file_path = StringField(required=True)
    detected_features = DictField(default=dict)
    garment_attributes = DictField(default=dict)
    confidence_score = FloatField(default=0.0)
    uploaded_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
