import datetime
import pytest
from app.manager import FoodShareManager

TODAY = datetime.date(2026, 10, 19)


# fresh manager for every test, uses a temp json so data/foodshare.json isnt touched
@pytest.fixture
def manager(tmp_path):
    m = FoodShareManager(data_path=str(tmp_path / "test_data.json"))
    m.create_user("grace", "admin123", "Administrator")
    m.create_user("kristine", "staff123", "Staff")
    m.create_user("wei", "vol123", "Volunteer")
    return m


@pytest.fixture
def staff(manager):
    return manager.find_user("kristine")


@pytest.fixture
def volunteer(manager):
    return manager.find_user("wei")


def make_item(name="Rice", quantity=10, expiry="2026-12-01", attrs=None, storage="Ambient"):
    return {"item_name": name, "quantity": quantity, "unit": "units", "expiry_date": expiry,
            "storage": storage, "dietary_attributes": attrs or ["Vegan"], "shelf_location": "A1"}


def make_household(**changes):
    d = {"preferred_name": "Kavitha", "contact_method": "SMS", "contact_detail": "012",
         "adults": 2, "children": 1, "infants": 0, "seniors": 0,
         "preferred_pickup_times": ["Friday morning"]}
    d.update(changes)
    return d
