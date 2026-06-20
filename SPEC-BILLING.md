# SPEC-BILLING — DreamCatcher → магазин с корзиной и онлайн-оплатой

> Это расширение к базовому `SPEC.md` (витрина). Базовый SPEC остаётся источником
> истины по витрине/i18n/админке; **этот документ — источник истины по биллингу**.
> Стек неизменен: FastAPI + Uvicorn + Jinja2 + SQLModel + SQLite, SSR, без node/docker,
> Python 3.12, CSS руками (токены из `design-system/dreamcatcher/MASTER.md`).

## Цель
Дать посетителю положить товары в корзину, оформить заказ и оплатить онлайн через
Viva.com; дать администратору управлять заказами.

## Вне рамок (можно позже)
Личный кабинет покупателя, регистрация, скидки/промокоды, мультивалютность
(только **EUR**).

---

## 0. Языки → только `el` + `en`
- `app/i18n.py`: `LANGS = ["el", "en"]`; убрать `ru`/`fr` из `LANG_NAMES`, `_BABEL_LOCALE`
  и из словаря `UI` (значения `ru`/`fr` удалить). `FALLBACK_CHAIN` остаётся `el → en`.
- `tests/test_smoke.py`: списки `parametrize(... ["el","en","ru","fr"])` → `["el","en"]`.
- `app/seed.py`: не создавать `ru`/`fr` переводы.
- Переключатель языков в `templates/base.html` и роуты `/{lang}/` работают через `LANGS`
  автоматически (правок не требуют, кроме проверки).

## 1. Модель данных (`app/models.py`)
Новые таблицы (SQLModel; **без** `from __future__ import annotations` в этом файле —
ломает Relationship):

**Order**
- `id` PK
- `number` — человекочитаемый номер заказа (уникальный, напр. `DC-20260620-0007`)
- `status` — `pending | paid | shipped | cancelled`
- `customer_name`, `customer_email`, `customer_phone`
- `ship_address`, `ship_city`, `ship_postcode`, `ship_country` (default `GR`)
- `shipping_method` (slug), `shipping_cost` (float, EUR)
- `subtotal`, `vat_amount`, `total` (float, EUR — все хранятся с учётом фиксации на момент заказа)
- `vat_rate` (float, снимок ставки, напр. `24.0`)
- `currency` (default `EUR`)
- `viva_order_code` (str|None), `viva_transaction_id` (str|None)
- `created_at`, `updated_at`

**OrderItem**
- `id` PK, `order_id` FK
- `product_id` (FK, nullable — товар может быть удалён позже)
- `title_snapshot`, `price_snapshot` (цена-снимок, с НДС, на момент заказа)
- `qty`
- `line_total` = `price_snapshot * qty`

**Product** — добавить контроль остатков (опционально-используемый):
- `stock: int = 0`, `track_stock: bool = False` (если `False` — остаток не ограничивает).
  `in_stock` вычисляется как `not track_stock or stock > 0`.

> Цены в проекте трактуются **с НДС включённым** (см. §5). `vat_amount` считается обратным
> ходом из брутто: `vat = total * rate / (100 + rate)`.

## 2. Корзина
- Хранение в **серверной сессии** (`SessionMiddleware` уже подключён): `request.session["cart"]`
  как `{ "<product_id>": qty }`.
- Новый модуль `app/cart.py` — чистая логика: `get_cart`, `add`, `set_qty`, `remove`, `clear`,
  `cart_view(session, db, lang)` → позиции с актуальными ценами + итоги (subtotal, vat, total,
  count). Никаких цен из сессии — только id+qty, цены берём из БД (на момент заказа фиксируем).
- Роуты в новом `app/routes/cart.py` (под `/{lang}` где нужен рендер, POST-операции с CSRF):
  - `POST /{lang}/cart/add` (product_id, qty=1)
  - `POST /{lang}/cart/update` (product_id, qty) — qty=0 удаляет
  - `POST /{lang}/cart/remove` (product_id)
  - `GET  /{lang}/cart` → `templates/public/cart.html`
- Товары с `price_on_request=True` **в корзину не кладутся** (для них — текущая форма запроса).
  Товары с `track_stock` и `stock<=0` — тоже не кладутся / ограничены остатком.
- Кнопка «В корзину» на странице товара и в каталоге (где цена задана и есть остаток);
  **счётчик корзины в шапке** (`templates/base.html`).

## 3. Оформление и оплата (биллинг)
- `GET /{lang}/checkout` → `templates/public/checkout.html`: контакты + адрес доставки +
  выбор способа доставки; итог с НДС. Пустую корзину — редирект на `/cart`.
- **Платёжная абстракция** `app/payments/`:
  - `base.py`: `PaymentProvider` (Protocol/ABC) с
    `create_checkout(order) -> CheckoutResult(redirect_url, provider_ref)` и
    `verify_webhook(request, raw_body) -> PaymentResult(order_ref, status, transaction_id)`.
  - `viva.py`: `VivaProvider` — первая реализация. Цель — позже подключить Stripe без
    переписывания заказов.
  - **MVP-режим: sandbox/demo-провайдер.** Реальные ключи не требуются: `create_checkout`
    отдаёт внутренний фейковый redirect (`/checkout/pay/{order}`), webhook вызывается вручную/
    кнопкой «оплатить» в demo. Контракт интерфейса = реальный, чтобы боевой Viva включался
    подменой реализации и ключей.
- **Поток:**
  1. `POST /{lang}/checkout` — валидирует форму, создаёт `Order` (status=`pending`) + `OrderItem`'ы
     из корзины (фиксируя цены и НДС), создаёт платёжную сессию провайдера → **redirect** на оплату.
  2. Возврат: `GET /{lang}/checkout/success` и `GET /{lang}/checkout/cancel`.
  3. **Webhook** `POST /payments/viva/webhook` — **единственный надёжный признак оплаты**.
     По нему `Order → paid`, уменьшается остаток (если `track_stock`), очищается корзина,
     опционально отправляется письмо. **Redirect на success оплату НЕ подтверждает.**
- Ключи Viva (`VIVA_MERCHANT_ID`, `VIVA_API_KEY`, `VIVA_WEBHOOK_SECRET`, `VIVA_SOURCE_CODE`,
  `VIVA_MODE=demo|live`) — в `.env` / `app/config.py`. В demo-режиме можно не задавать.

## 4. Админка (`app/routes/admin.py`, `templates/admin/`)
- Раздел **«Заказы»**:
  - `GET /admin/orders` — список с фильтром по статусу.
  - `GET /admin/orders/{id}` — карточка: позиции, суммы, контакты, адрес, статус оплаты,
    `viva_*` ссылки.
  - `POST /admin/orders/{id}/status` — смена статуса (`paid→shipped`, отмена), под CSRF + guard.
- Дашборд: добавить счётчики заказов (всего / pending / paid).
- **Настройки сайта** (`Setting`, через `DEFAULT_SETTINGS` в `app/deps.py` +
  `templates/admin/settings.html`) — новые ключи:
  - `vat_rate` (default `24` — Греция),
  - `shipping_methods` (например JSON/строки `slug|label_el|label_en|cost`),
  - `notify_email` (контактный email для уведомлений о заказах).
- Все новые POST — под существующей CSRF-защитой (`verify_csrf`) и admin-guard (`ensure_admin`).

## 5. Витрина / тексты
- Цена везде трактуется **с НДС** (брутто). В каталоге и карточке товара — **кнопка покупки**
  («В корзину») вместо «по запросу» там, где цена задана и товар в наличии. Для
  `price_on_request` — текущая форма запроса.
- Новые UI-строки в `app/i18n.py` (корзина, оформление, статусы заказа, кнопки) — на `el` и `en`.
- **Статические страницы** + ссылки в футере:
  - Условия продажи `/{lang}/terms`,
  - Политика возврата `/{lang}/returns`,
  - Конфиденциальность (GDPR) `/{lang}/privacy`,
  - **cookie-баннер** (минималистичный, с запоминанием согласия в localStorage/cookie).

## 6. Нефункциональные требования
- Прод-настройки: `https_only=True` для cookie сессии (через флаг конфигурации
  `SESSION_HTTPS_ONLY`, default по `DEBUG`), реальные `SECRET_KEY` и `ADMIN_PASSWORD_HASH`.
- **Идемпотентность webhook**: повторная доставка того же события не должна повторно
  переводить заказ в `paid`/повторно списывать остаток (проверка по `viva_transaction_id`
  и текущему статусу).
- Бэкап `data.db` и `static/uploads/` (скрипт в `scripts/`).

## 7. Критерии приёмки (Definition of Done)
1. Сайт работает только на `el` и `en`; `python -m pytest -q` — зелёный.
2. Можно положить товар в корзину, изменить количество, удалить, оформить заказ.
3. Тестовая оплата в demo-окружении проходит; заказ становится `paid` по webhook
   (идемпотентно).
4. Заказ виден в админке; статус меняется (`paid→shipped`, отмена).
5. Цены и итог считаются корректно с НДС 24% (брутто-трактовка).
6. Опубликованы Условия / Возврат / Конфиденциальность + работает cookie-баннер.

## Verification
- `python -m pytest -q` (обновлённый `tests/test_smoke.py` + новые тесты на корзину/НДС/webhook-идемпотентность).
- Ручной DoD §7 + скриншоты корзины/checkout на 375/768/1024/1440.
