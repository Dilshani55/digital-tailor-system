class DesignImageModel:
    def __init__(self, user_id, filename, file_path, detected_features=None):
        self.user_id = user_id
        self.filename = filename
        self.file_path = file_path
        self.detected_features = detected_features or {}

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "detected_features": self.detected_features
        }
