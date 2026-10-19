# a donor who chose to leave contact details (FR-05)
class Donor:
    def __init__(self, donor_id, name, contact, contact_consent):
        self.id = donor_id
        self.name = name
        self.contact = contact
        self.contact_consent = contact_consent

    def to_dict(self):
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d):
        return Donor(d["id"], d["name"], d["contact"], d["contact_consent"])


# one batch of donated food that sits on a shelf (FR-04, FR-08)
class DonationBatch:
    STORAGE = ["Ambient", "Chilled", "Frozen"]

    def __init__(self, batch_id, item_name, quantity, unit, expiry_date, storage,
                 dietary_attributes, shelf_location, received_date, donation_ref, donor_id=None):
        self.id = batch_id
        self.item_name = item_name
        self.quantity = quantity
        self.unit = unit
        self.expiry_date = expiry_date      # "YYYY-MM-DD"
        self.storage = storage
        self.dietary_attributes = dietary_attributes
        self.shelf_location = shelf_location
        self.received_date = received_date
        self.donation_ref = donation_ref    # e.g. DON-0001, shared by batches of one donation
        self.donor_id = donor_id            # None = anonymous donation

    def to_dict(self):
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d):
        return DonationBatch(d["id"], d["item_name"], d["quantity"], d["unit"], d["expiry_date"],
                             d["storage"], d["dietary_attributes"], d["shelf_location"],
                             d["received_date"], d["donation_ref"], d.get("donor_id"))
