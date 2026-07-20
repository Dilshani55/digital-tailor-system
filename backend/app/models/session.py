from datetime import datetime, timezone

class SessionModel:
    COLLECTION_NAME = 'sessions'

    def __init__(self, user_id, token, _id=None, created_at=None, expires_at=None):
        self._id = _id
        self.user_id = user_id
        self.token = token
        self.created_at = created_at or datetime.now(timezone.utc)
        self.expires_at = expires_at

    def to_dict(self):
        doc = {
            "user_id": self.user_id,
            "token": self.token,
            "created_at": self.created_at,
            "expires_at": self.expires_at
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
            token=doc.get("token"),
            created_at=doc.get("created_at"),
            expires_at=doc.get("expires_at")
        )
