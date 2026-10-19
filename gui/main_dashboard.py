import time
import streamlit as st
from app.manager import FoodShareManager
from gui.home_page import show_home_page

TIMEOUT_SECONDS = 10 * 60   # sign out after 10 minutes of no activity (FR-02)

# pages each role can open (FR-03), anything not listed is hidden
PAGES = {
    "Administrator": {"Home": show_home_page},
    "Staff": {"Home": show_home_page},
    "Volunteer": {"Home": show_home_page},
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


def launch():
    st.set_page_config(layout="wide", page_title="FoodShare Tracker")

    # one manager for the whole session so data isnt reloaded on every click
    if "manager" not in st.session_state:
        st.session_state.manager = FoodShareManager()
    manager = st.session_state.manager

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
