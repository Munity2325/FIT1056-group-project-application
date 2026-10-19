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
