import streamlit as st


def show_task_page(manager, user):
    st.header("My Tasks")
    tasks = manager.tasks_for(user)
    if not tasks:
        st.info("There are no tasks right now. Check back soon.")
        return

    for task in tasks:
        with st.container(border=True):
            st.write(f"**{task.task_type}** - {task.location} - about {task.est_minutes} minutes - {task.status}")
            if task.status == "Available":
                if st.button("Claim", key=f"claim{task.id}"):
                    _show_result(manager.claim_task(task.id, user))
                continue

            # only order ref, bag, items and shelf, no client details (FR-24)
            picking = manager.picking_list(task.id)
            if picking:
                st.write(f"Order {picking['order_ref']} - Bag {picking['bag_number']}")
                for note in picking["packing_notes"]:
                    st.warning(note)
                st.table([{"Item": i["item"], "Quantity": f"{i['quantity']} {i['unit']}", "Shelf": i["shelf"] or "-"}
                          for i in picking["items"]])
            if task.status == "Claimed" and st.button("Start", key=f"start{task.id}"):
                _show_result(manager.start_task(task.id, user))
            if task.status == "In progress" and st.button("Mark as packed", key=f"done{task.id}"):
                _show_result(manager.complete_task(task.id, user))


def _show_result(result):
    ok, message = result
    if ok:
        st.rerun()
    st.error(message)
