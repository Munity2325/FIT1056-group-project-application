import streamlit as st
import pandas as pd


def _batch_label(b, manager):
    return f"{b.id} - {b.item_name} ({manager.free_quantity(b)} {b.unit} free, exp {b.expiry_date})"


def show_order_page(manager, user):
    st.header("Food Allocation and Orders")
    tab_new, tab_orders = st.tabs(["New food allocation", "Orders"])
    with tab_new:
        _new_order(manager, user)
    with tab_orders:
        _orders(manager, user)


def _new_order(manager, user):
    if not manager.households:
        st.info("Register a household first.")
        return
    options = {f"H-{h.id:04d} - {h.preferred_name}": h.id for h in manager.households}
    household = manager.find_household(options[st.selectbox("Household", list(options.keys()))])
    st.caption(f"{household.size()} people. Needs: {', '.join(household.safety_needs) or 'none recorded'}. "
               f"Preferences: {', '.join(household.preferences) or 'none recorded'}.")

    # the suggestion is kept per household until the order is saved
    key = f"draft_{household.id}"
    if st.button("Suggest food allocation"):
        st.session_state[key] = manager.suggest_allocation(household.id)
    draft = st.session_state.get(key)
    if draft is None:
        st.write("Press the button to get a suggestion based on household size, needs and stock.")
        return

    st.subheader("Items")
    st.caption("Change a quantity to 0 to take an item out.")
    for item in draft:
        item["quantity"] = st.number_input(item["item_name"], min_value=0, value=int(item["quantity"]),
                                           step=1, key=f"q_{household.id}_{item['batch_id']}")

    with st.expander("Add another item"):
        batches = [b for b in manager.available_batches() if manager.free_quantity(b) > 0]
        labels = {_batch_label(b, manager): b for b in batches}
        if labels:
            choice = labels[st.selectbox("Item", list(labels.keys()))]
            qty = st.number_input("Quantity", min_value=1, step=1, key=f"addq_{household.id}")
            if manager.safety_conflicts(choice, household):
                st.error(f"{choice.item_name} is not suitable for this household and cannot be added.")
            elif st.button("Add item"):
                draft.append({"batch_id": choice.id, "item_name": choice.item_name, "quantity": int(qty)})
                st.rerun()

    # preferences can be overridden but only with a reason (FR-17)
    justifications = {}
    for item in draft:
        batch = manager.find_batch(item["batch_id"])
        if batch and item["quantity"] > 0 and manager.preference_conflicts(batch, household):
            justifications[batch.id] = st.text_input(
                f"Reason for including {batch.item_name} (goes against a preference)", key=f"why_{household.id}_{batch.id}")

    slots = household.preferred_pickup_times or manager.config["pickup_slots"]
    pickup = st.selectbox("Pickup time", slots)
    collector = st.text_input("Someone else collecting? (optional name)")
    if st.button("Create order"):
        items = [i for i in draft if i["quantity"] > 0]
        order, message = manager.create_order(household.id, items, pickup, user, collector, justifications)
        if order:
            st.session_state.pop(key)
            st.success(message)
        else:
            st.error(message)


def _orders(manager, user):
    if not manager.orders:
        st.info("No orders yet.")
        return
    rows = []
    for o in reversed(manager.orders):
        h = manager.find_household(o.household_id)
        rows.append({"Order": o.reference(), "Household": h.preferred_name, "Pickup": o.pickup_time,
                     "Status": o.status, "Items": sum(i["quantity"] for i in o.items)})
    st.dataframe(pd.DataFrame(rows), hide_index=True)

    options = {o.reference(): o.id for o in reversed(manager.orders)}
    order = manager.find_order(options[st.selectbox("Open order", list(options.keys()))])
    st.table([{"Item": i["item_name"], "Quantity": i["quantity"]} for i in order.items])
    if order.alternative_collector:
        st.write(f"**Collected by:** {order.alternative_collector}")
    for s in order.substitutions:
        st.write(f"Substitution: {s.original_item} replaced by {s.substitute_item} ({s.recorded_by})")
    for e in order.exceptions:
        st.write(f"Preference exception: {e['item_name']} - {e['reason']} ({e['by']})")

    if order.status == "Requested" and st.button("Approve and send for packing"):
        ok, message = manager.approve_order(order.id, user)
        st.success(message)
        st.rerun()

    if order.status in ("Requested", "Approved"):
        _substitution_form(manager, user, order)

    next_status = {"Packed": ["Ready"], "Ready": ["Collected", "Not Collected"]}.get(order.status, [])
    for status in next_status:
        if st.button(f"Mark as {status}", key=f"{order.id}_{status}"):
            ok, message = manager.set_order_status(order.id, status, user)
            (st.success if ok else st.error)(message)
            st.rerun()


def _substitution_form(manager, user, order):
    # swap an item that ran out for something that still suits the household (FR-18)
    household = manager.find_household(order.household_id)
    with st.expander("Record a substitution"):
        originals = {f"{i['item_name']} x{i['quantity']}": i["batch_id"] for i in order.items}
        suitable = [b for b in manager.available_batches()
                    if not manager.safety_conflicts(b, household) and not manager.preference_conflicts(b, household)
                    and manager.free_quantity(b) > 0]
        if not suitable:
            st.info("No suitable substitute is in stock right now.")
            return
        subs = {_batch_label(b, manager): b.id for b in suitable}
        with st.form(f"sub_{order.id}"):
            original = st.selectbox("Item that is not available", list(originals.keys()))
            substitute = st.selectbox("Substitute", list(subs.keys()))
            if st.form_submit_button("Save substitution"):
                ok, message = manager.record_substitution(order.id, originals[original], subs[substitute], user)
                (st.success if ok else st.error)(message)


def show_notification_page(manager, user):
    # messages are simulated, this log is where they "go" (FR-28, FR-29)
    st.header("Notification Log")
    if not manager.notifications:
        st.info("No notifications yet.")
        return
    st.dataframe(pd.DataFrame([{"Time": n.timestamp, "Order": n.order_ref, "Method": n.method,
                                "Type": n.kind, "Message": n.message}
                               for n in reversed(manager.notifications)]), hide_index=True)
