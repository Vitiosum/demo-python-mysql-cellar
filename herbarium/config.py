"""Settings, read straight from the variables Clever Cloud injects.

The MySQL and Cellar add-ons inject their own variables when they are linked
to the app. We read them here and never copy them into new variables.
"""

import hashlib
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    mysql_uri: str
    cellar_endpoint: str
    cellar_key_id: str
    cellar_key_secret: str
    bucket: str
    presign_ttl: int = 600  # seconds a presigned image URL stays valid
    max_upload_bytes: int = 5 * 1024 * 1024
    max_specimens: int = 400  # the cabinet has room for this many sheets


def _sqlalchemy_uri(uri: str) -> str:
    """MYSQL_ADDON_URI is mysql://user:pass@host:port/db; SQLAlchemy wants a driver."""
    if uri.startswith("mysql://"):
        return "mysql+pymysql://" + uri.removeprefix("mysql://")
    return uri


def _endpoint(host: str) -> str:
    """CELLAR_ADDON_HOST is a bare host on Clever Cloud; locally it can be a full URL."""
    if not host:
        return ""
    return host if host.startswith(("http://", "https://")) else f"https://{host}"


def load_settings() -> Settings:
    key_id = os.environ.get("CELLAR_ADDON_KEY_ID", "")
    # One private bucket per Cellar add-on. Bucket names are global, so the
    # default is derived from the add-on's key id (hashed, never shown).
    default_bucket = "herbarium-" + hashlib.sha256(key_id.encode()).hexdigest()[:10]
    return Settings(
        mysql_uri=_sqlalchemy_uri(os.environ.get("MYSQL_ADDON_URI", "")),
        cellar_endpoint=_endpoint(os.environ.get("CELLAR_ADDON_HOST", "")),
        cellar_key_id=key_id,
        cellar_key_secret=os.environ.get("CELLAR_ADDON_KEY_SECRET", ""),
        bucket=os.environ.get("CELLAR_BUCKET") or default_bucket,
    )


# Platform variables shown in the "Running on Clever Cloud" panel. Only these.
PLATFORM_VARS = [
    ("Application", "CC_APP_NAME"),
    ("App ID", "APP_ID"),
    ("Instance", "INSTANCE_NUMBER"),
    ("Instance type", "INSTANCE_TYPE"),
    ("Instance name", "CC_PRETTY_INSTANCE_NAME"),
    ("Commit", "CC_COMMIT_ID"),
    ("Deployment", "CC_DEPLOYMENT_ID"),
]


def on_clever_cloud() -> bool:
    return bool(os.environ.get("APP_ID"))


def platform_info() -> list[tuple[str, str]]:
    rows = []
    for label, name in PLATFORM_VARS:
        value = os.environ.get(name, "")
        if name == "CC_COMMIT_ID":
            value = value[:7]
        rows.append((label, value))
    return rows
