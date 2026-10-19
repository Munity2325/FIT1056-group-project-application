import streamlit as st
import pandas as pd


def show_home_page(manager, user):
    st.header(f"Welcome, {user.username}")

    if user.role == "Volunteer":
        st.write("Open **My Tasks** in the menu to see packing jobs you can pick up.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Batches in stock", len(manager.available_batches()))
    col2.metric("Client households", len(manager.households))
    col3.metric("Open orders", len([o for o in manager.orders if o.status in ("Requested", "Approved", "Packed", "Ready")]))

    # batches that should go out first (FR-10)
    st.subheader("Expiring in the next 7 days")
    soon = manager.expiring_soon()
    if soon:
        st.dataframe(pd.DataFrame([{"Item": b.item_name, "Expiry date": b.expiry_date,
                                    "Quantity left": f"{b.quantity} {b.unit}", "Shelf": b.shelf_location}
                                   for b in soon]), hide_index=True)
    else:
        st.success("No stock is expiring in the next 7 days.")
