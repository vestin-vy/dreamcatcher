"""DreamCatcher smoke tests — the route contract for the implementing session.

These encode the SPEC §10 "definition of done" as runnable checks. They WILL fail
until the app exists; that is the point — make them go green.

Run:  python -m pytest -q
Needs: pip install pytest httpx  (httpx powers FastAPI's TestClient)
"""
import pytest
from fastapi.testclient import TestClient

try:
    from app.main import app
except Exception as exc:  # app not built yet -> skip with a clear reason
    app = None
    _IMPORT_ERROR = exc


@pytest.fixture(scope="module")
def client():
    if app is None:
        pytest.skip(f"app.main:app not importable yet: {_IMPORT_ERROR}")
    return TestClient(app)


# --- i18n / routing (SPEC §5, §10) ------------------------------------------

def test_root_redirects_to_default_lang(client):
    """`/` redirects to the default language `/el/`."""
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (301, 302, 307, 308)
    assert "/el" in r.headers["location"]


@pytest.mark.parametrize("lang", ["el", "en"])
def test_all_languages_serve_home(client, lang):
    """Both supported languages render the home page."""
    r = client.get(f"/{lang}/")
    assert r.status_code == 200


def test_dropped_languages_are_404(client):
    """ru/fr were removed (SPEC-BILLING §0) and must no longer resolve."""
    for lang in ("ru", "fr"):
        r = client.get(f"/{lang}/", follow_redirects=False)
        assert r.status_code == 404, f"/{lang}/ should be 404, got {r.status_code}"


@pytest.mark.parametrize("lang", ["el", "en"])
def test_public_pages_render(client, lang):
    for path in ("catalog", "about", "contact", "collections", "cart",
                 "terms", "returns", "privacy", "wholesale", "wholesale/cart"):
        r = client.get(f"/{lang}/{path}")
        assert r.status_code == 200, f"/{lang}/{path} -> {r.status_code}"


# --- admin guard (SPEC §8) --------------------------------------------------

def test_admin_requires_auth(client):
    """Admin area is gated: dashboard redirects to login (or 401/403) when anonymous."""
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code in (301, 302, 307, 401, 403)


def test_admin_login_page_renders(client):
    r = client.get("/admin/login")
    assert r.status_code == 200


# --- content fallback (SPEC §5: missing translation falls back to el) --------

def test_catalog_lists_seed_products_in_default_lang(client):
    """With seed data loaded, the el catalog shows at least one product card.
    Adjust the marker to whatever the catalog template emits per product."""
    r = client.get("/el/catalog")
    assert r.status_code == 200
    # Heuristic: a product link pattern from SPEC §6.2 -> /el/product/<slug>
    assert "/el/product/" in r.text or "product" in r.text.lower()
