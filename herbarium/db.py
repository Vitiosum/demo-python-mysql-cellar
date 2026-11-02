"""MySQL: one table, `specimens`, and a record of the exact SQL that ran.

PyMySQL builds the final query text on the client side, so `cursor.mogrify()`
returns exactly what was sent to MySQL. We keep it to show it on each sheet.
"""

import time
from dataclasses import dataclass

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    func,
    insert,
    select,
    update,
)

metadata = MetaData()

specimens = Table(
    "specimens",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("latin_name", String(120), nullable=False),
    Column("common_name", String(120), nullable=False),
    Column("family", String(60), nullable=False, index=True),
    Column("locality", String(120), nullable=False),
    Column("collected_on", Date, nullable=False),
    Column("collector", String(80), nullable=False),
    Column("object_key", String(200), nullable=False),
    Column("content_type", String(40), nullable=False),
    Column("byte_size", Integer, nullable=False),
    Column("drawing", String(40)),  # "oak/1842" for a drawn specimen, NULL for a photo
    Column("seed_key", String(40), unique=True),  # set on seed rows: seeding is idempotent
    Column("created_sql", Text),  # the INSERT that created the row, as MySQL received it
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
    mysql_charset="utf8mb4",
)

# Columns shown as "the MySQL row" (created_sql is shown on its own).
ROW_COLUMNS = [c.name for c in specimens.columns if c.name != "created_sql"]


@dataclass
class Ran:
    """A statement as MySQL received it, and how long it took."""

    sql: str
    ms: float


def make_engine(uri: str) -> Engine:
    # xxs_sml allows 15 connections: 3 per instance leaves room for 2 instances
    # plus the old ones still draining during a deployment.
    engine = create_engine(uri, pool_size=2, max_overflow=1, pool_recycle=280, pool_pre_ping=True)

    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        conn.info["sql"] = cursor.mogrify(statement, parameters)
        conn.info["t0"] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        conn.info["ms"] = (time.perf_counter() - conn.info.pop("t0")) * 1000

    return engine


def _ran(conn) -> Ran:
    return Ran(sql=conn.info.pop("sql", ""), ms=round(conn.info.pop("ms", 0.0), 2))


def create_schema(engine: Engine) -> None:
    metadata.create_all(engine)  # CREATE TABLE only if it does not exist


def insert_specimen(engine: Engine, **fields) -> tuple[int, Ran]:
    """INSERT the row, then keep the exact INSERT text in the row itself."""
    with engine.begin() as conn:
        result = conn.execute(insert(specimens).values(**fields))
        new_id = result.inserted_primary_key[0]
        ran = _ran(conn)
        conn.execute(update(specimens).where(specimens.c.id == new_id).values(created_sql=ran.sql))
    return new_id, ran


def get_specimen(engine: Engine, specimen_id: int):
    with engine.connect() as conn:
        row = conn.execute(select(specimens).where(specimens.c.id == specimen_id)).mappings().first()
        return row, _ran(conn)


def neighbours(engine: Engine, specimen_id: int) -> tuple[int | None, int | None]:
    """The previous and next sheets in the cabinet."""
    with engine.connect() as conn:
        older = conn.execute(select(func.max(specimens.c.id)).where(specimens.c.id < specimen_id)).scalar()
        newer = conn.execute(select(func.min(specimens.c.id)).where(specimens.c.id > specimen_id)).scalar()
    return older, newer


def list_specimens(engine: Engine, family: str = "", locality: str = "", collector: str = ""):
    query = select(
        specimens.c.id,
        specimens.c.latin_name,
        specimens.c.common_name,
        specimens.c.family,
        specimens.c.locality,
        specimens.c.collected_on,
        specimens.c.collector,
        specimens.c.object_key,
        specimens.c.content_type,
    ).order_by(specimens.c.id.desc())
    if family:
        query = query.where(specimens.c.family == family)
    if locality:
        query = query.where(specimens.c.locality == locality)
    if collector:
        query = query.where(specimens.c.collector == collector)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
        return rows, _ran(conn)


def filter_options(engine: Engine) -> dict[str, list[str]]:
    with engine.connect() as conn:
        return {
            name: list(conn.execute(select(col).distinct().order_by(col)).scalars())
            for name, col in [
                ("family", specimens.c.family),
                ("locality", specimens.c.locality),
                ("collector", specimens.c.collector),
            ]
        }


def count_specimens(engine: Engine) -> tuple[int, Ran]:
    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(specimens)).scalar_one()
        return total, _ran(conn)


def ping(engine: Engine) -> str:
    with engine.connect() as conn:
        return conn.exec_driver_sql("SELECT VERSION()").scalar_one()
