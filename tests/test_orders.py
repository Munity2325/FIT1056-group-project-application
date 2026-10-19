# F-05 food allocation, pickup and F-08 notifications
import pytest
from conftest import TODAY, make_item, make_household


@pytest.fixture
def stocked(manager, staff):
    manager.record_donation([
        make_item("Peanut butter", attrs=["Vegan", "Contains nuts"]),
        make_item("Chicken", attrs=["Halal"]),
        make_item("Rice", attrs=["Vegan"]),
        make_item("Cheese", attrs=["Vegetarian", "Contains dairy"]),
        make_item("Pork sausages", attrs=["None applicable"]),
    ], staff, today=TODAY)
    return manager


def test_suggestion_skips_allergy_items(stocked, staff):
    # AC-22, FR-16
    household, _ = stocked.register_household(make_household(consent=True, safety_needs=["Nut allergy"]), staff)

    names = [i["item_name"] for i in stocked.suggest_allocation(household.id, today=TODAY)]

    assert "Peanut butter" not in names
    assert "Rice" in names


def test_suggestion_uses_household_size(stocked, staff):
    # AC-21
    household, _ = stocked.register_household(make_household(adults=2, children=1), staff)

    suggestion = stocked.suggest_allocation(household.id, today=TODAY)

    assert all(i["quantity"] == 3 for i in suggestion)


def test_safety_need_cannot_be_overridden(stocked, staff):
    # FR-16, even with a reason
    household, _ = stocked.register_household(make_household(consent=True, safety_needs=["Nut allergy"]), staff)

    order, message = stocked.create_order(household.id, [{"batch_id": 1, "quantity": 1}], "Friday morning",
                                          staff, justifications={1: "client asked"})

    assert order is None
    assert "not suitable" in message


def test_preference_needs_a_reason(stocked, staff):
    # AC-23, FR-17
    household, _ = stocked.register_household(make_household(consent=True, preferences=["Vegan"]), staff)

    no_reason, _ = stocked.create_order(household.id, [{"batch_id": 4, "quantity": 1}], "Friday morning", staff)
    with_reason, _ = stocked.create_order(household.id, [{"batch_id": 4, "quantity": 1}], "Friday morning",
                                          staff, justifications={4: "asked for cheese today"})

    assert no_reason is None
    assert with_reason.exceptions[0]["reason"] == "asked for cheese today"


def test_pickup_outside_preferred_times_is_refused(stocked, staff):
    # AC-24
    household, _ = stocked.register_household(make_household(), staff)

    order, _ = stocked.create_order(household.id, [{"batch_id": 3, "quantity": 1}], "Monday morning", staff)

    assert order is None


def test_alternative_collector_is_saved(stocked, staff):
    # AC-24, FR-20
    household, _ = stocked.register_household(make_household(), staff)

    order, _ = stocked.create_order(household.id, [{"batch_id": 3, "quantity": 1}], "Friday morning",
                                    staff, alternative_collector="Faizal")

    assert order.alternative_collector == "Faizal"


def test_cannot_order_more_than_free_stock(stocked, staff):
    # boundary: 10 in stock
    household, _ = stocked.register_household(make_household(), staff)

    too_many, _ = stocked.create_order(household.id, [{"batch_id": 3, "quantity": 11}], "Friday morning", staff)
    all_of_it, _ = stocked.create_order(household.id, [{"batch_id": 3, "quantity": 10}], "Friday morning", staff)

    assert too_many is None
    assert all_of_it is not None


def test_order_status_flow(stocked, staff, volunteer):
    # AC-25
    household, _ = stocked.register_household(make_household(), staff)
    order, _ = stocked.create_order(household.id, [{"batch_id": 3, "quantity": 2}], "Friday morning", staff)

    assert order.status == "Requested"
    assert not stocked.set_order_status(order.id, "Ready", staff)[0]
    stocked.approve_order(order.id, staff)
    task = stocked.tasks[0]
    stocked.claim_task(task.id, volunteer)
    stocked.start_task(task.id, volunteer)
    stocked.complete_task(task.id, volunteer)
    assert order.status == "Packed"
    stocked.set_order_status(order.id, "Ready", staff)
    stocked.set_order_status(order.id, "Collected", staff)
    assert order.status == "Collected"


def test_substitution_must_suit_household(stocked, staff):
    # AC-26
    household, _ = stocked.register_household(make_household(consent=True, safety_needs=["Halal"]), staff)
    order, _ = stocked.create_order(household.id, [{"batch_id": 2, "quantity": 1}], "Friday morning", staff)

    bad, _ = stocked.record_substitution(order.id, 2, 5, staff)
    good, _ = stocked.record_substitution(order.id, 2, 3, staff)

    assert not bad
    assert good
    assert order.items[0]["item_name"] == "Rice"
    assert order.substitutions[0].original_item == "Chicken"


def test_notifications_have_no_diet_details(stocked, staff, volunteer):
    # AC-37, AC-38, AC-39, FR-30
    household, _ = stocked.register_household(make_household(consent=True, safety_needs=["Halal"]), staff)
    order, _ = stocked.create_order(household.id, [{"batch_id": 2, "quantity": 1}], "Friday morning", staff)
    stocked.record_substitution(order.id, 2, 3, staff)
    stocked.approve_order(order.id, staff)
    task = stocked.tasks[0]
    for step in (stocked.claim_task, stocked.start_task, stocked.complete_task):
        step(task.id, volunteer)

    stocked.set_order_status(order.id, "Ready", staff)

    kinds = [n.kind for n in stocked.notifications]
    assert kinds == ["Substitution", "Pickup confirmation"]
    for n in stocked.notifications:
        assert n.method == "SMS"
        assert "FS-0001" in n.message
        assert "Halal" not in n.message and "Chicken" not in n.message
