"""Twelve specimens pressed at first start, so the cabinet is never empty.

Idempotent: a drawing is uploaded only if its object is missing, a row is
inserted only if its seed_key is missing. Two instances starting together
are fine: the UNIQUE seed_key lets only one insert win.
"""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .cellar import Cellar
from .db import insert_specimen, specimens
from .drawing import KINDS, draw

log = logging.getLogger("herbarium.seed")

# kind, locality, collected on, collector (collectors are fictional)
SEEDS = [
    ("oak", "Île-de-France", date(1887, 5, 14), "Léonie Garnier"),
    ("ginkgo", "Île-de-France", date(1891, 10, 28), "Auguste Marchand"),
    ("maple", "Île-de-France", date(1889, 9, 3), "Hortense Brissac"),
    ("ash", "Pays de la Loire", date(1893, 6, 21), "Émile Varenne"),
    ("lavender", "Provence", date(1890, 7, 9), "Léonie Garnier"),
    ("daisy", "Bretagne", date(1888, 4, 30), "Auguste Marchand"),
    ("foxglove", "Bretagne", date(1892, 6, 11), "Hortense Brissac"),
    ("fern", "Bretagne", date(1886, 8, 17), "Émile Varenne"),
    ("ivy", "Normandie", date(1894, 11, 2), "Léonie Garnier"),
    ("poppy", "Provence", date(1889, 6, 24), "Auguste Marchand"),
    ("willow", "Pays de la Loire", date(1891, 5, 5), "Hortense Brissac"),
    ("clover", "Normandie", date(1893, 7, 15), "Émile Varenne"),
]


def seed_collection(engine, cellar: Cellar) -> int:
    with engine.connect() as conn:
        done = set(conn.execute(select(specimens.c.seed_key).where(specimens.c.seed_key.is_not(None))).scalars())
    created = 0
    for number, (kind, locality, collected_on, collector) in enumerate(SEEDS, start=1):
        key, seed = f"sheets/seed/{kind}.svg", 100 + number
        if not cellar.exists(key):
            cellar.put(key, draw(kind, seed).encode(), "image/svg+xml")
        if f"seed-{kind}" in done:
            continue
        latin, common, family = KINDS[kind]
        try:
            insert_specimen(
                engine,
                latin_name=latin,
                common_name=common,
                family=family,
                locality=locality,
                collected_on=collected_on,
                collector=collector,
                object_key=key,
                content_type="image/svg+xml",
                byte_size=cellar.head(key)["size"],
                drawing=f"{kind}/{seed}",
                seed_key=f"seed-{kind}",
            )
            created += 1
        except IntegrityError:
            log.info("seed %s already pressed by another instance", kind)
    return created
