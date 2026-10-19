# who changed stock or did something sensitive, and why (FR-11)
class AuditLogEntry:
    def __init__(self, user, action, details, reason_code, quantity, timestamp):
        self.user = user
        self.action = action
        self.details = details
        self.reason_code = reason_code
        self.quantity = quantity
        self.timestamp = timestamp

    def to_dict(self):
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d):
        return AuditLogEntry(d["user"], d["action"], d["details"], d["reason_code"],
                             d["quantity"], d["timestamp"])


# a simulated message to a household, written to the notification log (FR-28 to FR-30)
class NotificationRecord:
    def __init__(self, order_ref, method, kind, message, timestamp):
        self.order_ref = order_ref
        self.method = method
        self.kind = kind                    # "Pickup confirmation" or "Substitution"
        self.message = message
        self.timestamp = timestamp

    def to_dict(self):
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d):
        return NotificationRecord(d["order_ref"], d["method"], d["kind"], d["message"], d["timestamp"])
