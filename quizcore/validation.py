"""Domain validation applies to every native form and service operation."""
import re

class AppError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status

def text(value, label, minimum=1, maximum=200):
    if not isinstance(value, str):
        raise AppError(f"{label} must be text.")
    value = value.strip()
    if not minimum <= len(value) <= maximum:
        raise AppError(f"{label} must contain {minimum}–{maximum} characters.")
    if any(ord(c) < 32 and c not in '\n\t' for c in value):
        raise AppError(f"{label} contains unsupported control characters.")
    return value

def integer(value, label, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise AppError(f"{label} must be a whole number.")
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise AppError(f"{label} must be a whole number.") from None
    if not low <= result <= high:
        raise AppError(f"{label} must be between {low} and {high}.")
    return result

def choice(value, label, choices):
    if not isinstance(value, str) or value not in choices:
        raise AppError(f"Choose a valid {label}.")
    return value

def username(value):
    value = text(value, "Username", 3, 40).lower()
    if not re.fullmatch(r"[a-z0-9_.-]+", value):
        raise AppError("Username may contain letters, numbers, dots, hyphens and underscores.")
    return value

def password(value):
    if not isinstance(value, str) or not 10 <= len(value) <= 128:
        raise AppError("Use a password containing 10–128 characters.")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"[0-9]", value):
        raise AppError("Include a letter and a number in the password.")
    return value

def require_role(user, *roles):
    if not user:
        raise AppError("Please sign in to continue.", 401)
    if user["role"] not in roles:
        raise AppError("Your role does not allow this action.", 403)

def exists(row, label="Record"):
    if row is None:
        raise AppError(f"{label} was not found.", 404)
    return row
