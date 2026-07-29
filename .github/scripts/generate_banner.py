#!/usr/bin/env python3
"""
Generate the theme-aware hero banner from profile.json, at three widths.

Everything the banner shows — name, role, stack rows, terminal script, metric
bars — comes from profile.json. Edit that file, re-run this script, and every
theme and every breakpoint stays in sync. Nothing about the author is
hard-coded here.

Six files come out, one per (breakpoint x theme). The README selects between
them with <picture> media queries, which is the only responsive mechanism
GitHub's markdown pipeline honours — there is no stylesheet to hook into.

    file            canvas      README breakpoint      layout
    dark/light      1200 x 620  >= 1024px  (lg, xl)    two columns
    *-md            800 x 1164  640-1023px (md)        stacked
    *-sm            420 x 1084  <= 639px   (sm)        stacked, condensed

Wide layout (unchanged — this is the desktop design):

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

Stacked layouts run the same panels down a single column, identity first —
on a phone the name matters more than the shell session:

    +--------------------+
    | title bar          |
    | SYSTEM.PROFILE     |
    | DEV.TERMINAL       |
    | ACTIVITY.MONITOR   |
    +--------------------+

The -sm dossier trades dotted leaders for label-above-value pairs so the
values keep a readable font size in a ~290px column; -md keeps the leaders.

Ambient layers, back to front: gradient lighting blobs, dot grid, drifting
particles, a slow scan line, then the panels, then the glowing frame. Every
animation is declarative SMIL, so it survives GitHub's camo proxy.

Usage:  python3 .github/scripts/generate_banner.py [profile.json] [outdir]
"""
import html
import json
import os
import random
import sys

FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

MONO_RATIO = 0.601  # advance width of one char in a monospace face, per em


# --------------------------------------------------------------- layouts ----
# Every number the artwork needs lives here, so a breakpoint is a data change
# rather than a code change. The "wide" block reproduces the original desktop
# geometry exactly; regenerating must leave dark.svg / light.svg untouched.
LAYOUTS = {
    "wide": {
        "suffix": "", "W": 1200, "H": 620, "stacked": False,

        "bar_h": 46, "bar_font": 12, "bar_branch_size": 11, "bar_text_y": 29,
        "bar_light_x0": 30, "bar_light_dx": 20, "bar_light_cy": 25,
        "bar_light_r": 5.5, "bar_pad_r": 34,

        "grid_x0": 24, "grid_y0": 70, "grid_step": 34,
        "bracket_inset": 18, "bracket_arm": 34,
        "particles": 30,
        "scan_h": 88, "scan_dur": "14s",
        "glows": [
            ("glowA", 215, 150, 330, 240, "0.75;1;0.75", "9s"),
            ("glowB", 1000, 520, 360, 260, "1;0.7;1", "11s"),
            ("glowC", 620, 60, 420, 150, "0.6;0.95;0.6", "13s"),
        ],

        "label_size": 10, "label_track": 2.6,
        "label_note_adv": 7.6, "label_note_size": 9.5, "label_note_gap": 18,

        "LX": 32, "LW": 496,
        "term_label_y": 76, "TERM_Y": 86, "TERM_H": 310,
        "term_size": 12, "term_step": 18, "term_x_pad": 20, "term_y_pad": 64,
        "term_bar_h": 30, "term_head_size": 9.5,
        "term_light_x0": 18, "term_light_dx": 15, "term_light_r": 4,

        "mon_label_y": 414, "MON_Y": 422, "MON_H": 156,
        "mon_bar_h": 28, "mon_head_size": 9.5, "mon_row_size": 11,
        "mon_label_x": 18, "mon_track_x": 130, "mon_track_w": 268,
        "mon_row_y0": 52, "mon_row_pitch": 28, "mon_pad_r": 18,

        "RX": 556, "RW": 612,
        "doss_label_y": 76, "doss_rule_y": 86,
        "doss_name_y": 122, "doss_name_size": 30, "doss_name_cps": 17,
        "doss_tagline_y": 148, "doss_tagline_size": 12.5,
        "doss_rows_y": 182, "doss_row_size": 13, "doss_row_pitch": 22,
        "doss_div_gap": 6, "doss_div_pitch": 30,
        "doss_note_gap": 14, "doss_note_size": 12.5,
    },

    "md": {
        "suffix": "-md", "W": 800, "H": 1164, "stacked": True,

        "bar_h": 44, "bar_font": 11.5, "bar_branch_size": 10.5, "bar_text_y": 28,
        "bar_light_x0": 28, "bar_light_dx": 19, "bar_light_cy": 24,
        "bar_light_r": 5, "bar_pad_r": 32,

        "grid_x0": 24, "grid_y0": 68, "grid_step": 34,
        "bracket_inset": 16, "bracket_arm": 30,
        "particles": 34,
        "scan_h": 96, "scan_dur": "20s",
        "glows": [
            ("glowA", 150, 190, 300, 260, "0.75;1;0.75", "9s"),
            ("glowB", 660, 880, 300, 320, "1;0.7;1", "11s"),
            ("glowC", 400, 70, 340, 150, "0.6;0.95;0.6", "13s"),
        ],

        "label_size": 10, "label_track": 2.6,
        "label_note_adv": 7.6, "label_note_size": 9.5, "label_note_gap": 18,

        "LX": 32, "LW": 736,
        "term_label_y": 620, "TERM_Y": 630, "TERM_H": 310,
        "term_size": 12, "term_step": 18, "term_x_pad": 20, "term_y_pad": 64,
        "term_bar_h": 30, "term_head_size": 9.5,
        "term_light_x0": 18, "term_light_dx": 15, "term_light_r": 4,

        "mon_label_y": 966, "MON_Y": 974, "MON_H": 156,
        "mon_bar_h": 28, "mon_head_size": 9.5, "mon_row_size": 11,
        "mon_label_x": 18, "mon_track_x": 140, "mon_track_w": 500,
        "mon_row_y0": 52, "mon_row_pitch": 28, "mon_pad_r": 18,

        "RX": 32, "RW": 736,
        "doss_label_y": 86, "doss_rule_y": 96,
        "doss_name_y": 134, "doss_name_size": 30, "doss_name_cps": 17,
        "doss_tagline_y": 160, "doss_tagline_size": 12.5,
        "doss_rows_y": 194, "doss_row_size": 13, "doss_row_pitch": 22,
        "doss_div_gap": 6, "doss_div_pitch": 30,
        "doss_note_gap": 14, "doss_note_size": 12.5,
    },

    "sm": {
        "suffix": "-sm", "W": 420, "H": 1084, "stacked": True,

        "bar_h": 36, "bar_font": 9.5, "bar_branch_size": 9, "bar_text_y": 23,
        "bar_light_x0": 20, "bar_light_dx": 14, "bar_light_cy": 18,
        "bar_light_r": 4, "bar_pad_r": 18,

        "grid_x0": 18, "grid_y0": 56, "grid_step": 30,
        "bracket_inset": 12, "bracket_arm": 22,
        "particles": 22,
        "scan_h": 70, "scan_dur": "20s",
        "glows": [
            ("glowA", 90, 170, 190, 240, "0.75;1;0.75", "9s"),
            ("glowB", 340, 820, 190, 300, "1;0.7;1", "11s"),
            ("glowC", 210, 60, 200, 130, "0.6;0.95;0.6", "13s"),
        ],

        "label_size": 9, "label_track": 2.2,
        "label_note_adv": 6.6, "label_note_size": 8.5, "label_note_gap": 14,

        "LX": 18, "LW": 384,
        "term_label_y": 606, "TERM_Y": 614, "TERM_H": 278,
        "term_size": 11, "term_step": 16, "term_x_pad": 16, "term_y_pad": 52,
        "term_bar_h": 24, "term_head_size": 8.5,
        "term_light_x0": 14, "term_light_dx": 12, "term_light_r": 3.4,

        "mon_label_y": 916, "MON_Y": 924, "MON_H": 140,
        "mon_bar_h": 24, "mon_head_size": 8.5, "mon_row_size": 10,
        "mon_label_x": 14, "mon_track_x": 100, "mon_track_w": 200,
        "mon_row_y0": 46, "mon_row_pitch": 26, "mon_pad_r": 14,

        "RX": 18, "RW": 384,
        "doss_label_y": 66, "doss_rule_y": 74,
        "doss_name_y": 104, "doss_name_size": 20, "doss_name_cps": 15,
        "doss_tagline_y": 124, "doss_tagline_size": 10,
        "doss_rows_y": 150, "doss_row_size": 11.5, "doss_row_pitch": 26,
        "doss_div_gap": 4, "doss_div_pitch": 24,
        "doss_note_gap": 12, "doss_note_size": 10,
        # -sm only: label sits above its value instead of sharing a leader line
        "doss_stacked_rows": True,
        "doss_key_size": 9, "doss_key_track": 1.4, "doss_value_dy": 13,
    },
}


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

C = {}          # active palette, populated by set_context()
L = {}          # active layout
SUFFIX = ""     # id namespace so both themes can coexist on one page


def set_context(theme, layout):
    global C, L, SUFFIX
    C = THEMES[theme]
    L = LAYOUTS[layout]
    SUFFIX = theme


def uid(base):
    return f"{base}_{SUFFIX}"


def esc(s):
    return html.escape(str(s), quote=True)


def cw(size):
    """Advance width of one monospace character at the given font size."""
    return size * MONO_RATIO


def wrap(text, budget):
    """Greedy word wrap, so a longer profile.json value never overruns the
    canvas on the narrow layouts. Always returns at least one line."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if len(cand) > budget and cur:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    lines.append(cur)
    return lines


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


def leader_row(label, value, y, begin, size=None):
    """A dossier line: `Label ......... Value`, justified to the column width.

    textLength + lengthAdjust pins every row to exactly RW pixels, so the values
    line up flush right no matter how the viewer's monospace font measures.
    """
    size = L["doss_row_size"] if size is None else size
    rx, rw = L["RX"], L["RW"]
    budget = int(rw / cw(size))
    dots = max(3, budget - len(label) - len(value) - 2)
    inner = (
        f'<text x="{rx}" y="{y}" font-size="{size}" textLength="{rw}" '
        f'lengthAdjust="spacingAndGlyphs" xml:space="preserve">'
        f'<tspan fill="{C["SECONDARY"]}">{esc(label)} </tspan>'
        f'<tspan fill="{C["DOTS"]}">{"." * dots}</tspan>'
        f'<tspan fill="{C["TEXT"]}" font-weight="600"> {esc(value)}</tspan></text>'
    )
    return fade_in(inner, begin, 0.4, dx=-10)


def stacked_row(label, value, y, begin):
    """Narrow-layout dossier entry: a small tracked-out key with a hairline
    rule, and the value on its own line beneath it at a readable size.

    Returns (markup, height_consumed) — wrapped values grow the row rather than
    spilling past the canvas edge.
    """
    rx, rw = L["RX"], L["RW"]
    key_size, val_size = L["doss_key_size"], L["doss_row_size"]
    adv = cw(key_size) + L["doss_key_track"]
    rule = max(2, int((rw - (len(label) + 1) * adv) / adv))
    lines = wrap(value, int(rw / cw(val_size)))

    out = [
        f'<text x="{rx}" y="{y}" font-size="{key_size}" '
        f'letter-spacing="{L["doss_key_track"]}" xml:space="preserve">'
        f'<tspan fill="{C["SECONDARY"]}">{esc(label.upper())} </tspan>'
        f'<tspan fill="{C["DOTS"]}">{"&#183;" * rule}</tspan></text>'
    ]
    ly = y + L["doss_value_dy"]
    for line in lines:
        out.append(
            f'<text x="{rx}" y="{ly}" font-size="{val_size}" font-weight="600" '
            f'fill="{C["TEXT"]}" xml:space="preserve">{esc(line)}</text>')
        ly += val_size + 3

    height = L["doss_row_pitch"] + (len(lines) - 1) * (val_size + 3)
    return fade_in("".join(out), begin, 0.4, dx=-8), height


def divider_row(label, y, begin, size=None):
    size = L["doss_row_size"] if size is None else size
    rx, rw = L["RX"], L["RW"]
    budget = int(rw / cw(size))
    rule = max(3, budget - len(label) - 4)
    inner = (
        f'<text x="{rx}" y="{y}" font-size="{size}" textLength="{rw}" '
        f'lengthAdjust="spacingAndGlyphs" xml:space="preserve">'
        f'<tspan fill="{C["ACCENT"]}">&#9670; {esc(label)} </tspan>'
        f'<tspan fill="{C["DOTS"]}">{"&#8212;" * rule}</tspan></text>'
    )
    return fade_in(inner, begin, 0.4)


def panel(x, y, w, h, pulse_offset=0.0):
    """Rounded panel with a slowly breathing accent border."""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{C["PANEL"]}" '
        f'stroke="{C["PANEL_STROKE"]}">'
        f'<animate attributeName="stroke" values="{C["PANEL_STROKE"]};'
        f'{C["PANEL_STROKE_HI"]};{C["PANEL_STROKE"]}" dur="5.5s" '
        f'begin="{pulse_offset:.2f}s" repeatCount="indefinite"/></rect>'
    )


def section_label(x, y, text, note=""):
    out = (f'<text x="{x}" y="{y}" font-size="{L["label_size"]}" '
           f'letter-spacing="{L["label_track"]}" '
           f'fill="{C["PRIMARY"]}">{esc(text)}</text>')
    if note:
        out += (f'<text x="{x + len(text) * L["label_note_adv"] + L["label_note_gap"]:.0f}" '
                f'y="{y}" font-size="{L["label_note_size"]}" '
                f'fill="{C["DIM"]}">{esc(note)}</text>')
    return out


# ------------------------------------------------------------ ambient art ---
def lighting():
    """Large, slowly breathing radial washes — the 'gradient lighting'."""
    return "".join(
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#{uid(gid)})">'
        f'<animate attributeName="opacity" values="{vals}" dur="{dur}" '
        f'repeatCount="indefinite"/>'
        f'</ellipse>'
        for gid, cx, cy, rx, ry, vals, dur in L["glows"]
    )


def dot_grid():
    """Sparse dot lattice — structure without noise."""
    step = L["grid_step"]
    dots = "".join(
        f'<circle cx="{x}" cy="{y}" r="1"/>'
        for y in range(L["grid_y0"], L["H"], step)
        for x in range(L["grid_x0"], L["W"], step)
    )
    return f'<g fill="{C["GRID"]}">{dots}</g>'


def particles(rng, count=None):
    """Drifting motes. Negative begins mean they are already mid-flight on
    first paint, so the banner never opens on a static frame."""
    count = L["particles"] if count is None else count
    w, h = L["W"], L["H"]
    palette = [C["PRIMARY"], C["SECONDARY"], C["ACCENT"]]
    out = []
    for _ in range(count):
        x = rng.uniform(20, w - 20)
        y = rng.uniform(60, h - 20)
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
        f'<rect x="2" y="{L["bar_h"] + 2}" width="{L["W"] - 4}" height="{L["scan_h"]}" '
        f'fill="url(#{uid("scan")})" opacity="0.9">'
        f'<animateTransform attributeName="transform" type="translate" '
        f'values="0 -90;0 {L["H"]};0 -90" dur="{L["scan_dur"]}" '
        f'repeatCount="indefinite"/></rect>'
    )


def corner_brackets():
    """Four thin L-brackets — a quiet HUD cue at the frame corners."""
    w, h = L["W"], L["H"]
    a, m, ln = L["bracket_inset"], L["bracket_arm"], C["PRIMARY"]
    pts = [
        (a, a, 1, 1), (w - a, a, -1, 1), (a, h - a, 1, -1), (w - a, h - a, -1, -1),
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
    w, bh = L["W"], L["bar_h"]
    ty = L["bar_text_y"]
    handle = p["username"].lower().split("-")[-1]
    title = f'{handle}@dev  ~  % ./profile.sh --live'
    lights = "".join(
        f'<circle cx="{L["bar_light_x0"] + i * L["bar_light_dx"]}" '
        f'cy="{L["bar_light_cy"]}" r="{L["bar_light_r"]}" fill="{col}"/>'
        for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840"))
    )
    return (
        f'<rect x="2" y="2" width="{w - 4}" height="{bh}" fill="{C["TITLEBAR"]}"/>'
        f'<line x1="2" y1="{bh + 2}" x2="{w - 2}" y2="{bh + 2}" stroke="{C["LINE"]}"/>'
        f'{lights}'
        f'<text x="{w // 2}" y="{ty}" text-anchor="middle" font-size="{L["bar_font"]}" '
        f'fill="{C["MUTED"]}">{esc(title)}</text>'
        f'<text x="{w - L["bar_pad_r"]}" y="{ty}" text-anchor="end" '
        f'font-size="{L["bar_branch_size"]}" fill="{C["DIM"]}">'
        f'main <tspan fill="{C["SUCCESS"]}">&#9679;</tspan></text>'
    )


def terminal(p, t0=0.55):
    """Animated shell session driven by profile.json -> terminal[]."""
    defs, body = [], []
    lx, lw = L["LX"], L["LW"]
    ty, th = L["TERM_Y"], L["TERM_H"]
    bh = L["term_bar_h"]
    x0, y0 = lx + L["term_x_pad"], ty + L["term_y_pad"]
    size, step = L["term_size"], L["term_step"]

    body.append(panel(lx, ty, lw, th, pulse_offset=0.0))
    body.append(f'<rect x="{lx}" y="{ty}" width="{lw}" height="{bh}" rx="12" '
                f'fill="{C["PANEL_BAR"]}"/>')
    body.append(f'<rect x="{lx}" y="{ty + bh - 12}" width="{lw}" height="12" '
                f'fill="{C["PANEL_BAR"]}"/>')
    body.append(f'<line x1="{lx}" y1="{ty + bh}" x2="{lx + lw}" y2="{ty + bh}" '
                f'stroke="{C["LINE"]}"/>')
    for i, col in enumerate((C["ALERT"], "#FEBC2E", C["SUCCESS"])):
        body.append(f'<circle cx="{lx + L["term_light_x0"] + i * L["term_light_dx"]}" '
                    f'cy="{ty + bh // 2}" r="{L["term_light_r"]}" '
                    f'fill="{col}" opacity="0.85"/>')
    body.append(f'<text x="{lx + lw - 16}" y="{ty + bh - 11}" text-anchor="end" '
                f'font-size="{L["term_head_size"]}" fill="{C["DIM"]}">'
                f'zsh &#8212; 80&#215;24</text>')

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
    lx, lw = L["LX"], L["LW"]
    my, mh, bh = L["MON_Y"], L["MON_H"], L["mon_bar_h"]
    row_size = L["mon_row_size"]

    body = [panel(lx, my, lw, mh, pulse_offset=1.4)]
    body.append(f'<rect x="{lx}" y="{my}" width="{lw}" height="{bh}" rx="12" '
                f'fill="{C["PANEL_BAR"]}"/>')
    body.append(f'<rect x="{lx}" y="{my + bh - 12}" width="{lw}" height="12" '
                f'fill="{C["PANEL_BAR"]}"/>')
    body.append(f'<line x1="{lx}" y1="{my + bh}" x2="{lx + lw}" y2="{my + bh}" '
                f'stroke="{C["LINE"]}"/>')
    body.append(f'<text x="{lx + 16}" y="{my + bh - 10}" font-size="{L["mon_head_size"]}" '
                f'letter-spacing="1.6" fill="{C["MUTED"]}">STACK.PROFICIENCY</text>')
    body.append(
        f'<text x="{lx + lw - 16}" y="{my + bh - 10}" text-anchor="end" '
        f'font-size="{L["mon_head_size"]}" fill="{C["SUCCESS"]}">&#9650; live'
        f'<animate attributeName="opacity" values="1;0.35;1" dur="2.2s" '
        f'repeatCount="indefinite"/></text>')

    label_x = lx + L["mon_label_x"]
    track_x = lx + L["mon_track_x"]
    track_w = L["mon_track_w"]
    pct_x = lx + lw - L["mon_pad_r"]

    for i, (label, target) in enumerate(p.get("metrics", [])):
        y = my + L["mon_row_y0"] + i * L["mon_row_pitch"]
        begin = t0 + i * 0.18
        fill_w = track_w * target / 100.0

        body.append(f'<text x="{label_x}" y="{y + 4}" font-size="{row_size}" '
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
                f'<text x="{pct_x}" y="{y + 4}" text-anchor="end" font-size="{row_size}" '
                f'font-weight="700" fill="{C["TEXT"]}" opacity="0">{val}%'
                f'<set attributeName="opacity" to="1" begin="{show:.2f}s"/>{hide}</text>')

    return "".join(body)


def dossier(p, t0=0.45):
    """Identity panel: typed name, tagline, then the dossier rows — dotted
    leaders on the wide and md canvases, key-over-value on sm."""
    defs, body = [], []
    rx, rw = L["RX"], L["RW"]
    stacked_rows = L.get("doss_stacked_rows", False)

    body.append(section_label(rx, L["doss_label_y"], "SYSTEM.PROFILE"))
    body.append(
        f'<text x="{rx + rw}" y="{L["doss_label_y"]}" text-anchor="end" '
        f'font-size="{L["label_size"] + 1}" '
        f'font-weight="700" fill="{C["ALERT"]}"><tspan>&#9679;</tspan> LIVE'
        f'<animate attributeName="opacity" values="1;0.3;1" dur="1.6s" '
        f'repeatCount="indefinite"/></text>')
    body.append(f'<line x1="{rx}" y1="{L["doss_rule_y"]}" x2="{rx + rw}" '
                f'y2="{L["doss_rule_y"]}" '
                f'stroke="url(#{uid("accent")})" stroke-width="1.5" opacity="0.75"/>')

    # name — typed, gradient-filled, with a soft glow
    d, b, dur = typing(
        uid("name"), rx, L["doss_name_y"],
        [(p["name"], f'url(#{uid("nameGrad")})', "700")],
        t0, size=L["doss_name_size"], cps=L["doss_name_cps"], hold=0.6)
    defs.append(d)
    body.append(f'<g filter="url(#{uid("textGlow")})">{b}</g>')

    t = t0 + dur + 0.15
    tagline_size = L["doss_tagline_size"]
    tag_lines = wrap(p["tagline"], int(rw / cw(tagline_size)))
    ty = L["doss_tagline_y"]
    for line in tag_lines:
        body.append(fade_in(
            f'<text x="{rx}" y="{ty}" font-size="{tagline_size}" fill="{C["MUTED"]}">'
            f'{esc(line)}</text>', t))
        ty += tagline_size + 4
    t += 0.28

    def emit(label, value, y, begin):
        """One dossier entry -> (markup, height consumed)."""
        if stacked_rows:
            return stacked_row(label, value, y, begin)
        return leader_row(label, value, y, begin), L["doss_row_pitch"]

    groups = [
        (None, [
            ("Role", p["role"]),
            ("Location", p["location"]),
            ("Education", p["education"]),
            ("Currently", p["company"]),
            ("Status", p["status"]),
        ]),
        ("Stack", list(p.get("stack", []))),
        ("Connect", [
            ("Email", p["email"]),
            ("Portfolio", p["portfolio"]),
            ("LinkedIn", p["linkedin"]),
            ("GitHub", "@" + p["username"]),
        ]),
    ]

    y = L["doss_rows_y"]
    for heading, rows in groups:
        if heading:
            t += 0.08
            body.append(divider_row(heading, y + L["doss_div_gap"], t))
            y += L["doss_div_pitch"]
            t += 0.12
        for label, value in rows:
            markup, height = emit(label, value, y, t)
            body.append(markup)
            y += height
            t += 0.11

    body.append(fade_in(
        f'<text x="{rx}" y="{y + L["doss_note_gap"]}" font-size="{L["doss_note_size"]}" '
        f'fill="{C["MUTED"]}">'
        f'&#9656; Stats, projects and more below '
        f'<tspan fill="{C["SECONDARY"]}">&#8595;</tspan> '
        f'<tspan fill="{C["ACCENT"]}">&#9608;'
        f'<animate attributeName="fill-opacity" values="1;0;1" dur="1s" '
        f'repeatCount="indefinite"/></tspan></text>', t + 0.2))

    return "".join(defs), "".join(body)


# ------------------------------------------------------------------ build ---
def build(p, theme, layout="wide"):
    set_context(theme, layout)
    w, h = L["W"], L["H"]
    rng = random.Random(20260728)  # fixed seed -> byte-stable regeneration

    term_defs, term_body, _ = terminal(p)
    doss_defs, doss_body = dossier(p)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" font-family="{FONT}" role="img" '
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
        f'<rect x="2" y="2" width="{w - 4}" height="{h - 4}" rx="18"/></clipPath>',

        term_defs,
        doss_defs,
        '</defs>',

        f'<rect x="2" y="2" width="{w - 4}" height="{h - 4}" rx="18" fill="{C["BG"]}"/>',
        f'<g clip-path="url(#{uid("winClip")})">',
        f'<rect x="2" y="2" width="{w - 4}" height="{h - 4}" fill="url(#{uid("panelGrad")})"/>',
        lighting(),
        dot_grid(),
        particles(rng),
        scan_line(),
        title_bar(p),
        corner_brackets(),
    ]

    # Stacked canvases lead with identity; the wide one keeps the shell on the
    # left, so the paint order differs even though the pieces are the same.
    terminal_block = [
        section_label(L["LX"], L["term_label_y"], "DEV.TERMINAL", "// live session"),
        term_body,
        section_label(L["LX"], L["mon_label_y"], "ACTIVITY.MONITOR", "// 30d"),
        monitor(p),
    ]
    svg += ([doss_body] + terminal_block) if L["stacked"] else (terminal_block + [doss_body])

    svg += [
        '</g>',

        f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="17" fill="none" '
        f'stroke="url(#{uid("accent")})" stroke-width="3" opacity="0.5" '
        f'filter="url(#{uid("frameGlow")})"/>',
        f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="17" fill="none" '
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
    for layout, spec in LAYOUTS.items():
        for theme in ("dark", "light"):
            svg = build(profile, theme, layout)
            path = os.path.join(outdir, f"{theme}{spec['suffix']}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg)
            print(f"wrote {path}  ({len(svg) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
