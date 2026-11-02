import xml.etree.ElementTree as ET

import pytest

from herbarium.drawing import KINDS, draw


@pytest.mark.parametrize("kind", list(KINDS))
def test_every_plant_is_valid_svg(kind):
    svg = draw(kind, 42)
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert root.get("viewBox") == "0 0 600 900"
    assert len(svg) < 200_000  # stays light for the browser and for Cellar


def test_same_seed_same_drawing_new_seed_new_drawing():
    assert draw("oak", 7) == draw("oak", 7)
    assert draw("oak", 7) != draw("oak", 8)
