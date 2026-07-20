from datetime import datetime, timezone

class UserModel:
    COLLECTION_NAME = 'users'

    def __init__(self, username, email, password_hash, _id=None, created_at=None):
        self._id = _id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at or datetime.now(timezone.utc)

    def to_dict(self):
        doc = {
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "created_at": self.created_at
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
            username=doc.get("username"),
            email=doc.get("email"),
            password_hash=doc.get("password_hash"),
            created_at=doc.get("created_at")
        )
