# F-01 user accounts, roles and access control
from app.manager import FoodShareManager


def test_login_with_correct_password(manager):
    assert manager.authenticate("kristine", "staff123").role == "Staff"


def test_login_with_wrong_password_fails(manager):
    assert manager.authenticate("kristine", "wrong") is None


def test_unknown_user_cannot_login(manager):
    assert manager.authenticate("nobody", "staff123") is None


def test_disabled_account_cannot_login(manager):
    # AC-01
    user = manager.find_user("wei")
    manager.set_user_active(user.id, False)

    assert manager.authenticate("wei", "vol123") is None


def test_password_is_not_stored_in_plain_text(manager, tmp_path):
    # AC-04, NFR-04
    text = open(tmp_path / "test_data.json").read()

    assert "staff123" not in text


def test_duplicate_username_is_rejected(manager):
    assert manager.create_user("Kristine", "x", "Staff") is None


def test_unknown_role_is_rejected(manager):
    assert manager.create_user("bob", "x", "Manager") is None


def test_volunteer_cannot_see_client_details(manager):
    # AC-02, AC-05, least privilege
    volunteer = manager.find_user("wei")
    staff = manager.find_user("kristine")

    assert not manager.can(volunteer, "view_client_details")
    assert manager.can(staff, "view_client_details")


def test_admin_can_manage_users_but_not_orders(manager):
    admin = manager.find_user("grace")

    assert manager.can(admin, "manage_users")
    assert not manager.can(admin, "manage_orders")


def test_users_are_saved_and_loaded(manager, tmp_path):
    reloaded = FoodShareManager(data_path=str(tmp_path / "test_data.json"))

    assert len(reloaded.users) == 3
