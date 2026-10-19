# a person who can sign in: Administrator, Staff or Volunteer
class User:
    ROLES = ["Administrator", "Staff", "Volunteer"]

    def __init__(self, user_id, username, password_hash, salt, role, active=True):
        self.id = user_id
        self.username = username
        self.password_hash = password_hash
        self.salt = salt
        self.role = role
        # accounts are disabled, never deleted, so the audit log still makes sense (FR-01)
        self.active = active

    def to_dict(self):
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d):
        return User(d["id"], d["username"], d["password_hash"], d["salt"], d["role"], d.get("active", True))
