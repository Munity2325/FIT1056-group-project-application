import json
import hashlib
import secrets
import datetime
import logging
import csv

from app.user import User
from app.donation import Donor, DonationBatch
from app.household import Household
from app.order import Order, Substitution
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
            adults = int(d.get("adults", 0))
            children = int(d.get("children", 0))
            infants = int(d.get("infants", 0))
            seniors = int(d.get("seniors", 0))
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

    # dietary rules, read from config so new needs don't need code changes

    def _breaks_need(self, batch, need):
        rule = self.config["needs"].get(need, {})
        attrs = batch.dietary_attributes
        if any(a in attrs for a in rule.get("exclude_if_has", [])):
            return True
        if rule.get("require_one_of") and not any(a in attrs for a in rule["require_one_of"]):
            return True
        return False

    def safety_conflicts(self, batch, household):
        # allergies, medical and religious needs (FR-16)
        return [n for n in household.safety_needs if self._breaks_need(batch, n)]

    def preference_conflicts(self, batch, household):
        # other preferences, staff can override these with a reason (FR-17)
        return [n for n in household.preferences if self._breaks_need(batch, n)]

    # food allocation and orders (F-05)

    def find_order(self, order_id):
        for order in self.orders:
            if order.id == order_id:
                return order
        return None

    def reserved_quantity(self, batch_id):
        # stock already promised to orders that are not packed yet
        total = 0
        for order in self.orders:
            if order.status in ("Requested", "Approved"):
                total += sum(i["quantity"] for i in order.items if i["batch_id"] == batch_id)
        return total

    def free_quantity(self, batch):
        return batch.quantity - self.reserved_quantity(batch.id)

    def suggest_allocation(self, household_id, max_items=8, today=None):
        # based only on household size, needs and stock, never on who "deserves" more (FR-15, NFR-10)
        household = self.find_household(household_id)
        if not household:
            return []
        suggestion, used_names = [], set()
        for batch in self.available_batches(today):   # earliest expiry first
            if batch.item_name.lower() in used_names:
                continue
            if self.safety_conflicts(batch, household) or self.preference_conflicts(batch, household):
                continue
            # baby items only when there is an infant at home
            if household.infants == 0 and batch.item_name.lower() in self.config["infant_items"]:
                continue
            free = self.free_quantity(batch)
            if free <= 0:
                continue
            suggestion.append({"batch_id": batch.id, "item_name": batch.item_name,
                               "quantity": min(household.size(), free)})
            used_names.add(batch.item_name.lower())
            if len(suggestion) == max_items:
                break
        return suggestion

    def create_order(self, household_id, items, pickup_time, user, alternative_collector="",
                     justifications=None, today=None):
        # justifications: {batch_id: reason} for items that go against a preference
        household = self.find_household(household_id)
        if not household:
            return None, "Household not found."
        allowed_slots = household.preferred_pickup_times or self.config["pickup_slots"]
        if pickup_time not in allowed_slots:
            return None, "Pickup time must be one of the household's preferred times."
        if not items:
            return None, "The order has no items."

        justifications = justifications or {}
        exceptions, clean_items = [], []
        for item in items:
            batch = self.find_batch(item["batch_id"])
            qty = int(item["quantity"])
            if not batch:
                return None, "One of the items no longer exists."
            if qty <= 0 or qty > self.free_quantity(batch):
                return None, f"Only {self.free_quantity(batch)} {batch.unit} of {batch.item_name} are available."
            # nobody can override a safety need, admins included (FR-16)
            if self.safety_conflicts(batch, household):
                return None, f"{batch.item_name} is not suitable for this household and cannot be added."
            if self.preference_conflicts(batch, household):
                reason = str(justifications.get(batch.id, "")).strip()
                if not reason:
                    return None, f"{batch.item_name} goes against a recorded preference. Please give a reason."
                exceptions.append({"batch_id": batch.id, "item_name": batch.item_name,
                                   "reason": reason, "by": user.username})
            clean_items.append({"batch_id": batch.id, "item_name": batch.item_name, "quantity": qty})

        order = Order(self._next_id(self.orders), household.id, clean_items, pickup_time,
                      user.username, self._now(), alternative_collector=alternative_collector.strip(),
                      exceptions=exceptions)
        self.orders.append(order)
        self._save_data()
        logging.info(f"Order {order.reference()} created by {user.username}.")
        return order, f"Order {order.reference()} created."

    def approve_order(self, order_id, user):
        order = self.find_order(order_id)
        if not order or order.status != "Requested":
            return False, "Only requested orders can be approved."
        order.status = "Approved"
        # approving makes a packing task for volunteers (F-06)
        self.tasks.append(Task(self._next_id(self.tasks), "Pack order", "Store room", 10, order.id))
        self._save_data()
        logging.info(f"Order {order.reference()} approved by {user.username}.")
        return True, f"Order {order.reference()} approved and sent to volunteers for packing."

    def set_order_status(self, order_id, status, user):
        order = self.find_order(order_id)
        if not order:
            return False, "Order not found."
        allowed = {"Packed": ["Ready"], "Ready": ["Collected", "Not Collected"]}
        if status not in allowed.get(order.status, []):
            return False, f"An order that is {order.status} cannot be set to {status}."
        order.status = status
        if status == "Ready":
            self._notify(order, "Pickup confirmation")
        if status == "Collected":
            household = self.find_household(order.household_id)
            household.last_service_date = datetime.date.today().isoformat()
        self._save_data()
        logging.info(f"Order {order.reference()} set to {status} by {user.username}.")
        return True, f"Order {order.reference()} is now {status}."

    def _find_order_item(self, order, batch_id):
        for item in order.items:
            if item["batch_id"] == batch_id:
                return item
        return None

    def record_substitution(self, order_id, original_batch_id, substitute_batch_id, user):
        # swap an unavailable item for a suitable one and tell the client (FR-18, FR-29)
        order = self.find_order(order_id)
        if not order or order.status not in ("Requested", "Approved"):
            return False, "Substitutions can only be made before the order is packed."
        original = self._find_order_item(order, original_batch_id)
        substitute = self.find_batch(substitute_batch_id)
        household = self.find_household(order.household_id)
        if not original or not substitute:
            return False, "Item not found."
        if self.safety_conflicts(substitute, household) or self.preference_conflicts(substitute, household):
            return False, f"{substitute.item_name} does not suit this household's dietary needs."
        # the original item's reservation is released by the swap
        if original["quantity"] > self.free_quantity(substitute):
            return False, f"Not enough {substitute.item_name} in stock."

        order.substitutions.append(Substitution(original["item_name"], substitute.item_name, substitute.id,
                                                user.username, self._now(), original["quantity"]))
        # if the substitute is already in the order just add to that line
        existing = self._find_order_item(order, substitute.id)
        if existing:
            existing["quantity"] += original["quantity"]
            order.items.remove(original)
        else:
            original["batch_id"] = substitute.id
            original["item_name"] = substitute.item_name
        self._notify(order, "Substitution")
        self._save_data()
        logging.info(f"Substitution on {order.reference()} by {user.username}.")
        return True, f"{substitute.item_name} recorded as the substitute. The client has been notified."

    # notifications (F-08), simulated by writing to a log

    def _notify(self, order, kind):
        household = self.find_household(order.household_id)
        template = self.messages["substitution" if kind == "Substitution" else "pickup_confirmation"]
        # message only has the order reference and pickup time, never diet or health info (FR-30)
        message = template.format(order_ref=order.reference(), pickup_time=order.pickup_time)
        record = NotificationRecord(order.reference(), household.contact_method, kind, message, self._now())
        self.notifications.append(record)
        logging.info(f"Notification ({kind}) for {order.reference()} via {household.contact_method}.")
        return record

    # volunteer tasks (F-06)

    def find_task(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def tasks_for(self, user):
        # open tasks plus the ones this volunteer already has (FR-22)
        return [t for t in self.tasks
                if t.status == "Available"
                or (t.status != "Completed" and t.history and t.history[-1]["user"] == user.username)]

    def _move_task(self, task_id, user, from_status, to_status):
        task = self.find_task(task_id)
        if not task or task.status != from_status:
            return None, f"This task is not {from_status.lower()}."
        if from_status != "Available" and task.history[-1]["user"] != user.username:
            return None, "This task belongs to another volunteer."
        task.status = to_status
        # who did what and when, for every step (FR-23)
        task.history.append({"status": to_status, "user": user.username, "timestamp": self._now()})
        return task, None

    def claim_task(self, task_id, user):
        task, problem = self._move_task(task_id, user, "Available", "Claimed")
        if problem:
            return False, problem
        self._save_data()
        return True, "Task claimed."

    def start_task(self, task_id, user):
        task, problem = self._move_task(task_id, user, "Claimed", "In progress")
        if problem:
            return False, problem
        self._save_data()
        return True, "Task started."

    def complete_task(self, task_id, user):
        task = self.find_task(task_id)
        order = self.find_order(task.order_id) if task else None
        # check stock first so a half-packed order never happens
        if order:
            for item in order.items:
                batch = self.find_batch(item["batch_id"])
                if not batch or batch.quantity < item["quantity"]:
                    return False, f"Not enough {item['item_name']} left. Please tell a staff member."
        task, problem = self._move_task(task_id, user, "In progress", "Completed")
        if problem:
            return False, problem
        if order:
            # packing takes the items out of stock automatically (FR-09)
            for item in order.items:
                self.find_batch(item["batch_id"]).quantity -= item["quantity"]
            order.status = "Packed"
        self._save_data()
        logging.info(f"Task {task.id} completed by {user.username}.")
        return True, "Task completed. Stock has been updated."

    def picking_list(self, task_id):
        # only what is needed to pack: no name, contact or household details (FR-24, NFR-06)
        task = self.find_task(task_id)
        order = self.find_order(task.order_id) if task else None
        if not order:
            return None
        household = self.find_household(order.household_id)
        notes = [self.config["packing_notes"][n] for n in household.safety_needs
                 if n in self.config["packing_notes"]]
        lines = []
        for item in order.items:
            batch = self.find_batch(item["batch_id"])
            lines.append({"item": item["item_name"], "quantity": item["quantity"],
                          "unit": batch.unit if batch else "", "shelf": batch.shelf_location if batch else ""})
        return {"order_ref": order.reference(), "bag_number": order.id, "items": lines, "packing_notes": notes}

    # reports (F-07), always grouped with no client names or contacts (FR-27)

    def _orders_between(self, start, end):
        return [o for o in self.orders if start.isoformat() <= o.created_at[:10] <= end.isoformat()]

    def demand_report(self, start, end):
        # requested vs supplied per item, plus items that had to be substituted (FR-25)
        rows = {}
        for order in self._orders_between(start, end):
            supplied = order.status in ("Packed", "Ready", "Collected", "Not Collected")
            for item in order.items:
                row = self._demand_row(rows, item["item_name"])
                row["requested"] += item["quantity"]
                if supplied:
                    row["supplied"] += item["quantity"]
            # move substituted amounts back to the item that was really asked for
            for sub in order.substitutions:
                self._demand_row(rows, sub.substitute_item)["requested"] -= sub.quantity
                row = self._demand_row(rows, sub.original_item)
                row["requested"] += sub.quantity
                row["unavailable"] += sub.quantity
                if sub.substitute_item not in row["substituted_with"]:
                    row["substituted_with"].append(sub.substitute_item)
        # turn the list of substitutes into text for the table and csv
        for row in rows.values():
            row["substituted_with"] = ", ".join(row["substituted_with"])
        return sorted(rows.values(), key=lambda r: r["item"])

    def _demand_row(self, rows, name):
        return rows.setdefault(name, {"item": name, "requested": 0, "supplied": 0,
                                      "unavailable": 0, "substituted_with": []})

    def _size_group(self, household):
        size = household.size()
        if size == 1:
            return "1 person"
        if size <= 3:
            return "2-3 people"
        if size <= 5:
            return "4-5 people"
        return "6+ people"

    def fairness_report(self, start, end):
        # how much food went to each household size and from each staff member (FR-26)
        rows = {}
        for order in self._orders_between(start, end):
            household = self.find_household(order.household_id)
            key = (self._size_group(household), order.created_by)
            row = rows.setdefault(key, {"household_size": key[0], "allocated_by": key[1],
                                        "orders": 0, "items": 0, "people": 0})
            row["orders"] += 1
            row["items"] += sum(i["quantity"] for i in order.items)
            row["people"] += household.size()
        result = []
        for row in rows.values():
            row["items_per_person"] = round(row["items"] / row["people"], 2) if row["people"] else 0
            del row["people"]
            result.append(row)
        return sorted(result, key=lambda r: (r["household_size"], r["allocated_by"]))

    def export_report(self, rows, out_path):
        if not rows:
            return False
        # newline="" stops empty rows on windows
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        logging.info(f"Report exported to {out_path}.")
        return True
