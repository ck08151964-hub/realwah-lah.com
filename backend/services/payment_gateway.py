"""
Abstract Payment Gateway Framework

Provides a modular interface for payment processing. Allows plugging in
different payment providers (Skrill, Gift Cards, Stripe, etc.) without
changing the application logic.

Replaces: services/stripe_client.py (DEPRECATED — removed in favor of modular gateway)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class DepositStatus(Enum):
    """Status of a deposit transaction"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PayoutStatus(Enum):
    """Status of a payout transaction"""
    REQUESTED = "requested"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass
class DepositSession:
    """Represents a user's deposit session"""
    session_id: str
    url: Optional[str]  # Redirect URL for deposit completion
    status: DepositStatus
    amount_usd: float
    gateway_id: str
    metadata: Dict[str, Any]


@dataclass
class DepositStatus_Response:
    """Status query response for a deposit"""
    status: DepositStatus
    payment_status: str  # "paid", "unpaid", etc.
    amount_usd: float
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class PayoutRequest:
    """Represents a user's payout request"""
    user_id: str
    amount_usd: float
    destination: str  # Email, phone, wallet address, etc.
    payout_type: str  # "giftcard", "crypto", "bank", etc.
    metadata: Dict[str, Any]


@dataclass
class PayoutResponse:
    """Response from a payout request"""
    transaction_id: str
    status: PayoutStatus
    message: str
    estimated_delivery: Optional[str] = None


class PaymentGateway(ABC):
    """Abstract base class for payment gateways"""

    gateway_id: str = "abstract"
    display_name: str = "Abstract Gateway"
    supported_currencies: list = ["USD"]

    @abstractmethod
    async def create_deposit_session(
        self,
        user_id: str,
        amount_usd: float,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DepositSession:
        """Create a deposit session and return URL for user to complete payment"""
        pass

    @abstractmethod
    async def get_deposit_status(self, session_id: str) -> DepositStatus_Response:
        """Check the status of a deposit session"""
        pass

    @abstractmethod
    async def handle_webhook(
        self, body: bytes, signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate and parse an incoming webhook from the gateway"""
        pass

    @abstractmethod
    async def create_payout(self, request: PayoutRequest) -> PayoutResponse:
        """Initiate a payout to the user"""
        pass


class SkrillGateway(PaymentGateway):
    """Skrill payment gateway for deposits and payouts"""

    gateway_id = "skrill"
    display_name = "Skrill"
    supported_currencies = ["USD"]

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        # TODO: Initialize Skrill SDK when credentials available

    async def create_deposit_session(
        self,
        user_id: str,
        amount_usd: float,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DepositSession:
        """Create a Skrill deposit session"""
        # TODO: Implement Skrill deposit flow
        # For now, return a placeholder
        return DepositSession(
            session_id=f"skrill_{user_id}_{int(amount_usd * 100)}",
            url="https://skrill-placeholder-not-implemented.com",
            status=DepositStatus.PENDING,
            amount_usd=amount_usd,
            gateway_id=self.gateway_id,
            metadata=metadata or {},
        )

    async def get_deposit_status(self, session_id: str) -> DepositStatus_Response:
        """Query Skrill deposit status"""
        # TODO: Implement status checking
        return DepositStatus_Response(
            status=DepositStatus.PENDING,
            payment_status="unpaid",
            amount_usd=0.0,
            error_message="Skrill gateway not yet implemented",
        )

    async def handle_webhook(
        self, body: bytes, signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle Skrill webhook"""
        # TODO: Implement webhook validation
        return {"status": "unimplemented"}

    async def create_payout(self, request: PayoutRequest) -> PayoutResponse:
        """Create a Skrill payout"""
        # TODO: Implement Skrill payout
        return PayoutResponse(
            transaction_id="skrill_payout_placeholder",
            status=PayoutStatus.REQUESTED,
            message="Skrill payout not yet implemented",
        )


class GiftCardGateway(PaymentGateway):
    """Gift card payout gateway"""

    gateway_id = "giftcard"
    display_name = "Gift Card"
    supported_currencies = ["USD"]

    def __init__(self, db=None):
        self.db = db

    async def create_deposit_session(
        self,
        user_id: str,
        amount_usd: float,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DepositSession:
        """Gift cards are not used for deposits"""
        raise NotImplementedError("Gift cards are for payouts only")

    async def get_deposit_status(self, session_id: str) -> DepositStatus_Response:
        """Not applicable for gift cards"""
        raise NotImplementedError("Gift cards are for payouts only")

    async def handle_webhook(
        self, body: bytes, signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """Not applicable for gift cards"""
        raise NotImplementedError("Gift cards do not use webhooks")

    async def create_payout(self, request: PayoutRequest) -> PayoutResponse:
        """Create a gift card payout request"""
        # Gift card payouts are admin-fulfilled
        if self.db:
            payout_doc = {
                "user_id": request.user_id,
                "amount_usd": request.amount_usd,
                "destination": request.destination,  # Email
                "payout_type": "giftcard",
                "status": "requested",
                "metadata": request.metadata,
                "created_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
            }
            result = await self.db.gift_card_requests.insert_one(payout_doc)
            return PayoutResponse(
                transaction_id=str(result.inserted_id),
                status=PayoutStatus.REQUESTED,
                message=f"Gift card request submitted. Code will be emailed to {request.destination}",
                estimated_delivery="24 hours",
            )

        return PayoutResponse(
            transaction_id="giftcard_placeholder",
            status=PayoutStatus.REQUESTED,
            message="Gift card payout requested",
        )


class DepositTestGateway(PaymentGateway):
    """Test gateway for development and verification"""

    gateway_id = "test"
    display_name = "Test Gateway"
    supported_currencies = ["USD"]

    async def create_deposit_session(
        self,
        user_id: str,
        amount_usd: float,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DepositSession:
        """Create a test deposit session"""
        return DepositSession(
            session_id=f"test_session_{user_id}_{int(amount_usd * 100)}",
            url=f"{success_url}?status=test",
            status=DepositStatus.COMPLETED,
            amount_usd=amount_usd,
            gateway_id=self.gateway_id,
            metadata=metadata or {},
        )

    async def get_deposit_status(self, session_id: str) -> DepositStatus_Response:
        """Get test deposit status (always succeeds)"""
        return DepositStatus_Response(
            status=DepositStatus.COMPLETED,
            payment_status="paid",
            amount_usd=10.0,
        )

    async def handle_webhook(
        self, body: bytes, signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle test webhook"""
        return {"status": "test_webhook_received"}

    async def create_payout(self, request: PayoutRequest) -> PayoutResponse:
        """Create a test payout"""
        return PayoutResponse(
            transaction_id=f"test_payout_{request.user_id}",
            status=PayoutStatus.COMPLETED,
            message="Test payout completed",
        )
