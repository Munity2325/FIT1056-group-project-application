# F-02 donations and F-03 inventory
import datetime
from conftest import TODAY, make_item


def test_valid_donation_goes_into_stock_with_reference(manager, staff):
    # AC-06
    result = manager.record_donation([make_item("Milk", 24, "2026-10-30")], staff, today=TODAY)

    assert result["ok"]
    assert result["ref"] == "DON-0001"
    assert manager.batches[0].quantity == 24
    assert manager.get_donation_confirmation("DON-0001")["items"] == ["24 units Milk"]


def test_expired_batch_is_rejected(manager, staff):
    # AC-07, boundary: one day before today
    result = manager.record_donation([make_item(expiry="2026-10-18")], staff, today=TODAY)

    assert len(result["rejected"]) == 1
    assert manager.batches == []


def test_batch_expiring_today_is_accepted(manager, staff):
    # boundary: expiry equal to the receipt date
    result = manager.record_donation([make_item(expiry="2026-10-19")], staff, today=TODAY)

    assert len(result["batches"]) == 1


def test_rejected_item_can_be_recorded_as_disposal(manager, staff):
    result = manager.record_donation([make_item(expiry="2026-01-01")], staff, today=TODAY)

    manager.record_intake_disposal(result["ref"], result["rejected"][0], staff)

    assert manager.audit_log[0].action == "Disposal at intake"
    assert manager.audit_log[0].reason_code == "Expired"


def test_attribute_outside_controlled_list_is_rejected(manager, staff):
    # AC-08
    result = manager.record_donation([make_item(attrs=["Organic"])], staff, today=TODAY)

    assert not result["ok"]


def test_quantity_zero_is_rejected_and_one_is_accepted(manager, staff):
    # boundary values for quantity
    assert not manager.record_donation([make_item(quantity=0)], staff, today=TODAY)["ok"]
    assert manager.record_donation([make_item(quantity=1)], staff, today=TODAY)["ok"]


def test_anonymous_donation_keeps_no_donor(manager, staff):
    # AC-09
    manager.record_donation([make_item()], staff, donor=None, today=TODAY)

    assert manager.donors == []
    assert manager.batches[0].donor_id is None


def test_donor_without_contact_consent_is_recorded(manager, staff):
    # AC-10
    manager.record_donation([make_item()], staff, today=TODAY,
                            donor={"name": "Tan", "contact": "0123", "contact_consent": False})

    assert manager.donors[0].contact == "0123"
    assert manager.donors[0].contact_consent is False


def test_earliest_expiry_comes_first(manager, staff):
    # AC-11, FEFO
    manager.record_donation([make_item("Rice", expiry="2026-12-01"), make_item("Rice", expiry="2026-11-01")],
                            staff, today=TODAY)

    assert manager.available_batches(TODAY)[0].expiry_date == "2026-11-01"


def test_expiring_soon_boundary_7_and_8_days(manager, staff):
    # AC-15, 7 days is included, 8 is not
    seven = (TODAY + datetime.timedelta(days=7)).isoformat()
    eight = (TODAY + datetime.timedelta(days=8)).isoformat()
    manager.record_donation([make_item("A", expiry=seven), make_item("B", expiry=eight)], staff, today=TODAY)

    names = [b.item_name for b in manager.expiring_soon(today=TODAY)]

    assert names == ["A"]


def test_stock_adjustment_is_logged(manager, volunteer, staff):
    # AC-13
    manager.record_donation([make_item("Milk", 10)], staff, today=TODAY)

    ok, _ = manager.adjust_stock(1, 4, "Damaged", volunteer)

    assert ok
    assert manager.batches[0].quantity == 6
    entry = manager.audit_log[-1]
    assert (entry.user, entry.reason_code, entry.quantity) == ("wei", "Damaged", 4)


def test_adjustment_without_reason_is_refused(manager, staff):
    manager.record_donation([make_item(quantity=10)], staff, today=TODAY)

    ok, _ = manager.adjust_stock(1, 1, "", staff)

    assert not ok


def test_adjustment_boundary_whole_batch_and_one_more(manager, staff):
    manager.record_donation([make_item(quantity=10)], staff, today=TODAY)

    assert not manager.adjust_stock(1, 11, "Miscount", staff)[0]
    assert manager.adjust_stock(1, 10, "Miscount", staff)[0]
