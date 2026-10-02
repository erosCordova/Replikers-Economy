from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
)


class LedgerTransactionPublic(
    BaseModel
):
    id: int
    idempotency_key: str
    transaction_type: str
    currency: str
    amount_cents: int

    from_account_id: int
    to_account_id: int

    project_id: int | None
    contract_id: int | None
    repliker_id: int | None

    external_reference: str | None
    description: str

    created_at: datetime


class UserWalletSnapshot(
    BaseModel
):
    user_id: int
    currency: str

    available_account_id: int | None
    pending_account_id: int | None

    available_cents: int
    pending_cents: int
    total_cents: int


class ProjectEconomySnapshot(
    BaseModel
):
    project_id: int
    currency: str

    payment_status: str

    custody_account_id: int | None

    custody_balance_cents: int
    contract_reserved_cents: int
    unallocated_cents: int


class LedgerListResponse(
    BaseModel
):
    items: list[
        LedgerTransactionPublic
    ]

    count: int


class SimulatedFundingRequest(
    BaseModel
):
    idempotency_key: str = Field(
        min_length=6,
        max_length=180,
    )

    amount_cents: int | None = Field(
        default=None,
        gt=0,
    )


class SimulatedFundingResponse(
    BaseModel
):
    mode: str

    real_money: bool

    project_id: int

    transaction_id: int

    currency: str

    amount_cents: int

    required_amount_cents: int

    custody_balance_cents: int

    remaining_to_fund_cents: int

    payment_status: str

    fully_funded: bool


class SimulatedWithdrawalRequest(
    BaseModel
):
    idempotency_key: str = Field(
        min_length=6,
        max_length=180,
    )

    amount_cents: int = Field(
        gt=0,
    )

    currency: str = Field(
        default="PEN",
        min_length=3,
        max_length=10,
    )


class SimulatedWithdrawalResponse(
    BaseModel
):
    mode: str

    real_money: bool

    transaction_id: int

    currency: str

    amount_cents: int

    remaining_available_cents: int
