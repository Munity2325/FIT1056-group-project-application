# F-04 client profiles, consent and needs
import datetime
from conftest import TODAY, make_household


def test_register_with_required_fields_only(manager, staff):
    # AC-16
    household, _ = manager.register_household(make_household(), staff)

    assert household is not None
    assert household.safety_needs == []


def test_missing_name_is_rejected(manager, staff):
    household, message = manager.register_household(make_household(preferred_name=" "), staff)

    assert household is None
    assert "name" in message.lower()


def test_seniors_boundary(manager, staff):
    # seniors can equal adults but not be more
    assert manager.register_household(make_household(adults=2, seniors=2), staff)[0]
    assert manager.register_household(make_household(adults=2, seniors=3), staff)[0] is None


def test_no_income_or_id_fields(manager, staff):
    # AC-20, NFR-07
    household, _ = manager.register_household(make_household(), staff)

    fields = household.to_dict().keys()

    assert not any(word in f for f in fields for word in ("income", "employment", "ic_number", "id_number"))


def test_needs_not_saved_without_consent(manager, staff):
    household, _ = manager.register_household(
        make_household(consent=False, safety_needs=["Nut allergy"]), staff)

    assert household.safety_needs == []


def test_needs_saved_with_consent(manager, staff):
    household, _ = manager.register_household(
        make_household(consent=True, safety_needs=["Nut allergy"]), staff)

    assert household.safety_needs == ["Nut allergy"]
    assert household.consent.given


def test_withdrawing_consent_deletes_needs(manager, staff):
    # AC-18
    household, _ = manager.register_household(
        make_household(consent=True, safety_needs=["Halal"], accessibility_needs="cane"), staff)

    manager.withdraw_consent(household.id, staff)

    assert household.safety_needs == []
    assert household.accessibility_needs == ""
    assert not household.consent.given


def test_inactive_after_24_months(manager, staff):
    # NFR-08
    manager.register_household(make_household(), staff, today=TODAY)

    later = TODAY + datetime.timedelta(days=24 * 30 + 1)

    assert len(manager.inactive_households(today=later)) == 1
    assert manager.inactive_households(today=TODAY) == []
