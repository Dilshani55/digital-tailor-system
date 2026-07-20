class PDFExportModel:
    def __init__(self, pattern_result_id, pdf_path, generated_at=None):
        self.pattern_result_id = pattern_result_id
        self.pdf_path = pdf_path
        self.generated_at = generated_at

    def to_dict(self):
        return {
            "pattern_result_id": self.pattern_result_id,
            "pdf_path": self.pdf_path,
            "generated_at": self.generated_at
        }
