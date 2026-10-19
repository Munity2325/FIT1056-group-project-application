import json
import hashlib
import secrets
import datetime
import logging

from app.user import User
from app.donation import Donor, DonationBatch
from app.household import Household
from app.order import Order
from app.task import Task
from app.records import AuditLogEntry, NotificationRecord

# what each role is allowed to do (FR-03, NFR-06)
# a new role gets nothing until it is added here
PERMISSIONS = {
    "Administrator": {"manage_users", "view_reports", "view_inventory", "view_audit_log"},
    "Staff": {"record_donations", "view_inventory", "adjust_stock", "manage_households",
              "view_client_details", "manage_orders", "view_reports", "view_notifications"},
    "Volunteer": {"view_tasks", "adjust_stock", "view_inventory"},
}

# why we ask for each field, shown next to it on the form (FR-13)
FIELD_HELP = {
    "preferred_name": "So staff know what to call you. It does not need to be your full legal name.",
    "contact_method": "So we can tell you when your food is ready, in the way that suits you.",
    "household": "So the food allocation has enough for everyone at home.",
    "infants": "So we can include formula or baby food in your food allocation.",
    "seniors": "So we can include food that suits older adults.",
    "pickup_times": "So your pickup fits around school, work or transport.",
    "needs": "Only kept if you agree. Used so we never give you food you cannot eat.",
    "accessibility": "Only kept if you agree. Helps us make pickup easier for you.",
}


class FoodShareManager:
    def __init__(self, data_path="data/foodshare.json", config_path="config/dietary_config.json",
                 messages_path="config/messages.json"):
        self.data_path = data_path
        self.users = []
        self.donors = []
        self.batches = []
        self.households = []
        self.orders = []
        self.tasks = []
        self.audit_log = []
        self.notifications = []
        self.donation_counter = 0   # last used DON- number

        # settings live in json so they can change without touching the code (NFR-14)
        with open(config_path, "r") as f:
            self.config = json.load(f)
        with open(messages_path, "r") as f:
            self.messages = json.load(f)

        self._load_data()

    # saving and loading

    def _load_data(self):
        try:
            with open(self.data_path, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            print("Data file not found. Starting with a clean state.")
            return
        except json.JSONDecodeError:
            print("Data file is corrupted. Starting with a clean state.")
            return

        self.users = [User.from_dict(d) for d in data.get("users", [])]
        self.donors = [Donor.from_dict(d) for d in data.get("donors", [])]
        self.batches = [DonationBatch.from_dict(d) for d in data.get("batches", [])]
        self.households = [Household.from_dict(d) for d in data.get("households", [])]
        self.orders = [Order.from_dict(d) for d in data.get("orders", [])]
        self.tasks = [Task.from_dict(d) for d in data.get("tasks", [])]
        self.audit_log = [AuditLogEntry.from_dict(d) for d in data.get("audit_log", [])]
        self.notifications = [NotificationRecord.from_dict(d) for d in data.get("notifications", [])]
        self.donation_counter = data.get("donation_counter", 0)

    def _save_data(self):
        data = {
            "users": [u.to_dict() for u in self.users],
            "donors": [d.to_dict() for d in self.donors],
            "batches": [b.to_dict() for b in self.batches],
            "households": [h.to_dict() for h in self.households],
            "orders": [o.to_dict() for o in self.orders],
            "tasks": [t.to_dict() for t in self.tasks],
            "audit_log": [a.to_dict() for a in self.audit_log],
            "notifications": [n.to_dict() for n in self.notifications],
            "donation_counter": self.donation_counter,
        }
        with open(self.data_path, "w") as f:
            json.dump(data, f, indent=4)

    def _next_id(self, records):
        # biggest id + 1, so a gap from a deleted record is never reused
        if not records:
            return 1
        return max(r.id for r in records) + 1

    def _now(self):
        return datetime.datetime.now().isoformat(timespec="seconds")

    # user accounts and access (F-01)

    @staticmethod
    def hash_password(password, salt):
        # passwords are only ever stored as salted hashes (NFR-04)
        return hashlib.sha256((salt + password).encode()).hexdigest()

    def find_user(self, username):
        for user in self.users:
            if user.username.lower() == username.lower():
                return user
        return None

    def find_user_by_id(self, user_id):
        for user in self.users:
            if user.id == user_id:
                return user
        return None

    def create_user(self, username, password, role):
        if not username.strip() or not password:
            print("Error: Username and password are required.")
            return None
        if role not in User.ROLES:
            print(f"Error: Unknown role {role}.")
            return None
        if self.find_user(username):
            print(f"Error: Username {username} is already taken.")
            return None

        salt = secrets.token_hex(8)
        user = User(self._next_id(self.users), username.strip(), self.hash_password(password, salt), salt, role)
        self.users.append(user)
        self._save_data()
        logging.info(f"User account created: {user.username} ({role}).")
        return user

    def authenticate(self, username, password):
        user = self.find_user(username)
        # same answer for wrong name or wrong password, so nobody can guess usernames
        if not user or not user.active:
            return None
        if self.hash_password(password, user.salt) != user.password_hash:
            return None
        return user

    def set_user_active(self, user_id, active):
        user = self.find_user_by_id(user_id)
        if not user:
            return False
        user.active = active
        self._save_data()
        logging.info(f"User {user.username} {'enabled' if active else 'disabled'}.")
        return True

    def change_role(self, user_id, role):
        user = self.find_user_by_id(user_id)
        if not user or role not in User.ROLES:
            return False
        user.role = role
        self._save_data()
        return True

    def can(self, user, action):
        if user is None or not user.active:
            return False
        return action in PERMISSIONS.get(user.role, set())

    # donations (F-02)

    def _today(self, today=None):
        return today or datetime.date.today()

    def record_donation(self, items, user, donor=None, today=None):
        # items: list of dicts with item_name, quantity, unit, expiry_date, storage,
        # dietary_attributes, shelf_location
        # donor: None for anonymous, or {"name", "contact", "contact_consent"}
        today = self._today(today)
        accepted, rejected, errors = [], [], []

        for item in items:
            problem = self._check_batch(item)
            if problem:
                errors.append(f"{item.get('item_name') or 'Item'}: {problem}")
                continue
            expiry = datetime.date.fromisoformat(item["expiry_date"])
            # expired food never goes into stock (FR-06)
            if expiry < today:
                rejected.append(item)
            else:
                accepted.append(item)

        if errors:
            return {"ok": False, "errors": errors}

        donor_id = None
        if donor and donor.get("name", "").strip():
            new_donor = Donor(self._next_id(self.donors), donor["name"].strip(),
                              donor.get("contact", "").strip(), bool(donor.get("contact_consent")))
            self.donors.append(new_donor)
            donor_id = new_donor.id

        self.donation_counter += 1
        ref = f"DON-{self.donation_counter:04d}"
        new_batches = []
        for item in accepted:
            batch = DonationBatch(self._next_id(self.batches), item["item_name"].strip(), int(item["quantity"]),
                                  item["unit"], item["expiry_date"], item["storage"],
                                  item["dietary_attributes"], item.get("shelf_location", "").strip(),
                                  today.isoformat(), ref, donor_id)
            self.batches.append(batch)
            new_batches.append(batch)

        self._save_data()
        logging.info(f"Donation {ref} recorded by {user.username}: {len(new_batches)} batch(es), {len(rejected)} expired.")
        return {"ok": True, "ref": ref, "date": today.isoformat(), "batches": new_batches, "rejected": rejected}

    def _check_batch(self, item):
        if not str(item.get("item_name", "")).strip():
            return "item name is required"
        try:
            if int(item.get("quantity", 0)) <= 0:
                return "quantity must be more than 0"
        except (TypeError, ValueError):
            return "quantity must be a whole number"
        if not item.get("unit"):
            return "unit is required"
        try:
            datetime.date.fromisoformat(str(item.get("expiry_date")))
        except ValueError:
            return "expiry date must be YYYY-MM-DD"
        if item.get("storage") not in DonationBatch.STORAGE:
            return "storage must be Ambient, Chilled or Frozen"
        attrs = item.get("dietary_attributes", [])
        # only values from the controlled list (FR-04)
        if not attrs or any(a not in self.config["attributes"] for a in attrs):
            return "choose dietary attributes from the list"
        return None

    def record_intake_disposal(self, ref, item, user):
        # expired item at intake gets written off instead of stocked (FR-06)
        self.audit_log.append(AuditLogEntry(user.username, "Disposal at intake",
                                            f"{ref} {item['item_name']}", "Expired",
                                            int(item["quantity"]), self._now()))
        self._save_data()
        return True

    def get_donation_confirmation(self, ref):
        # summary that can be given to the donor (FR-07)
        batches = [b for b in self.batches if b.donation_ref == ref]
        if not batches:
            return None
        return {"ref": ref, "date": batches[0].received_date,
                "items": [f"{b.quantity} {b.unit} {b.item_name}" for b in batches]}

    # inventory (F-03)

    def find_batch(self, batch_id):
        for batch in self.batches:
            if batch.id == batch_id:
                return batch
        return None

    def available_batches(self, today=None):
        # usable stock, earliest expiry first so it gets used first (FR-10)
        today = self._today(today)
        usable = [b for b in self.batches
                  if b.quantity > 0 and datetime.date.fromisoformat(b.expiry_date) >= today]
        return sorted(usable, key=lambda b: b.expiry_date)

    def expiring_soon(self, days=7, today=None):
        today = self._today(today)
        limit = today + datetime.timedelta(days=days)
        return [b for b in self.available_batches(today)
                if datetime.date.fromisoformat(b.expiry_date) <= limit]

    def adjust_stock(self, batch_id, quantity, reason_code, user):
        # damaged / expired / miscounted stock, always with a reason (FR-11)
        batch = self.find_batch(batch_id)
        if not batch:
            return False, "Batch not found."
        if reason_code not in self.config["reason_codes"]:
            return False, "Please choose a reason."
        if quantity <= 0 or quantity > batch.quantity:
            return False, f"Quantity must be between 1 and {batch.quantity}."

        batch.quantity -= quantity
        self.audit_log.append(AuditLogEntry(user.username, "Stock adjustment",
                                            f"Batch {batch.id} {batch.item_name}", reason_code,
                                            quantity, self._now()))
        self._save_data()
        logging.info(f"Stock adjusted: batch {batch.id} -{quantity} ({reason_code}) by {user.username}.")
        return True, f"{batch.item_name} reduced by {quantity}. {batch.quantity} left."

    # client households and consent (F-04)

    def find_household(self, household_id):
        for household in self.households:
            if household.id == household_id:
                return household
        return None

    def _check_household(self, d):
        if not str(d.get("preferred_name", "")).strip():
            return "Preferred name is required."
        if d.get("contact_method") not in self.config["contact_methods"]:
            return "Please choose a contact method."
        if d.get("contact_method") != "In person" and not str(d.get("contact_detail", "")).strip():
            return "Please enter a phone number or email for this contact method."
        try:
            adults, children, infants, seniors = (int(d.get(k, 0)) for k in ("adults", "children", "infants", "seniors"))
        except (TypeError, ValueError):
            return "Household numbers must be whole numbers."
        if adults < 1:
            return "A household needs at least 1 adult."
        if min(children, infants, seniors) < 0:
            return "Household numbers cannot be negative."
        if seniors > adults:
            return "Adults aged 65+ cannot be more than the number of adults."
        if any(t not in self.config["pickup_slots"] for t in d.get("preferred_pickup_times", [])):
            return "Please choose pickup times from the list."
        return None

    def register_household(self, d, user, today=None):
        # only the minimum details, no income or ID numbers (FR-12, NFR-07)
        problem = self._check_household(d)
        if problem:
            return None, problem

        household = Household(self._next_id(self.households), d["preferred_name"].strip(),
                              d["contact_method"], d.get("contact_detail", "").strip(),
                              int(d["adults"]), int(d.get("children", 0)), int(d.get("infants", 0)),
                              int(d.get("seniors", 0)), d.get("preferred_pickup_times", []),
                              private_note=d.get("private_note", "").strip(),
                              last_service_date=self._today(today).isoformat())
        self.households.append(household)
        self._save_data()
        # sensitive needs only go in once consent is given
        if d.get("consent"):
            self.give_consent(household.id, d.get("safety_needs", []), d.get("preferences", []),
                              d.get("accessibility_needs", ""), user, today)
        logging.info(f"Household {household.id} registered by {user.username}.")
        return household, f"Household registered with reference H-{household.id:04d}."

    def update_household(self, household_id, d, user):
        household = self.find_household(household_id)
        if not household:
            return False, "Household not found."
        problem = self._check_household(d)
        if problem:
            return False, problem
        household.preferred_name = d["preferred_name"].strip()
        household.contact_method = d["contact_method"]
        household.contact_detail = d.get("contact_detail", "").strip()
        household.adults = int(d["adults"])
        household.children = int(d.get("children", 0))
        household.infants = int(d.get("infants", 0))
        household.seniors = int(d.get("seniors", 0))
        household.preferred_pickup_times = d.get("preferred_pickup_times", [])
        household.private_note = d.get("private_note", "").strip()
        self._save_data()
        return True, "Household details updated."

    def give_consent(self, household_id, safety_needs, preferences, accessibility_needs, user, today=None):
        household = self.find_household(household_id)
        if not household:
            return False, "Household not found."
        known = self.config["needs"]
        if any(n not in known for n in list(safety_needs) + list(preferences)):
            return False, "Please choose dietary needs from the list."
        household.consent.given = True
        household.consent.date = self._today(today).isoformat()
        household.consent.withdrawn_date = None
        household.safety_needs = list(safety_needs)
        # a safety need already covers the same preference
        household.preferences = [p for p in preferences if p not in safety_needs]
        household.accessibility_needs = accessibility_needs.strip()
        self._save_data()
        logging.info(f"Consent recorded for household {household.id} by {user.username}.")
        return True, "Consent and needs saved."

    def withdraw_consent(self, household_id, user, today=None):
        # withdrawn consent means the needs are deleted, not just hidden (FR-14)
        household = self.find_household(household_id)
        if not household:
            return False, "Household not found."
        household.consent.given = False
        household.consent.withdrawn_date = self._today(today).isoformat()
        household.safety_needs = []
        household.preferences = []
        household.accessibility_needs = ""
        self._save_data()
        logging.info(f"Consent withdrawn for household {household.id} by {user.username}.")
        return True, "Consent withdrawn. Dietary and accessibility details were removed."

    def inactive_households(self, months=24, today=None):
        # records to review for deletion after 24 months without service (NFR-08)
        today = self._today(today)
        limit = today - datetime.timedelta(days=months * 30)
        return [h for h in self.households
                if h.last_service_date and datetime.date.fromisoformat(h.last_service_date) < limit]
