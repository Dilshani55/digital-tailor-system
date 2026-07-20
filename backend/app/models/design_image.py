from datetime import datetime, timezone

class DesignImageModel:
    COLLECTION_NAME = 'design_images'

    def __init__(self, user_id, filename, file_path, detected_features=None, _id=None, uploaded_at=None):
        self._id = _id
        self.user_id = user_id
        self.filename = filename
        self.file_path = file_path
        self.detected_features = detected_features or {}
        self.uploaded_at = uploaded_at or datetime.now(timezone.utc)

    def to_dict(self):
        doc = {
            "user_id": self.user_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "detected_features": self.detected_features,
            "uploaded_at": self.uploaded_at
        }
        if self._id:
            doc["_id"] = self._id
        return doc

    @classmethod
    def from_dict(cls, doc):
        if not doc:
            return None
        return cls(
            _id=doc.get("_id"),
            user_id=doc.get("user_id"),
            filename=doc.get("filename"),
            file_path=doc.get("file_path"),
            detected_features=doc.get("detected_features"),
            uploaded_at=doc.get("uploaded_at")
        )
