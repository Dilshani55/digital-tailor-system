class SessionModel:
    def __init__(self, user_id, token, created_at=None):
        self.user_id = user_id
        self.token = token
        self.created_at = created_at

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "token": self.token,
            "created_at": self.created_at
        }
