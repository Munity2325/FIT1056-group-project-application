# a volunteer job, e.g. packing an order (FR-22, FR-23)
class Task:
    def __init__(self, task_id, task_type, location, est_minutes, order_id=None,
                 status="Available", history=None):
        self.id = task_id
        self.task_type = task_type
        self.location = location
        self.est_minutes = est_minutes
        self.order_id = order_id
        self.status = status                # Available -> Claimed -> In progress -> Completed
        # every change: {"status", "user", "timestamp"}
        self.history = history or []

    def to_dict(self):
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d):
        return Task(d["id"], d["task_type"], d["location"], d["est_minutes"], d.get("order_id"),
                    d.get("status", "Available"), d.get("history", []))
