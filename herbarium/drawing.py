"""Botanical illustrations drawn by code.

Each plant is a small recipe: stems are walked step by step, leaves are built
from a width profile, flowers from petals. The seed makes every sheet unique.
The result is an SVG in the manner of an ink-outlined, pressed specimen.
"""

import math
import random

W, H = 600, 900
INK = "#3a2a1b"
BARK = "#6b4f33"
STALK = "#6f7240"

# name: (Latin name, common name, family)
KINDS: dict[str, tuple[str, str, str]] = {
    "oak": ("Quercus robur", "English oak", "Fagaceae"),
    "ginkgo": ("Ginkgo biloba", "Maidenhair tree", "Ginkgoaceae"),
    "maple": ("Acer pseudoplatanus", "Sycamore maple", "Sapindaceae"),
    "ash": ("Fraxinus excelsior", "Common ash", "Oleaceae"),
    "lavender": ("Lavandula angustifolia", "True lavender", "Lamiaceae"),
    "daisy": ("Bellis perennis", "Common daisy", "Asteraceae"),
    "foxglove": ("Digitalis purpurea", "Foxglove", "Plantaginaceae"),
    "fern": ("Polypodium vulgare", "Common polypody", "Polypodiaceae"),
    "ivy": ("Hedera helix", "Common ivy", "Araliaceae"),
    "poppy": ("Papaver rhoeas", "Corn poppy", "Papaveraceae"),
    "willow": ("Salix alba", "White willow", "Salicaceae"),
    "clover": ("Trifolium pratense", "Red clover", "Fabaceae"),
}


def _n(v: float) -> str:
    return f"{v:.1f}"


def _smooth(points) -> str:
    """Cubic Bezier segments through the points (Catmull-Rom), no leading M."""
    segs = []
    last = len(points) - 1
    for i in range(last):
        p0, p1, p2 = points[max(i - 1, 0)], points[i], points[i + 1]
        p3 = points[min(i + 2, last)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        segs.append(f"C{_n(c1[0])} {_n(c1[1])} {_n(c2[0])} {_n(c2[1])} {_n(p2[0])} {_n(p2[1])}")
    return " ".join(segs)


def _open(points) -> str:
    return f"M{_n(points[0][0])} {_n(points[0][1])} {_smooth(points)}"


def _closed(points) -> str:
    n = len(points)
    segs = [f"M{_n(points[0][0])} {_n(points[0][1])}"]
    for i in range(n):
        p0, p1, p2, p3 = points[i - 1], points[i], points[(i + 1) % n], points[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        segs.append(f"C{_n(c1[0])} {_n(c1[1])} {_n(c2[0])} {_n(c2[1])} {_n(p2[0])} {_n(p2[1])}")
    return " ".join(segs) + " Z"


PROFILES = {
    "lanceolate": lambda t: math.sin(math.pi * t) ** 0.9 * (1 - 0.35 * t),
    "ovate": lambda t: math.sin(math.pi * t**0.75),
    "elliptic": lambda t: math.sin(math.pi * t),
    "obovate": lambda t: math.sin(math.pi * t**1.45) ** 0.85,
    "spatulate": lambda t: math.sin(math.pi * t**2.4) ** 0.8 * min(1.0, 0.18 + t),
    "linear": lambda t: min(1.0, t * 7, (1 - t) * 4),
    "oblong": lambda t: min(1.0, t * 6) ** 0.6 * max(0.0, 1 - t**5) ** 0.5,
    "oak": lambda t: math.sin(math.pi * t**1.2) * (0.5 + 0.5 * abs(math.sin(t * math.pi * 4.5)) ** 0.6),
    "wing": lambda t: math.sin(math.pi * t**0.6) ** 1.2 * (0.35 + 0.65 * t),
    "bud": lambda t: math.sin(math.pi * t**0.8) ** 0.7,
}


class Sketch:
    """Collects SVG fragments and the area they cover."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.seed = seed
        self.parts: list[str] = []
        self.stems: list[list[tuple[float, float]]] = []
        self.box = [math.inf, math.inf, -math.inf, -math.inf]

    def r(self, a: float, b: float) -> float:
        return self.rng.uniform(a, b)

    def add(self, fragment: str) -> None:
        self.parts.append(fragment)

    def reach(self, x: float, y: float, pad: float = 0.0) -> None:
        b = self.box
        b[0], b[1] = min(b[0], x - pad), min(b[1], y - pad)
        b[2], b[3] = max(b[2], x + pad), max(b[3], y + pad)

    def svg(self) -> str:
        x0, y0, x1, y1 = self.box
        margin = 14
        scale = min(1.0, (W - 2 * margin) / (x1 - x0), (H - 2 * margin) / (y1 - y0))
        tx = W / 2 - scale * (x0 + x1) / 2
        ty = (H - margin) - scale * y1
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
            "<defs>"
            '<pattern id="hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(38)">'
            f'<line x1="0" y1="0" x2="0" y2="4" stroke="{INK}" stroke-width="0.7" opacity="0.38"/></pattern>'
            '<filter id="ink" x="-6%" y="-6%" width="112%" height="112%">'
            f'<feTurbulence type="fractalNoise" baseFrequency="0.045" numOctaves="2" seed="{self.seed % 997}" result="n"/>'
            '<feDisplacementMap in="SourceGraphic" in2="n" scale="2.6" xChannelSelector="R" yChannelSelector="G"/>'
            f'<feDropShadow dx="1.4" dy="2.2" stdDeviation="1.6" flood-color="{INK}" flood-opacity="0.22"/>'
            "</filter></defs>"
            f'<g filter="url(#ink)"><g transform="translate({_n(tx)} {_n(ty)}) scale({scale:.3f})">'
            + "".join(self.parts)
            + "</g></g></svg>"
        )


# ---------------------------------------------------------------- geometry


def walk(sk: Sketch, x, y, heading, length, curl=0.0, steps=24, wobble=1.5):
    """A centre line: start somewhere, turn a little at each step."""
    pts = [(x, y)]
    step, h = length / steps, heading
    for _ in range(steps):
        h += curl / steps + sk.r(-wobble, wobble)
        x += math.cos(math.radians(h)) * step
        y += math.sin(math.radians(h)) * step
        pts.append((x, y))
    return pts


def heading_at(pts, i) -> float:
    a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def _rot(x, y, angle, px, py):
    a = math.radians(angle)
    return x + px * math.cos(a) - py * math.sin(a), y + px * math.sin(a) + py * math.cos(a)


def stem(sk: Sketch, pts, w0, w1, color=STALK, hairs=0):
    """A tapered stalk drawn as a filled outline."""
    left, right = [], []
    last = len(pts) - 1
    for i, (x, y) in enumerate(pts):
        (xa, ya), (xb, yb) = pts[max(i - 1, 0)], pts[min(i + 1, last)]
        length = math.hypot(xb - xa, yb - ya) or 1
        nx, ny = -(yb - ya) / length, (xb - xa) / length
        w = (w0 + (w1 - w0) * i / last) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
        sk.reach(x, y, w)
    d = f"{_open(left)} L{_n(right[-1][0])} {_n(right[-1][1])} {_smooth(right[::-1])} Z"
    sk.add(f'<path d="{d}" fill="{color}" stroke="{INK}" stroke-width="0.9" stroke-linejoin="round"/>')
    if w0 >= 3.5:
        sk.stems.append(pts)
    if hairs:
        lines = []
        for _ in range(hairs):
            i = sk.rng.randrange(1, last)
            x, y = pts[i]
            h = heading_at(pts, i) + sk.rng.choice((-1, 1)) * sk.r(40, 75)
            hx, hy = _rot(x, y, h, sk.r(4, 8), 0)
            lines.append(f"M{_n(x)} {_n(y)} L{_n(hx)} {_n(hy)}")
        sk.add(f'<path d="{" ".join(lines)}" stroke="{INK}" stroke-width="0.5" opacity="0.6"/>')


def leaf(sk: Sketch, x, y, angle, length, width, profile, color, *, petiole=0.0, bend=0.0,
         veins=6, serrate=0.0, vein_color=INK, steps=24, simple=False):
    """A simple leaf along +x, then rotated: blade, shading, outline, midrib, veins."""
    prof = PROFILES[profile]
    up, lo, mid = [], [], []
    for i in range(steps + 1):
        t = i / steps
        cx = petiole + t * length
        cy = bend * length * 0.12 * math.sin(math.pi * t)
        w = prof(t) * width
        if serrate:
            w *= 1 - serrate * abs(math.sin(t * math.pi * 24))
        up.append((cx, cy - w))
        lo.append((cx, cy + w))
        mid.append((cx, cy))
    for px, py in (up[steps // 2], lo[steps // 2], mid[-1]):
        sk.reach(*_rot(x, y, angle, px, py))
    blade = f"{_open(up)} {_smooth(lo[::-1])} Z"
    if simple:  # small leaflets: one filled outline and a midrib keep the file light
        sk.add(f'<g transform="translate({_n(x)} {_n(y)}) rotate({_n(angle)})">'
               f'<path d="{blade}" fill="{color}" stroke="{INK}" stroke-width="0.8"/>'
               f'<path d="M{_n(mid[0][0])} 0 L{_n(mid[-1][0] * 0.9)} 0" stroke="{INK}" stroke-width="0.6" opacity="0.7"/></g>')
        return
    shade = f"{_open(mid)} {_smooth(lo[::-1])} Z"
    parts = []
    if petiole:
        parts.append(f'<path d="M0 0 L{_n(petiole + 2)} 0" stroke="{INK}" stroke-width="1.7" stroke-linecap="round"/>')
    parts.append(f'<path d="{blade}" fill="{color}" fill-opacity="0.92" stroke="{INK}" stroke-width="1"/>')
    parts.append(f'<path d="{shade}" fill="url(#hatch)"/>')
    parts.append(f'<path d="{_open(mid)}" fill="none" stroke="{vein_color}" stroke-width="0.9" opacity="0.85"/>')
    if veins:
        vs = []
        for k in range(veins):
            t = 0.14 + 0.7 * k / max(1, veins - 1)
            i, j = round(t * steps), min(steps, round((t + 0.12) * steps))
            m = mid[i]
            for edge in (up, lo):
                ex = m[0] + (edge[j][0] - m[0]) * 0.86
                ey = m[1] + (edge[j][1] - m[1]) * 0.86
                qx, qy = m[0] + (ex - m[0]) * 0.2, m[1] + (ey - m[1]) * 0.8
                vs.append(f"M{_n(m[0])} {_n(m[1])} Q{_n(qx)} {_n(qy)} {_n(ex)} {_n(ey)}")
        parts.append(f'<path d="{" ".join(vs)}" fill="none" stroke="{vein_color}" stroke-width="0.55" opacity="0.6"/>')
    sk.add(f'<g transform="translate({_n(x)} {_n(y)}) rotate({_n(angle)})">{"".join(parts)}</g>')


def palmate(sk: Sketch, x, y, angle, radius, color, lobes, *, sigma=0.32, base=0.28, teeth=0.0,
            petiole=0.0, vein_color=INK):
    """A lobed leaf (maple, ivy) drawn in polar coordinates around its centre."""
    pts = []
    for i in range(110):
        th = -math.pi + 2 * math.pi * i / 110
        r = base + sum(f * math.exp(-((th - math.radians(d)) ** 2) / (2 * sigma**2)) for d, f in lobes)
        if teeth:
            r *= 1 + teeth * math.sin(th * 40)
        pts.append((petiole + radius * r * math.cos(th), radius * r * math.sin(th)))
    sk.reach(*_rot(x, y, angle, petiole, 0), radius * 1.05)
    blade = _closed(pts)
    veins = []
    for d, f in lobes:
        r = radius * (base + f) * 0.88
        a = math.radians(d)
        veins.append(f"M{_n(petiole)} 0 L{_n(petiole + r * math.cos(a))} {_n(r * math.sin(a))}")
    sk.add(
        f'<g transform="translate({_n(x)} {_n(y)}) rotate({_n(angle)})">'
        f'<path d="M0 0 L{_n(petiole)} 0" stroke="{INK}" stroke-width="2" stroke-linecap="round"/>'
        f'<path d="{blade}" fill="{color}" fill-opacity="0.92" stroke="{INK}" stroke-width="1"/>'
        f'<path d="{blade}" fill="url(#hatch)" opacity="0.55"/>'
        f'<path d="{" ".join(veins)}" stroke="{vein_color}" stroke-width="1" opacity="0.8" fill="none"/>'
        "</g>"
    )


def roots(sk: Sketch, x, y, depth=3, length=55.0, heading=90.0):
    pts = walk(sk, x, y, heading, length, curl=sk.r(-35, 35), steps=7, wobble=9)
    pts = [(px, min(py, y + 95)) for px, py in pts]
    for px, py in pts:
        sk.reach(px, py)
    sk.add(f'<path d="{_open(pts)}" fill="none" stroke="{INK}" stroke-width="{0.5 + depth * 0.45:.2f}" '
           'stroke-linecap="round" opacity="0.85"/>')
    if depth > 0:
        for _ in range(sk.rng.randint(2, 3)):
            px, py = pts[sk.rng.randrange(2, len(pts))]
            roots(sk, px, py, depth - 1, length * 0.62, heading + sk.r(-55, 55))


def strap(sk: Sketch, pts, t: float):
    """A strip of gummed linen tape holding the stem down on the sheet."""
    i = min(len(pts) - 1, max(1, round(t * (len(pts) - 1))))
    x, y = pts[i]
    angle = heading_at(pts, i) + 90 + sk.r(-16, 16)
    length, width = sk.r(64, 84), sk.r(13, 16)
    sk.add(f'<g transform="translate({_n(x)} {_n(y)}) rotate({_n(angle)})">'
           f'<rect x="{_n(-length / 2)}" y="{_n(-width / 2)}" width="{_n(length)}" height="{_n(width)}" '
           'fill="#f3ead2" stroke="#cdbd96" stroke-width="0.7"/>'
           f'<path d="M{_n(-length / 2 + 3)} {_n(-width / 4)} H{_n(length / 2 - 3)} M{_n(-length / 2 + 3)} {_n(width / 4)} '
           f'H{_n(length / 2 - 3)}" stroke="#cdbd96" stroke-width="0.6" stroke-dasharray="1.5 2.5"/></g>')


def mount_straps(sk: Sketch):
    """Tape the two longest stems, like a herbarium preparator would."""
    stems = sorted(sk.stems, key=lambda pts: -sum(math.dist(a, b) for a, b in zip(pts, pts[1:])))
    for pts, spots in zip(stems, ((0.16, 0.58), (0.42,))):
        for t in spots:
            strap(sk, pts, t)


def cut_end(sk: Sketch, pts, width):
    """The clean diagonal cut at the base of a twig."""
    x, y = pts[0]
    sk.add(f'<ellipse cx="{_n(x)}" cy="{_n(y)}" rx="{_n(width * 0.55)}" ry="{_n(width * 0.3)}" '
           f'fill="#c9b48a" stroke="{INK}" stroke-width="0.8" transform="rotate(-20 {_n(x)} {_n(y)})"/>')


# ---------------------------------------------------------------- organs


def daisy_head(sk: Sketch, x, y, r):
    sk.reach(x, y, r)
    petals = []
    for k in range(22):
        a = 360 * k / 22 + sk.r(-4, 4)
        px, py = _rot(x, y, a, r * 0.58, 0)
        tint = "#ead2cf" if k % 3 == 0 else "#f3ecdc"
        petals.append(f'<ellipse cx="{_n(px)}" cy="{_n(py)}" rx="{_n(r * 0.44)}" ry="{_n(r * 0.1)}" '
                      f'transform="rotate({_n(a)} {_n(px)} {_n(py)})" fill="{tint}" stroke="{INK}" stroke-width="0.6"/>')
    dots = []
    for _ in range(26):
        a, d = sk.r(0, 2 * math.pi), r * 0.26 * math.sqrt(sk.r(0, 1))
        dots.append(f'<circle cx="{_n(x + d * math.cos(a))}" cy="{_n(y + d * math.sin(a))}" r="0.9"/>')
    sk.add("".join(petals))
    sk.add(f'<circle cx="{_n(x)}" cy="{_n(y)}" r="{_n(r * 0.3)}" fill="#c99d38" stroke="{INK}" stroke-width="0.8"/>'
           f'<g fill="{INK}" opacity="0.55">{"".join(dots)}</g>')


def poppy_flower(sk: Sketch, x, y, r, angle):
    sk.reach(x, y, r)
    for k, a in enumerate((angle + 45, angle + 225, angle + 135, angle - 45)):
        color = "#8e3530" if k < 2 else "#a8443b"
        leaf(sk, x, y, a + sk.r(-8, 8), r, r * 0.62, "obovate", color, veins=0)
    sk.add(f'<circle cx="{_n(x)}" cy="{_n(y)}" r="{_n(r * 0.3)}" fill="#2b1d17" opacity="0.55"/>')
    dots = "".join(
        f'<circle cx="{_n(x + r * 0.27 * math.cos(a))}" cy="{_n(y + r * 0.27 * math.sin(a))}" r="1.3"/>'
        for a in (2 * math.pi * k / 28 for k in range(28))
    )
    rays = " ".join(
        f"M{_n(x)} {_n(y)} L{_n(x + r * 0.15 * math.cos(a))} {_n(y + r * 0.15 * math.sin(a))}"
        for a in (2 * math.pi * k / 9 for k in range(9))
    )
    sk.add(f'<g fill="{INK}">{dots}</g>'
           f'<circle cx="{_n(x)}" cy="{_n(y)}" r="{_n(r * 0.17)}" fill="#7a7d45" stroke="{INK}" stroke-width="0.8"/>'
           f'<path d="{rays}" stroke="{INK}" stroke-width="0.8"/>')


def bell(sk: Sketch, x, y, angle, size, color):
    """A foxglove flower: a tube widening to a lipped mouth."""
    up, lo = [], []
    for i in range(13):
        t = i / 12
        w = size * (0.12 + 0.3 * t**1.4)
        up.append((t * size, -w))
        lo.append((t * size * 1.08, w * 1.1))
    sk.reach(*_rot(x, y, angle, size, 0), size * 0.45)
    d = f"{_open(up)} Q{_n(size * 1.18)} 0 {_n(lo[-1][0])} {_n(lo[-1][1])} {_smooth(lo[::-1])} Z"
    spots = "".join(
        f'<circle cx="{_n(size * sk.r(0.62, 0.95))}" cy="{_n(size * sk.r(0.05, 0.28))}" r="{_n(sk.r(0.8, 1.6))}"/>'
        for _ in range(6)
    )
    sk.add(f'<g transform="translate({_n(x)} {_n(y)}) rotate({_n(angle)})">'
           f'<path d="{d}" fill="{color}" fill-opacity="0.93"/>'
           f'<path d="M0 0 {_smooth([(0, 0)] + lo[1:])} L{_n(size)} 0 Z" fill="url(#hatch)"/>'
           f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="0.9"/>'
           f'<g fill="#4a2335" opacity="0.7">{spots}</g></g>')


def clover_head(sk: Sketch, x, y, r):
    sk.reach(x, y, r)
    florets = []
    for ring, (count, dist) in enumerate(((16, 0.78), (12, 0.5), (7, 0.22))):
        for k in range(count):
            a = 360 * k / count + ring * 11 + sk.r(-6, 6)
            px, py = _rot(x, y, a, r * dist, 0)
            color = "#b3738a" if (k + ring) % 2 else "#cf9aab"
            florets.append(f'<ellipse cx="{_n(px)}" cy="{_n(py)}" rx="{_n(r * 0.34)}" ry="{_n(r * 0.12)}" '
                           f'transform="rotate({_n(a)} {_n(px)} {_n(py)})" fill="{color}" stroke="{INK}" stroke-width="0.5"/>')
    sk.add("".join(florets))


def acorn(sk: Sketch, x, y, angle, size):
    nx, ny = _rot(x, y, angle, size * 1.05, 0)
    sk.reach(nx, ny, size)
    sk.add(f'<g transform="translate({_n(x)} {_n(y)}) rotate({_n(angle)})">'
           f'<ellipse cx="{_n(size * 1.15)}" cy="0" rx="{_n(size * 0.75)}" ry="{_n(size * 0.48)}" fill="#8b6a3c" stroke="{INK}" stroke-width="0.9"/>'
           f'<path d="M{_n(size * 1.6)} -{_n(size * 0.18)} q{_n(size * 0.2)} {_n(size * 0.18)} 0 {_n(size * 0.36)}" stroke="#d9c49b" stroke-width="1.2" fill="none" opacity="0.7"/>'
           f'<path d="M{_n(size * 0.75)} -{_n(size * 0.55)} a{_n(size * 0.6)} {_n(size * 0.55)} 0 0 0 0 {_n(size * 1.1)} Z" fill="#a08455" stroke="{INK}" stroke-width="0.9"/>'
           f'<path d="M{_n(size * 0.75)} -{_n(size * 0.55)} a{_n(size * 0.6)} {_n(size * 0.55)} 0 0 0 0 {_n(size * 1.1)} Z" fill="url(#hatch)"/>'
           f'<line x1="{_n(size * 1.9)}" y1="0" x2="{_n(size * 2.05)}" y2="0" stroke="{INK}" stroke-width="1.4"/>'
           "</g>")


def berries(sk: Sketch, x, y, r, count):
    sk.reach(x, y, r * 3)
    out = []
    for _ in range(count):
        a, d = sk.r(0, 2 * math.pi), r * 1.6 * math.sqrt(sk.r(0, 1))
        bx, by = x + d * math.cos(a), y + d * math.sin(a)
        out.append(f'<path d="M{_n(x)} {_n(y + r * 2.2)} L{_n(bx)} {_n(by)}" stroke="{INK}" stroke-width="0.6"/>'
                   f'<circle cx="{_n(bx)}" cy="{_n(by)}" r="{_n(r)}" fill="#2f2a33" stroke="{INK}" stroke-width="0.6"/>'
                   f'<circle cx="{_n(bx - r * 0.3)}" cy="{_n(by - r * 0.35)}" r="{_n(r * 0.25)}" fill="#c9c2b0"/>')
    sk.add("".join(out))


# ---------------------------------------------------------------- plants


def draw_oak(sk: Sketch):
    main = walk(sk, 300, 880, -90 + sk.r(-6, 6), 560, curl=sk.r(-25, 25), wobble=2.5)
    side_i = sk.rng.randint(9, 13)
    side = walk(sk, *main[side_i], heading_at(main, side_i) + sk.rng.choice((-1, 1)) * sk.r(28, 40), 240,
                curl=sk.r(-20, 20), steps=12, wobble=3)
    for branch, w in ((side, 7), (main, 11)):
        stem(sk, branch, w, 3, BARK)
        last = len(branch) - 1
        for k in range(sk.rng.randint(4, 6)):
            i = max(1, last - k * 2 - sk.rng.randint(0, 1))
            angle = heading_at(branch, i) + (-1) ** k * sk.r(30, 70)
            leaf(sk, *branch[i], angle, sk.r(105, 140), sk.r(30, 38), "oak", "#6e7a3f", petiole=6, bend=sk.r(-1, 1), veins=5)
    cut_end(sk, main, 11)
    i = sk.rng.randint(14, 18)
    peduncle = walk(sk, *main[i], heading_at(main, i) + sk.r(50, 80), 70, curl=30, steps=8)
    stem(sk, peduncle, 2.5, 2, BARK)
    for a in (-30, 35):
        acorn(sk, *peduncle[-1], heading_at(peduncle, len(peduncle) - 1) + a, sk.r(22, 26))


def draw_ginkgo(sk: Sketch):
    main = walk(sk, 290, 880, -90 + sk.r(-8, 8), 520, curl=sk.r(-20, 20), wobble=2)
    stem(sk, main, 10, 4, BARK)
    cut_end(sk, main, 10)
    for i in (8, 15, 22, len(main) - 1):
        sx, sy = main[min(i, len(main) - 1)]
        sk.add(f'<circle cx="{_n(sx)}" cy="{_n(sy)}" r="5.5" fill="{BARK}" stroke="{INK}" stroke-width="0.8"/>')
        for _ in range(sk.rng.randint(3, 5)):
            angle = -90 + sk.r(-100, 100)
            size, petiole = sk.r(60, 82), sk.r(38, 80)
            spread, arc = 60, []
            for k in range(41):
                a = -spread + 2 * spread * k / 40
                r = size * (1 - 0.2 * math.exp(-((a / 6) ** 2))) * (1 + 0.025 * math.sin(k * 1.7))
                arc.append((petiole + r * math.cos(math.radians(a)), r * math.sin(math.radians(a))))
            sk.reach(*_rot(sx, sy, angle, petiole + size, 0), size * 0.9)
            d = (f"M{_n(petiole)} 0 Q{_n(petiole + size * 0.3)} {_n(arc[0][1] * 0.3)} {_n(arc[0][0])} {_n(arc[0][1])} "
                 f"{_smooth(arc)} Q{_n(petiole + size * 0.3)} {_n(arc[-1][1] * 0.3)} {_n(petiole)} 0 Z")
            ribs = " ".join(
                f"M{_n(petiole)} 0 L{_n(petiole + size * 0.93 * math.cos(math.radians(a)))} "
                f"{_n(size * 0.93 * math.sin(math.radians(a)))}"
                for a in range(-spread + 5, spread - 3, 6)
            )
            sk.add(f'<g transform="translate({_n(sx)} {_n(sy)}) rotate({_n(angle)})">'
                   f'<path d="M0 0 L{_n(petiole)} 0" stroke="{INK}" stroke-width="1.4"/>'
                   f'<path d="{d}" fill="#b89a3c" fill-opacity="0.92"/>'
                   f'<path d="{ribs}" stroke="{INK}" stroke-width="0.45" opacity="0.5"/>'
                   f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="1"/></g>')


def draw_maple(sk: Sketch):
    main = walk(sk, 300, 880, -90 + sk.r(-5, 5), 470, curl=sk.r(-18, 18), wobble=2)
    stem(sk, main, 10, 4, BARK)
    cut_end(sk, main, 10)
    color = sk.rng.choice(("#7a7238", "#8f5a33", "#6f7a3c"))
    lobes = [(0, 1.0), (48, 0.85), (-48, 0.85), (100, 0.5), (-100, 0.5)]
    for i, side in ((10, 1), (10, -1), (len(main) - 1, 0), (18, 1), (18, -1)):
        h = heading_at(main, i)
        angle = h + side * sk.r(40, 62) if side else h + sk.r(-10, 10)
        size = sk.r(78, 100) if i != 18 else sk.r(55, 70)
        palmate(sk, *main[i], angle, size, color, lobes, sigma=0.3, base=0.3, teeth=0.035,
                petiole=sk.r(70, 110) if i != 18 else 50)
    i = 24
    for side in (-1, 1):
        a = heading_at(main, i) + side * sk.r(95, 125)
        leaf(sk, *main[i], a, sk.r(70, 85), 15, "wing", "#b39a62", petiole=30, veins=4, bend=side * 0.8)
        sx, sy = _rot(*main[i], a, 34, 0)
        sk.add(f'<circle cx="{_n(sx)}" cy="{_n(sy)}" r="7" fill="#8b6a3c" stroke="{INK}" stroke-width="0.8"/>')


def draw_ash(sk: Sketch):
    rachis = walk(sk, 300, 885, -90 + sk.r(-10, 10), 640, curl=sk.r(-30, 30), steps=30, wobble=1.2)
    stem(sk, rachis, 7, 2.5, "#7a6a3e")
    cut_end(sk, rachis, 7)
    pairs = sk.rng.randint(4, 5)
    for k in range(pairs):
        i = 9 + k * (20 // pairs)
        h = heading_at(rachis, i)
        for side in (-1, 1):
            leaf(sk, *rachis[i], h + side * sk.r(52, 70), sk.r(115, 145), sk.r(22, 27), "lanceolate", "#5e6e3b",
                 petiole=4, bend=side * sk.r(0.3, 1.0), veins=7, serrate=0.05)
    leaf(sk, *rachis[-1], heading_at(rachis, len(rachis) - 1), sk.r(120, 140), 25, "lanceolate", "#5e6e3b",
         petiole=4, veins=7, serrate=0.05)


def draw_lavender(sk: Sketch):
    base_x = 300
    for s in range(sk.rng.randint(3, 5)):
        stalk = walk(sk, base_x + sk.r(-8, 8), 800, -90 + sk.r(-22, 22), sk.r(560, 700), curl=sk.r(-16, 16), wobble=0.8)
        stem(sk, stalk, 4, 2, "#7d8460")
        last = len(stalk) - 1
        for i in range(2, int(last * 0.45), 3):
            h = heading_at(stalk, i)
            for side in (-1, 1):
                leaf(sk, *stalk[i], h + side * sk.r(18, 32), sk.r(55, 75), 4.5, "linear", "#8a967a", steps=8, simple=True)
        spike = []
        for i in range(int(last * 0.72), last + 1):
            x, y = stalk[i]
            for side in (-1, 1, 0):
                spike.append(f'<ellipse cx="{_n(x + side * 4.5)}" cy="{_n(y)}" rx="3.4" ry="5.6" '
                             f'fill="#7f6ea3" stroke="{INK}" stroke-width="0.5"/>')
            sk.reach(x, y, 8)
        sk.add("".join(spike))
    roots(sk, base_x, 800, depth=3, length=50)


def draw_daisy(sk: Sketch):
    bx, by = 300, 790
    for k in range(sk.rng.randint(8, 11)):
        angle = -180 + 180 * k / 9 + sk.r(-10, 10)
        leaf(sk, bx, by, angle, sk.r(95, 135), sk.r(17, 22), "spatulate", "#64743a", veins=3, petiole=8)
    for k, (dx, height) in enumerate(((-1, sk.r(430, 520)), (1, sk.r(360, 450)), (0.2, sk.r(260, 320)))):
        scape = walk(sk, bx, by, -90 + dx * sk.r(8, 18), height, curl=dx * sk.r(5, 20), wobble=0.7)
        stem(sk, scape, 3.6, 2.2, "#73793f", hairs=10)
        hx, hy = scape[-1]
        if k < 2:
            daisy_head(sk, hx, hy, sk.r(38, 46))
        else:
            leaf(sk, hx, hy, -90, 26, 11, "bud", "#7a8048", veins=0)
    roots(sk, bx, by, depth=3, length=48)


def draw_foxglove(sk: Sketch):
    bx, by = 300, 810
    for k in range(5):
        angle = -180 + 45 * k + sk.r(-12, 12)
        leaf(sk, bx, by, angle, sk.r(150, 190), sk.r(42, 52), "ovate", "#66724a", petiole=20, bend=sk.r(-1, 1), veins=8)
    stalk = walk(sk, bx, by, -90 + sk.r(-4, 4), 700, curl=sk.r(-12, 12), wobble=0.6)
    stem(sk, stalk, 7, 2.4, "#6f7a45", hairs=16)
    last = len(stalk) - 1
    side = sk.rng.choice((-1, 1))
    for n, i in enumerate(range(9, last + 1)):
        h = heading_at(stalk, i)
        t = n / (last - 9)
        if t < 0.8:
            bell(sk, *stalk[i], h + side * (128 - 30 * t) + sk.r(-8, 8), 56 - 30 * t, "#9a6a8a")
        else:
            leaf(sk, *stalk[i], h + side * 60, 16, 6, "bud", "#8f7a6e", veins=0)


def draw_fern(sk: Sketch):
    rhizome = walk(sk, 170, 830, sk.r(-8, 8), 260, curl=sk.r(-15, 15), steps=12, wobble=3)
    stem(sk, rhizome, 12, 9, "#7a5a36", hairs=18)
    for f_i in range(sk.rng.randint(2, 3)):
        i = 3 + f_i * 4
        frond = walk(sk, *rhizome[i], -90 + sk.r(-28, 28), sk.r(540, 680), curl=sk.r(-30, 30), steps=30, wobble=0.5)
        stem(sk, frond, 4.5, 1.3, "#6b5a3a")
        last = len(frond) - 1
        fertile = f_i == 0
        for i2 in range(5, last):
            t = i2 / last
            size = 150 * (1 - t) ** 0.75 * min(1.0, 0.55 + t * 2.2)
            h = heading_at(frond, i2)
            for side in (-1, 1):
                angle = h + side * (72 - 22 * t)
                leaf(sk, *frond[i2], angle, size, max(4.0, size * 0.13), "oblong", "#57683a", steps=6, simple=True)
                if fertile and size > 40:
                    dots = "".join(
                        f'<circle cx="{_n(_rot(*frond[i2], angle, size * d, side * size * 0.06)[0])}" '
                        f'cy="{_n(_rot(*frond[i2], angle, size * d, side * size * 0.06)[1])}" r="2.1"/>'
                        for d in (0.35, 0.5, 0.65, 0.8)
                    )
                    sk.add(f'<g fill="#9b6a2e" stroke="{INK}" stroke-width="0.4">{dots}</g>')
    for i in range(0, len(rhizome), 2):
        roots(sk, *rhizome[i], depth=1, length=28)


def draw_ivy(sk: Sketch):
    vine = walk(sk, 150, 870, -62 + sk.r(-6, 6), 760, curl=sk.r(-30, 10), steps=34, wobble=6)
    stem(sk, vine, 7, 3, "#6a5a3a")
    cut_end(sk, vine, 7)
    tufts = []
    for i in range(2, len(vine) - 2, 2):
        x, y = vine[i]
        for _ in range(4):
            hx, hy = _rot(x, y, heading_at(vine, i) + 90 + sk.r(-25, 25), sk.r(5, 11), 0)
            tufts.append(f"M{_n(x)} {_n(y)} L{_n(hx)} {_n(hy)}")
    sk.add(f'<path d="{" ".join(tufts)}" stroke="{INK}" stroke-width="0.6" opacity="0.7"/>')
    lobes = [(0, 1.0), (62, 0.62), (-62, 0.62), (125, 0.32), (-125, 0.32)]
    for k, i in enumerate(range(3, len(vine), 4)):
        side = -1 if k % 2 else 1
        palmate(sk, *vine[i], heading_at(vine, i) + side * sk.r(55, 85), sk.r(52, 66), "#44553a", lobes,
                sigma=0.42, base=0.32, petiole=sk.r(40, 70), vein_color="#d8d0a8")
    berries(sk, *vine[-1], 7, 9)


def draw_poppy(sk: Sketch):
    bx, by = 300, 800
    for k in range(4):
        angle = -170 + 50 * k + sk.r(-10, 10)
        leaf(sk, bx, by, angle, sk.r(120, 160), sk.r(18, 24), "oak", "#6a7a45", veins=4, petiole=10)
    open_stalk = walk(sk, bx, by, -90 + sk.r(-6, 6), sk.r(520, 600), curl=sk.r(-20, 20), wobble=0.8)
    stem(sk, open_stalk, 4.5, 3, "#6d7840", hairs=24)
    poppy_flower(sk, *open_stalk[-1], sk.r(62, 74), sk.r(0, 90))
    bud_stalk = walk(sk, bx, by, -90 + sk.r(10, 18), sk.r(330, 400), curl=95, wobble=0.6)
    stem(sk, bud_stalk, 3.6, 2.6, "#6d7840", hairs=16)
    leaf(sk, *bud_stalk[-1], heading_at(bud_stalk, len(bud_stalk) - 1), 40, 16, "bud", "#77824a", veins=0)
    roots(sk, bx, by, depth=3, length=52)


def draw_willow(sk: Sketch):
    twig = walk(sk, 320, 885, -90 + sk.r(-14, 14), 680, curl=sk.r(-35, 35), steps=30, wobble=1.4)
    stem(sk, twig, 7, 2, "#8a6a3a")
    cut_end(sk, twig, 7)
    last = len(twig) - 1
    for k, i in enumerate(range(3, last + 1, 2)):
        side = -1 if k % 2 else 1
        leaf(sk, *twig[i], heading_at(twig, i) + side * sk.r(18, 38), sk.r(105, 150), sk.r(9, 12), "lanceolate",
             "#7d8a5a", petiole=6, bend=side * sk.r(0.2, 0.9), veins=9, serrate=0.04)
    leaf(sk, *twig[-1], heading_at(twig, last), 110, 10, "lanceolate", "#7d8a5a", petiole=4, veins=9)


def draw_clover(sk: Sketch):
    runner = walk(sk, 140, 810, sk.r(-14, -4), 330, curl=sk.r(-10, 10), steps=14, wobble=3)
    stem(sk, runner, 5, 3.5, "#6f7a43", hairs=12)
    for n, i in enumerate((2, 6, 10, 13)):
        petiole = walk(sk, *runner[i], -90 + sk.r(-35, 35), sk.r(160, 340), curl=sk.r(-20, 20), wobble=0.8)
        stem(sk, petiole, 2.8, 2, "#6f7a43", hairs=6)
        tip = petiole[-1]
        h = heading_at(petiole, len(petiole) - 1)
        if n in (1, 3):
            clover_head(sk, *tip, sk.r(40, 48))
            leaf(sk, *petiole[-4], h - 60, 50, 13, "elliptic", "#5b6e3a", veins=3)
            leaf(sk, *petiole[-4], h + 60, 50, 13, "elliptic", "#5b6e3a", veins=3)
        else:
            for a in (-62, 0, 62):
                leaf(sk, *tip, h + a, sk.r(64, 78), sk.r(23, 28), "obovate", "#5b6e3a", veins=4)
                cx, cy = _rot(*tip, h + a, 38, 0)
                sk.add(f'<path d="M{_n(cx - 6)} {_n(cy - 5)} L{_n(cx)} {_n(cy)} L{_n(cx - 6)} {_n(cy + 5)}" '
                       f'transform="rotate({_n(h + a)} {_n(cx)} {_n(cy)})" stroke="#d9d4ad" stroke-width="2.4" '
                       'fill="none" opacity="0.7"/>')
    for i in range(1, len(runner), 3):
        roots(sk, *runner[i], depth=2, length=36)


RECIPES = {
    "oak": draw_oak,
    "ginkgo": draw_ginkgo,
    "maple": draw_maple,
    "ash": draw_ash,
    "lavender": draw_lavender,
    "daisy": draw_daisy,
    "foxglove": draw_foxglove,
    "fern": draw_fern,
    "ivy": draw_ivy,
    "poppy": draw_poppy,
    "willow": draw_willow,
    "clover": draw_clover,
}


def draw(kind: str, seed: int) -> str:
    """Return the SVG of one specimen. Same kind and seed, same drawing."""
    sketch = Sketch(seed * 7919 + list(RECIPES).index(kind))
    RECIPES[kind](sketch)
    mount_straps(sketch)
    return sketch.svg()
