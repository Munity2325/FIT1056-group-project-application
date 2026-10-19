import streamlit as st
import pandas as pd
from app.user import User


def show_user_page(manager, user):
    st.header("User Accounts")
    st.dataframe(pd.DataFrame([{"ID": u.id, "Username": u.username, "Role": u.role,
                                "Status": "Active" if u.active else "Disabled"} for u in manager.users]),
                 hide_index=True)

    st.subheader("Create an account")
    with st.form("create_user", clear_on_submit=True):
        username = st.text_input("Username")
        password = st.text_input("Temporary password", type="password")
        role = st.selectbox("Role", User.ROLES)
        if st.form_submit_button("Create account"):
            if not username.strip() or not password:
                st.warning("Please enter a username and a password.")
            elif manager.create_user(username, password, role):
                st.success(f"Account {username.strip()} created as {role}.")
            else:
                st.error("That username is already taken.")

    # accounts are disabled, not deleted, so the history stays (FR-01)
    st.subheader("Change an account")
    others = {f"{u.id} - {u.username}": u for u in manager.users if u.id != user.id}
    if not others:
        return
    target = others[st.selectbox("Account", list(others.keys()))]
    col1, col2 = st.columns(2)
    new_role = col1.selectbox("Role", User.ROLES, index=User.ROLES.index(target.role), key=f"role{target.id}")
    if col1.button("Save role"):
        manager.change_role(target.id, new_role)
        st.success(f"{target.username} is now {new_role}.")
    if target.active and col2.button("Disable account"):
        manager.set_user_active(target.id, False)
        st.rerun()
    if not target.active and col2.button("Enable account"):
        manager.set_user_active(target.id, True)
        st.rerun()

    # records to review for deletion (NFR-08), only references are shown
    old = manager.inactive_households()
    st.subheader("Client records to review")
    if old:
        st.write("No service for 24 months: " + ", ".join(f"H-{h.id:04d}" for h in old))
    else:
        st.write("No client records need review.")
