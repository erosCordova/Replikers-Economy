from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from app.auth.password_policy import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    PasswordPolicyError,
    validate_new_password,
)


class UserRegister(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=120,
    )

    email: EmailStr

    password: str = Field(
        min_length=
            MIN_PASSWORD_LENGTH,
        max_length=
            MAX_PASSWORD_LENGTH,
    )

    @field_validator(
        "full_name"
    )
    @classmethod
    def normalize_full_name(
        cls,
        value: str,
    ) -> str:
        clean = value.strip()

        if len(clean) < 2:
            raise ValueError(
                "El nombre debe tener "
                "al menos 2 caracteres."
            )

        return clean

    @field_validator(
        "password"
    )
    @classmethod
    def validate_password(
        cls,
        value: str,
    ) -> str:
        try:
            return (
                validate_new_password(
                    value
                )
            )

        except PasswordPolicyError as exc:
            raise ValueError(
                str(exc)
            ) from exc


class UserLogin(BaseModel):
    email: EmailStr

    password: str = Field(
        min_length=1,
        max_length=
            MAX_PASSWORD_LENGTH,
    )


class UserPublic(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class AuthResponse(BaseModel):
    access_token: str

    token_type: str = (
        "bearer"
    )

    user: UserPublic
