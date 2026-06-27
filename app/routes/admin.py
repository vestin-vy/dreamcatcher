"""Admin area (SPEC §8): login, dashboard, product/category/settings CRUD, uploads."""
from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlmodel import Session, select
from starlette.datastructures import UploadFile  # form() yields these (not fastapi's subclass)

from app import marketing
from app import orders as orders_mod
from app.db import get_session
from app.deps import DEFAULT_SETTINGS, get_site_settings, is_authenticated
from app.i18n import LANGS, pick_translation
from app.images import InvalidImageError, delete_image_files, save_image
from app.models import (
    ORDER_STATUSES,
    Category,
    CategoryTranslation,
    Order,
    OrderItem,
    Product,
    ProductImage,
    ProductTranslation,
    Setting,
)
from app.security import (
    check_admin_credentials,
    get_csrf_token,
    login_admin,
    logout_admin,
    record_attempt,
    reset_attempts,
    too_many_attempts,
    verify_csrf,
)
from app.templating import render

router = APIRouter(prefix="/admin")


# --- helpers ----------------------------------------------------------------

def ensure_admin(request: Request) -> RedirectResponse | None:
    """Return a redirect to login if not authenticated, else None."""
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    return None


def flash(request: Request, message: str, level: str = "success") -> None:
    request.session.setdefault("_flash", []).append({"message": message, "level": level})


def pop_flashes(request: Request) -> list[dict]:
    flashes = request.session.pop("_flash", [])
    return flashes


def admin_render(request: Request, template: str, **ctx):
    """Render an admin page with csrf token + flashes injected."""
    return render(
        request, template,
        csrf_token=get_csrf_token(request),
        flashes=pop_flashes(request),
        **ctx,
    )


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[-\s]+", "-", value)
    return value or "item"


def unique_slug(session: Session, base: str, exclude_id: int | None = None) -> str:
    base = slugify(base)
    slug = base
    i = 2
    while True:
        existing = session.exec(select(Product).where(Product.slug == slug)).first()
        if not existing or existing.id == exclude_id:
            return slug
        slug = f"{base}-{i}"
        i += 1


def bad_csrf_redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


# --- auth -------------------------------------------------------------------

@router.get("/login")
def login_form(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/admin", status_code=302)
    return admin_render(request, "admin/login.html", error=None)


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(""),
):
    if not verify_csrf(request, csrf_token):
        return admin_render(request, "admin/login.html", error="Invalid session, please retry.")
    if too_many_attempts(request):
        return admin_render(request, "admin/login.html", error="Too many attempts. Try again later.")
    if check_admin_credentials(username, password):
        reset_attempts(request)
        login_admin(request)
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    record_attempt(request)
    return admin_render(request, "admin/login.html", error="Invalid credentials.")


@router.post("/logout")
def logout(request: Request):
    logout_admin(request)
    return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)


# --- dashboard --------------------------------------------------------------

@router.get("")
@router.get("/")
def dashboard(request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    total = len(session.exec(select(Product)).all())
    active = len(session.exec(select(Product).where(Product.is_active == True)).all())  # noqa: E712
    featured = len(session.exec(select(Product).where(Product.is_featured == True)).all())  # noqa: E712
    cats = session.exec(select(Category)).all()
    cat_counts = []
    for c in cats:
        n = len(session.exec(select(Product).where(Product.category_id == c.id)).all())
        tr = pick_translation(c.translations, "en")
        cat_counts.append({"name": tr.name if tr else c.slug, "count": n})
    orders_total = len(session.exec(select(Order)).all())
    orders_pending = len(session.exec(select(Order).where(Order.status == "pending")).all())
    orders_paid = len(session.exec(select(Order).where(Order.status == "paid")).all())
    return admin_render(
        request, "admin/dashboard.html",
        stats={"total": total, "active": active, "featured": featured,
               "categories": len(cats),
               "orders": orders_total, "orders_pending": orders_pending,
               "orders_paid": orders_paid},
        cat_counts=cat_counts,
    )


# --- products ---------------------------------------------------------------

@router.get("/products")
def product_list(request: Request, session: Session = Depends(get_session), q: str = ""):
    if r := ensure_admin(request):
        return r
    products = session.exec(select(Product).order_by(Product.sort_order, Product.id)).all()
    rows = []
    for p in products:
        tr = pick_translation(p.translations, "en")
        if q and q.lower() not in (tr.title.lower() if tr else p.slug):
            continue
        rows.append({
            "id": p.id, "slug": p.slug,
            "title": tr.title if tr else p.slug,
            "price": p.price, "currency": p.currency,
            "price_on_request": p.price_on_request,
            "stock": p.stock,
            "is_active": p.is_active, "is_featured": p.is_featured,
            "image": f"/media/{p.images[0].id}/thumb" if p.images else None,
        })
    return admin_render(request, "admin/product_list.html", products=rows, q=q)


def _all_categories(session: Session) -> list[dict]:
    cats = session.exec(select(Category).order_by(Category.sort_order)).all()
    out = []
    for c in cats:
        tr = pick_translation(c.translations, "en")
        out.append({"id": c.id, "name": tr.name if tr else c.slug})
    return out


def _product_form_ctx(session: Session, product: Product | None) -> dict:
    translations = {}
    if product:
        for tr in product.translations:
            translations[tr.lang] = {"title": tr.title, "description": tr.description,
                                     "material": tr.material or ""}
    return {
        "product": product,
        "translations": translations,
        "categories": _all_categories(session),
        "langs": LANGS,
        "images": product.images if product else [],
    }


@router.get("/products/new")
def product_new(request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    return admin_render(request, "admin/product_form.html", mode="new",
                        **_product_form_ctx(session, None))


@router.get("/products/{product_id}/edit")
def product_edit(product_id: int, request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    product = session.get(Product, product_id)
    if not product:
        flash(request, "Product not found.", "error")
        return RedirectResponse(url="/admin/products", status_code=303)
    return admin_render(request, "admin/product_form.html", mode="edit",
                        **_product_form_ctx(session, product))


def _validate_product_form(form) -> str | None:
    """Server-side backstop for the admin product form (HTML `required` is bypassable)."""
    if not (form.get("title_el") or "").strip():
        return "Greek title is required."
    if not (form.get("category_id") or "").strip():
        return "Category is required."
    if not (form.get("currency") or "").strip():
        return "Currency is required."
    if form.get("price_on_request") != "on" and not (form.get("price") or "").strip():
        return "Price is required unless 'price on request' is set."
    return None


def _save_product_from_form(session: Session, request: Request, form, product: Product) -> None:
    product.sku = (form.get("sku") or "").strip() or None
    cat = form.get("category_id")
    product.category_id = int(cat) if cat else None
    price_raw = (form.get("price") or "").strip()
    product.price = float(price_raw.replace(",", ".")) if price_raw else None
    product.currency = (form.get("currency") or "EUR").strip() or "EUR"
    product.price_on_request = form.get("price_on_request") == "on"
    product.is_active = form.get("is_active") == "on"
    product.is_featured = form.get("is_featured") == "on"
    # Stock is always tracked and required (addendum). Blank/invalid -> 0.
    stock_raw = (form.get("stock") or "0").strip()
    product.stock = max(0, int(stock_raw)) if stock_raw.lstrip("-").isdigit() else 0
    product.track_stock = True
    order_raw = (form.get("sort_order") or "0").strip()
    product.sort_order = int(order_raw) if order_raw.lstrip("-").isdigit() else 0

    # Translations per language.
    existing = {tr.lang: tr for tr in product.translations}
    for lang in LANGS:
        title = (form.get(f"title_{lang}") or "").strip()
        desc = (form.get(f"description_{lang}") or "").strip()
        material = (form.get(f"material_{lang}") or "").strip() or None
        if lang in existing:
            tr = existing[lang]
            tr.title, tr.description, tr.material = title, desc, material
            session.add(tr)
        elif title or desc or material:
            session.add(ProductTranslation(
                product_id=product.id, lang=lang,
                title=title or product.slug, description=desc, material=material,
            ))


@router.post("/products/new")
async def product_create(request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect("/admin/products/new")
    if err := _validate_product_form(form):
        flash(request, err, "error")
        return RedirectResponse(url="/admin/products/new", status_code=303)
    title_el = (form.get("title_el") or "").strip()
    base = title_el or (form.get("title_en") or "").strip() or "item"
    product = Product(slug=unique_slug(session, base))
    session.add(product)
    session.commit()
    session.refresh(product)
    _save_product_from_form(session, request, form, product)
    session.commit()
    flash(request, "Product created.")
    return RedirectResponse(url=f"/admin/products/{product.id}/edit", status_code=303)


@router.post("/products/{product_id}/edit")
async def product_update(product_id: int, request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    product = session.get(Product, product_id)
    if not product:
        flash(request, "Product not found.", "error")
        return RedirectResponse(url="/admin/products", status_code=303)
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect(f"/admin/products/{product_id}/edit")
    if err := _validate_product_form(form):
        flash(request, err, "error")
        return RedirectResponse(url=f"/admin/products/{product_id}/edit", status_code=303)
    _save_product_from_form(session, request, form, product)
    from datetime import datetime, timezone
    product.updated_at = datetime.now(timezone.utc)
    session.add(product)
    session.commit()
    flash(request, "Product saved.")
    return RedirectResponse(url=f"/admin/products/{product_id}/edit", status_code=303)


@router.post("/products/{product_id}/delete")
async def product_delete(product_id: int, request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect("/admin/products")
    product = session.get(Product, product_id)
    if product:
        # Detach historical order items (FK is nullable; snapshots preserve the record).
        # Without this the product.id FK on orderitem blocks the delete -> IntegrityError -> 500.
        for item in session.exec(select(OrderItem).where(OrderItem.product_id == product.id)).all():
            item.product_id = None
            session.add(item)
        for im in product.images:  # hard delete: remove files too (SPEC §4 default)
            delete_image_files(im.filename, im.thumb)
        session.delete(product)
        session.commit()
        flash(request, "Product deleted.")
    return RedirectResponse(url="/admin/products", status_code=303)


@router.post("/products/{product_id}/toggle")
async def product_toggle(product_id: int, request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect("/admin/products")
    product = session.get(Product, product_id)
    if product:
        field = form.get("field")
        if field == "is_active":
            product.is_active = not product.is_active
        elif field == "is_featured":
            product.is_featured = not product.is_featured
        session.add(product)
        session.commit()
    return RedirectResponse(url="/admin/products", status_code=303)


# --- product images ---------------------------------------------------------

@router.post("/products/{product_id}/images")
async def upload_images(product_id: int, request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    product = session.get(Product, product_id)
    if not product:
        flash(request, "Product not found.", "error")
        return RedirectResponse(url="/admin/products", status_code=303)
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect(f"/admin/products/{product_id}/edit")
    files = form.getlist("images")
    next_order = max([im.sort_order for im in product.images], default=-1) + 1
    saved = 0
    rejected: list[str] = []
    for f in files:
        if not isinstance(f, UploadFile) or not f.filename:
            continue
        data = await f.read()
        if not data:
            rejected.append(f"{f.filename}: empty file")
            continue
        try:
            meta = save_image(data)
        except InvalidImageError as exc:
            rejected.append(f"{f.filename}: {exc}")
            continue
        session.add(ProductImage(
            product_id=product.id, filename=meta["filename"], thumb=meta["thumb"],
            width=meta["width"], height=meta["height"], sort_order=next_order,
            alt=(form.get("alt") or None),
            data=meta["data"], thumb_data=meta["thumb_data"],
            content_type=meta["content_type"],
        ))
        next_order += 1
        saved += 1
    session.commit()
    if saved:
        flash(request, f"{saved} image(s) uploaded.")
    if rejected:
        flash(request, "Rejected — " + "; ".join(rejected), "error")
    return RedirectResponse(url=f"/admin/products/{product_id}/edit", status_code=303)


@router.post("/images/{image_id}/delete")
async def delete_image(image_id: int, request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    form = await request.form()
    img = session.get(ProductImage, image_id)
    pid = img.product_id if img else None
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect(f"/admin/products/{pid}/edit" if pid else "/admin/products")
    if img:
        delete_image_files(img.filename, img.thumb)
        session.delete(img)
        session.commit()
        flash(request, "Image deleted.")
    return RedirectResponse(url=f"/admin/products/{pid}/edit" if pid else "/admin/products", status_code=303)


@router.post("/images/{image_id}/main")
async def set_main_image(image_id: int, request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    form = await request.form()
    img = session.get(ProductImage, image_id)
    pid = img.product_id if img else None
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect(f"/admin/products/{pid}/edit" if pid else "/admin/products")
    if img:
        siblings = session.exec(
            select(ProductImage).where(ProductImage.product_id == img.product_id)
            .order_by(ProductImage.sort_order)
        ).all()
        img.sort_order = -1
        session.add(img)
        # Renormalize order so chosen image is first (0).
        order = 0
        for s in [img] + [s for s in siblings if s.id != img.id]:
            s.sort_order = order
            session.add(s)
            order += 1
        session.commit()
        flash(request, "Main image updated.")
    return RedirectResponse(url=f"/admin/products/{pid}/edit" if pid else "/admin/products", status_code=303)


# --- categories -------------------------------------------------------------

@router.get("/categories")
def category_list(request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    cats = session.exec(select(Category).order_by(Category.sort_order)).all()
    rows = []
    for c in cats:
        names = {tr.lang: tr.name for tr in c.translations}
        pcount = len(session.exec(select(Product).where(Product.category_id == c.id)).all())
        has_img = bool(c.image_data or c.image)
        rows.append({"id": c.id, "slug": c.slug, "is_active": c.is_active,
                     "sort_order": c.sort_order, "names": names,
                     "image": f"/media/category/{c.id}" if has_img else None,
                     "thumb": f"/media/category/{c.id}/thumb" if has_img else None,
                     "products": pcount})
    return admin_render(request, "admin/categories.html", categories=rows, langs=LANGS)


async def _save_category_image(request: Request, form, cat: Category) -> None:
    """Apply image changes from a category form: remove and/or replace."""
    if form.get("remove_image") == "on" and (cat.image or cat.image_data):
        delete_image_files(cat.image, cat.thumb)
        cat.image = cat.thumb = None
        cat.image_data = cat.thumb_data = cat.image_content_type = None
    file = form.get("image")
    if isinstance(file, UploadFile) and file.filename:
        data = await file.read()
        if data:
            try:
                meta = save_image(data)
            except InvalidImageError as exc:
                flash(request, f"Category image rejected — {exc}.", "error")
                return
            if cat.image:
                delete_image_files(cat.image, cat.thumb)
            cat.image, cat.thumb = meta["filename"], meta["thumb"]
            # DB-backed bytes are the source of truth (survive ephemeral disks).
            cat.image_data = meta["data"]
            cat.thumb_data = meta["thumb_data"]
            cat.image_content_type = meta["content_type"]


@router.post("/categories/new")
async def category_create(request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect("/admin/categories")
    slug = slugify(form.get("slug") or form.get("name_en") or form.get("name_el") or "category")
    cat = Category(slug=slug, sort_order=int(form.get("sort_order") or 0),
                   is_active=form.get("is_active") == "on")
    session.add(cat)
    session.commit()
    session.refresh(cat)
    for lang in LANGS:
        name = (form.get(f"name_{lang}") or "").strip()
        if name:
            session.add(CategoryTranslation(category_id=cat.id, lang=lang, name=name))
    await _save_category_image(request, form, cat)
    session.add(cat)
    session.commit()
    flash(request, "Category created.")
    return RedirectResponse(url="/admin/categories", status_code=303)


@router.post("/categories/{category_id}/edit")
async def category_update(category_id: int, request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    cat = session.get(Category, category_id)
    if not cat:
        return RedirectResponse(url="/admin/categories", status_code=303)
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect("/admin/categories")
    cat.sort_order = int(form.get("sort_order") or 0)
    cat.is_active = form.get("is_active") == "on"
    existing = {tr.lang: tr for tr in cat.translations}
    for lang in LANGS:
        name = (form.get(f"name_{lang}") or "").strip()
        if lang in existing:
            existing[lang].name = name
            session.add(existing[lang])
        elif name:
            session.add(CategoryTranslation(category_id=cat.id, lang=lang, name=name))
    await _save_category_image(request, form, cat)
    session.add(cat)
    session.commit()
    flash(request, "Category saved.")
    return RedirectResponse(url="/admin/categories", status_code=303)


@router.post("/categories/{category_id}/delete")
async def category_delete(category_id: int, request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect("/admin/categories")
    cat = session.get(Category, category_id)
    if cat:
        # Block deletion while products are still assigned — the admin must move
        # them to another category first (avoids silently orphaning products).
        n = len(session.exec(select(Product).where(Product.category_id == cat.id)).all())
        if n:
            flash(request,
                  f"Can’t delete this category — {n} product(s) are still in it. "
                  "Move them to another category first.", "error")
            return RedirectResponse(url="/admin/categories", status_code=303)
        if cat.image:
            delete_image_files(cat.image, cat.thumb)
        session.delete(cat)
        session.commit()
        flash(request, "Category deleted.")
    return RedirectResponse(url="/admin/categories", status_code=303)


# --- settings ---------------------------------------------------------------

@router.get("/settings")
def settings_form(request: Request, site: dict = Depends(get_site_settings)):
    if r := ensure_admin(request):
        return r
    return admin_render(request, "admin/settings.html", site=site,
                        keys=list(DEFAULT_SETTINGS.keys()))


@router.post("/settings")
async def settings_save(request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect("/admin/settings")
    checkbox_keys = {"show_prices", "carousel_autoscroll", "carousel_arrows"}
    for key in DEFAULT_SETTINGS:
        if key in checkbox_keys:
            value = "1" if form.get(key) else "0"
        elif key in form:
            value = (form.get(key) or "").strip()
        else:
            continue
        row = session.get(Setting, key)
        if row:
            row.value = value
        else:
            row = Setting(key=key, value=value)
        session.add(row)
    session.commit()
    flash(request, "Settings saved.")
    return RedirectResponse(url="/admin/settings", status_code=303)


# --- orders (SPEC-BILLING §4) -----------------------------------------------

@router.get("/orders")
def order_list(request: Request, session: Session = Depends(get_session), status: str = ""):
    if r := ensure_admin(request):
        return r
    query = select(Order).order_by(Order.created_at.desc())
    if status in ORDER_STATUSES:
        query = query.where(Order.status == status)
    orders = session.exec(query).all()
    rows = [{
        "id": o.id, "number": o.number, "status": o.status,
        "is_wholesale": o.is_wholesale, "is_anonymized": o.anonymized_at is not None,
        "customer_name": o.customer_name, "customer_email": o.customer_email,
        "total": o.total, "currency": o.currency, "created_at": o.created_at,
        "items": len(o.items),
    } for o in orders]
    return admin_render(
        request, "admin/orders.html",
        orders=rows, statuses=ORDER_STATUSES, active_status=status,
    )


@router.get("/orders/{order_id}")
def order_detail(order_id: int, request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    order = session.get(Order, order_id)
    if not order:
        flash(request, "Order not found.", "error")
        return RedirectResponse(url="/admin/orders", status_code=303)
    return admin_render(
        request, "admin/order_detail.html", order=order, statuses=ORDER_STATUSES,
    )


# Allowed manual status transitions from the admin (payment -> paid is automatic via webhook).
_ALLOWED_TRANSITIONS = {
    "pending": {"cancelled"},
    "paid": {"shipped", "cancelled"},
    "shipped": {"cancelled"},
    "cancelled": set(),
    "wholesale": {"shipped", "cancelled"},  # B2B request -> fulfilled or cancelled
}


@router.post("/orders/{order_id}/status")
async def order_set_status(order_id: int, request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect(f"/admin/orders/{order_id}")
    order = session.get(Order, order_id)
    if not order:
        flash(request, "Order not found.", "error")
        return RedirectResponse(url="/admin/orders", status_code=303)
    new_status = (form.get("status") or "").strip()
    if new_status in _ALLOWED_TRANSITIONS.get(order.status, set()):
        from datetime import datetime, timezone
        order.status = new_status
        order.updated_at = datetime.now(timezone.utc)
        session.add(order)
        session.commit()
        flash(request, f"Order {order.number} → {new_status}.")
    else:
        flash(request, f"Cannot change {order.status} → {new_status}.", "error")
    return RedirectResponse(url=f"/admin/orders/{order_id}", status_code=303)


@router.post("/orders/{order_id}/anonymize")
async def order_anonymize(order_id: int, request: Request, session: Session = Depends(get_session)):
    """Erasure-on-request: irreversibly anonymize one order's PII (financials kept)."""
    if r := ensure_admin(request):
        return r
    form = await request.form()
    if not verify_csrf(request, form.get("csrf_token")):
        return bad_csrf_redirect(f"/admin/orders/{order_id}")
    order = session.get(Order, order_id)
    if not order:
        flash(request, "Order not found.", "error")
        return RedirectResponse(url="/admin/orders", status_code=303)
    if orders_mod.anonymize_order(session, order):
        flash(request, f"Order {order.number} PII anonymized (financial record kept).")
    else:
        flash(request, f"Order {order.number} was already anonymized.", "error")
    return RedirectResponse(url=f"/admin/orders/{order_id}", status_code=303)


# --- marketing list (Task 3) -------------------------------------------------

@router.get("/marketing")
def marketing_list(request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    rows = [{
        "email": c.email, "consented_at": c.consented_at, "lang": c.lang, "source": c.source,
    } for c in marketing.subscribed(session)]
    return admin_render(request, "admin/marketing.html", subscribers=rows)


@router.get("/marketing/export.csv")
def marketing_csv(request: Request, session: Session = Depends(get_session)):
    if r := ensure_admin(request):
        return r
    import csv
    import io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["email", "consented_at", "lang", "source"])
    for c in marketing.subscribed(session):
        writer.writerow([c.email,
                         c.consented_at.isoformat() if c.consented_at else "",
                         c.lang, c.source])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=marketing_subscribers.csv"})
