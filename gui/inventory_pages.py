import streamlit as st
import pandas as pd


def show_inventory_page(manager, user):
    st.header("Inventory")
    batches = manager.available_batches()
    search = st.text_input("Search by item name")
    if search.strip():
        batches = [b for b in batches if search.strip().lower() in b.item_name.lower()]

    # earliest expiry first, that is the order to use stock in (FR-10)
    if batches:
        st.dataframe(pd.DataFrame([{
            "Batch": b.id, "Item": b.item_name, "Quantity": b.quantity, "Unit": b.unit,
            "Expiry date": b.expiry_date, "Storage": b.storage, "Shelf": b.shelf_location,
            "Dietary": ", ".join(b.dietary_attributes)} for b in batches]), hide_index=True)
    else:
        st.info("No stock found.")

    if manager.can(user, "adjust_stock"):
        show_adjust_form(manager, user)


def show_adjust_form(manager, user):
    # damaged, expired or miscounted stock, picked from a list so nobody has to type (FR-11)
    st.subheader("Report damaged or missing stock")
    options = {f"{b.id} - {b.item_name} ({b.quantity} {b.unit}, shelf {b.shelf_location or '-'})": b.id
               for b in manager.batches if b.quantity > 0}
    if not options:
        st.info("There is no stock to adjust.")
        return
    with st.form("adjust_form"):
        choice = st.selectbox("Batch", list(options.keys()))
        quantity = st.number_input("How many to remove", min_value=1, step=1)
        reason = st.selectbox("Reason", manager.config["reason_codes"])
        if st.form_submit_button("Save adjustment"):
            ok, message = manager.adjust_stock(options[choice], int(quantity), reason, user)
            if ok:
                st.success(message)
            else:
                st.error(message)


def show_stock_problem_page(manager, user):
    st.header("Report a Stock Problem")
    st.write("Found something leaking, damaged or out of date? Record it here.")
    show_adjust_form(manager, user)


def show_audit_log_page(manager, user):
    st.header("Audit Log")
    if not manager.audit_log:
        st.info("Nothing has been recorded yet.")
        return
    st.dataframe(pd.DataFrame([{"Time": a.timestamp, "User": a.user, "Action": a.action, "Details": a.details,
                                "Reason": a.reason_code, "Quantity": a.quantity}
                               for a in reversed(manager.audit_log)]), hide_index=True)
