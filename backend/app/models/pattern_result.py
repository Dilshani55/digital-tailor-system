from datetime import datetime, timezone

class PatternResultModel:
    COLLECTION_NAME = 'pattern_results'

    def __init__(self, user_id, design_image_id, drafting_block_data, nesting_efficiency, required_fabric_yardage, _id=None, created_at=None):
        self._id = _id
        self.user_id = user_id
        self.design_image_id = design_image_id
        self.drafting_block_data = drafting_block_data
        self.nesting_efficiency = nesting_efficiency
        self.required_fabric_yardage = required_fabric_yardage
        self.created_at = created_at or datetime.now(timezone.utc)

    def to_dict(self):
        doc = {
            "user_id": self.user_id,
            "design_image_id": self.design_image_id,
            "drafting_block_data": self.drafting_block_data,
            "nesting_efficiency": self.nesting_efficiency,
            "required_fabric_yardage": self.required_fabric_yardage,
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
            design_image_id=doc.get("design_image_id"),
            drafting_block_data=doc.get("drafting_block_data"),
            nesting_efficiency=doc.get("nesting_efficiency"),
            required_fabric_yardage=doc.get("required_fabric_yardage"),
            created_at=doc.get("created_at")
        )
