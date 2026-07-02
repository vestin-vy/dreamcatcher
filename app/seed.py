"""Seed demo data (SPEC §11.2): categories, products, translations, settings, images.

Run:  python -m app.seed
Idempotent: drops and recreates all tables, then repopulates.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw
from sqlmodel import SQLModel, Session, select

from app.config import settings
from app.db import engine, init_db
from app.images import save_image
from app.models import (
    Category,
    CategoryTranslation,
    Product,
    ProductImage,
    ProductTranslation,
    Setting,
)

# --- palette for generated placeholder photos -------------------------------
_SWATCHES = [
    ((26, 22, 20), (161, 98, 7)),     # black -> gold
    ((68, 64, 60), (214, 211, 209)),  # warm grey
    ((40, 33, 30), (231, 199, 122)),  # espresso -> champagne
    ((24, 24, 27), (120, 113, 108)),  # ink -> taupe
]


def _placeholder_image(label: str, idx: int) -> bytes:
    """Render a simple gradient + label as PNG bytes (fed into the WebP pipeline)."""
    w, h = 1000, 1250
    top, bottom = _SWATCHES[idx % len(_SWATCHES)]
    img = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        f = y / h
        draw.line(
            [(0, y), (w, y)],
            fill=(
                int(top[0] + (bottom[0] - top[0]) * f),
                int(top[1] + (bottom[1] - top[1]) * f),
                int(top[2] + (bottom[2] - top[2]) * f),
            ),
        )
    # A simple diamond motif.
    cx, cy, r = w // 2, h // 2, 150
    draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)],
                 outline=(255, 255, 255), width=4)
    draw.text((cx - len(label) * 9, cy + r + 40), label, fill=(255, 255, 255))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# --- data -------------------------------------------------------------------
CATEGORIES = [
    {"slug": "rings", "order": 1, "names": {"el": "Δαχτυλίδια", "en": "Rings"}},
    {"slug": "necklaces", "order": 2, "names": {"el": "Κολιέ", "en": "Necklaces"}},
    {"slug": "earrings", "order": 3, "names": {"el": "Σκουλαρίκια", "en": "Earrings"}},
    {"slug": "bracelets", "order": 4, "names": {"el": "Βραχιόλια", "en": "Bracelets"}},
    {"slug": "anklets", "order": 5, "names": {"el": "Βραχιόλια ποδιού", "en": "Anklets"}},
    {"slug": "pendants", "order": 6, "names": {"el": "Μενταγιόν", "en": "Pendants"}},
    {"slug": "brooches", "order": 7, "names": {"el": "Καρφίτσες", "en": "Brooches"}},
    {"slug": "charms", "order": 8, "names": {"el": "Γούρια & Charms", "en": "Charms"}},
    {"slug": "hair-accessories", "order": 9, "names": {"el": "Αξεσουάρ μαλλιών", "en": "Hair accessories"}},
    {"slug": "sets", "order": 10, "names": {"el": "Σετ κοσμημάτων", "en": "Jewelry sets"}},
    {"slug": "body-jewelry", "order": 11, "names": {"el": "Κοσμήματα σώματος", "en": "Body jewelry"}},
    {"slug": "watches", "order": 12, "names": {"el": "Ρολόγια", "en": "Watches"}},
]

# Each product has el + en translations (en falls back to el when missing).
# A couple of items use stock tracking to exercise the out-of-stock path.
PRODUCTS = [
    {
        "slug": "aurora-solitaire-ring", "cat": "rings", "price": 1290.0, "featured": True, "sku": "DC-R-001", "stock": 8,
        "tr": {
            "el": {"title": "Δαχτυλίδι Aurora", "material": "Χρυσός 18Κ, διαμάντι", "description": "Μονόπετρο δαχτυλίδι με λαμπερό διαμάντι, σύμβολο διαχρονικής κομψότητας."},
            "en": {"title": "Aurora Solitaire Ring", "material": "18K gold, diamond", "description": "A solitaire ring with a brilliant diamond — a symbol of timeless elegance."},
        },
    },
    {
        "slug": "luna-pearl-necklace", "cat": "necklaces", "price": 760.0, "featured": True, "sku": "DC-N-001", "stock": 5,
        "tr": {
            "el": {"title": "Κολιέ Luna", "material": "Ασήμι 925, μαργαριτάρι", "description": "Λεπτό κολιέ με φυσικό μαργαριτάρι που φωτίζει διακριτικά."},
            "en": {"title": "Luna Pearl Necklace", "material": "925 silver, pearl", "description": "A delicate necklace with a natural pearl that glows softly."},
        },
    },
    {
        "slug": "celeste-drop-earrings", "cat": "earrings", "price": 540.0, "featured": True, "sku": "DC-E-001", "stock": 6,
        "tr": {
            "el": {"title": "Σκουλαρίκια Celeste", "material": "Χρυσός 14Κ, ζαφείρι", "description": "Κρεμαστά σκουλαρίκια με βαθύ μπλε ζαφείρι."},
            "en": {"title": "Celeste Drop Earrings", "material": "14K gold, sapphire", "description": "Drop earrings featuring a deep blue sapphire."},
        },
    },
    {
        "slug": "eternity-tennis-bracelet", "cat": "bracelets", "price": 0.0, "on_request": True, "featured": True, "sku": "DC-B-001",
        "tr": {
            "el": {"title": "Βραχιόλι Eternity", "material": "Λευκόχρυσος, διαμάντια", "description": "Βραχιόλι tennis με σειρά διαμαντιών. Τιμή κατόπιν αιτήματος."},
            "en": {"title": "Eternity Tennis Bracelet", "material": "White gold, diamonds", "description": "A tennis bracelet with a row of diamonds. Price on request."},
        },
    },
    {
        "slug": "olive-leaf-band", "cat": "rings", "price": 320.0, "sku": "DC-R-002",
        "stock": 0,  # demonstrates the out-of-stock state (Εξαντλήθηκε)
        "tr": {
            "el": {"title": "Δαχτυλίδι Olive Leaf", "material": "Ασήμι 925", "description": "Βέρα εμπνευσμένη από το φύλλο ελιάς, σύμβολο ειρήνης."},
            "en": {"title": "Olive Leaf Band", "material": "925 silver", "description": "A band inspired by the olive leaf, a symbol of peace."},
        },
    },
    {
        "slug": "helios-chain-necklace", "cat": "necklaces", "price": 410.0, "sku": "DC-N-002", "stock": 12,
        "tr": {
            "el": {"title": "Κολιέ Helios", "material": "Χρυσός 14Κ", "description": "Αλυσίδα με μενταγιόν ήλιου, για καθημερινή λάμψη."},
            "en": {"title": "Helios Chain Necklace", "material": "14K gold", "description": "A chain with a sun pendant for everyday shine."},
        },
    },
    {
        "slug": "thalassa-hoop-earrings", "cat": "earrings", "price": 280.0, "sku": "DC-E-002", "stock": 20,
        "tr": {
            "el": {"title": "Κρίκοι Thalassa", "material": "Χρυσός 14Κ", "description": "Κλασικοί κρίκοι με λεπτή υφή, ελαφρύ βάρος."},
            "en": {"title": "Thalassa Hoop Earrings", "material": "14K gold", "description": "Classic hoops with a fine texture and light weight."},
        },
    },
    {
        "slug": "meandros-cuff", "cat": "bracelets", "price": 690.0, "sku": "DC-B-002", "stock": 4,
        "tr": {
            "el": {"title": "Βραχιόλι Meandros", "material": "Ασήμι 925, επιχρύσωση", "description": "Βραχιόλι με αρχαιοελληνικό μοτίβο μαιάνδρου."},
            "en": {"title": "Meandros Cuff", "material": "925 silver, gold plated", "description": "A cuff featuring the ancient Greek meander motif."},
        },
    },
]


def run() -> None:
    settings.ensure_dirs()
    # Fresh start.
    SQLModel.metadata.drop_all(engine)
    init_db()

    with Session(engine) as session:
        # Categories
        cat_by_slug: dict[str, Category] = {}
        for c in CATEGORIES:
            cat = Category(slug=c["slug"], sort_order=c["order"], is_active=True)
            # No seeded image: tiles fall back to the designed static/img/cat-<slug>.svg.
            session.add(cat)
            session.commit()
            session.refresh(cat)
            for lang, name in c["names"].items():
                session.add(CategoryTranslation(category_id=cat.id, lang=lang, name=name))
            cat_by_slug[c["slug"]] = cat
        session.commit()

        # Products
        for i, p in enumerate(PRODUCTS):
            product = Product(
                slug=p["slug"], sku=p.get("sku"),
                category_id=cat_by_slug[p["cat"]].id,
                price=None if p.get("on_request") else p["price"],
                currency="EUR",
                price_on_request=p.get("on_request", False),
                is_active=True, is_featured=p.get("featured", False),
                stock=p.get("stock", 0), track_stock=True,
                sort_order=i,
            )
            session.add(product)
            session.commit()
            session.refresh(product)

            for lang, fields in p["tr"].items():
                session.add(ProductTranslation(
                    product_id=product.id, lang=lang,
                    title=fields["title"], description=fields["description"],
                    material=fields.get("material"),
                ))

            # Two generated images per product.
            label = p["tr"]["en"]["title"]
            for n in range(2):
                meta = save_image(_placeholder_image(label, i + n))
                session.add(ProductImage(
                    product_id=product.id, filename=meta["filename"], thumb=meta["thumb"],
                    width=meta["width"], height=meta["height"], sort_order=n,
                    alt=label,
                    data=meta["data"], thumb_data=meta["thumb_data"],
                    content_type=meta["content_type"],
                ))
            session.commit()

        # Settings
        site_settings = {
            "site_title": "DreamCatcher",
            "phone": "+30 210 321 0000",
            "email": "hello@dreamcatcher.gr",
            "address": "Λ. Ειρήνης 2, Ηλιούπολη 163 45",
            "whatsapp": "302103210000",
            "viber": "302103210000",
            "instagram": "dreamcatchergreece",
            "map_lat": "37.9779",
            "map_lng": "23.7350",
            "default_lang": "el",
            "show_prices": "1",
            "about_text": (
                "DreamCatcher is an Athens-based atelier crafting fine jewelry by hand.\n\n"
                "Each piece blends Greek heritage with contemporary design — made to be worn "
                "every day and treasured for a lifetime."
            ),
            # Billing (SPEC-BILLING §4)
            "vat_rate": "24",
            "shipping_methods": (
                "courier|Ταχυμεταφορά|Courier|5\n"
                "pickup|Παραλαβή από το κατάστημα|Store pickup|0"
            ),
            "notify_email": "orders@dreamcatcher.gr",
        }
        for key, value in site_settings.items():
            existing = session.get(Setting, key)
            if existing:
                existing.value = value
                session.add(existing)
            else:
                session.add(Setting(key=key, value=value))
        session.commit()

        n_products = len(session.exec(select(Product)).all())
        print(f"Seeded {len(CATEGORIES)} categories, {n_products} products, "
              f"{len(site_settings)} settings.")


def seed_if_empty() -> None:
    """Seed only when there are no products yet (safe on ephemeral hosts).

    Called from the app lifespan when AUTO_SEED is on; never wipes a populated DB.
    """
    with Session(engine) as session:
        existing = session.exec(select(Product).limit(1)).first()
    if existing is None:
        print("AUTO_SEED: empty database -> seeding demo data")
        run()


if __name__ == "__main__":
    run()
