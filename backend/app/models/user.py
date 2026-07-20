class UserModel:
    def __init__(self, username, email, password_hash):
        self.username = username
        self.email = email
        self.password_hash = password_hash

    def to_dict(self):
        return {
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash
        }
