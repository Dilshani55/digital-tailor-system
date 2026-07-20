from datetime import datetime, timezone

class MeasurementModel:
    COLLECTION_NAME = 'measurements'

    def __init__(self, user_id, bust, waist, hip, height, unit='cm', _id=None, created_at=None):
        self._id = _id
        self.user_id = user_id
        self.bust = float(bust)
        self.waist = float(waist)
        self.hip = float(hip)
        self.height = float(height)
        self.unit = unit
        self.created_at = created_at or datetime.now(timezone.utc)

    def to_dict(self):
        doc = {
            "user_id": self.user_id,
            "bust": self.bust,
            "waist": self.waist,
            "hip": self.hip,
            "height": self.height,
            "unit": self.unit,
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
            user_id=doc.get("user_id"),
            bust=doc.get("bust"),
            waist=doc.get("waist"),
            hip=doc.get("hip"),
            height=doc.get("height"),
            unit=doc.get("unit", "cm"),
            created_at=doc.get("created_at")
        )
