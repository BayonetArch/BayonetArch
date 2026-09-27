#!/usr/bin/env python3
"""Two-pass icon builder: draws, measures the real ink bounding box, then
re-emits each icon scaled + translated so every glyph shares the same optical
box. That matters because a baseline-aligned <img> aligns by its BOX bottom, so
icons with different ink offsets would sit at visibly different heights.

Target box (in the 24-unit viewBox): x centred on 12, ink spanning y 2.9..20.5.
Stroke width is pre-divided by the scale factor so the rendered stroke stays a
constant 1.8 everywhere and the set reads as one family.
"""
import os, re, subprocess, sys, zlib, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(HERE, "icons")
TMP = "/tmp/opencode/iconfit"
RENDER = 240.0          # px the 24-unit viewBox is rendered at
STROKE = 1.8
COLOUR = "#b4637a"
# Measured against a real 24px/600 heading: an icon band of 2.9..20.5 within
# the viewBox lands 1.5px above the cap-height centre once the <img> box is
# baseline-aligned. The band is therefore shifted down by 1.8 units (1.5px at a
# 20px render) to sit optically centred against the text.
TARGET_TOP, TARGET_BOT = 4.7, 22.3

SHAPES = {
    "about": """
<rect x="2.6" y="3.6" width="18.8" height="14" rx="2.6"/>
<path d="M6.6 8.4l2.7 2.6-2.7 2.6"/>
<path d="M12.2 14.1h5"/>""",
    "stack": """
<path d="M12 3.1l8.3 4.2-8.3 4.2-8.3-4.2z"/>
<path d="M3.7 11.6l8.3 4.2 8.3-4.2"/>
<path d="M3.7 15.4l8.3 4.2 8.3-4.2"/>""",
    "stats": """
<path d="M4 3.4v13.9a1.7 1.7 0 0 0 1.7 1.7H20.4"/>
<path d="M8.6 15.6v-3.9"/>
<path d="M13.1 15.6v-7.7"/>
<path d="M17.6 15.6v-10.6"/>""",
    "featured": """
<path d="M12 3.1l2.6 5.5 6 .9-4.3 4.2 1 6-5.3-2.9-5.3 2.9 1-6-4.3-4.2 6-.9z"/>""",
    "nekout": """
<rect x="2.6" y="3.6" width="18.8" height="14" rx="2.6"/>
<path d="M10.3 7.6l6.1 3.9-6.1 3.9z"/>""",
    "crate": """
<path d="M20.6 7.6v7.9a1.6 1.6 0 0 1-.85 1.39l-6.9 3.85a1.6 1.6 0 0 1-1.7 0l-6.9-3.85a1.6 1.6 0 0 1-.85-1.39V7.6"/>
<path d="M3.5 7.35l7.65-3.7a1.6 1.6 0 0 1 1.7 0l7.65 3.7-7.65 3.8a1.6 1.6 0 0 1-1.7 0z"/>
<path d="M12 11.3v9.9"/>""",
    "flask": """
<path d="M9.4 3.3h5.2"/>
<path d="M10.6 3.3v5.9L5 16.9a2 2 0 0 0 1.72 3.05h10.56A2 2 0 0 0 19 16.9L13.4 9.2V3.3"/>
<path d="M7.7 13.7h8.6"/>""",
    "contact": """
<rect x="2.6" y="4.6" width="18.8" height="13.4" rx="2.6"/>
<path d="M3.6 6.9l7.5 5.1a2 2 0 0 0 2.2 0l7.5-5.1"/>""",
    "zoom": """
<circle cx="10.4" cy="9.4" r="6.3"/>
<path d="M15.1 14.1l4.8 4.8"/>""",
    "rocket": """
<path d="M12 2.6c2.95 2.4 4.55 5.85 4.55 9.5l1.35 3.1-3.15-.85a10.9 10.9 0 0 1-5.5 0l-3.15.85 1.35-3.1c0-3.65 1.6-7.1 4.55-9.5z"/>
<circle cx="12" cy="9.7" r="1.85"/>
<path d="M9.5 15.2c-.7 1.4-1 2.85-1 4.25 1.4 0 2.85-.3 4.25-1"/>
<path d="M14.5 15.2c.7 1.4 1 2.85 1 4.25-1.4 0-2.85-.3-4.25-1"/>""",
    "window": """
<rect x="2.6" y="3.6" width="18.8" height="14" rx="2.6"/>
<path d="M2.6 8.5h18.8"/>
<path d="M12 8.5v9.1"/>""",
    "clapper": """
<path d="M3.4 10.2h17.2v7.4a2 2 0 0 1-2 2H5.4a2 2 0 0 1-2-2z"/>
<path d="M4.1 4.4l16.1 2.6-1.2 3.9L2.9 8.3z"/>""",

    # download into a tray
    "download": """
<path d="M12 3.4v11.2"/>
<path d="M7.4 10.4L12 15l4.6-4.6"/>
<path d="M3.9 17.4v1.5a2 2 0 0 0 2 2h12.2a2 2 0 0 0 2-2v-1.5"/>""",

    # globe
    "globe": """
<circle cx="12" cy="12" r="8.9"/>
<path d="M3.1 12h17.8"/>
<path d="M12 3.1c2.55 2.45 3.9 5.55 3.9 8.9S14.55 18.45 12 20.9c-2.55-2.45-3.9-5.55-3.9-8.9S9.45 5.55 12 3.1z"/>""",

    # git branch
    "git": """
<circle cx="6.4" cy="5.6" r="2.3"/>
<circle cx="6.4" cy="18.4" r="2.3"/>
<circle cx="17.6" cy="9.2" r="2.3"/>
<path d="M6.4 7.9v8.2"/>
<path d="M17.6 11.5c0 3.1-2.5 4.5-5.6 5"/>""",

    # briefcase
    "briefcase": """
<rect x="2.9" y="6.9" width="18.2" height="13" rx="2.2"/>
<path d="M8.7 6.9V5.3a1.6 1.6 0 0 1 1.6-1.6h3.4a1.6 1.6 0 0 1 1.6 1.6v1.6"/>
<path d="M2.9 12.4h18.2"/>""",

    # play
    "play": """
<path d="M7.6 4.6l12.2 7.4-12.2 7.4z"/>""",
}


def emit(name, body, transform=None, stroke=STROKE):
    hdr = ('xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{COLOUR}" stroke-width="{stroke:.3f}" stroke-linecap="round" '
           'stroke-linejoin="round"')
    inner = body.strip()
    if transform:
        inner = f'<g transform="{transform}">\n{inner}\n</g>'
    svg = f"<svg {hdr} width=\"24\" height=\"24\">\n{inner}\n</svg>\n"
    with open(os.path.join(ICONS, name + ".svg"), "w") as f:
        f.write(svg)


def render(name):
    """Render one icon and return its ink bbox in 24-unit viewBox coords."""
    png = os.path.join(TMP, name + ".png")
    html = os.path.join(TMP, name + ".html")
    with open(html, "w") as f:
        f.write('<html><body style="margin:0;background:#fff">'
                f'<img src="file://{os.path.join(ICONS, name)}.svg" '
                f'width="{int(RENDER)}" height="{int(RENDER)}"></body></html>')
    subprocess.run(["chromium-browser", "--headless", "--disable-gpu", "--no-sandbox",
                    "--hide-scrollbars", f"--screenshot={png}",
                    f"--window-size={int(RENDER)},{int(RENDER)}", f"file://{html}"],
                   capture_output=True, timeout=90)
    d = open(png, "rb").read()
    pos, idat, w, h, bd, ct = 8, b"", 0, 0, 0, 0
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos + 4])[0]
        t = d[pos + 4:pos + 8]
        if t == b"IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", d[pos + 8:pos + 18])
        elif t == b"IDAT":
            idat += d[pos + 8:pos + 8 + ln]
        elif t == b"IEND":
            break
        pos += 12 + ln
    raw = zlib.decompress(idat)
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    stride = w * nch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        if ft == 1:
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 255
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                c = prev[i - nch] if i >= nch else 0
                b = prev[i]
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line
    k = RENDER / 24.0
    xs, ys = [], []
    for i in range(0, len(out), nch):
        if out[i] < 245 or out[i + 1] < 245 or out[i + 2] < 245:
            q = i // nch
            xs.append(q % w)
            ys.append(q // w)
    if not xs:
        return None
    return (min(xs) / k, min(ys) / k, (max(xs) + 1) / k, (max(ys) + 1) / k)


os.makedirs(TMP, exist_ok=True)
names = list(SHAPES)

# pass 1 - raw, untransformed
for n in names:
    emit(n, SHAPES[n])
box1 = {}
for n in names:
    box1[n] = render(n)
    if box1[n] is None:
        sys.exit(f"FATAL: {n} rendered no ink")

# pass 2 - fit every glyph into the shared optical box
fits = {}
for n in names:
    x0, y0, x1, y1 = box1[n]
    s = (TARGET_BOT - TARGET_TOP) / (y1 - y0)
    tx = 12.0 - s * ((x0 + x1) / 2.0)
    ty = TARGET_TOP - s * y0
    fits[n] = (s, tx, ty)
    emit(n, SHAPES[n], f"translate({tx:.3f},{ty:.3f}) scale({s:.4f})", STROKE / s)

print("pass 1 raw ink heights / pass 2 scale factors")
for n in names:
    x0, y0, x1, y1 = box1[n]
    print("  %-9s h=%5.2f  ->  scale %.3f" % (n, y1 - y0, fits[n][0]))

# verify
print("\nverification (target: top %.1f, bottom %.1f, centred on 12.0)"
      % (TARGET_TOP, TARGET_BOT))
ok = True
for n in names:
    b = render(n)
    x0, y0, x1, y1 = b
    h, cx = y1 - y0, (x0 + x1) / 2
    good = abs(y0 - TARGET_TOP) < 0.45 and abs(y1 - TARGET_BOT) < 0.45 and abs(cx - 12) < 0.3
    ok &= good
    print("  %-9s top=%5.2f bot=%5.2f h=%5.2f cx=%5.2f w=%5.2f  %s"
          % (n, y0, y1, h, cx, x1 - x0, "ok" if good else "<-- OFF"))
print("\nall icons normalised:", ok)
