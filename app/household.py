# whether the household agreed to us keeping sensitive needs (FR-14)
class ConsentRecord:
    def __init__(self, given=False, date=None, withdrawn_date=None):
        self.given = given
        self.date = date
        self.withdrawn_date = withdrawn_date

    def to_dict(self):
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d):
        return ConsentRecord(d.get("given", False), d.get("date"), d.get("withdrawn_date"))


# client household, only keeps what is needed to give suitable food (FR-12)
class Household:
    def __init__(self, household_id, preferred_name, contact_method, contact_detail,
                 adults, children, infants, seniors, preferred_pickup_times,
                 safety_needs=None, preferences=None, accessibility_needs="",
                 private_note="", consent=None, last_service_date=None):
        self.id = household_id
        self.preferred_name = preferred_name
        self.contact_method = contact_method
        self.contact_detail = contact_detail
        self.adults = adults
        self.children = children
        self.infants = infants
        self.seniors = seniors              # adults aged 65 or older
        self.preferred_pickup_times = preferred_pickup_times
        # allergies, medical and religious needs - never overridden (FR-16)
        self.safety_needs = safety_needs or []
        # other dietary preferences - can be overridden with a reason (FR-17)
        self.preferences = preferences or []
        self.accessibility_needs = accessibility_needs
        self.private_note = private_note    # staff only, never shown to volunteers
        self.consent = consent or ConsentRecord()
        self.last_service_date = last_service_date

    def size(self):
        return self.adults + self.children + self.infants

    def to_dict(self):
        d = dict(self.__dict__)
        d["consent"] = self.consent.to_dict()
        return d

    @staticmethod
    def from_dict(d):
        return Household(d["id"], d["preferred_name"], d["contact_method"], d["contact_detail"],
                         d["adults"], d["children"], d["infants"], d["seniors"],
                         d["preferred_pickup_times"], d.get("safety_needs"), d.get("preferences"),
                         d.get("accessibility_needs", ""), d.get("private_note", ""),
                         ConsentRecord.from_dict(d.get("consent", {})), d.get("last_service_date"))
