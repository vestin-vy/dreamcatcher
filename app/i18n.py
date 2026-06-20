"""Internationalization: language list, UI string dictionary, fallback helpers.

Strategy (SPEC §5): URL prefix per language `/el|/en`. UI strings live in the `UI`
dict below (el + en). Content strings (product/category names) come from the DB with a
fallback chain el -> en. Babel is used only for price/date formatting.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from babel.numbers import format_currency

LANGS: list[str] = ["el", "en"]
DEFAULT: str = "el"
FALLBACK_CHAIN: list[str] = ["el", "en"]

# Human-readable language names for the switcher (each in its own language).
LANG_NAMES: dict[str, str] = {
    "el": "Ελληνικά",
    "en": "English",
}

# Babel locale per app language (for currency/number formatting).
_BABEL_LOCALE: dict[str, str] = {"el": "el_GR", "en": "en_US"}


# --- UI strings -------------------------------------------------------------
# key -> {lang: text}. Missing key/lang falls back through FALLBACK_CHAIN.
UI: dict[str, dict[str, str]] = {
    # Navigation
    "nav.home": {"el": "Αρχική", "en": "Home"},
    "nav.catalog": {"el": "Κατάλογος", "en": "Catalog"},
    "nav.collections": {"el": "Συλλογές", "en": "Collections"},
    "nav.about": {"el": "Σχετικά", "en": "About"},
    "nav.contact": {"el": "Επικοινωνία", "en": "Contact"},
    "nav.menu": {"el": "Μενού", "en": "Menu"},
    "nav.cart": {"el": "Καλάθι", "en": "Cart"},
    # Hero / home
    "home.hero.tagline": {
        "el": "Χειροποίητα κοσμήματα που λένε τη δική σας ιστορία",
        "en": "Handcrafted jewelry that tells your story",
    },
    "home.hero.cta": {"el": "Δείτε τον κατάλογο", "en": "View the catalog"},
    "home.featured.title": {"el": "Επιλεγμένα", "en": "Featured"},
    "home.featured.subtitle": {
        "el": "Τα πιο αγαπημένα μας κομμάτια",
        "en": "Our most loved pieces",
    },
    "home.categories.title": {"el": "Κατηγορίες", "en": "Categories"},
    "home.about.title": {"el": "Η ιστορία μας", "en": "Our story"},
    "home.about.more": {"el": "Μάθετε περισσότερα", "en": "Learn more"},
    "home.cta.title": {"el": "Ας μιλήσουμε", "en": "Let's talk"},
    "home.cta.subtitle": {
        "el": "Έχετε κάτι στο μυαλό σας; Επικοινωνήστε μαζί μας.",
        "en": "Have something in mind? Get in touch.",
    },
    # Catalog
    "catalog.title": {"el": "Κατάλογος", "en": "Catalog"},
    "catalog.all": {"el": "Όλα", "en": "All"},
    "catalog.sort": {"el": "Ταξινόμηση", "en": "Sort"},
    "catalog.sort.newest": {"el": "Νεότερα", "en": "Newest"},
    "catalog.sort.price_asc": {"el": "Τιμή ↑", "en": "Price ↑"},
    "catalog.sort.price_desc": {"el": "Τιμή ↓", "en": "Price ↓"},
    "catalog.empty": {"el": "Δεν βρέθηκαν προϊόντα.", "en": "No products found."},
    # Product
    "product.price_on_request": {"el": "Κατόπιν αιτήματος", "en": "Price on request"},
    "product.material": {"el": "Υλικό", "en": "Material"},
    "product.sku": {"el": "Κωδικός", "en": "SKU"},
    "product.request": {"el": "Ζητήστε πληροφορίες", "en": "Request / Contact"},
    "product.related": {"el": "Παρόμοια κομμάτια", "en": "Related pieces"},
    "product.gallery": {"el": "Γκαλερί εικόνων", "en": "Image gallery"},
    "product.out_of_stock": {"el": "Εξαντλήθηκε", "en": "Out of stock"},
    # Cart (SPEC-BILLING §2)
    "cart.title": {"el": "Το καλάθι μου", "en": "My cart"},
    "cart.empty": {"el": "Το καλάθι σας είναι άδειο.", "en": "Your cart is empty."},
    "cart.add": {"el": "Στο καλάθι", "en": "Add to cart"},
    "cart.qty": {"el": "Ποσότητα", "en": "Quantity"},
    "cart.update": {"el": "Ενημέρωση", "en": "Update"},
    "cart.remove": {"el": "Αφαίρεση", "en": "Remove"},
    "cart.item": {"el": "Προϊόν", "en": "Item"},
    "cart.price": {"el": "Τιμή", "en": "Price"},
    "cart.line_total": {"el": "Σύνολο", "en": "Total"},
    "cart.subtotal": {"el": "Υποσύνολο", "en": "Subtotal"},
    "cart.vat": {"el": "ΦΠΑ", "en": "VAT"},
    "cart.vat_included": {"el": "συμπεριλαμβανομένου ΦΠΑ", "en": "VAT included"},
    "cart.shipping": {"el": "Μεταφορικά", "en": "Shipping"},
    "cart.total": {"el": "Σύνολο", "en": "Total"},
    "cart.checkout": {"el": "Ολοκλήρωση παραγγελίας", "en": "Checkout"},
    "cart.continue": {"el": "Συνέχεια αγορών", "en": "Continue shopping"},
    # Checkout (SPEC-BILLING §3)
    "checkout.title": {"el": "Ολοκλήρωση παραγγελίας", "en": "Checkout"},
    "checkout.contact": {"el": "Στοιχεία επικοινωνίας", "en": "Contact details"},
    "checkout.name": {"el": "Ονοματεπώνυμο", "en": "Full name"},
    "checkout.email": {"el": "Email", "en": "Email"},
    "checkout.phone": {"el": "Τηλέφωνο", "en": "Phone"},
    "checkout.shipping_address": {"el": "Διεύθυνση αποστολής", "en": "Shipping address"},
    "checkout.address": {"el": "Διεύθυνση", "en": "Address"},
    "checkout.city": {"el": "Πόλη", "en": "City"},
    "checkout.postcode": {"el": "Τ.Κ.", "en": "Postcode"},
    "checkout.country": {"el": "Χώρα", "en": "Country"},
    "checkout.shipping_method": {"el": "Τρόπος αποστολής", "en": "Shipping method"},
    "checkout.pay": {"el": "Πληρωμή", "en": "Pay now"},
    "checkout.summary": {"el": "Σύνοψη παραγγελίας", "en": "Order summary"},
    "checkout.success.title": {"el": "Ευχαριστούμε!", "en": "Thank you!"},
    "checkout.success.body": {
        "el": "Η παραγγελία σας ελήφθη. Θα λάβετε επιβεβαίωση μόλις ολοκληρωθεί η πληρωμή.",
        "en": "Your order has been received. You'll get a confirmation once payment is complete.",
    },
    "checkout.cancel.title": {"el": "Η πληρωμή ακυρώθηκε", "en": "Payment cancelled"},
    "checkout.cancel.body": {
        "el": "Η πληρωμή ακυρώθηκε. Το καλάθι σας διατηρήθηκε.",
        "en": "The payment was cancelled. Your cart has been kept.",
    },
    "checkout.demo.title": {"el": "Δοκιμαστική πληρωμή", "en": "Demo payment"},
    "checkout.demo.body": {
        "el": "Περιβάλλον επίδειξης — δεν χρεώνεται κανένα ποσό.",
        "en": "Demo environment — no real charge is made.",
    },
    "checkout.demo.pay": {"el": "Προσομοίωση επιτυχούς πληρωμής", "en": "Simulate successful payment"},
    "checkout.order_number": {"el": "Αριθμός παραγγελίας", "en": "Order number"},
    # Order statuses (SPEC-BILLING §4)
    "order.status.pending": {"el": "Σε αναμονή", "en": "Pending"},
    "order.status.paid": {"el": "Πληρωμένη", "en": "Paid"},
    "order.status.shipped": {"el": "Απεστάλη", "en": "Shipped"},
    "order.status.cancelled": {"el": "Ακυρώθηκε", "en": "Cancelled"},
    # Contact
    "contact.title": {"el": "Επικοινωνία", "en": "Contact"},
    "contact.address": {"el": "Διεύθυνση", "en": "Address"},
    "contact.phone": {"el": "Τηλέφωνο", "en": "Phone"},
    "contact.email": {"el": "Email", "en": "Email"},
    "contact.form.title": {"el": "Στείλτε μήνυμα", "en": "Send a message"},
    "contact.form.name": {"el": "Όνομα", "en": "Name"},
    "contact.form.contact": {"el": "Email ή τηλέφωνο", "en": "Email or phone"},
    "contact.form.message": {"el": "Μήνυμα", "en": "Message"},
    "contact.form.send": {"el": "Αποστολή", "en": "Send"},
    "contact.form.whatsapp": {"el": "Γράψτε στο WhatsApp", "en": "Message on WhatsApp"},
    "contact.follow": {"el": "Ακολουθήστε μας", "en": "Follow us"},
    # Collections
    "collections.title": {"el": "Συλλογές", "en": "Collections"},
    "collections.featured": {"el": "Δημοφιλή", "en": "Highlights"},
    "collections.by_category": {"el": "Ανά κατηγορία", "en": "By category"},
    # About
    "about.title": {"el": "Σχετικά με εμάς", "en": "About us"},
    # Legal / footer pages (SPEC-BILLING §5)
    "legal.terms": {"el": "Όροι πώλησης", "en": "Terms of sale"},
    "legal.returns": {"el": "Πολιτική επιστροφών", "en": "Returns policy"},
    "legal.privacy": {"el": "Πολιτική απορρήτου", "en": "Privacy policy"},
    "legal.legal": {"el": "Νομικά", "en": "Legal"},
    # Cookie banner (SPEC-BILLING §5)
    "cookie.text": {
        "el": "Χρησιμοποιούμε απαραίτητα cookies για τη λειτουργία του καλαθιού και της παραγγελίας.",
        "en": "We use essential cookies to make the cart and checkout work.",
    },
    "cookie.accept": {"el": "Εντάξει", "en": "Got it"},
    # Footer
    "footer.tagline": {
        "el": "Χειροποίητα κοσμήματα, φτιαγμένα με μεράκι.",
        "en": "Handcrafted jewelry, made with care.",
    },
    "footer.nav": {"el": "Πλοήγηση", "en": "Navigation"},
    "footer.contact": {"el": "Επικοινωνία", "en": "Contact"},
    "footer.rights": {"el": "Με επιφύλαξη παντός δικαιώματος.", "en": "All rights reserved."},
    # Admin
    "admin.login": {"el": "Σύνδεση", "en": "Login"},
    "admin.logout": {"el": "Αποσύνδεση", "en": "Logout"},
}


def t(lang: str, key: str) -> str:
    """Translate a UI key. Falls back el -> en, then returns the key itself."""
    entry = UI.get(key)
    if not entry:
        return key
    if lang in entry:
        return entry[lang]
    for fb in FALLBACK_CHAIN:
        if fb in entry:
            return entry[fb]
    return key


def make_translator(lang: str):
    """Return a single-arg translator bound to `lang` (for Jinja: `_('nav.home')`)."""
    return lambda key: t(lang, key)


def pick_translation(translations: Iterable, lang: str):
    """Pick the translation row for `lang` from a list, falling back el -> en -> first.

    `translations` is an iterable of objects with a `.lang` attribute.
    Returns the matching object or None if the iterable is empty.
    """
    rows = list(translations)
    if not rows:
        return None
    by_lang = {row.lang: row for row in rows}
    if lang in by_lang:
        return by_lang[lang]
    for fb in FALLBACK_CHAIN:
        if fb in by_lang:
            return by_lang[fb]
    return rows[0]


def format_price(value: Decimal | float | None, currency: str, lang: str) -> str:
    """Format a price with Babel for the given language locale."""
    if value is None:
        return ""
    locale = _BABEL_LOCALE.get(lang, "en_US")
    return format_currency(Decimal(str(value)), currency or "EUR", locale=locale)


def hreflang_alternates(path_no_lang: str) -> list[dict[str, str]]:
    """Build hreflang alternates for a path that already excludes the lang prefix.

    `path_no_lang` should start with '/' (e.g. '/catalog' or '' for home).
    """
    out = []
    for lang in LANGS:
        href = f"/{lang}{path_no_lang}" if path_no_lang else f"/{lang}/"
        out.append({"lang": lang, "href": href})
    return out
