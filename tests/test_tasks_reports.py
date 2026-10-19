# F-06 volunteer tasks and F-07 reports
import csv
import datetime
import pytest
from conftest import TODAY, make_item, make_household


@pytest.fixture
def packed_order(manager, staff, volunteer):
    manager.record_donation([make_item("Rice", 10), make_item("Soup", 10, attrs=["Vegetarian"])], staff, today=TODAY)
    household, _ = manager.register_household(
        make_household(consent=True, safety_needs=["Vegetarian"], private_note="private"), staff)
    order, _ = manager.create_order(household.id, [{"batch_id": 1, "quantity": 3}, {"batch_id": 2, "quantity": 2}],
                                    "Friday morning", staff)
    manager.approve_order(order.id, staff)
    return order


def test_picking_list_has_no_client_details(manager, packed_order):
    # AC-02, AC-30
    picking = manager.picking_list(manager.tasks[0].id)

    text = str(picking)
    assert picking["order_ref"] == "FS-0001"
    assert picking["packing_notes"] == ["Vegetarian order"]
    assert "Kavitha" not in text and "012" not in text and "private" not in text


def test_task_steps_are_recorded(manager, packed_order, volunteer):
    # AC-29, AC-31
    task = manager.tasks[0]

    manager.claim_task(task.id, volunteer)
    manager.start_task(task.id, volunteer)
    manager.complete_task(task.id, volunteer)

    assert [h["status"] for h in task.history] == ["Claimed", "In progress", "Completed"]
    assert all(h["user"] == "wei" for h in task.history)


def test_packing_reduces_stock(manager, packed_order, volunteer):
    # AC-12, 10 - 3 = 7
    task = manager.tasks[0]
    for step in (manager.claim_task, manager.start_task, manager.complete_task):
        step(task.id, volunteer)

    assert manager.find_batch(1).quantity == 7


def test_other_volunteer_cannot_finish_my_task(manager, packed_order, volunteer):
    other = manager.create_user("ali", "x", "Volunteer")
    manager.claim_task(manager.tasks[0].id, volunteer)

    ok, _ = manager.start_task(manager.tasks[0].id, other)

    assert not ok


def test_task_cannot_skip_steps(manager, packed_order, volunteer):
    ok, _ = manager.complete_task(manager.tasks[0].id, volunteer)

    assert not ok


def test_demand_report(manager, packed_order, staff):
    # AC-32, AC-35
    manager.record_substitution(packed_order.id, 2, 1, staff)

    rows = {r["item"]: r for r in manager.demand_report(datetime.date.today(), datetime.date.today())}

    assert rows["Soup"]["requested"] == 2
    assert rows["Soup"]["unavailable"] == 2
    assert rows["Soup"]["substituted_with"] == "Rice"


def test_fairness_report_groups_by_size_and_allocator(manager, packed_order):
    # AC-34
    rows = manager.fairness_report(datetime.date.today(), datetime.date.today())

    assert rows == [{"household_size": "2-3 people", "allocated_by": "kristine", "orders": 1,
                     "items": 5, "items_per_person": 1.67}]


def test_report_export_has_no_names(manager, packed_order, tmp_path):
    # AC-33, AC-36
    path = tmp_path / "fairness.csv"

    manager.export_report(manager.fairness_report(datetime.date.today(), datetime.date.today()), str(path))

    text = path.read_text()
    assert text.splitlines()[0] == "household_size,allocated_by,orders,items,items_per_person"
    assert "Kavitha" not in text and "012" not in text


def test_export_of_empty_report_is_refused(manager, tmp_path):
    assert not manager.export_report([], str(tmp_path / "x.csv"))
