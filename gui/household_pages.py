import streamlit as st
from app.manager import FIELD_HELP


def _household_label(h):
    return f"H-{h.id:04d} - {h.preferred_name}"


def show_household_page(manager, user):
    st.header("Client Households")
    tab_list, tab_new = st.tabs(["Find and update", "Register a household"])
    with tab_new:
        _register_form(manager, user)
    with tab_list:
        _household_details(manager, user)


def _register_form(manager, user):
    slots = manager.config["pickup_slots"]
    needs = list(manager.config["needs"].keys())
    st.caption("Only ask for what is on this form. We never ask for income, employment or ID numbers.")
    with st.form("register_form"):
        name = st.text_input("Preferred name")
        st.caption(FIELD_HELP["preferred_name"])
        col1, col2 = st.columns(2)
        method = col1.selectbox("Contact method", manager.config["contact_methods"])
        detail = col2.text_input("Phone number or email")
        st.caption(FIELD_HELP["contact_method"])
        c1, c2, c3, c4 = st.columns(4)
        adults = c1.number_input("Adults", min_value=1, value=1, step=1)
        children = c2.number_input("Children", min_value=0, step=1)
        infants = c3.number_input("Infants", min_value=0, step=1)
        seniors = c4.number_input("Adults aged 65+", min_value=0, step=1)
        st.caption(FIELD_HELP["household"] + " " + FIELD_HELP["infants"])
        pickup = st.multiselect("Preferred pickup times", slots)
        st.caption(FIELD_HELP["pickup_times"])

        st.markdown("**Dietary and accessibility needs**")
        st.caption(FIELD_HELP["needs"])
        consent = st.checkbox("The client agrees to us keeping their dietary and accessibility needs")
        safety = st.multiselect("Allergies, medical or religious needs (never overridden)", needs)
        prefs = st.multiselect("Other food preferences", needs)
        access = st.text_input("Accessibility needs (optional)")
        note = st.text_area("Private staff note (optional, never shown to volunteers)")
        submitted = st.form_submit_button("Register household")

    if submitted:
        if (safety or prefs or access.strip()) and not consent:
            st.warning("Dietary and accessibility needs can only be saved if the client agrees. Tick the consent box or clear those fields.")
            return
        household, message = manager.register_household({
            "preferred_name": name, "contact_method": method, "contact_detail": detail,
            "adults": adults, "children": children, "infants": infants, "seniors": seniors,
            "preferred_pickup_times": pickup, "consent": consent, "safety_needs": safety,
            "preferences": prefs, "accessibility_needs": access, "private_note": note}, user)
        if household:
            st.success(message)
        else:
            st.error(message)


def _household_details(manager, user):
    if not manager.households:
        st.info("No households registered yet.")
        return
    search = st.text_input("Search by preferred name or reference")
    found = [h for h in manager.households
             if search.strip().lower() in _household_label(h).lower()]
    if not found:
        st.error(f"No household matches {search}.")
        return
    options = {_household_label(h): h.id for h in found}
    household = manager.find_household(options[st.selectbox("Household", list(options.keys()))])

    st.write(f"**Household:** {household.adults} adults ({household.seniors} aged 65+), "
             f"{household.children} children, {household.infants} infants")
    st.write(f"**Contact:** {household.contact_method} {household.contact_detail}")
    st.write(f"**Pickup times:** {', '.join(household.preferred_pickup_times) or 'Any'}")
    if household.consent.given:
        st.write(f"**Needs (never overridden):** {', '.join(household.safety_needs) or 'None'}")
        st.write(f"**Preferences:** {', '.join(household.preferences) or 'None'}")
        st.write(f"**Accessibility:** {household.accessibility_needs or 'None'}")
    else:
        st.info("No consent for dietary or accessibility details, so none are stored.")
    if household.private_note:
        st.write(f"**Private note:** {household.private_note}")

    with st.expander("Update contact and household details"):
        with st.form(f"edit_{household.id}"):
            name = st.text_input("Preferred name", household.preferred_name)
            methods = manager.config["contact_methods"]
            method = st.selectbox("Contact method", methods, index=methods.index(household.contact_method))
            detail = st.text_input("Phone number or email", household.contact_detail)
            c1, c2, c3, c4 = st.columns(4)
            adults = c1.number_input("Adults", min_value=1, value=household.adults, step=1)
            children = c2.number_input("Children", min_value=0, value=household.children, step=1)
            infants = c3.number_input("Infants", min_value=0, value=household.infants, step=1)
            seniors = c4.number_input("Adults aged 65+", min_value=0, value=household.seniors, step=1)
            pickup = st.multiselect("Preferred pickup times", manager.config["pickup_slots"],
                                    default=household.preferred_pickup_times)
            note = st.text_area("Private staff note", household.private_note)
            if st.form_submit_button("Save changes"):
                ok, message = manager.update_household(household.id, {
                    "preferred_name": name, "contact_method": method, "contact_detail": detail,
                    "adults": adults, "children": children, "infants": infants, "seniors": seniors,
                    "preferred_pickup_times": pickup, "private_note": note}, user)
                if ok:
                    st.success(message)
                else:
                    st.error(message)

    # consent can be given or taken back at any time (FR-14)
    with st.expander("Consent and dietary needs"):
        needs = list(manager.config["needs"].keys())
        with st.form(f"consent_{household.id}"):
            st.caption(FIELD_HELP["needs"])
            safety = st.multiselect("Allergies, medical or religious needs (never overridden)", needs,
                                    default=household.safety_needs)
            prefs = st.multiselect("Other food preferences", needs, default=household.preferences)
            access = st.text_input("Accessibility needs", household.accessibility_needs)
            if st.form_submit_button("Client agrees - save needs"):
                ok, message = manager.give_consent(household.id, safety, prefs, access, user)
                if ok:
                    st.success(message)
                else:
                    st.error(message)
        if household.consent.given and st.button("Client withdraws consent"):
            ok, message = manager.withdraw_consent(household.id, user)
            st.success(message)
            st.rerun()
