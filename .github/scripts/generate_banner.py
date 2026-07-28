#!/usr/bin/env python3
"""
Generate the theme-aware hero banner (dark.svg + light.svg) from profile.json.

Everything the banner shows — name, role, stack rows, terminal script, metric
bars — comes from profile.json. Edit that file, re-run this script, and both
themes stay in sync. Nothing about the author is hard-coded here.

Layout (1200 x 620, viewBox-scaled so it stays responsive in any README):

    +--------------------------------------------------------------+
    | traffic lights        owais@dev ~ % ./profile.sh --live       |
    +---------------------------+----------------------------------+
    | DEV.TERMINAL              | SYSTEM.PROFILE            * LIVE |
    |  animated typing +        |  name (typed, gradient)          |
    |  syntax-lit code block    |  tagline                         |
    |---------------------------|  dotted-leader dossier rows      |
    | ACTIVITY.MONITOR          |  - Stack ----------------------- |
    |  animated proficiency     |  - Contact --------------------- |
    |  bars + counters          |                                  |
    +---------------------------+----------------------------------+

Ambient layers, back to front: gradient lighting blobs, dot grid, drifting
particles, a slow scan line, then the panels, then the glowing frame.

Usage:  python3 .github/scripts/generate_banner.py [profile.json] [outdir]
"""
import html
import json
import os
import random
import sys

# ---------------------------------------------------------------- canvas ----
W, H = 1200, 620
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

# left column (terminal + monitor). The two panels plus the gap between them
# span 86 -> 578; adjust TERM_H and MON_H together or the stack drifts.
LX, LW = 32, 496
TERM_Y, TERM_H = 86, 310
MON_LABEL_Y = 414
MON_Y, MON_H = 422, 156

# right column (dossier)
RX, RW = 556, 612

MONO_RATIO = 0.601  # advance width of one char in a monospace face, per em


# ---------------------------------------------------------------- themes ----
THEMES = {
    "dark": {
        "BG": "#0D1117", "BG2": "#0F1626",
        "PANEL": "#0F1523", "PANEL_BAR": "#131C2E", "TITLEBAR": "#111827",
        "PRIMARY": "#3B82F6", "SECONDARY": "#06B6D4", "ACCENT": "#8B5CF6",
        "SUCCESS": "#10B981", "ALERT": "#F87171",
        "TEXT": "#F8FAFC", "MUTED": "#94A3B8", "DIM": "#475569",
        "LINE": "rgba(255,255,255,0.08)",
        "DOTS": "rgba(148,163,184,0.30)",
        "TRACK": "rgba(148,163,184,0.16)",
        "GRID": "rgba(148,163,184,0.06)",
        "PANEL_STROKE": "rgba(59,130,246,0.30)",
        "PANEL_STROKE_HI": "rgba(6,182,212,0.55)",
        "CODE_KEY": "#38BDF8", "CODE_STR": "#A78BFA", "CODE_PUNC": "#64748B",
        "MONOGRAM_TX": "#F5F3FF",
        "SCAN": "rgba(59,130,246,0.16)",
        "GLOW_A": 0.42, "GLOW_B": 0.34,
    },
    "light": {
        "BG": "#F8FAFC", "BG2": "#EDF2F9",
        "PANEL": "#FFFFFF", "PANEL_BAR": "#F1F5F9", "TITLEBAR": "#E9EFF7",
        "PRIMARY": "#2563EB", "SECONDARY": "#0891B2", "ACCENT": "#7C3AED",
        "SUCCESS": "#059669", "ALERT": "#DC2626",
        "TEXT": "#0F172A", "MUTED": "#475569", "DIM": "#94A3B8",
        "LINE": "rgba(15,23,42,0.10)",
        "DOTS": "rgba(71,85,105,0.28)",
        "TRACK": "rgba(71,85,105,0.14)",
        "GRID": "rgba(15,23,42,0.05)",
        "PANEL_STROKE": "rgba(37,99,235,0.28)",
        "PANEL_STROKE_HI": "rgba(8,145,178,0.50)",
        "CODE_KEY": "#0369A1", "CODE_STR": "#7C3AED", "CODE_PUNC": "#64748B",
        "MONOGRAM_TX": "#FFFFFF",
        "SCAN": "rgba(37,99,235,0.10)",
        "GLOW_A": 0.30, "GLOW_B": 0.24,
    },
}

C = {}          # active palette, populated by set_theme()
SUFFIX = ""     # id namespace so both themes can coexist on one page


def set_theme(name):
    global C, SUFFIX
    C = THEMES[name]
    SUFFIX = name


def uid(base):
    return f"{base}_{SUFFIX}"


def esc(s):
    return html.escape(str(s), quote=True)


def cw(size):
    """Advance width of one monospace character at the given font size."""
    return size * MONO_RATIO


# ------------------------------------------------------------- primitives ---
def typing(gid, x, y, segs, begin, size=12, cps=26, caret=True, hold=None):
    """Character-by-character reveal.

    A clip rect widens one glyph at a time (calcMode="discrete", so it steps
    rather than slides) while a caret block hops along with it. After typing,
    the caret blinks until `hold` seconds have passed; pass hold=None to let it
    blink forever, which is what the final line wants.

    segs: [(text, fill, weight_or_None), ...]  ->  returns (defs, body)
    """
    full = "".join(s[0] for s in segs)
    n = len(full)
    adv = cw(size)
    dur = max(0.14, n / cps)

    widths = ";".join(f"{i * adv:.2f}" for i in range(n + 1))
    xs = ";".join(f"{x + i * adv:.2f}" for i in range(n + 1))
    keys = ";".join(f"{i / n:.4f}" for i in range(n + 1))

    defs = (
        f'<clipPath id="{gid}">'
        f'<rect x="{x - 1}" y="{y - size:.1f}" width="0" height="{size * 1.6:.1f}">'
        f'<animate attributeName="width" values="{widths}" keyTimes="{keys}" '
        f'calcMode="discrete" dur="{dur:.2f}s" begin="{begin:.2f}s" fill="freeze"/>'
        f'</rect></clipPath>'
    )

    tspans = "".join(
        f'<tspan fill="{fill}"{f" font-weight=\"{wt}\"" if wt else ""}>{esc(t)}</tspan>'
        for t, fill, wt in segs
    )
    body = [
        f'<g clip-path="url(#{gid})">'
        f'<text x="{x}" y="{y}" font-size="{size}" xml:space="preserve">{tspans}</text></g>'
    ]

    if caret:
        blink_end = (
            f'<set attributeName="opacity" to="0" begin="{begin + dur + hold:.2f}s"/>'
            if hold is not None else ""
        )
        body.append(
            f'<rect x="{x:.1f}" y="{y - size * 0.82:.1f}" width="{adv:.1f}" '
            f'height="{size * 1.02:.1f}" rx="1" fill="{C["SECONDARY"]}" opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{begin:.2f}s"/>'
            f'<animate attributeName="x" values="{xs}" keyTimes="{keys}" calcMode="discrete" '
            f'dur="{dur:.2f}s" begin="{begin:.2f}s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="1;0;1" dur="0.9s" '
            f'begin="{begin + dur:.2f}s" repeatCount="indefinite"/>'
            f'{blink_end}</rect>'
        )
    return defs, "".join(body), dur


def fade_in(inner, begin, dur=0.45, dx=0):
    """Wrap markup in a group that fades (and optionally slides) into view."""
    slide = (
        f'<animateTransform attributeName="transform" type="translate" '
        f'values="{dx} 0;0 0" dur="{dur:.2f}s" begin="{begin:.2f}s" fill="freeze"/>'
        if dx else ""
    )
    return (
        f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" '
        f'dur="{dur:.2f}s" begin="{begin:.2f}s" fill="freeze"/>{slide}{inner}</g>'
    )


def leader_row(label, value, y, begin, size=13):
    """A dossier line: `Label ......... Value`, justified to the column width.

    textLength + lengthAdjust pins every row to exactly RW pixels, so the values
    line up flush right no matter how the viewer's monospace font measures.
    """
    budget = int(RW / cw(size))
    dots = max(3, budget - len(label) - len(value) - 2)
    inner = (
        f'<text x="{RX}" y="{y}" font-size="{size}" textLength="{RW}" '
        f'lengthAdjust="spacingAndGlyphs" xml:space="preserve">'
        f'<tspan fill="{C["SECONDARY"]}">{esc(label)} </tspan>'
        f'<tspan fill="{C["DOTS"]}">{"." * dots}</tspan>'
        f'<tspan fill="{C["TEXT"]}" font-weight="600"> {esc(value)}</tspan></text>'
    )
    return fade_in(inner, begin, 0.4, dx=-10)


def divider_row(label, y, begin, size=13):
    budget = int(RW / cw(size))
    rule = max(3, budget - len(label) - 4)
    inner = (
        f'<text x="{RX}" y="{y}" font-size="{size}" textLength="{RW}" '
        f'lengthAdjust="spacingAndGlyphs" xml:space="preserve">'
        f'<tspan fill="{C["ACCENT"]}">&#9670; {esc(label)} </tspan>'
        f'<tspan fill="{C["DOTS"]}">{"&#8212;" * rule}</tspan></text>'
    )
    return fade_in(inner, begin, 0.4)


def panel(x, y, w, h, begin=0.0, pulse_offset=0.0):
    """Rounded panel with a slowly breathing accent border."""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{C["PANEL"]}" '
        f'stroke="{C["PANEL_STROKE"]}">'
        f'<animate attributeName="stroke" values="{C["PANEL_STROKE"]};'
        f'{C["PANEL_STROKE_HI"]};{C["PANEL_STROKE"]}" dur="5.5s" '
        f'begin="{pulse_offset:.2f}s" repeatCount="indefinite"/></rect>'
    )


def section_label(x, y, text, note=""):
    out = (f'<text x="{x}" y="{y}" font-size="10" letter-spacing="2.6" '
           f'fill="{C["PRIMARY"]}">{esc(text)}</text>')
    if note:
        out += (f'<text x="{x + len(text) * 7.6 + 18:.0f}" y="{y}" font-size="9.5" '
                f'fill="{C["DIM"]}">{esc(note)}</text>')
    return out


# ------------------------------------------------------------ ambient art ---
def lighting():
    """Two large, slowly breathing radial washes — the 'gradient lighting'."""
    return (
        f'<ellipse cx="215" cy="150" rx="330" ry="240" fill="url(#{uid("glowA")})">'
        f'<animate attributeName="opacity" values="0.75;1;0.75" dur="9s" repeatCount="indefinite"/>'
        f'</ellipse>'
        f'<ellipse cx="1000" cy="520" rx="360" ry="260" fill="url(#{uid("glowB")})">'
        f'<animate attributeName="opacity" values="1;0.7;1" dur="11s" repeatCount="indefinite"/>'
        f'</ellipse>'
        f'<ellipse cx="620" cy="60" rx="420" ry="150" fill="url(#{uid("glowC")})">'
        f'<animate attributeName="opacity" values="0.6;0.95;0.6" dur="13s" repeatCount="indefinite"/>'
        f'</ellipse>'
    )


def dot_grid():
    """Sparse dot lattice — structure without noise."""
    dots = "".join(
        f'<circle cx="{x}" cy="{y}" r="1"/>'
        for y in range(70, H, 34) for x in range(24, W, 34)
    )
    return f'<g fill="{C["GRID"]}">{dots}</g>'


def particles(rng, count=30):
    """Drifting motes. Negative begins mean they are already mid-flight on
    first paint, so the banner never opens on a static frame."""
    palette = [C["PRIMARY"], C["SECONDARY"], C["ACCENT"]]
    out = []
    for _ in range(count):
        x = rng.uniform(20, W - 20)
        y = rng.uniform(60, H - 20)
        r = rng.uniform(0.8, 2.2)
        col = rng.choice(palette)
        op = rng.uniform(0.18, 0.55)
        rise = rng.uniform(14, 42)
        dur = rng.uniform(7, 15)
        delay = -rng.uniform(0, dur)
        out.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{col}" opacity="{op:.2f}">'
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="0 0;0 {-rise:.1f};0 0" dur="{dur:.1f}s" begin="{delay:.2f}s" '
            f'repeatCount="indefinite" calcMode="spline" keyTimes="0;0.5;1" '
            f'keySplines="0.4 0 0.6 1;0.4 0 0.6 1"/>'
            f'<animate attributeName="opacity" values="{op:.2f};{op * 0.15:.2f};{op:.2f}" '
            f'dur="{dur * 0.6:.1f}s" begin="{delay:.2f}s" repeatCount="indefinite"/>'
            f'</circle>'
        )
    return "".join(out)


def scan_line():
    return (
        f'<rect x="2" y="48" width="1196" height="88" fill="url(#{uid("scan")})" opacity="0.9">'
        f'<animateTransform attributeName="transform" type="translate" '
        f'values="0 -90;0 {H};0 -90" dur="14s" repeatCount="indefinite"/></rect>'
    )


def corner_brackets():
    """Four thin L-brackets — a quiet HUD cue at the frame corners."""
    a, m, ln = 18, 34, C["PRIMARY"]
    pts = [
        (a, a, 1, 1), (W - a, a, -1, 1), (a, H - a, 1, -1), (W - a, H - a, -1, -1),
    ]
    out = []
    for x, y, sx, sy in pts:
        out.append(
            f'<path d="M{x} {y + sy * m} L{x} {y} L{x + sx * m} {y}" fill="none" '
            f'stroke="{ln}" stroke-width="1.6" stroke-linecap="round" opacity="0.35">'
            f'<animate attributeName="opacity" values="0.18;0.5;0.18" dur="6s" '
            f'repeatCount="indefinite"/></path>'
        )
    return "".join(out)


# ---------------------------------------------------------------- regions ---
def title_bar(p):
    handle = p["username"].lower().split("-")[-1]
    title = f'{handle}@dev  ~  % ./profile.sh --live'
    lights = "".join(
        f'<circle cx="{cx}" cy="25" r="5.5" fill="{col}"/>'
        for cx, col in ((30, "#FF5F57"), (50, "#FEBC2E"), (70, "#28C840"))
    )
    return (
        f'<rect x="2" y="2" width="1196" height="46" fill="{C["TITLEBAR"]}"/>'
        f'<line x1="2" y1="48" x2="1198" y2="48" stroke="{C["LINE"]}"/>'
        f'{lights}'
        f'<text x="600" y="29" text-anchor="middle" font-size="12" '
        f'fill="{C["MUTED"]}">{esc(title)}</text>'
        f'<text x="1166" y="29" text-anchor="end" font-size="11" fill="{C["DIM"]}">'
        f'main <tspan fill="{C["SUCCESS"]}">&#9679;</tspan></text>'
    )


def terminal(p, t0=0.55):
    """Animated shell session driven by profile.json -> terminal[]."""
    defs, body = [], []
    x0, y0 = LX + 20, TERM_Y + 64
    size, step = 12, 18

    body.append(panel(LX, TERM_Y, LW, TERM_H, pulse_offset=0.0))
    body.append(f'<rect x="{LX}" y="{TERM_Y}" width="{LW}" height="30" rx="12" '
                f'fill="{C["PANEL_BAR"]}"/>')
    body.append(f'<rect x="{LX}" y="{TERM_Y + 18}" width="{LW}" height="12" '
                f'fill="{C["PANEL_BAR"]}"/>')
    body.append(f'<line x1="{LX}" y1="{TERM_Y + 30}" x2="{LX + LW}" y2="{TERM_Y + 30}" '
                f'stroke="{C["LINE"]}"/>')
    for i, col in enumerate((C["ALERT"], "#FEBC2E", C["SUCCESS"])):
        body.append(f'<circle cx="{LX + 18 + i * 15}" cy="{TERM_Y + 15}" r="4" '
                    f'fill="{col}" opacity="0.85"/>')
    body.append(f'<text x="{LX + LW - 16}" y="{TERM_Y + 19}" text-anchor="end" '
                f'font-size="9.5" fill="{C["DIM"]}">zsh &#8212; 80&#215;24</text>')

    lines = p.get("terminal", [])
    t = t0
    row = 0
    for i, ln in enumerate(lines):
        kind = ln["type"]
        y = y0 + row * step

        if kind == "gap":
            row += 1
            t += 0.12
            continue

        if kind == "cmd":
            segs = [("$ ", C["SUCCESS"], "700"), (ln["text"], C["TEXT"], None)]
            # every command caret retires once typed — the trailing prompt at the
            # bottom of the session owns the one cursor that blinks forever
            d, b, dur = typing(uid(f"tt{i}"), x0, y, segs, t, size=size, hold=0.05)
            defs.append(d)
            body.append(b)
            t += dur + 0.32

        elif kind == "code":
            body.append(fade_in(
                f'<text x="{x0}" y="{y}" font-size="{size}" xml:space="preserve">'
                f'{code_spans(ln["text"])}</text>', t, 0.32, dx=-6))
            t += 0.2

        elif kind == "ok":
            inner = (
                f'<text x="{x0}" y="{y}" font-size="{size}" xml:space="preserve">'
                f'<tspan fill="{C["SUCCESS"]}" font-weight="700">&#10003; </tspan>'
                f'<tspan fill="{C["MUTED"]}">{esc(ln["text"])}</tspan></text>'
            )
            body.append(fade_in(inner, t, 0.35, dx=-6))
            t += 0.3

        else:  # "out"
            inner = (
                f'<text x="{x0}" y="{y}" font-size="{size}" xml:space="preserve">'
                f'<tspan fill="{C["SECONDARY"]}">{esc(ln["text"])}</tspan></text>'
            )
            body.append(fade_in(inner, t, 0.35, dx=-6))
            t += 0.3

        row += 1

    # trailing prompt with an eternally blinking block cursor
    y = y0 + row * step
    body.append(fade_in(
        f'<text x="{x0}" y="{y}" font-size="{size}">'
        f'<tspan fill="{C["SUCCESS"]}" font-weight="700">$ </tspan>'
        f'<tspan fill="{C["SECONDARY"]}">&#9608;'
        f'<animate attributeName="fill-opacity" values="1;0;1" dur="1s" '
        f'repeatCount="indefinite"/></tspan></text>', t + 0.1))

    return "".join(defs), "".join(body), t


def code_spans(text):
    """Cheap JSON-ish highlighter: keys cyan, strings violet, punctuation dim."""
    out, buf, i = [], "", 0

    def flush(fill=None):
        nonlocal buf
        if buf:
            out.append(f'<tspan fill="{fill or C["CODE_PUNC"]}">{esc(buf)}</tspan>')
            buf = ""

    while i < len(text):
        ch = text[i]
        if ch == '"':
            j = text.find('"', i + 1)
            if j == -1:
                buf += ch
                i += 1
                continue
            token = text[i:j + 1]
            # a quoted token immediately followed by ':' is a key
            rest = text[j + 1:].lstrip()
            fill = C["CODE_KEY"] if rest.startswith(":") else C["CODE_STR"]
            flush()
            out.append(f'<tspan fill="{fill}">{esc(token)}</tspan>')
            i = j + 1
        else:
            buf += ch
            i += 1
    flush()
    return "".join(out)


def monitor(p, t0=1.15):
    """Proficiency dashboard: animated bars with stepped count-up readouts."""
    body = [panel(LX, MON_Y, LW, MON_H, pulse_offset=1.4)]
    body.append(f'<rect x="{LX}" y="{MON_Y}" width="{LW}" height="28" rx="12" '
                f'fill="{C["PANEL_BAR"]}"/>')
    body.append(f'<rect x="{LX}" y="{MON_Y + 16}" width="{LW}" height="12" '
                f'fill="{C["PANEL_BAR"]}"/>')
    body.append(f'<line x1="{LX}" y1="{MON_Y + 28}" x2="{LX + LW}" y2="{MON_Y + 28}" '
                f'stroke="{C["LINE"]}"/>')
    body.append(f'<text x="{LX + 16}" y="{MON_Y + 18}" font-size="9.5" '
                f'letter-spacing="1.6" fill="{C["MUTED"]}">STACK.PROFICIENCY</text>')
    body.append(
        f'<text x="{LX + LW - 16}" y="{MON_Y + 18}" text-anchor="end" font-size="9.5" '
        f'fill="{C["SUCCESS"]}">&#9650; live'
        f'<animate attributeName="opacity" values="1;0.35;1" dur="2.2s" '
        f'repeatCount="indefinite"/></text>')

    label_x = LX + 18
    track_x = LX + 130
    track_w = 268
    pct_x = LX + LW - 18

    for i, (label, target) in enumerate(p.get("metrics", [])):
        y = MON_Y + 52 + i * 28
        begin = t0 + i * 0.18
        fill_w = track_w * target / 100.0

        body.append(f'<text x="{label_x}" y="{y + 4}" font-size="11" '
                    f'fill="{C["MUTED"]}">{esc(label)}</text>')
        body.append(f'<rect x="{track_x}" y="{y - 3}" width="{track_w}" height="7" '
                    f'rx="3.5" fill="{C["TRACK"]}"/>')
        body.append(
            f'<rect x="{track_x}" y="{y - 3}" width="0" height="7" rx="3.5" '
            f'fill="url(#{uid("barGrad")})">'
            f'<animate attributeName="width" from="0" to="{fill_w:.1f}" dur="1.1s" '
            f'begin="{begin:.2f}s" fill="freeze" calcMode="spline" keyTimes="0;1" '
            f'keySplines="0.22 1 0.36 1"/></rect>')
        # travelling highlight that rides the filled portion
        body.append(
            f'<rect x="{track_x}" y="{y - 3}" width="26" height="7" rx="3.5" '
            f'fill="{C["TEXT"]}" opacity="0">'
            f'<animate attributeName="opacity" values="0;0.22;0" dur="2.6s" '
            f'begin="{begin + 1.1:.2f}s" repeatCount="indefinite"/>'
            f'<animate attributeName="x" from="{track_x}" to="{track_x + fill_w - 26:.1f}" '
            f'dur="2.6s" begin="{begin + 1.1:.2f}s" repeatCount="indefinite"/></rect>')

        # stepped count-up: one <text> per frame, swapped by <set>
        steps = 8
        frame = 1.1 / steps
        for k in range(steps + 1):
            val = round(target * k / steps)
            show = begin + k * frame
            hide = (f'<set attributeName="opacity" to="0" '
                    f'begin="{show + frame:.2f}s"/>' if k < steps else "")
            body.append(
                f'<text x="{pct_x}" y="{y + 4}" text-anchor="end" font-size="11" '
                f'font-weight="700" fill="{C["TEXT"]}" opacity="0">{val}%'
                f'<set attributeName="opacity" to="1" begin="{show:.2f}s"/>{hide}</text>')

    return "".join(body)


def dossier(p, t0=0.45):
    """Right-hand identity panel: typed name, tagline, dotted-leader rows."""
    defs, body = [], []

    body.append(section_label(RX, 76, "SYSTEM.PROFILE"))
    body.append(
        f'<text x="{RX + RW}" y="76" text-anchor="end" font-size="11" '
        f'font-weight="700" fill="{C["ALERT"]}"><tspan>&#9679;</tspan> LIVE'
        f'<animate attributeName="opacity" values="1;0.3;1" dur="1.6s" '
        f'repeatCount="indefinite"/></text>')
    body.append(f'<line x1="{RX}" y1="86" x2="{RX + RW}" y2="86" '
                f'stroke="url(#{uid("accent")})" stroke-width="1.5" opacity="0.75"/>')

    # name — typed, gradient-filled, with a soft glow
    d, b, dur = typing(
        uid("name"), RX, 122, [(p["name"], f'url(#{uid("nameGrad")})', "700")],
        t0, size=30, cps=17, hold=0.6)
    defs.append(d)
    body.append(f'<g filter="url(#{uid("textGlow")})">{b}</g>')

    t = t0 + dur + 0.15
    body.append(fade_in(
        f'<text x="{RX}" y="148" font-size="12.5" fill="{C["MUTED"]}">'
        f'{esc(p["tagline"])}</text>', t))
    t += 0.28

    rows = [
        ("Role", p["role"]),
        ("Location", p["location"]),
        ("Education", p["education"]),
        ("Currently", p["company"]),
        ("Status", p["status"]),
    ]
    y = 182
    for label, value in rows:
        body.append(leader_row(label, value, y, t))
        y += 22
        t += 0.11

    t += 0.08
    body.append(divider_row("Stack", y + 6, t))
    y += 30
    t += 0.12
    for label, value in p.get("stack", []):
        body.append(leader_row(label, value, y, t))
        y += 22
        t += 0.11

    t += 0.08
    body.append(divider_row("Connect", y + 6, t))
    y += 30
    t += 0.12
    for label, value in (
        ("Email", p["email"]),
        ("Portfolio", p["portfolio"]),
        ("LinkedIn", p["linkedin"]),
        ("GitHub", "@" + p["username"]),
    ):
        body.append(leader_row(label, value, y, t))
        y += 22
        t += 0.11

    body.append(fade_in(
        f'<text x="{RX}" y="{y + 14}" font-size="12.5" fill="{C["MUTED"]}">'
        f'&#9656; Stats, projects and more below '
        f'<tspan fill="{C["SECONDARY"]}">&#8595;</tspan> '
        f'<tspan fill="{C["ACCENT"]}">&#9608;'
        f'<animate attributeName="fill-opacity" values="1;0;1" dur="1s" '
        f'repeatCount="indefinite"/></tspan></text>', t + 0.2))

    return "".join(defs), "".join(body)


# ------------------------------------------------------------------ build ---
def build(p, theme):
    set_theme(theme)
    rng = random.Random(20260728)  # fixed seed -> byte-stable regeneration

    term_defs, term_body, _ = terminal(p)
    doss_defs, doss_body = dossier(p)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" '
        f'aria-label="{esc(p["name"])} — {esc(p["role"])} — {esc(p["tagline"])}">',
        '<defs>',

        # animated tri-colour accent used by the frame and rules
        f'<linearGradient id="{uid("accent")}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{C["PRIMARY"]}"><animate attributeName="stop-color" '
        f'values="{C["PRIMARY"]};{C["SECONDARY"]};{C["ACCENT"]};{C["PRIMARY"]}" '
        f'dur="10s" repeatCount="indefinite"/></stop>'
        f'<stop offset="0.5" stop-color="{C["SECONDARY"]}"><animate attributeName="stop-color" '
        f'values="{C["SECONDARY"]};{C["ACCENT"]};{C["PRIMARY"]};{C["SECONDARY"]}" '
        f'dur="10s" repeatCount="indefinite"/></stop>'
        f'<stop offset="1" stop-color="{C["ACCENT"]}"><animate attributeName="stop-color" '
        f'values="{C["ACCENT"]};{C["PRIMARY"]};{C["SECONDARY"]};{C["ACCENT"]}" '
        f'dur="10s" repeatCount="indefinite"/></stop></linearGradient>',

        # name fill — same hues, drifting sideways for a slow sheen
        f'<linearGradient id="{uid("nameGrad")}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{C["PRIMARY"]}"/>'
        f'<stop offset="0.5" stop-color="{C["SECONDARY"]}"/>'
        f'<stop offset="1" stop-color="{C["ACCENT"]}"/>'
        f'<animateTransform attributeName="gradientTransform" type="translate" '
        f'values="-0.35 0;0.35 0;-0.35 0" dur="8s" repeatCount="indefinite"/></linearGradient>',

        f'<linearGradient id="{uid("barGrad")}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{C["PRIMARY"]}"/>'
        f'<stop offset="1" stop-color="{C["SECONDARY"]}"/></linearGradient>',

        f'<linearGradient id="{uid("panelGrad")}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{C["BG"]}"/>'
        f'<stop offset="1" stop-color="{C["BG2"]}"/></linearGradient>',

        f'<linearGradient id="{uid("scan")}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{C["SCAN"]}" stop-opacity="0"/>'
        f'<stop offset="0.5" stop-color="{C["SCAN"]}"/>'
        f'<stop offset="1" stop-color="{C["SCAN"]}" stop-opacity="0"/></linearGradient>',

        f'<radialGradient id="{uid("glowA")}">'
        f'<stop offset="0" stop-color="{C["PRIMARY"]}" stop-opacity="{C["GLOW_A"]}"/>'
        f'<stop offset="1" stop-color="{C["PRIMARY"]}" stop-opacity="0"/></radialGradient>',
        f'<radialGradient id="{uid("glowB")}">'
        f'<stop offset="0" stop-color="{C["ACCENT"]}" stop-opacity="{C["GLOW_B"]}"/>'
        f'<stop offset="1" stop-color="{C["ACCENT"]}" stop-opacity="0"/></radialGradient>',
        f'<radialGradient id="{uid("glowC")}">'
        f'<stop offset="0" stop-color="{C["SECONDARY"]}" stop-opacity="{C["GLOW_B"] * 0.8:.2f}"/>'
        f'<stop offset="1" stop-color="{C["SECONDARY"]}" stop-opacity="0"/></radialGradient>',

        f'<filter id="{uid("frameGlow")}" x="-40%" y="-40%" width="180%" height="180%">'
        f'<feGaussianBlur stdDeviation="7"/></filter>',
        f'<filter id="{uid("textGlow")}" x="-30%" y="-30%" width="160%" height="160%">'
        f'<feGaussianBlur stdDeviation="1" result="b"/>'
        f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',

        f'<clipPath id="{uid("winClip")}">'
        f'<rect x="2" y="2" width="1196" height="616" rx="18"/></clipPath>',

        term_defs,
        doss_defs,
        '</defs>',

        f'<rect x="2" y="2" width="1196" height="616" rx="18" fill="{C["BG"]}"/>',
        f'<g clip-path="url(#{uid("winClip")})">',
        f'<rect x="2" y="2" width="1196" height="616" fill="url(#{uid("panelGrad")})"/>',
        lighting(),
        dot_grid(),
        particles(rng),
        scan_line(),
        title_bar(p),
        corner_brackets(),

        section_label(LX, 76, "DEV.TERMINAL", "// live session"),
        term_body,
        section_label(LX, MON_LABEL_Y, "ACTIVITY.MONITOR", "// 30d"),
        monitor(p),
        doss_body,
        '</g>',

        f'<rect x="3" y="3" width="1194" height="614" rx="17" fill="none" '
        f'stroke="url(#{uid("accent")})" stroke-width="3" opacity="0.5" '
        f'filter="url(#{uid("frameGlow")})"/>',
        f'<rect x="3" y="3" width="1194" height="614" rx="17" fill="none" '
        f'stroke="url(#{uid("accent")})" stroke-width="1.6"/>',
        '</svg>',
    ]
    return "".join(svg)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "profile.json"
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    with open(src, encoding="utf-8") as f:
        profile = json.load(f)

    os.makedirs(outdir, exist_ok=True)
    for theme in ("dark", "light"):
        svg = build(profile, theme)
        path = os.path.join(outdir, f"{theme}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {path}  ({len(svg) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
