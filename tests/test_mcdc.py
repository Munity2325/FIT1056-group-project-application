# MC/DC tests, each condition is shown to change the result on its own
from conftest import TODAY, make_item, make_household


# decision in authenticate: user exists AND user active AND password matches
def test_mcdc_login_all_true(manager):
    assert manager.authenticate("kristine", "staff123") is not None


def test_mcdc_login_user_missing(manager):
    assert manager.authenticate("nobody", "staff123") is None


def test_mcdc_login_user_disabled(manager):
    manager.set_user_active(manager.find_user("kristine").id, False)

    assert manager.authenticate("kristine", "staff123") is None


def test_mcdc_login_wrong_password(manager):
    assert manager.authenticate("kristine", "nope") is None


# decision in create_order for each item:
# refuse if safety conflict OR (preference conflict AND no reason)
def _setup(manager, staff, safety=None, prefs=None):
    manager.record_donation([make_item("Cheese", attrs=["Vegetarian", "Contains dairy"])], staff, today=TODAY)
    household, _ = manager.register_household(
        make_household(consent=True, safety_needs=safety or [], preferences=prefs or []), staff)
    return household


def test_mcdc_order_no_conflicts_accepted(manager, staff):
    h = _setup(manager, staff)

    order, _ = manager.create_order(h.id, [{"batch_id": 1, "quantity": 1}], "Friday morning", staff)

    assert order is not None


def test_mcdc_order_safety_conflict_refused(manager, staff):
    # only the safety condition changed from the case above
    h = _setup(manager, staff, safety=["Dairy allergy"])

    order, _ = manager.create_order(h.id, [{"batch_id": 1, "quantity": 1}], "Friday morning", staff)

    assert order is None


def test_mcdc_order_preference_without_reason_refused(manager, staff):
    # only the preference condition changed from the first case
    h = _setup(manager, staff, prefs=["Dairy allergy"])

    order, _ = manager.create_order(h.id, [{"batch_id": 1, "quantity": 1}], "Friday morning", staff)

    assert order is None


def test_mcdc_order_preference_with_reason_accepted(manager, staff):
    # only the reason condition changed from the case above
    h = _setup(manager, staff, prefs=["Dairy allergy"])

    order, _ = manager.create_order(h.id, [{"batch_id": 1, "quantity": 1}], "Friday morning", staff,
                                    justifications={1: "client asked"})

    assert order is not None
