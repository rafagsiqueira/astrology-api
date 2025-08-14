"""Models for App Store subscription handling."""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class SubscriptionType(str, Enum):
    """Subscription types supported by the app."""
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    LIFETIME = "lifetime"


class SubscriptionStatus(str, Enum):
    """User subscription status."""
    NONE = "none"
    ACTIVE = "active"
    EXPIRED = "expired"
    GRACE_PERIOD = "grace_period"
    BILLING_RETRY = "billing_retry"
    REVOKED = "revoked"
    LIFETIME = "lifetime"


class NotificationType(str, Enum):
    """App Store Server notification types."""
    # Initial purchase notifications
    INITIAL_BUY = "INITIAL_BUY"
    
    # Subscription lifecycle
    DID_RENEW = "DID_RENEW"
    CANCEL = "CANCEL"
    DID_FAIL_TO_RENEW = "DID_FAIL_TO_RENEW"
    DID_RECOVER = "DID_RECOVER"
    
    # Billing retry and grace period
    GRACE_PERIOD_EXPIRED = "GRACE_PERIOD_EXPIRED"
    
    # Refunds and revokes
    REFUND = "REFUND"
    REVOKE = "REVOKE"
    
    # Price changes
    PRICE_INCREASE = "PRICE_INCREASE"
    
    # Other events
    RENEWAL_EXTENDED = "RENEWAL_EXTENDED"
    RENEWAL_EXTENSION = "RENEWAL_EXTENSION"
    AUTO_RENEW_ENABLED = "AUTO_RENEW_ENABLED"
    AUTO_RENEW_DISABLED = "AUTO_RENEW_DISABLED"
    VOLUNTARY_CANCELLATION = "VOLUNTARY_CANCELLATION"
    
    # External purchase events
    EXTERNAL_PURCHASE_TOKEN = "EXTERNAL_PURCHASE_TOKEN"
    
    # Offer redemption
    OFFER_REDEEMED = "OFFER_REDEEMED"


class AppStoreEnvironment(str, Enum):
    """App Store environment types."""
    SANDBOX = "Sandbox"
    PRODUCTION = "Production"


class TransactionInfo(BaseModel):
    """Transaction information from App Store."""
    original_transaction_id: str
    transaction_id: str
    web_order_line_item_id: str
    bundle_id: str
    product_id: str
    subscription_group_identifier: str
    purchase_date: int
    original_purchase_date: int
    expires_date: Optional[int] = None
    quantity: int = 1
    type: str  # "Auto-Renewable Subscription" or "Non-Consumable"
    in_app_ownership_type: str = "PURCHASED"
    signed_date: int
    environment: AppStoreEnvironment
    transaction_reason: Optional[str] = None
    storefront: Optional[str] = None
    storefront_id: Optional[str] = None
    price: Optional[int] = None
    currency: Optional[str] = None


class RenewalInfo(BaseModel):
    """Renewal information for subscriptions."""
    original_transaction_id: str
    auto_renew_product_id: str
    product_id: str
    auto_renew_status: int  # 0 = off, 1 = on
    environment: AppStoreEnvironment
    signed_date: int
    is_in_billing_retry_period: Optional[bool] = None
    expiration_intent: Optional[int] = None  # Reason for expiration
    grace_period_expires_date: Optional[int] = None
    offer_type: Optional[int] = None
    offer_identifier: Optional[str] = None
    price_increase_status: Optional[int] = None


class NotificationData(BaseModel):
    """App Store Server notification data."""
    app_apple_id: str
    bundle_id: str
    bundle_version: str
    environment: AppStoreEnvironment
    signed_transaction_info: str  # JWT containing TransactionInfo
    signed_renewal_info: Optional[str] = None  # JWT containing RenewalInfo


class AppStoreNotification(BaseModel):
    """Complete App Store Server notification."""
    notification_uuid: str
    notification_type: NotificationType
    subtype: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    external_purchase_token: Optional[str] = None
    data: NotificationData
    version: str = "2.0"
    signed_date: int


class UserSubscription(BaseModel):
    """User subscription status in Firestore."""
    user_id: str
    subscription_type: SubscriptionType
    subscription_status: SubscriptionStatus
    original_transaction_id: str
    current_transaction_id: str
    product_id: str
    purchase_date: datetime
    expires_date: Optional[datetime] = None
    auto_renew_enabled: bool = True
    is_in_billing_retry: bool = False
    grace_period_expires_date: Optional[datetime] = None
    environment: AppStoreEnvironment
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_firestore_dict(self) -> Dict[str, Any]:
        """Convert to Firestore-compatible dictionary."""
        data = {
            "user_id": self.user_id,
            "subscription_type": self.subscription_type.value,
            "subscription_status": self.subscription_status.value,
            "original_transaction_id": self.original_transaction_id,
            "current_transaction_id": self.current_transaction_id,
            "product_id": self.product_id,
            "purchase_date": self.purchase_date,
            "auto_renew_enabled": self.auto_renew_enabled,
            "is_in_billing_retry": self.is_in_billing_retry,
            "environment": self.environment.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
        
        # Add optional fields if they exist
        if self.expires_date:
            data["expires_date"] = self.expires_date
        if self.grace_period_expires_date:
            data["grace_period_expires_date"] = self.grace_period_expires_date
            
        return data


class SubscriptionAnalyticsEvent(BaseModel):
    """Analytics event for subscription tracking."""
    event_name: str
    user_id: str
    transaction_id: str
    product_id: str
    subscription_type: SubscriptionType
    environment: AppStoreEnvironment
    revenue: Optional[float] = None
    currency: Optional[str] = None
    notification_type: Optional[NotificationType] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Product ID mappings (replace with your actual product IDs)
PRODUCT_ID_MAPPINGS = {
    "com.digify.avra.weekly": SubscriptionType.WEEKLY,
    "com.digify.avra.monthly": SubscriptionType.MONTHLY,
    "com.digify.avra.lifetime": SubscriptionType.LIFETIME,
}

# Reverse mapping for quick lookup
SUBSCRIPTION_TYPE_TO_PRODUCT_ID = {v: k for k, v in PRODUCT_ID_MAPPINGS.items()}