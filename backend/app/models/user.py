from mongoengine import Document, StringField, DateTimeField
from datetime import datetime, timezone

class User(Document):
    meta = {'collection': 'users'}

    full_name = StringField(required=True)
    email = StringField(required=True, unique=True)
    password = StringField(required=True)
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
