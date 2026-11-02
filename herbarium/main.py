"""The Herbarium: a FastAPI app on Clever Cloud.

A specimen = a row in MySQL (the label) + an image in a private Cellar bucket.
Routes are plain `def`: FastAPI runs them in a thread pool, which suits the
synchronous SQLAlchemy and boto3 clients.
"""

import logging
import random
import re
import secrets
import threading
import time
import unicodedata
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import db
from .cellar import Cellar
from .config import load_settings, on_clever_cloud, platform_info
from .drawing import KINDS, draw
from .seed import seed_collection

log = logging.getLogger("herbarium")
HERE = Path(__file__).parent
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


class CabinetLocked(Exception):
    """MySQL or Cellar is not reachable (or not linked)."""


# ---------------------------------------------------------------- startup


def prepare(app: FastAPI) -> None:
    """Create the table and the bucket if missing, then press the seed specimens."""
    db.create_schema(app.state.engine)
    if app.state.cellar.ensure_bucket():
        log.info("created private bucket %s", app.state.cellar.bucket)
    created = seed_collection(app.state.engine, app.state.cellar)
    log.info("cabinet ready, %d seed specimens pressed now", created)
    app.state.ready = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    app.state.ready = False
    app.state.lock = threading.Lock()
    app.state.engine = db.make_engine(settings.mysql_uri) if settings.mysql_uri else None
    app.state.cellar = Cellar(settings) if settings.cellar_endpoint else None
    if app.state.engine and app.state.cellar:
        try:
            prepare(app)
        except Exception:
            log.exception("could not prepare MySQL and Cellar yet; will retry on the next page view")
    else:
        log.error("MYSQL_ADDON_URI or CELLAR_ADDON_HOST is missing: link both add-ons to the app")
    yield
    if app.state.engine:
        app.state.engine.dispose()


app = FastAPI(title="The Herbarium", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")


def need(request: Request) -> tuple:
    """The MySQL engine and the Cellar client, ready to use."""
    state = request.app.state
    if not state.engine or not state.cellar:
        raise CabinetLocked("MYSQL_ADDON_URI or CELLAR_ADDON_HOST is not set: link the MySQL and Cellar add-ons.")
    if not state.ready:
        with state.lock:
            if not state.ready:
                try:
                    prepare(request.app)
                except Exception as err:
                    raise CabinetLocked(f"MySQL or Cellar did not answer ({type(err).__name__}).") from err
    return state.engine, state.cellar


# ---------------------------------------------------------------- template helpers


def herb_date(value: date) -> str:
    """Herbarium style: 14.V.1887"""
    return f"{value.day}.{ROMAN[value.month - 1]}.{value.year}"


def initials(name: str) -> str:
    """Label style: Hortense Brissac -> H. Brissac"""
    parts = name.split()
    return " ".join([f"{p[0]}." for p in parts[:-1]] + parts[-1:]) if len(parts) > 1 else name


def human_bytes(value: int) -> str:
    for unit in ("bytes", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "bytes" else f"{value:.1f} {unit}"
        value /= 1024
    return str(value)


templates.env.filters["herb_date"] = herb_date
templates.env.filters["human_bytes"] = human_bytes
templates.env.filters["initials"] = initials


def page(request: Request, name: str, status: int = 200, **context):
    ledger = None
    state = request.app.state
    if state.ready:
        try:
            count, count_ran = db.count_specimens(state.engine)
            ledger = {"count": count, "count_sql": count_ran.sql, **state.cellar.stats()}
        except Exception:
            log.exception("ledger unavailable")
    context.update(
        platform=platform_info(),
        on_clever=on_clever_cloud(),
        ledger=ledger,
        bucket=state.cellar.bucket if state.cellar else "",
        path=request.url.path,
    )
    return templates.TemplateResponse(request, name, context, status_code=status)


# ---------------------------------------------------------------- security headers


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # Refuse oversized uploads before reading them (photos are capped at 5 MB)
    if int(request.headers.get("content-length") or 0) > 6 * 1024 * 1024:
        return JSONResponse({"detail": "Request too large: photos are limited to 5 MB."}, status_code=413)
    response = await call_next(request)
    endpoint = request.app.state.settings.cellar_endpoint
    cellar_origin = "{0.scheme}://{0.netloc}".format(urlsplit(endpoint)) if endpoint else ""
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"img-src 'self' data: blob: {cellar_origin}; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; script-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(CabinetLocked)
async def cabinet_locked(request: Request, exc: CabinetLocked):
    return page(request, "error.html", 503, title="The cabinet is locked", message=str(exc),
                hint="Check /health/deep, then the add-on variables with clever env.")


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith(("/api/", "/health", "/draw/", "/static/")):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return page(request, "error.html", exc.status_code, title="No sheet here",
                message="This drawer is empty. The specimen may never have been pressed.", hint="")


# ---------------------------------------------------------------- health


@app.get("/health")
def health():
    """Liveness only: never touches an add-on."""
    return {"status": "ok"}


@app.get("/health/deep")
def health_deep(request: Request):
    state = request.app.state
    report, ok = {}, True
    try:
        report["mysql"] = {"ok": True, "version": db.ping(state.engine)}
    except Exception as err:
        ok, report["mysql"] = False, {"ok": False, "error": type(err).__name__}
    try:
        state.cellar.s3.head_bucket(Bucket=state.cellar.bucket)
        report["cellar"] = {"ok": True, "bucket": state.cellar.bucket}
    except Exception as err:
        ok, report["cellar"] = False, {"ok": False, "error": type(err).__name__}
    return JSONResponse({"status": "ok" if ok else "degraded", **report}, status_code=200 if ok else 503)


# ---------------------------------------------------------------- pages


@app.get("/cc-brand.css", include_in_schema=False)
def brand_css():
    return FileResponse(HERE / "static" / "cc-brand.css", media_type="text/css")


@app.get("/")
def collection(request: Request, family: str = "", place: str = "", collector: str = ""):
    engine, cellar = need(request)
    rows, ran = db.list_specimens(engine, family=family, locality=place, collector=collector)
    sheets = [{**row, "image_url": cellar.presign(row["object_key"])} for row in rows]
    return page(request, "collection.html", sheets=sheets, ran=ran, options=db.filter_options(engine),
                active={"family": family, "place": place, "collector": collector})


@app.get("/specimen/{specimen_id}")
def sheet(request: Request, specimen_id: int, pressed: int = 0, put_ms: float = 0, insert_ms: float = 0):
    engine, cellar = need(request)
    row, ran = db.get_specimen(engine, specimen_id)
    if row is None:
        raise HTTPException(404, "No such specimen")
    t0 = time.perf_counter()
    obj = cellar.head(row["object_key"])
    head_ms = round((time.perf_counter() - t0) * 1000, 1)
    expires = datetime.now(timezone.utc) + timedelta(seconds=cellar.ttl)
    older, newer = db.neighbours(engine, specimen_id)
    return page(
        request, "sheet.html",
        s=row, ran=ran, obj=obj, head_ms=head_ms,
        row_items=[(name, row[name]) for name in db.ROW_COLUMNS],
        image_url=cellar.presign(row["object_key"]), unsigned_url=cellar.unsigned_url(row["object_key"]),
        expires_at=expires, ttl=cellar.ttl, older=older, newer=newer,
        pressed=bool(pressed), put_ms=put_ms, insert_ms=insert_ms,
    )


@app.get("/press")
def press_form(request: Request):
    need(request)
    return page(request, "press.html", kinds=KINDS, seeds={k: random.randint(1, 99_999) for k in KINDS},
                values={"source": "drawn"}, errors={})


@app.get("/draw/{kind}.svg")
def draw_preview(kind: str, seed: int = Query(1, ge=0, le=999_999)):
    if kind not in KINDS:
        raise HTTPException(404, "Unknown plant")
    return Response(draw(kind, seed), media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------- pressing a specimen

IMAGE_SIGNATURES = [  # magic bytes: we trust the file content, not its name
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
]
_recent_presses: dict[str, list[float]] = {}


def sniff_image(head: bytes) -> tuple[str, str] | None:
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "webp"
    for magic, content_type, ext in IMAGE_SIGNATURES:
        if head.startswith(magic):
            return content_type, ext
    return None


def slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:40] or "specimen"


def allow_press(ip: str, limit: int = 12, window: int = 600) -> bool:
    now = time.monotonic()
    recent = [t for t in _recent_presses.get(ip, []) if now - t < window]
    allowed = len(recent) < limit
    _recent_presses[ip] = recent + [now] if allowed else recent
    return allowed


@app.post("/press")
def press(
    request: Request,
    source: str = Form("drawn"),
    drawn: str = Form(""),  # "oak:1842": which recipe, which seed
    latin_name: str = Form(""),
    common_name: str = Form(""),
    family: str = Form(""),
    locality: str = Form(""),
    collected_on: str = Form(""),
    collector: str = Form(""),
    photo: UploadFile | None = File(None),
):
    engine, cellar = need(request)
    settings = request.app.state.settings
    values = {k: v.strip() for k, v in {
        "source": source, "drawn": drawn, "latin_name": latin_name, "common_name": common_name,
        "family": family, "locality": locality, "collected_on": collected_on, "collector": collector,
    }.items()}
    errors: dict[str, str] = {}

    for field, label, low, high in [
        ("latin_name", "Latin name", 3, 120), ("common_name", "Common name", 2, 120),
        ("family", "Family", 3, 60), ("locality", "Locality", 2, 120), ("collector", "Collector", 2, 80),
    ]:
        if not low <= len(values[field]) <= high:
            errors[field] = f"{label}: between {low} and {high} characters."
    try:
        when = date.fromisoformat(values["collected_on"])
        if not date(1700, 1, 1) <= when <= date.today():
            errors["collected_on"] = "Date: between 1700 and today."
    except ValueError:
        errors["collected_on"] = "Date: pick the day the plant was collected."

    body = content_type = ext = drawing = None
    if source == "photo":
        data = photo.file.read(settings.max_upload_bytes + 1) if photo and photo.filename else b""
        sniffed = sniff_image(data[:16])
        if not data:
            errors["photo"] = "Choose a photo of your leaf or plant."
        elif len(data) > settings.max_upload_bytes:
            errors["photo"] = "The photo is larger than 5 MB."
        elif sniffed is None:
            errors["photo"] = "Only JPEG, PNG, WebP or GIF images can be pressed."
        else:
            body, (content_type, ext) = data, sniffed
    else:
        kind, _, seed = values["drawn"].partition(":")
        if kind in KINDS and seed.isdigit() and int(seed) <= 999_999:
            body, content_type, ext = draw(kind, int(seed)).encode(), "image/svg+xml", "svg"
            drawing = f"{kind}/{int(seed)}"
        else:
            errors["kind"] = "Pick one of the drawn specimens."

    if not errors and db.count_specimens(engine)[0] >= settings.max_specimens:
        errors["form"] = f"The cabinet is full ({settings.max_specimens} sheets). Pressing is closed for now."
    if not errors and not allow_press(request.client.host if request.client else "?"):
        errors["form"] = "You pressed many specimens in a short time. Try again in a few minutes."
    if errors:
        return page(request, "press.html", 422, kinds=KINDS,
                    seeds={k: random.randint(1, 99_999) for k in KINDS}, values=values, errors=errors)

    key = f"sheets/{date.today():%Y/%m}/{slug(values['latin_name'])}-{secrets.token_hex(3)}.{ext}"
    put_ms = cellar.put(key, body, content_type)  # 1. the image goes to Cellar
    try:
        new_id, ran = db.insert_specimen(  # 2. the label goes to MySQL
            engine,
            latin_name=values["latin_name"], common_name=values["common_name"], family=values["family"],
            locality=values["locality"], collected_on=when, collector=values["collector"],
            object_key=key, content_type=content_type, byte_size=len(body), drawing=drawing,
        )
    except Exception:
        cellar.s3.delete_object(Bucket=cellar.bucket, Key=key)  # no orphan image without a label
        raise
    return RedirectResponse(f"/specimen/{new_id}?pressed=1&put_ms={put_ms}&insert_ms={ran.ms}", status_code=303)


# ---------------------------------------------------------------- JSON


@app.get("/api/specimens/{specimen_id}")
def api_specimen(request: Request, specimen_id: int):
    engine, cellar = need(request)
    row, ran = db.get_specimen(engine, specimen_id)
    if row is None:
        raise HTTPException(404, "No such specimen")
    return {
        "specimen": {k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in row.items()},
        "read_sql": ran.sql,
        "cellar": {"bucket": cellar.bucket, "key": row["object_key"], **{
            k: v for k, v in cellar.head(row["object_key"]).items() if k != "last_modified"}},
        "image_url": cellar.presign(row["object_key"]),
        "image_url_expires_in": cellar.ttl,
    }
