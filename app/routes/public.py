"""Public site routes (SPEC §6), all under the `/{lang}` prefix."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session, select

from app.deps import get_lang, get_session, get_site_settings
from app.i18n import pick_translation
from app.models import Category, Product
from app.templating import render

router = APIRouter()


# --- view-model helpers -----------------------------------------------------

def _category_name(category: Category | None, lang: str) -> str | None:
    if not category:
        return None
    tr = pick_translation(category.translations, lang)
    return tr.name if tr else category.slug


def product_view(product: Product, lang: str) -> dict:
    """Flatten a Product into a template-friendly dict with the resolved lang."""
    tr = pick_translation(product.translations, lang)
    images = product.images
    # Images are served from the DB via /media/{id} (survive ephemeral disks).
    main_image = f"/media/{images[0].id}" if images else None
    return {
        "id": product.id,
        "slug": product.slug,
        "sku": product.sku,
        "title": tr.title if tr else product.slug,
        "description": tr.description if tr else "",
        "material": tr.material if tr else None,
        "price": product.price,
        "currency": product.currency,
        "price_on_request": product.price_on_request,
        "is_featured": product.is_featured,
        "stock": product.stock,
        "track_stock": product.track_stock,
        "in_stock": (not product.track_stock) or product.stock > 0,
        "category_id": product.category_id,
        "category_name": _category_name(product.category, lang),
        "image": main_image,
        "images": [
            {"filename": f"/media/{im.id}", "thumb": f"/media/{im.id}/thumb",
             "alt": im.alt or (tr.title if tr else "")}
            for im in images
        ],
    }


def active_categories(session: Session, lang: str) -> list[dict]:
    cats = session.exec(
        select(Category).where(Category.is_active == True).order_by(Category.sort_order)  # noqa: E712
    ).all()
    return [
        {"id": c.id, "slug": c.slug, "name": _category_name(c, lang),
         "image": c.image, "thumb": c.thumb}
        for c in cats
    ]


# --- routes -----------------------------------------------------------------

@router.get("/{lang}/", name="home")
def home(
    request: Request,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
    site: dict = Depends(get_site_settings),
):
    try:
        featured_limit = int(site.get("featured_limit") or 6)
    except (TypeError, ValueError):
        featured_limit = 6
    featured_limit = max(1, min(24, featured_limit))
    featured = session.exec(
        select(Product)
        .where(Product.is_active == True, Product.is_featured == True)  # noqa: E712
        .order_by(Product.sort_order, Product.created_at.desc())
        .limit(featured_limit)
    ).all()
    cats = active_categories(session, lang)
    return render(
        request, "public/home.html", lang=lang, site=site,
        featured=[product_view(p, lang) for p in featured],
        categories=cats,
        show_prices=site.get("show_prices") == "1",
    )


@router.get("/{lang}/catalog", name="catalog")
def catalog(
    request: Request,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
    site: dict = Depends(get_site_settings),
    category: str | None = None,
    sort: str = "newest",
):
    query = select(Product).where(Product.is_active == True)  # noqa: E712
    active_cat = None
    if category:
        active_cat = session.exec(select(Category).where(Category.slug == category)).first()
        if active_cat:
            query = query.where(Product.category_id == active_cat.id)

    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    else:
        sort = "newest"
        query = query.order_by(Product.created_at.desc(), Product.sort_order)

    products = session.exec(query).all()
    return render(
        request, "public/catalog.html", lang=lang, site=site,
        products=[product_view(p, lang) for p in products],
        categories=active_categories(session, lang),
        active_category=category, sort=sort,
        show_prices=site.get("show_prices") == "1",
    )


@router.get("/{lang}/product/{slug}", name="product")
def product_detail(
    slug: str,
    request: Request,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
    site: dict = Depends(get_site_settings),
):
    product = session.exec(
        select(Product).where(Product.slug == slug, Product.is_active == True)  # noqa: E712
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    related_q = (
        select(Product)
        .where(
            Product.is_active == True,  # noqa: E712
            Product.category_id == product.category_id,
            Product.id != product.id,
        )
        .order_by(Product.created_at.desc())
        .limit(4)
    )
    related = session.exec(related_q).all() if product.category_id else []
    return render(
        request, "public/product.html", lang=lang, site=site,
        product=product_view(product, lang),
        related=[product_view(p, lang) for p in related],
        show_prices=site.get("show_prices") == "1",
    )


@router.get("/{lang}/about", name="about")
def about(
    request: Request,
    lang: str = Depends(get_lang),
    site: dict = Depends(get_site_settings),
):
    return render(request, "public/about.html", lang=lang, site=site)


@router.get("/{lang}/contact", name="contact")
def contact(
    request: Request,
    lang: str = Depends(get_lang),
    site: dict = Depends(get_site_settings),
):
    return render(request, "public/contact.html", lang=lang, site=site)


@router.get("/{lang}/collections", name="collections")
def collections(
    request: Request,
    lang: str = Depends(get_lang),
    session: Session = Depends(get_session),
    site: dict = Depends(get_site_settings),
):
    featured = session.exec(
        select(Product)
        .where(Product.is_active == True, Product.is_featured == True)  # noqa: E712
        .order_by(Product.sort_order, Product.created_at.desc())
    ).all()
    cats = active_categories(session, lang)
    # A small sample of products per category for the "by category" sections.
    by_category = []
    for c in cats:
        items = session.exec(
            select(Product)
            .where(Product.is_active == True, Product.category_id == c["id"])  # noqa: E712
            .order_by(Product.created_at.desc())
            .limit(4)
        ).all()
        if items:
            by_category.append({"category": c, "products": [product_view(p, lang) for p in items]})
    return render(
        request, "public/collections.html", lang=lang, site=site,
        featured=[product_view(p, lang) for p in featured],
        by_category=by_category,
        show_prices=site.get("show_prices") == "1",
    )


# --- Legal pages (SPEC-BILLING §5) ------------------------------------------

@router.get("/{lang}/terms", name="terms")
def terms(request: Request, lang: str = Depends(get_lang), site: dict = Depends(get_site_settings)):
    return render(request, "public/legal.html", lang=lang, site=site, kind="terms")


@router.get("/{lang}/returns", name="returns")
def returns(request: Request, lang: str = Depends(get_lang), site: dict = Depends(get_site_settings)):
    return render(request, "public/legal.html", lang=lang, site=site, kind="returns")


@router.get("/{lang}/privacy", name="privacy")
def privacy(request: Request, lang: str = Depends(get_lang), site: dict = Depends(get_site_settings)):
    return render(request, "public/legal.html", lang=lang, site=site, kind="privacy")


# --- SEO files (no language prefix) -----------------------------------------

@router.get("/robots.txt", include_in_schema=False)
def robots() -> Response:
    body = "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n"
    return Response(content=body, media_type="text/plain")


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(session: Session = Depends(get_session)) -> Response:
    from app.i18n import LANGS

    urls: list[str] = []
    static_paths = ["", "catalog", "collections", "about", "contact"]
    for lang in LANGS:
        for p in static_paths:
            loc = f"/{lang}/{p}" if p else f"/{lang}/"
            urls.append(loc)
    products = session.exec(
        select(Product.slug).where(Product.is_active == True)  # noqa: E712
    ).all()
    for lang in LANGS:
        for slug in products:
            urls.append(f"/{lang}/product/{slug}")

    items = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{items}</urlset>"
    )
    return Response(content=xml, media_type="application/xml")
