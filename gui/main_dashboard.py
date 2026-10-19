import time
import streamlit as st
from app.manager import FoodShareManager
from gui.home_page import show_home_page
from gui.donation_pages import show_donation_page
from gui.inventory_pages import show_inventory_page, show_stock_problem_page, show_audit_log_page
from gui.household_pages import show_household_page
from gui.order_pages import show_order_page, show_notification_page
from gui.volunteer_pages import show_task_page
from gui.report_pages import show_report_page
from gui.admin_pages import show_user_page

TIMEOUT_SECONDS = 10 * 60   # sign out after 10 minutes of no activity (FR-02)

# pages each role can open (FR-03), anything not listed is hidden
PAGES = {
    "Administrator": {"Home": show_home_page, "User Accounts": show_user_page, "Reports": show_report_page,
                      "Inventory": show_inventory_page, "Audit Log": show_audit_log_page},
    "Staff": {"Home": show_home_page, "Record Donation": show_donation_page, "Inventory": show_inventory_page,
              "Client Households": show_household_page, "Food Allocation": show_order_page,
              "Notification Log": show_notification_page, "Reports": show_report_page},
    "Volunteer": {"Home": show_home_page, "My Tasks": show_task_page,
                  "Report Stock Problem": show_stock_problem_page},
}


def _sign_out(message=None):
    st.session_state.user_id = None
    if message:
        st.session_state.sign_out_message = message


def _login_screen(manager):
    st.title("FoodShare Tracker")
    st.caption("Community Harvest Food Bank")
    if st.session_state.get("sign_out_message"):
        st.info(st.session_state.pop("sign_out_message"))

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        user = manager.authenticate(username, password)
        if user:
            st.session_state.user_id = user.id
            st.session_state.last_active = time.time()
            st.rerun()
        else:
            st.error("The username or password is not right, or the account is disabled.")


@st.cache_resource
def get_manager():
    # one shared manager for everyone, so the desktop and the tablet see the same data
    return FoodShareManager()


def launch():
    st.set_page_config(layout="wide", page_title="FoodShare Tracker")
    manager = get_manager()

    user = manager.find_user_by_id(st.session_state.get("user_id"))
    if user and time.time() - st.session_state.get("last_active", 0) > TIMEOUT_SECONDS:
        _sign_out("You were signed out after 10 minutes without activity.")
        user = None
    if not user or not user.active:
        _login_screen(manager)
        return
    st.session_state.last_active = time.time()

    st.sidebar.title("FoodShare Tracker")
    st.sidebar.write(f"Signed in as **{user.username}** ({user.role})")
    pages = PAGES[user.role]
    page = st.sidebar.radio("Go to", list(pages.keys()))
    st.sidebar.divider()
    if st.sidebar.button("Sign out"):
        _sign_out("You have signed out.")
        st.rerun()

    pages[page](manager, user)
