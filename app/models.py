"""SQLModel data models (SPEC §4).

Category / CategoryTranslation, Product / ProductTranslation, ProductImage, Setting.

Note: intentionally NO `from __future__ import annotations` here — it would turn the
Relationship type hints into plain strings that SQLAlchemy cannot resolve.
"""
from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Categories -------------------------------------------------------------

class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    sort_order: int = Field(default=0)
    is_active: bool = Field(default=True)
    # Optional category image (paths relative to static/, like ProductImage).
    image: str | None = Field(default=None)
    thumb: str | None = Field(default=None)

    translations: list["CategoryTranslation"] = Relationship(
        back_populates="category",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )
    products: list["Product"] = Relationship(back_populates="category")


class CategoryTranslation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    lang: str = Field(index=True)  # el | en
    name: str

    category: Category | None = Relationship(back_populates="translations")


# --- Products ---------------------------------------------------------------

class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    sku: str | None = Field(default=None)
    category_id: int | None = Field(default=None, foreign_key="category.id", index=True)
    price: float | None = Field(default=None)
    currency: str = Field(default="EUR")
    price_on_request: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_featured: bool = Field(default=False)
    sort_order: int = Field(default=0)
    # Stock control (SPEC-BILLING §1 + addendum). Stock is always tracked now; the
    # admin always provides it. `track_stock` is kept as an internal always-on flag
    # (no UI toggle) so existing enforcement keyed on it keeps working without a migration.
    stock: int = Field(default=0)
    track_stock: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    category: Category | None = Relationship(back_populates="products")
    translations: list["ProductTranslation"] = Relationship(
        back_populates="product",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )
    images: list["ProductImage"] = Relationship(
        back_populates="product",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "lazy": "selectin",
            "order_by": "ProductImage.sort_order",
        },
    )


class ProductTranslation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    lang: str = Field(index=True)  # el | en
    title: str
    description: str = Field(default="")
    material: str | None = Field(default=None)

    product: Product | None = Relationship(back_populates="translations")


class ProductImage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    filename: str  # legacy path relative to static/ (e.g. uploads/uuid.webp)
    thumb: str  # legacy path relative to static/ (e.g. uploads/thumbs/uuid.webp)
    alt: str | None = Field(default=None)
    sort_order: int = Field(default=0)  # first (lowest) = main image
    width: int = Field(default=0)
    height: int = Field(default=0)
    # Image bytes live IN the database (served via /media/{id}) so they survive
    # redeploys on hosts with an ephemeral filesystem (e.g. Render). The on-disk
    # files (filename/thumb) are kept only as a local-dev convenience/fallback.
    content_type: str = Field(default="image/webp")
    data: bytes | None = Field(default=None)        # full (resized) image bytes
    thumb_data: bytes | None = Field(default=None)  # thumbnail bytes

    product: Product | None = Relationship(back_populates="images")


# --- Orders (SPEC-BILLING §1) -----------------------------------------------

# Allowed order statuses. Retail: pending -> paid -> shipped, or cancelled.
# Wholesale requests start at "wholesale" (no payment) -> shipped, or cancelled.
ORDER_STATUSES = ("pending", "paid", "shipped", "cancelled", "wholesale")


class Order(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(index=True, unique=True)  # human-readable, e.g. DC-20260620-0007
    status: str = Field(default="pending", index=True)  # see ORDER_STATUSES
    is_wholesale: bool = Field(default=False, index=True)  # B2B request (no payment, no stock cap)

    # Contact details
    customer_name: str = Field(default="")
    customer_email: str = Field(default="")
    customer_phone: str = Field(default="")

    # Shipping address
    ship_address: str = Field(default="")
    ship_city: str = Field(default="")
    ship_postcode: str = Field(default="")
    ship_country: str = Field(default="GR")

    # Shipping + money (all snapshots at order time; prices are gross / VAT-inclusive)
    shipping_method: str = Field(default="")
    shipping_cost: float = Field(default=0.0)
    subtotal: float = Field(default=0.0)   # gross sum of line items (no shipping)
    vat_amount: float = Field(default=0.0)  # VAT contained in `total` (back-computed)
    vat_rate: float = Field(default=0.0)    # snapshot of the rate used, e.g. 24.0
    total: float = Field(default=0.0)       # subtotal + shipping_cost, gross
    currency: str = Field(default="EUR")

    # Payment provider linkage
    viva_order_code: str | None = Field(default=None)
    viva_transaction_id: str | None = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    # When the order's contact/shipping PII was irreversibly anonymized (GDPR
    # retention / erasure). Financial fields are preserved; see app/orders.py.
    anonymized_at: datetime | None = Field(default=None)

    items: list["OrderItem"] = Relationship(
        back_populates="order",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )


class OrderItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    # Nullable: the product may be deleted later; the snapshot fields preserve the record.
    product_id: int | None = Field(default=None, foreign_key="product.id")
    title_snapshot: str = Field(default="")
    price_snapshot: float = Field(default=0.0)  # unit price, gross, at order time
    qty: int = Field(default=1)
    line_total: float = Field(default=0.0)      # price_snapshot * qty

    order: Order | None = Relationship(back_populates="items")


# --- Settings (key-value site config) ---------------------------------------

class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = Field(default="")


# --- Marketing consent (GDPR/ePrivacy, Task 3) ------------------------------
# Decoupled from orders and keyed by email. Order anonymization (Task 2) never
# touches this table — marketing consent stands on its own lawful basis.

class MarketingConsent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    status: str = Field(default="subscribed", index=True)  # subscribed | withdrawn
    consented_at: datetime | None = Field(default=None)
    withdrawn_at: datetime | None = Field(default=None)
    lang: str = Field(default="el")                         # language at capture (el | en)
    consent_text: str = Field(default="")                  # exact wording shown at capture
    source: str = Field(default="")                        # e.g. "checkout_confirmation"
    unsubscribe_token: str = Field(index=True, unique=True)  # random, unguessable
