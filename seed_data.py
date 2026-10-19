# makes demo data in data/foodshare.json, run: python seed_data.py
import os
import datetime
from app.manager import FoodShareManager

DATA_PATH = "data/foodshare.json"

if os.path.exists(DATA_PATH):
    os.remove(DATA_PATH)

m = FoodShareManager(data_path=DATA_PATH)
admin = m.create_user("grace", "admin123", "Administrator")
staff = m.create_user("kristine", "staff123", "Staff")
m.create_user("weisheng", "volunteer123", "Volunteer")

today = datetime.date.today()
def day(n):
    return (today + datetime.timedelta(days=n)).isoformat()

m.record_donation([
    {"item_name": "Milk", "quantity": 24, "unit": "cartons", "expiry_date": day(5), "storage": "Chilled",
     "dietary_attributes": ["Vegetarian", "Contains dairy"], "shelf_location": "Fridge 1"},
    {"item_name": "Rice", "quantity": 40, "unit": "kg bags", "expiry_date": day(200), "storage": "Ambient",
     "dietary_attributes": ["Vegan"], "shelf_location": "A1"},
    {"item_name": "Canned chickpeas", "quantity": 30, "unit": "tins", "expiry_date": day(300), "storage": "Ambient",
     "dietary_attributes": ["Vegan"], "shelf_location": "A2"},
], staff, donor={"name": "Tan Grocery", "contact": "03-1234 5678", "contact_consent": True})

m.record_donation([
    {"item_name": "Chicken (halal)", "quantity": 15, "unit": "packs", "expiry_date": day(20), "storage": "Frozen",
     "dietary_attributes": ["Halal"], "shelf_location": "Freezer 1"},
    {"item_name": "Peanut butter", "quantity": 12, "unit": "jars", "expiry_date": day(120), "storage": "Ambient",
     "dietary_attributes": ["Vegan", "Contains nuts"], "shelf_location": "B1"},
    {"item_name": "Bread", "quantity": 20, "unit": "loaves", "expiry_date": day(3), "storage": "Ambient",
     "dietary_attributes": ["Vegetarian", "Contains gluten"], "shelf_location": "B2"},
    {"item_name": "Baby formula", "quantity": 10, "unit": "tins", "expiry_date": day(150), "storage": "Ambient",
     "dietary_attributes": ["Vegetarian", "Contains dairy"], "shelf_location": "C1"},
], staff)

m.register_household({"preferred_name": "Kavitha", "contact_method": "SMS", "contact_detail": "012-345 6789",
                      "adults": 2, "children": 2, "infants": 1, "seniors": 1,
                      "preferred_pickup_times": ["Monday afternoon", "Friday afternoon"],
                      "consent": True, "safety_needs": ["Vegetarian"], "preferences": []}, staff)
m.register_household({"preferred_name": "Hassan", "contact_method": "Phone call", "contact_detail": "019-876 5432",
                      "adults": 1, "children": 0, "infants": 0, "seniors": 1,
                      "preferred_pickup_times": ["Friday morning"],
                      "consent": True, "safety_needs": ["Halal"], "preferences": [],
                      "accessibility_needs": "Uses a walking cane, son Faizal may collect"}, staff)

print("Demo data created in", DATA_PATH)
print("Logins: grace/admin123 (Administrator), kristine/staff123 (Staff), weisheng/volunteer123 (Volunteer)")
