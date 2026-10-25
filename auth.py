# auth.py
"""
Simple file-based authentication and user management module.
Uses SHA-256 with salt for secure and dependency-free password hashing.
"""

import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Dict, Optional

AUTH_FILE = Path(__file__).parent / "users.json"
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "admin"


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    """Generate salted SHA-256 hash formatted as salt$hash."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${hashed}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored salt$hash."""
    if "$" not in stored_hash:
        return False
    salt, _ = stored_hash.split("$", 1)
    return _hash_password(password, salt) == stored_hash


def load_users() -> Dict[str, Dict[str, str]]:
    """Load users from the JSON file or initialize with default admin."""
    if not AUTH_FILE.exists():
        default_users = {
            DEFAULT_ADMIN_USER: {
                "password_hash": _hash_password(DEFAULT_ADMIN_PASS),
                "role": "admin"
            }
        }
        save_users(default_users)
        return default_users

    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        default_users = {
            DEFAULT_ADMIN_USER: {
                "password_hash": _hash_password(DEFAULT_ADMIN_PASS),
                "role": "admin"
            }
        }
        save_users(default_users)
        return default_users


def save_users(users: Dict[str, Dict[str, str]]) -> None:
    """Save users dictionary to the JSON file."""
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def authenticate_user(username: str, password: str) -> bool:
    """Check if credentials are valid."""
    username = username.strip()
    users = load_users()
    if username in users:
        stored_hash = users[username].get("password_hash", "")
        return _verify_password(password, stored_hash)
    return False


def add_user(username: str, password: str, role: str = "user") -> tuple[bool, str]:
    """Add a new user."""
    username = username.strip()
    if not username:
        return False, "Username cannot be empty."
    if not password:
        return False, "Password cannot be empty."

    users = load_users()
    if username in users:
        return False, f"User '{username}' already exists."

    users[username] = {
        "password_hash": _hash_password(password),
        "role": role
    }
    save_users(users)
    return True, f"User '{username}' created successfully."


def update_password(username: str, new_password: str) -> tuple[bool, str]:
    """Update password for an existing user."""
    username = username.strip()
    if not new_password:
        return False, "Password cannot be empty."

    users = load_users()
    if username not in users:
        return False, f"User '{username}' not found."

    users[username]["password_hash"] = _hash_password(new_password)
    save_users(users)
    return True, f"Password for '{username}' updated successfully."


def delete_user(username: str, current_user: str) -> tuple[bool, str]:
    """Delete a user account."""
    username = username.strip()
    if username == current_user:
        return False, "You cannot delete your own account while logged in."

    users = load_users()
    if username not in users:
        return False, f"User '{username}' not found."

    if len(users) <= 1:
        return False, "Cannot delete the last remaining user."

    del users[username]
    save_users(users)
    return True, f"User '{username}' deleted successfully."
