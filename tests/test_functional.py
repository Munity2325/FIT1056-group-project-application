# functional / end-to-end tests, clicking through the real streamlit app like a user would
import os
import shutil
import time
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# run the app in a temp folder with its own copy of the demo data
@pytest.fixture(autouse=True)
def app_folder(tmp_path, monkeypatch):
    shutil.copytree(os.path.join(ROOT, "config"), tmp_path / "config")
    shutil.copytree(os.path.join(ROOT, "data"), tmp_path / "data", ignore=shutil.ignore_patterns("backups"))
    monkeypatch.chdir(tmp_path)
    st.cache_resource.clear()


def login(username, password):
    at = AppTest.from_file(os.path.join(ROOT, "main.py"), default_timeout=30).run()
    at.text_input[0].set_value(username)
    at.text_input[1].set_value(password)
    at.button[0].click().run()
    return at


def button(at, label):
    return [b for b in at.button if b.label == label][0]


def go(at, page):
    at.sidebar.radio[0].set_value(page).run()


def test_ftest01_staff_can_sign_in():
    # FR-01, FR-02
    at = login("kristine", "staff123")

    assert at.header[0].value == "Welcome, kristine"


def test_ftest02_wrong_password_and_disabled_account():
    # FR-02, equivalence classes: wrong password / disabled account
    assert login("kristine", "wrong").error

    admin = login("grace", "admin123")
    go(admin, "User Accounts")
    button(admin, "Disable account").click().run()      # first other account is kristine
    assert login("kristine", "staff123").error


def test_ftest03_timeout_boundary():
    # FR-02, boundary: 599 seconds stays signed in, 601 seconds signs out
    at = login("kristine", "staff123")
    at.session_state.last_active = time.time() - 599
    at.run()
    assert at.header[0].value == "Welcome, kristine"

    at.session_state.last_active = time.time() - 601
    at.run()
    assert "signed out" in at.info[0].value


def test_ftest04_each_role_sees_only_its_pages():
    # FR-03, NFR-06
    assert "Client Households" in login("kristine", "staff123").sidebar.radio[0].options
    volunteer_pages = login("weisheng", "volunteer123").sidebar.radio[0].options
    admin_pages = login("grace", "admin123").sidebar.radio[0].options
    assert "Client Households" not in volunteer_pages
    assert "Food Allocation" not in admin_pages


def test_ftest05_record_donation_with_expired_item():
    # FR-04, FR-06, FR-07
    import datetime
    at = login("kristine", "staff123")
    go(at, "Record Donation")
    at.text_input[0].set_value("Yoghurt")
    at.date_input[0].set_value(datetime.date(2020, 1, 1))
    at.multiselect[0].set_value(["Vegetarian", "Contains dairy"])
    button(at, "Add item").click().run()
    at.text_input[0].set_value("Oats")
    at.date_input[0].set_value(datetime.date.today() + datetime.timedelta(days=90))
    at.multiselect[0].set_value(["Vegan"])
    button(at, "Add item").click().run()

    button(at, "Save donation").click().run()

    assert "saved" in at.success[0].value
    assert "was not added to stock" in at.error[0].value


def test_ftest06_volunteer_reports_damaged_stock():
    # FR-11
    at = login("weisheng", "volunteer123")
    go(at, "Report Stock Problem")

    button(at, "Save adjustment").click().run()

    assert "reduced by 1" in at.success[0].value
    admin = login("grace", "admin123")
    go(admin, "Audit Log")
    assert admin.dataframe[0].value.iloc[0]["User"] == "weisheng"


def test_ftest07_needs_need_consent():
    # FR-12, FR-14
    at = login("kristine", "staff123")
    go(at, "Client Households")
    # the second tab is "Register a household"
    tab = at.tabs[1]
    [t for t in tab.text_input if t.label == "Preferred name"][0].set_value("Test Family")
    [t for t in tab.text_input if t.label == "Phone number or email"][0].set_value("011-111")
    [m for m in tab.multiselect if m.label.startswith("Allergies")][0].set_value(["Nut allergy"])

    button(at, "Register household").click().run()
    assert at.warning

    at.tabs[1].checkbox[0].check()
    button(at, "Register household").click().run()
    assert "registered" in at.success[0].value


def test_ftest08_full_order_flow():
    # FR-15, FR-21, FR-23, FR-09, FR-24, FR-28: staff -> volunteer -> staff
    staff = login("kristine", "staff123")
    go(staff, "Food Allocation")
    staff.selectbox[0].set_value("H-0002 - Hassan").run()
    button(staff, "Suggest food allocation").click().run()
    button(staff, "Create order").click().run()
    assert "created" in staff.success[0].value
    staff.run()
    button(staff, "Approve and send for packing").click().run()

    volunteer = login("weisheng", "volunteer123")
    go(volunteer, "My Tasks")
    button(volunteer, "Claim").click().run()
    picking_text = str([m.value for m in volunteer.markdown]) + str(volunteer.table[0].value)
    assert "Hassan" not in picking_text and "019" not in picking_text
    button(volunteer, "Start").click().run()
    button(volunteer, "Mark as packed").click().run()

    staff.run()
    button(staff, "Mark as Ready").click().run()
    go(staff, "Notification Log")
    log = staff.dataframe[0].value.iloc[0]
    assert log["Type"] == "Pickup confirmation"
    assert log["Method"] == "Phone call"
    assert "Halal" not in log["Message"]


def test_ftest09_allergy_item_cannot_be_added():
    # FR-16
    at = login("kristine", "staff123")
    go(at, "Food Allocation")
    at.selectbox[0].set_value("H-0001 - Kavitha").run()      # vegetarian
    button(at, "Suggest food allocation").click().run()
    item = [s for s in at.selectbox if s.label == "Item"][0]
    item.set_value([o for o in item.options if "Chicken" in o][0]).run()

    assert "cannot be added" in at.error[0].value


def test_ftest10_report_has_no_client_names():
    # FR-25, FR-26, FR-27
    staff = login("kristine", "staff123")
    go(staff, "Food Allocation")
    button(staff, "Suggest food allocation").click().run()
    button(staff, "Create order").click().run()

    go(staff, "Reports")
    staff.radio[0].set_value("Fairness").run()
    text = staff.dataframe[0].value.to_csv()

    assert "Kavitha" not in text and "012" not in text
