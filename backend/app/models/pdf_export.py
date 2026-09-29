from mongoengine import Document, ReferenceField, StringField, DateTimeField
from datetime import datetime, timezone
from app.models.pattern_result import PatternResult

class PdfExport(Document):
    meta = {'collection': 'pdf_exports', 'indexes': [('pattern_id', '-exported_at')]}

    pattern_id = ReferenceField(PatternResult, required=True)
    file_path = StringField(required=True)
    exported_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
