import datetime
import streamlit as st

UNITS = ["units", "tins", "cartons", "packs", "jars", "loaves", "bottles", "kg bags"]


def show_donation_page(manager, user):
    st.header("Record a Donation")

    # items wait here until the whole donation is saved
    if "donation_items" not in st.session_state:
        st.session_state.donation_items = []

    st.subheader("1. Add the items")
    with st.form("item_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        item_name = col1.text_input("Item name")
        quantity = col2.number_input("Quantity", min_value=1, step=1)
        unit = col3.selectbox("Unit", UNITS)
        col4, col5, col6 = st.columns(3)
        expiry = col4.date_input("Expiry date", min_value=datetime.date(2000, 1, 1))
        storage = col5.selectbox("Storage", ["Ambient", "Chilled", "Frozen"])
        shelf = col6.text_input("Shelf location (e.g. A1)")
        attributes = st.multiselect("Dietary attributes", manager.config["attributes"])
        if st.form_submit_button("Add item"):
            if not item_name.strip():
                st.warning("Please enter an item name.")
            elif not attributes:
                st.warning("Please choose at least one dietary attribute (or 'None applicable').")
            else:
                st.session_state.donation_items.append({
                    "item_name": item_name.strip(), "quantity": int(quantity), "unit": unit,
                    "expiry_date": expiry.isoformat(), "storage": storage,
                    "dietary_attributes": attributes, "shelf_location": shelf.strip()})

    items = st.session_state.donation_items
    if items:
        st.table([{"Item": i["item_name"], "Quantity": f"{i['quantity']} {i['unit']}",
                   "Expiry": i["expiry_date"], "Storage": i["storage"],
                   "Dietary": ", ".join(i["dietary_attributes"])} for i in items])
        if st.button("Clear items"):
            st.session_state.donation_items = []
            st.rerun()

    st.subheader("2. Donor (optional)")
    with st.form("donor_form"):
        anonymous = st.checkbox("Anonymous donation (no donor details kept)", value=True)
        donor_name = st.text_input("Donor name")
        donor_contact = st.text_input("Phone or email")
        consent = st.checkbox("Donor agrees to be contacted")
        save = st.form_submit_button("Save donation")

    if save:
        if not items:
            st.warning("Please add at least one item first.")
        else:
            donor = None if anonymous else {"name": donor_name, "contact": donor_contact, "contact_consent": consent}
            result = manager.record_donation(items, user, donor)
            if not result["ok"]:
                for e in result["errors"]:
                    st.error(e)
            else:
                st.session_state.donation_items = []
                st.session_state.last_donation = result

    # confirmation for the donor (FR-07) and expired items to write off (FR-06)
    result = st.session_state.get("last_donation")
    if result:
        confirmation = manager.get_donation_confirmation(result["ref"])
        if confirmation:
            st.success(f"Donation {confirmation['ref']} saved on {confirmation['date']}.")
            st.write("Items received: " + ", ".join(confirmation["items"]))
        for n, item in enumerate(result["rejected"]):
            st.error(f"{item['item_name']} expired on {item['expiry_date']} and was not added to stock.")
            if st.button(f"Record {item['quantity']} {item['unit']} of {item['item_name']} as disposal", key=f"dispose{n}"):
                manager.record_intake_disposal(result["ref"], item, user)
                result["rejected"].remove(item)
                st.rerun()
        if st.button("Done"):
            del st.session_state.last_donation
            st.rerun()
