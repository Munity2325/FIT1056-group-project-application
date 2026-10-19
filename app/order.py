# a replacement item recorded when the original item ran out (FR-18)
class Substitution:
    def __init__(self, original_item, substitute_item, substitute_batch_id, recorded_by, timestamp, quantity=0):
        self.original_item = original_item
        self.substitute_item = substitute_item
        self.substitute_batch_id = substitute_batch_id
        self.recorded_by = recorded_by
        self.timestamp = timestamp
        self.quantity = quantity

    def to_dict(self):
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d):
        return Substitution(d["original_item"], d["substitute_item"], d["substitute_batch_id"],
                            d["recorded_by"], d["timestamp"], d.get("quantity", 0))


# a food allocation for one household and its pickup details (FR-19 to FR-21)
class Order:
    STATUSES = ["Requested", "Approved", "Packed", "Ready", "Collected", "Not Collected"]

    def __init__(self, order_id, household_id, items, pickup_time, created_by, created_at,
                 status="Requested", alternative_collector="", substitutions=None, exceptions=None):
        self.id = order_id
        self.household_id = household_id
        # each item: {"batch_id", "item_name", "quantity"}
        self.items = items
        self.pickup_time = pickup_time
        self.created_by = created_by
        self.created_at = created_at
        self.status = status
        self.alternative_collector = alternative_collector
        self.substitutions = substitutions or []
        # preference overrides with their justification (FR-17)
        self.exceptions = exceptions or []

    def reference(self):
        # order reference used on picking lists instead of the client's name
        return f"FS-{self.id:04d}"

    def to_dict(self):
        d = dict(self.__dict__)
        d["substitutions"] = [s.to_dict() for s in self.substitutions]
        return d

    @staticmethod
    def from_dict(d):
        return Order(d["id"], d["household_id"], d["items"], d["pickup_time"], d["created_by"],
                     d["created_at"], d.get("status", "Requested"), d.get("alternative_collector", ""),
                     [Substitution.from_dict(s) for s in d.get("substitutions", [])],
                     d.get("exceptions", []))
