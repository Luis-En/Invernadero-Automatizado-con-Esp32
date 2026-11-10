"""Shared password policy for new credentials.

Login stays permissive by design: rejecting a legacy weak password at login
would lock users out instead of improving security. The policy applies whenever
a password is created or changed.
"""

import re
from typing import List


def validate_password_strength(password: str, username: str = "") -> List[str]:
    errors: List[str] = []
    if len(password) < 12:
        errors.append("La contraseña debe tener al menos 12 caracteres")
    if len(password.encode("utf-8")) > 72:
        errors.append("La contraseña no puede superar 72 bytes en UTF-8")
    if not re.search(r"[a-z]", password):
        errors.append("Debe incluir al menos una minúscula")
    if not re.search(r"[A-Z]", password):
        errors.append("Debe incluir al menos una mayúscula")
    if not re.search(r"\d", password):
        errors.append("Debe incluir al menos un número")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("Debe incluir al menos un símbolo")
    if username and username.lower() in password.lower():
        errors.append("La contraseña no puede contener el nombre de usuario")
    return errors


def password_is_strong(password: str, username: str = "") -> bool:
    return not validate_password_strength(password, username)
