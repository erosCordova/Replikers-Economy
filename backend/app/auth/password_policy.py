MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


class PasswordPolicyError(
    ValueError
):
    pass


def validate_new_password(
    password: str,
) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            "La contraseña debe tener "
            f"al menos {MIN_PASSWORD_LENGTH} "
            "caracteres."
        )

    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            "La contraseña no puede superar "
            f"{MAX_PASSWORD_LENGTH} caracteres."
        )

    if not password.strip():
        raise PasswordPolicyError(
            "La contraseña no puede contener "
            "solo espacios."
        )

    return password
