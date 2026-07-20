from datetime import datetime, timezone

class PDFExportModel:
    COLLECTION_NAME = 'pdf_exports'

    def __init__(self, pattern_result_id, pdf_path, _id=None, generated_at=None):
        self._id = _id
        self.pattern_result_id = pattern_result_id
        self.pdf_path = pdf_path
        self.generated_at = generated_at or datetime.now(timezone.utc)

    def to_dict(self):
        doc = {
            "pattern_result_id": self.pattern_result_id,
            "pdf_path": self.pdf_path,
            "generated_at": self.generated_at
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
            pattern_result_id=doc.get("pattern_result_id"),
            pdf_path=doc.get("pdf_path"),
            generated_at=doc.get("generated_at")
        )
