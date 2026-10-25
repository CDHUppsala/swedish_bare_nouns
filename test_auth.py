import unittest
import os
from auth import (
    AUTH_FILE,
    _hash_password,
    _verify_password,
    load_users,
    save_users,
    authenticate_user,
    add_user,
    update_password,
    delete_user,
    DEFAULT_ADMIN_USER,
    DEFAULT_ADMIN_PASS
)

class TestAuth(unittest.TestCase):
    def setUp(self):
        if AUTH_FILE.exists():
            AUTH_FILE.unlink()

    def tearDown(self):
        if AUTH_FILE.exists():
            AUTH_FILE.unlink()

    def test_default_user_creation(self):
        users = load_users()
        self.assertIn(DEFAULT_ADMIN_USER, users)
        self.assertTrue(authenticate_user(DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASS))
        self.assertFalse(authenticate_user(DEFAULT_ADMIN_USER, "wrong_password"))
        self.assertFalse(authenticate_user("nonexistent", "pass"))

    def test_add_user(self):
        success, msg = add_user("alice", "secret123", role="user")
        self.assertTrue(success)
        self.assertTrue(authenticate_user("alice", "secret123"))

        # Duplicate username
        success2, msg2 = add_user("alice", "otherpass")
        self.assertFalse(success2)
        self.assertIn("already exists", msg2)

    def test_update_password(self):
        add_user("bob", "initial_pass")
        self.assertTrue(authenticate_user("bob", "initial_pass"))

        success, _ = update_password("bob", "new_secure_pass")
        self.assertTrue(success)
        self.assertFalse(authenticate_user("bob", "initial_pass"))
        self.assertTrue(authenticate_user("bob", "new_secure_pass"))

    def test_delete_user(self):
        add_user("charlie", "pass123")
        self.assertIn("charlie", load_users())

        # Cannot delete self
        success_self, msg_self = delete_user("admin", current_user="admin")
        self.assertFalse(success_self)

        # Delete another user
        success, _ = delete_user("charlie", current_user="admin")
        self.assertTrue(success)
        self.assertNotIn("charlie", load_users())

if __name__ == '__main__':
    unittest.main()
