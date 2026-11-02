import struct
import zlib

from herbarium.main import herb_date, initials, sniff_image

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n"
    + struct.pack(">I", 13) + b"IHDR" + struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    + struct.pack(">I", zlib.crc32(b"IHDR" + struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)))
)
LABEL = {
    "latin_name": "Asplenium scolopendrium",
    "common_name": "Hart's-tongue fern",
    "family": "Aspleniaceae",
    "locality": "Forêt de Brocéliande",
    "collected_on": "2026-10-30",
    "collector": "Test Collector",
}


# ---------------------------------------------------------------- without add-ons


def test_health_never_touches_an_addon(bare_client):
    assert bare_client.get("/health").json() == {"status": "ok"}


def test_pages_explain_a_missing_addon(bare_client):
    response = bare_client.get("/")
    assert response.status_code == 503
    assert "link the MySQL and Cellar add-ons" in response.text


def test_image_sniffing_trusts_content_not_names():
    assert sniff_image(b"\xff\xd8\xff\xe0rest") == ("image/jpeg", "jpg")
    assert sniff_image(PNG_1PX[:16]) == ("image/png", "png")
    assert sniff_image(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == ("image/webp", "webp")
    assert sniff_image(b"GIF89a....") == ("image/gif", "gif")
    assert sniff_image(b"<svg xmlns=...") is None
    assert sniff_image(b"#!/bin/sh") is None


def test_label_formatting():
    from datetime import date

    assert herb_date(date(1887, 5, 14)) == "14.V.1887"
    assert initials("Hortense Brissac") == "H. Brissac"
    assert initials("Linnaeus") == "Linnaeus"


# ---------------------------------------------------------------- with MySQL + Cellar


def test_seed_fills_the_cabinet_once(client):
    from herbarium.seed import seed_collection

    assert client.get("/health/deep").status_code == 200
    page = client.get("/")
    assert page.status_code == 200
    assert page.text.count('class="sheet-card"') == 12
    state = client.app.state
    assert seed_collection(state.engine, state.cellar) == 0  # idempotent


def test_press_a_drawn_specimen_then_read_it_back(client):
    response = client.post("/press", data={"source": "drawn", "drawn": "fern:4242", **LABEL}, follow_redirects=False)
    assert response.status_code == 303
    specimen_id = int(response.headers["location"].split("/specimen/")[1].split("?")[0])

    record = client.get(f"/api/specimens/{specimen_id}").json()
    assert record["specimen"]["latin_name"] == LABEL["latin_name"]
    assert record["specimen"]["drawing"] == "fern/4242"
    assert record["specimen"]["created_sql"].startswith("INSERT INTO specimens")
    assert "Forêt de Brocéliande" in record["specimen"]["created_sql"]
    assert record["cellar"]["content_type"] == "image/svg+xml"
    assert record["cellar"]["size"] == record["specimen"]["byte_size"]
    assert "X-Amz-Signature=" in record["image_url"]

    sheet = client.get(f"/specimen/{specimen_id}?pressed=1")
    assert sheet.status_code == 200
    assert "Asplenium scolopendrium" in sheet.text and "Pressed." in sheet.text


def test_press_a_photo(client):
    files = {"photo": ("leaf.png", PNG_1PX, "image/png")}
    response = client.post("/press", data={"source": "photo", **LABEL}, files=files, follow_redirects=False)
    assert response.status_code == 303
    specimen_id = response.headers["location"].split("/specimen/")[1].split("?")[0]
    record = client.get(f"/api/specimens/{specimen_id}").json()
    assert record["cellar"]["content_type"] == "image/png"
    assert record["specimen"]["object_key"].endswith(".png")


def test_refuses_what_is_not_an_image(client):
    files = {"photo": ("leaf.png", b"<script>alert(1)</script>", "image/png")}
    response = client.post("/press", data={"source": "photo", **LABEL}, files=files)
    assert response.status_code == 422
    assert "Only JPEG, PNG, WebP or GIF" in response.text


def test_refuses_photos_over_5_mb(client):
    big = b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024)
    response = client.post("/press", data={"source": "photo", **LABEL}, files={"photo": ("big.jpg", big, "image/jpeg")})
    assert response.status_code == 422
    assert "larger than 5 MB" in response.text


def test_filters_by_family(client):
    page = client.get("/?family=Fagaceae")
    assert "Quercus robur" in page.text
    assert "Ginkgo biloba" not in page.text
    assert "WHERE specimens.family = &#39;Fagaceae&#39;" in page.text
