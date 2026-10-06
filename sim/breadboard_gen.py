#!/usr/bin/env python3
"""Generate the breadboard layout page (sim/breadboard.html) for the 4-digit test build.

Two full-size breadboards (63 columns, rows a-j, two rails top and bottom):
  Board A: two DC56-11 duals + four 74HCT595 + 32 segment resistors
  Board B: STM32G030F6 on a TSSOP-20 adapter, LD1117V33, GPS breakout, buttons
Every placement is checked: no hole used twice, no hole under a part body, and the
connectivity the breadboard strips produce must equal the intended netlist.
"""
import collections
import html
import json
import os
import sys

P = 12                       # px per 0.1" hole pitch
ROWS = "abcdefghij"
ROW_Y = {r: (3 + i if i < 5 else 5 + i) for i, r in enumerate(ROWS)}  # a..e = 3..7, f..j = 10..14
RAIL_Y = {0: 0, 1: 1, 2: 16, 3: 17}
BOARD_H = 18
COLS = 63
BOARDS = {"A": (110, 40), "B": (110, 40 + (BOARD_H + 9) * P)}   # px origin of each board

# rail names per board: line index -> net shown on that rail
RAILS = {"A": {0: "+5V", 1: "GND", 2: "GND", 3: None}, "B": {0: "+3V3", 1: "GND", 2: "GND", 3: "+5V"}}

def hxy(h):
    """Pixel centre of hole h = (board, row, col); row is 'a'..'j' or rail index 0..3."""
    b, r, c = h
    ox, oy = BOARDS[b]
    y = RAIL_Y[r] if isinstance(r, int) else ROW_Y[r]
    return ox + c * P, oy + y * P

def strip(h):
    b, r, c = h
    if isinstance(r, int):
        return (b, "rail", r)
    return (b, "top" if r in "abcde" else "bot", c)

def rail_ok(c):
    return c % 6 != 0          # rail holes come in groups of five

# ---------------------------------------------------------------------------
parts = []       # dicts: ref, kind, label, pins{name: hole or ('off', id)}, draw info
wires = []       # dicts: a, b, color, label (holes or off-board points)
used = {}        # hole -> owner
blocked = {}     # hole -> part covering it

def use(h, owner):
    b, r, c = h
    assert 1 <= c <= COLS, (h, owner)
    if isinstance(r, int):
        assert rail_ok(c), f"no rail hole at {h} ({owner})"
    assert h not in used, f"hole {h} used by {used[h]} and {owner}"
    assert h not in blocked, f"hole {h} is under {blocked[h]} ({owner})"
    used[h] = owner
    return h

def block(b, rows, cols, owner):
    for r in rows:
        for c in cols:
            blocked[(b, r, c)] = owner

def part(ref, kind, pins, label="", **draw):
    for name, h in pins.items():
        if h[0] != "off":
            use(h, f"{ref}.{name}")
    parts.append(dict(ref=ref, kind=kind, pins=pins, label=label, **draw))

def wire(a, b, color, label="", route=None, k=0):
    for h in (a, b):
        if h[0] != "off":
            use(h, f"wire {label}")
    wires.append(dict(a=a, b=b, color=color, label=label, route=route, k=k))

def rail_hole(b, line, near):
    """Nearest free rail hole to column `near`."""
    for d in range(0, 20):
        for c in (near + d, near - d):
            h = (b, line, c)
            if 1 <= c <= COLS and rail_ok(c) and h not in used:
                return h
    raise RuntimeError("rail full")

# ---------------------------------------------------------------------------
# Intended netlist: (ref, pin) -> net. Filled as parts are placed.
want = {}

def net(ref, pin, n):
    want[(ref, pin)] = n

# ------------------------------- Board A -----------------------------------
# DC56-11 pins: top row (left->right) 18..10, bottom row (left->right) 1..9
DS_TOP = [18, 17, 16, 15, 14, 13, 12, 11, 10]
DS_BOT = [1, 2, 3, 4, 5, 6, 7, 8, 9]
DS_FN = {1: ("1", "E"), 2: ("1", "D"), 3: ("1", "C"), 4: ("1", "DP"), 5: ("2", "E"), 6: ("2", "D"),
         7: ("2", "G"), 8: ("2", "C"), 9: ("2", "DP"), 10: ("2", "B"), 11: ("2", "A"), 12: ("2", "F"),
         13: ("2", "CC"), 14: ("1", "CC"), 15: ("1", "B"), 16: ("1", "A"), 17: ("1", "G"), 18: ("1", "F")}

# 74HCT595 DIP-16, notch left: bottom row pins 1..8 left->right, top row 16..9 left->right
def u595(ref, s):
    pins = {}
    for i, p in enumerate(range(1, 9)):
        pins[str(p)] = ("A", "f", s + i)
    for i, p in enumerate(range(16, 8, -1)):
        pins[str(p)] = ("A", "e", s + i)
    part(ref, "dip", pins, "74HCT595", cols=(s, s + 7), rows=("e", "f"), board="A")

Q = {"QA": "15", "QB": "1", "QC": "2", "QD": "3", "QE": "4", "QF": "5", "QG": "6", "QH": "7"}

# Segment mapping chosen for short, uncrossed resistor runs on the breadboard.
# The firmware takes a per-digit lookup table, so any output can drive any segment.
MAP_DIG1 = {"QA": "A", "QB": "B", "QC": "E", "QD": "D", "QE": "C", "QF": "DP", "QG": "F", "QH": "G"}
MAP_DIG2 = {"QA": "A", "QB": "E", "QC": "D", "QD": "G", "QE": "C", "QF": "DP", "QG": "F", "QH": "B"}

def ds_pin_col(d0, pin):
    if pin in DS_TOP:
        return "a", d0 + DS_TOP.index(pin)
    return "j", d0 + DS_BOT.index(pin)

def ds_pin_for(side, seg):
    for p, (sd, sg) in DS_FN.items():
        if sd == side and sg == seg:
            return p
    raise KeyError((side, seg))

SEG_COLORS = ["#d9473b", "#2f7fd1", "#2f9e57", "#9b51c9"]   # per digit, for resistor/jumper tint

def build_pair(k, s_a, d0, s_b, digit_a, digit_b, shift):
    ds = f"DS{k}"
    pins = {}
    for i, p in enumerate(DS_TOP):
        pins[str(p)] = ("A", "c", d0 + i)
    for i, p in enumerate(DS_BOT):
        pins[str(p)] = ("A", "g", d0 + i)
    block("A", "bdefh", range(d0, d0 + 9), ds)
    part(ds, "dual", pins, "DC56-11", cols=(d0, d0 + 8), board="A")
    for p, (side, seg) in DS_FN.items():
        digit = digit_a if side == "1" else digit_b
        net(ds, str(p), "GND" if seg == "CC" else f"D{digit}_{seg}")
    # common cathodes to the top GND rail
    for p in (14, 13):
        r, c = ds_pin_col(d0, p)
        wire(("A", r, c), rail_hole("A", 1, c), "#222", "GND")

    for ref, s, digit, side, mp in (("U%d" % (2 * k - 1), s_a, digit_a, "1", MAP_DIG1),
                                     ("U%d" % (2 * k), s_b, digit_b, "2", MAP_DIG2)):
        color = SEG_COLORS[digit - 1]
        for q, seg in mp.items():
            pin = ds_pin_for(side, seg)
            row, col = ds_pin_col(d0, pin)
            out_col = s + (int(Q[q]) - 1 if q != "QA" else 1)
            rname = f"R{digit}{seg}"
            net(ref, Q[q], f"D{digit}_{q}")
            net(rname, "1", f"D{digit}_{q}")
            net(rname, "2", f"D{digit}_{seg}")
            if q == "QA":
                part(rname, "res", {"1": ("A", "d", out_col), "2": ("A", row, col)}, "470", color=color)
            elif row == "j":
                part(rname, "res", {"1": ("A", "g", out_col), "2": ("A", "j", col)}, "470", color=color)
            else:
                # top display pin: resistor into a free strip next to the chip, then a jumper
                inter = {("1", "B"): 1, ("1", "F"): 10, ("1", "G"): 11, ("2", "F"): 21, ("2", "B"): 22}[(side, seg)] + shift
                near_row = "i" if seg == "F" else "h"
                part(rname, "res", {"1": ("A", near_row, out_col), "2": ("A", near_row, inter)}, "470", color=color)
                wire(("A", "j", inter), ("A", "a", col), color, f"D{digit}_{seg}")

def chip_power_and_bus(ref, s, prev):
    """Power, decoupling and the daisy-chained control lines for one '595 at column s."""
    net(ref, "16", "+5V"); net(ref, "10", "+5V"); net(ref, "8", "GND")
    net(ref, "13", "DISP_OE"); net(ref, "12", "SR_LATCH"); net(ref, "11", "SR_CLK")
    wire(("A", "a", s), rail_hole("A", 0, s), "#d33", "+5V")
    wire(("A", "a", s + 6), rail_hole("A", 0, s + 6), "#d33", "+5V")
    wire(("A", "j", s + 7), rail_hole("A", 2, s + 7), "#222", "GND")
    cref = "C" + ref[1:]
    part(cref, "cap", {"1": ("A", "b", s), "2": rail_hole("A", 1, s)}, "100n")
    net(cref, "1", "+5V"); net(cref, "2", "GND")
    if prev is not None:
        ps = prev
        wire(("A", "a", ps + 7), ("A", "a", s + 2), "#2f9e57", "chain data")
        wire(("A", "b", ps + 3), ("A", "a", s + 3), "#2f6fd1", "DISP_OE")
        wire(("A", "b", ps + 4), ("A", "a", s + 4), "#8e44ad", "SR_LATCH")
        wire(("A", "b", ps + 5), ("A", "a", s + 5), "#e0b000", "SR_CLK")

chips = [("U1", 2), ("U2", 23), ("U3", 33), ("U4", 54)]
for ref, s in chips:
    u595(ref, s)
build_pair(1, 2, 12, 23, 1, 2, 0)
build_pair(2, 33, 43, 54, 3, 4, 31)
prev = None
for i, (ref, s) in enumerate(chips):
    chip_power_and_bus(ref, s, prev)
    nxt = chips[i + 1][0] if i + 1 < len(chips) else None
    net(ref, "14", "SR_DATA" if i == 0 else f"SR_D{i + 1}")
    net(ref, "9", f"SR_D{i + 2}" if nxt else "NC")
    prev = s
# bridge the top and bottom GND rails of board A
wire(rail_hole("A", 1, 63), rail_hole("A", 2, 63), "#222", "GND")

# ------------------------------- Board B -----------------------------------
# TSSOP-20 adapter, 0.6" wide, pins 1..10 on row g (left->right), 20..11 on row c (left->right)
MCU_SIG = {1: "NC", 2: "NC", 3: "BTN_MODE", 4: "+3V3", 5: "GND", 6: "NRST", 7: "NC", 8: "BTN_BRIGHT",
           9: "GPS_RXD", 10: "GPS_TXD", 11: "DISP_OE", 12: "SR_CLK_MCU", 13: "GPS_PPS", 14: "SR_DATA",
           15: "SR_LATCH_MCU", 16: "LED", 17: "NC", 18: "SWDIO", 19: "SWCLK", 20: "NC"}
MCU_NAME = {1: "PB7", 2: "PC14", 3: "PC15", 4: "VDD", 5: "VSS", 6: "NRST", 7: "PA0", 8: "PA1", 9: "PA2",
            10: "PA3", 11: "PA4", 12: "PA5", 13: "PA6", 14: "PA7", 15: "PB0", 16: "PA11", 17: "PA12",
            18: "PA13", 19: "PA14", 20: "PB6"}
m0 = 10
mpins = {}
for i in range(10):
    mpins[str(1 + i)] = ("B", "g", m0 + i)
    mpins[str(20 - i)] = ("B", "c", m0 + i)
block("B", "bdefh", range(m0, m0 + 10), "U5")
part("U5", "adapter", mpins, "STM32G030F6", cols=(m0, m0 + 9), board="B")
for p, n in MCU_SIG.items():
    net("U5", str(p), n)

def mcol(p):
    return mpins[str(p)][2]

# Regulator LD1117V33 (TO-220): 1 GND, 2 VOUT, 3 VIN, legs on row h
part("U6", "to220", {"1": ("B", "h", 3), "2": ("B", "h", 4), "3": ("B", "h", 5)}, "LD1117V33")
net("U6", "1", "GND"); net("U6", "2", "+3V3"); net("U6", "3", "+5V")
wire(("B", "j", 3), rail_hole("B", 2, 3), "#222", "GND")
wire(("B", "j", 5), rail_hole("B", 3, 5), "#d33", "+5V")
wire(("B", "f", 4), rail_hole("B", 0, 4), "#f08a24", "+3V3")
part("C5", "ecap", {"1": ("B", "i", 5), "2": rail_hole("B", 2, 6)}, "10µ")
part("C6", "ecap", {"1": ("B", "i", 4), "2": rail_hole("B", 2, 2)}, "10µ")
net("C5", "1", "+5V"); net("C5", "2", "GND"); net("C6", "1", "+3V3"); net("C6", "2", "GND")

# MCU power, decoupling, reset
wire(("B", "j", mcol(4)), rail_hole("B", 0, mcol(4)), "#f08a24", "+3V3")
wire(("B", "j", mcol(5)), rail_hole("B", 2, mcol(5)), "#222", "GND")
part("C7", "cap", {"1": ("B", "i", mcol(4)), "2": ("B", "i", mcol(5))}, "100n")
net("C7", "1", "+3V3"); net("C7", "2", "GND")
part("C8", "cap", {"1": ("B", "i", mcol(6)), "2": rail_hole("B", 2, mcol(6) + 1)}, "100n")
net("C8", "1", "NRST"); net("C8", "2", "GND")

# Buttons (2-leg view: use diagonally opposite legs of a 4-leg tactile switch)
for ref, p, c1, lab in (("SW2", 3, 22, "MODE"), ("SW1", 8, 26, "BRIGHT")):
    wire(("B", "j", mcol(p)), ("B", "j", c1), "#888", MCU_SIG[p])
    part(ref, "button", {"1": ("B", "h", c1), "2": ("B", "h", c1 + 2)}, lab)
    wire(("B", "j", c1 + 2), rail_hole("B", 2, c1 + 2), "#222", "GND")
    net(ref, "1", MCU_SIG[p]); net(ref, "2", "GND")

# Status LED on PA11
part("R5", "res", {"1": ("B", "a", mcol(16)), "2": ("B", "c", 20)}, "1k", color="#666")
part("D1", "led", {"A": ("B", "e", 20), "K": ("B", "f", 20)}, "LED")
wire(("B", "j", 20), rail_hole("B", 2, 20), "#222", "GND")
net("R5", "1", "LED"); net("R5", "2", "LED_A"); net("D1", "A", "LED_A"); net("D1", "K", "GND")

# Display control lines: hubs in free columns next to the adapter
wire(("B", "a", mcol(11)), ("B", "e", 21), "#2f6fd1", "DISP_OE")                      # OE hub col 21
part("R6", "res", {"1": ("B", "d", 21), "2": rail_hole("B", 0, 21)}, "10k", color="#666")
net("R6", "1", "DISP_OE"); net("R6", "2", "+3V3")
part("R7", "res", {"1": ("B", "a", mcol(15)), "2": ("B", "c", 23)}, "33", color="#666")   # latch hub col 23
net("R7", "1", "SR_LATCH_MCU"); net("R7", "2", "SR_LATCH")
part("R8", "res", {"1": ("B", "a", mcol(12)), "2": ("B", "c", 25)}, "33", color="#666")   # clock hub col 25
net("R8", "1", "SR_CLK_MCU"); net("R8", "2", "SR_CLK")

# GPS breakout: 5-pin header on row j, module hangs off the bottom edge
GPS = {"VCC": 40, "GND": 41, "TX": 42, "RX": 43, "PPS": 44}
part("GPS", "gps", {k: ("B", "j", c) for k, c in GPS.items()}, "ATGM336H breakout")
for c in range(39, 46):
    for line in (2, 3):
        if rail_ok(c):
            blocked[("B", line, c)] = "GPS"
net("GPS", "VCC", "+5V"); net("GPS", "GND", "GND"); net("GPS", "TX", "GPS_TXD")
net("GPS", "RX", "GPS_RXD"); net("GPS", "PPS", "GPS_PPS")
wire(("B", "f", 40), rail_hole("B", 3, 37), "#d33", "+5V")
wire(("B", "f", 41), rail_hole("B", 2, 38), "#222", "GND")
wire(("B", "g", 42), ("B", "i", mcol(10)), "#16a2b8", "GPS_TXD")
wire(("B", "g", 43), ("B", "i", mcol(9)), "#0e7c86", "GPS_RXD")
wire(("B", "g", 44), ("B", "a", mcol(13)), "#e05aa0", "GPS_PPS")

# bridge the top and bottom GND rails of board B
wire(rail_hole("B", 1, 62), rail_hole("B", 2, 62), "#222", "GND")

# ST-Link (off board, left of board B)
bx, by = BOARDS["B"]
STL = {"5V": (bx - 52, by + 13 * P), "GND": (bx - 52, by + 14.5 * P),
       "SWDIO": (bx - 52, by + 4 * P), "SWCLK": (bx - 52, by + 5.5 * P)}
part("ST", "stlink", {k: ("off", k) for k in STL}, "ST-Link")
net("ST", "5V", "+5V"); net("ST", "GND", "GND"); net("ST", "SWDIO", "SWDIO"); net("ST", "SWCLK", "SWCLK")
wire(("off", "5V"), rail_hole("B", 3, 2), "#d33", "+5V")
wire(("off", "GND"), rail_hole("B", 2, 1), "#222", "GND")
wire(("off", "SWDIO"), ("B", "a", mcol(18)), "#7a5230", "SWDIO")
wire(("off", "SWCLK"), ("B", "a", mcol(19)), "#999", "SWCLK")

# Between the boards
# long wires run around the board edges (drawn that way so they don't hide the parts)
wire(rail_hole("B", 3, 62), rail_hole("A", 0, 62), "#d33", "+5V", route="right", k=0)
wire(rail_hole("B", 2, 61), rail_hole("A", 2, 61), "#222", "GND", route="right", k=1)
wire(("B", "a", mcol(14)), ("A", "a", 4), "#2f9e57", "SR_DATA", route="left", k=0)   # U1 SER
wire(("B", "a", 21), ("A", "a", 5), "#2f6fd1", "DISP_OE", route="left", k=1)         # U1 OE
wire(("B", "a", 23), ("A", "a", 6), "#8e44ad", "SR_LATCH", route="left", k=2)        # U1 RCLK
wire(("B", "a", 25), ("A", "a", 7), "#e0b000", "SR_CLK", route="left", k=3)          # U1 SRCLK

# Logic analyser probe points (free holes, just markers)
PROBES = {"PPS": ("B", "h", 44), "LATCH": ("B", "b", 23), "GPS TX": ("B", "h", 42), "GND": rail_hole("B", 2, 30)}

# ---------------------------------------------------------------------------
# Verify: union strips through wires, then compare pin groupings with `want`.
parent = {}
def find(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
def union(a, b):
    parent[find(a)] = find(b)
def node(h):
    return ("off", h[1]) if h[0] == "off" else strip(h)

for w in wires:
    union(node(w["a"]), node(w["b"]))
got = collections.defaultdict(set)
pin_root = {}
for p in parts:
    for name, h in p["pins"].items():
        rt = find(node(h))
        got[rt].add((p["ref"], name))
        pin_root[(p["ref"], name)] = rt
errors = []
for key in pin_root:
    if key not in want:
        errors.append(f"no intended net for {key}")
by_net = collections.defaultdict(set)
for key, n in want.items():
    if key not in pin_root:
        errors.append(f"intended pin {key} not placed")
        continue
    if n == "NC":
        if len(got[pin_root[key]]) != 1:
            errors.append(f"{key} should be unconnected but shares a strip with {sorted(got[pin_root[key]] - {key})}")
        continue
    by_net[n].add(key)
root_net = {}
for n, keys in by_net.items():
    roots = {pin_root[k] for k in keys}
    if len(roots) != 1:
        errors.append(f"net {n} is split across {len(roots)} groups: " +
                      "; ".join(sorted(str(sorted(k for k in keys if pin_root[k] == r)) for r in roots)))
    for r in roots:
        if r in root_net and root_net[r] != n:
            errors.append(f"nets {n} and {root_net[r]} are shorted together")
        root_net[r] = n
# rails carry the net they are labelled with
for b, lines in RAILS.items():
    for line, n in lines.items():
        r = find((b, "rail", line))
        if n and r in root_net and root_net[r] != n:
            errors.append(f"rail {b}{line} labelled {n} carries {root_net[r]}")
if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"OK: {len(parts)} parts, {len(wires)} wires, {len(by_net)} nets, {len(used)} holes used")

# ---------------------------------------------------------------------------
# Drawing
def esc(s):
    return html.escape(str(s), quote=True)

def nets_of_hole(h):
    rt = find(node(h))
    return root_net.get(rt, "")

svg = []
W = BOARDS["A"][0] + (COLS + 3) * P + 20
Hpx = BOARDS["B"][1] + (BOARD_H + 6) * P

def board_svg(b):
    ox, oy = BOARDS[b]
    out = [f'<rect x="{ox - P}" y="{oy - P}" width="{(COLS + 1) * P}" height="{(BOARD_H + 1) * P}" rx="8" class="bb"/>']
    out.append(f'<rect x="{ox - P / 2}" y="{oy + 8 * P + 2}" width="{COLS * P}" height="{P - 4}" rx="2" class="channel"/>')
    for line, y in RAIL_Y.items():
        n = RAILS[b][line]
        cls = "rail-pos" if n and n.startswith("+") else "rail-neg"
        yy = oy + y * P
        side = -0.55 if line in (0, 2) else 0.55
        out.append(f'<line x1="{ox}" x2="{ox + (COLS - 1) * P}" y1="{yy + side * P}" y2="{yy + side * P}" class="{cls}"/>')
        out.append(f'<text x="{ox - P * 0.8}" y="{yy + 3}" class="raillab">{esc(n or "")}</text>')
        for c in range(1, COLS + 1):
            if rail_ok(c):
                out.append(f'<rect x="{ox + c * P - 2}" y="{yy - 2}" width="4" height="4" class="hole"/>')
    for r in ROWS:
        for c in range(1, COLS + 1):
            x, y = hxy((b, r, c))
            out.append(f'<rect x="{x - 2}" y="{y - 2}" width="4" height="4" class="hole"/>')
        x, y = hxy((b, r, 0))
        out.append(f'<text x="{x - 2}" y="{y + 3}" class="rowlab">{r}</text>')
    for c in (1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60):
        x, y = hxy((b, "a", c))
        out.append(f'<text x="{x}" y="{oy + 2.2 * P}" class="collab">{c}</text>')
    out.append(f'<text x="{ox + (COLS - 5) * P}" y="{oy - P * 1.4}" class="boardlab">Board {b}</text>')
    return out

for b in BOARDS:
    svg += board_svg(b)

def pt(h):
    if h[0] == "off":
        return STL[h[1]]
    return hxy(h)

def curve(a, b, lift):
    (x1, y1), (x2, y2) = a, b
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    L = max((dx * dx + dy * dy) ** 0.5, 1)
    nx, ny = -dy / L, dx / L
    return f"M{x1},{y1} Q{mx + nx * lift},{my + ny * lift} {x2},{y2}"

# parts first (under wires)
for p in parts:
    k = p["kind"]
    ref, lab = esc(p["ref"]), esc(p["label"])
    pins = p["pins"]
    netlist = " ".join(sorted({nets_of_hole(h) for h in pins.values()} - {""}))
    g = f'<g class="part" data-ref="{ref}" data-nets="{esc(netlist)}" tabindex="0">'
    if k == "dip":
        c0, c1 = p["cols"]
        x0, y0 = hxy(("A", "e", c0)); x1, y1 = hxy(("A", "f", c1))
        g += (f'<rect x="{x0 - 5}" y="{y0 + 2}" width="{x1 - x0 + 10}" height="{y1 - y0 - 4}" rx="2" class="ic"/>'
              f'<circle cx="{x0 - 5}" cy="{(y0 + y1) / 2}" r="4" class="notch"/>'
              f'<circle cx="{x0}" cy="{y1 - 7}" r="1.6" class="pin1"/>'
              f'<text x="{(x0 + x1) / 2}" y="{(y0 + y1) / 2 + 3}" class="iclab">{ref} {lab}</text>')
    elif k == "dual":
        c0, c1 = p["cols"]
        x0, y0 = hxy(("A", "c", c0)); x1, y1 = hxy(("A", "g", c1))
        g += f'<rect x="{x0 - 7}" y="{y0 - 9}" width="{x1 - x0 + 14}" height="{y1 - y0 + 18}" rx="3" class="disp"/>'
        for d in range(2):
            gx = x0 + 6 + d * (x1 - x0) / 2
            g += (f'<text x="{gx + 12}" y="{y1 - 2}" class="glyph">8.</text>')
        g += f'<text x="{(x0 + x1) / 2}" y="{y0 + 1}" class="displab">{ref} {lab}</text>'
    elif k == "adapter":
        c0, c1 = p["cols"]
        x0, y0 = hxy(("B", "c", c0)); x1, y1 = hxy(("B", "g", c1))
        g += (f'<rect x="{x0 - 7}" y="{y0 - 7}" width="{x1 - x0 + 14}" height="{y1 - y0 + 14}" rx="2" class="adapter"/>'
              f'<rect x="{(x0 + x1) / 2 - 16}" y="{(y0 + y1) / 2 - 11}" width="32" height="22" rx="1" class="ic"/>'
              f'<circle cx="{x0}" cy="{y1 - 6}" r="1.8" class="pin1"/>'
              f'<text x="{(x0 + x1) / 2}" y="{y0 + 10}" class="adlab">{ref} {lab}</text>')
        for pn, h in pins.items():
            x, y = hxy(h)
            dy = 9 if h[1] == "g" else -6
            g += f'<text x="{x}" y="{y + dy}" class="pinlab">{esc(MCU_NAME[int(pn)])}</text>'
    elif k in ("res", "cap", "ecap", "button", "led"):
        hs = list(pins.values())
        a, b = pt(hs[0]), pt(hs[1])
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        g += f'<path d="M{a[0]},{a[1]} L{b[0]},{b[1]}" class="lead"/>'
        if k == "res":
            import math
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            g += (f'<g transform="translate({mx} {my}) rotate({ang})">'
                  f'<rect x="-9" y="-3.2" width="18" height="6.4" rx="3" class="resbody" style="stroke:{p.get("color", "#666")}"/>'
                  f'</g>')
        elif k == "cap":
            g += f'<circle cx="{mx}" cy="{my}" r="4.5" class="ccap"/>'
        elif k == "ecap":
            g += f'<circle cx="{mx}" cy="{my}" r="6" class="ecap"/><text x="{mx}" y="{my + 2.5}" class="tiny">+</text>'
        elif k == "button":
            g += (f'<rect x="{mx - 9}" y="{my - 9}" width="18" height="18" rx="2" class="tact"/>'
                  f'<circle cx="{mx}" cy="{my}" r="5" class="btncap"/>'
                  f'<text x="{mx}" y="{my + 19}" class="smalllab">{lab}</text>')
        elif k == "led":
            g += f'<circle cx="{mx}" cy="{my}" r="5" class="led"/>'
        if k in ("res", "cap", "ecap") and lab:
            g += f'<text x="{mx}" y="{my - 6}" class="vallab">{lab}</text>'
    elif k == "to220":
        xs = [hxy(h) for h in pins.values()]
        x0, y0 = xs[0]; x2, _ = xs[2]
        g += (f'<rect x="{x0 - 7}" y="{y0 - 30}" width="{x2 - x0 + 14}" height="24" rx="1" class="tab"/>'
              f'<rect x="{x0 - 7}" y="{y0 - 16}" width="{x2 - x0 + 14}" height="12" class="ic"/>'
              f'<text x="{(x0 + x2) / 2}" y="{y0 - 33}" class="smalllab">{lab}</text>')
        for h in pins.values():
            x, y = hxy(h)
            g += f'<line x1="{x}" y1="{y0 - 4}" x2="{x}" y2="{y}" class="leg"/>'
    elif k == "gps":
        xs = [hxy(h) for h in pins.values()]
        x0, y0 = xs[0]; x4, _ = xs[-1]
        g += (f'<rect x="{x0 - 22}" y="{y0 + 4}" width="{x4 - x0 + 44}" height="58" rx="4" class="gpspcb"/>'
              f'<rect x="{(x0 + x4) / 2 - 14}" y="{y0 + 20}" width="28" height="28" rx="3" class="patch"/>'
              f'<text x="{(x0 + x4) / 2}" y="{y0 + 72}" class="smalllab">{lab} (match your board\'s pin labels)</text>')
        for name, h in pins.items():
            x, y = hxy(h)
            g += f'<text x="{x}" y="{y + 13}" class="pinlab light">{esc(name)}</text>'
    elif k == "stlink":
        g += (f'<rect x="{bx - 82}" y="{by + 2 * P}" width="26" height="{14 * P}" rx="3" class="stl"/>'
              f'<text x="{bx - 69}" y="{by + 9 * P}" class="stllab" transform="rotate(-90 {bx - 69} {by + 9 * P})">ST-Link</text>')
        for name, (x, y) in STL.items():
            g += f'<circle cx="{x}" cy="{y}" r="2.5" class="pin1"/><text x="{x - 2}" y="{y - 4}" class="pinlab" text-anchor="end">{esc(name)}</text>'
    g += "</g>"
    svg.append(g)

# wires on top
for i, w in enumerate(wires):
    a, b = pt(w["a"]), pt(w["b"])
    n = w["label"]
    real = nets_of_hole(w["a"]) if w["a"][0] != "off" else nets_of_hole(w["b"])
    dist = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
    lift = min(40, 6 + dist * 0.12) * (1 if i % 2 else -1)
    d = curve(a, b, lift)
    if w.get("route"):
        k = w["k"]
        top = a if a[1] < b[1] else b
        bot = b if top is a else a
        ax, ay = BOARDS["A"]; bxx, byy = BOARDS["B"]
        if w["route"] == "left":
            xm = ax - 3.2 * P - k * 6
            yA = ay - 1.6 * P - k * 4          # lane above board A's top rail
            yB = byy - 2.2 * P - k * 4         # lane in the gap above board B
            d = (f"M{bot[0]},{bot[1]} L{bot[0]},{yB} L{xm},{yB} L{xm},{yA} L{top[0]},{yA} L{top[0]},{top[1]}")
        else:
            xm = ax + (COLS + 1.6) * P + k * 6
            d = f"M{top[0]},{top[1]} L{xm},{top[1]} L{xm},{bot[1]} L{bot[0]},{bot[1]}"
    svg.append(f'<path d="{d}" class="wire" style="stroke:{w["color"]}" data-nets="{esc(real)}"/>')
    for (x, y) in (a, b):
        svg.append(f'<circle cx="{x}" cy="{y}" r="2.2" class="wend" style="fill:{w["color"]}"/>')

for name, h in PROBES.items():
    x, y = hxy(h)
    svg.append(f'<g class="probe"><circle cx="{x}" cy="{y}" r="4.5"/><text x="{x + 7}" y="{y - 5}">{esc(name)}</text></g>')

svg_markup = f'<svg id="bbsvg" viewBox="0 0 {W} {Hpx}" xmlns="http://www.w3.org/2000/svg">' + "".join(svg) + "</svg>"

# ---------------------------------------------------------------------------
# Wiring table: grouped steps
def hname(h):
    if h[0] == "off":
        return f"ST-Link {h[1]}"
    b, r, c = h
    if isinstance(r, int):
        return f"{b} rail {RAILS[b][r] or '(unused)'} @{c}"
    return f"{b}-{r}{c}"

rows = []
for p in parts:
    if p["kind"] in ("res", "cap", "ecap", "button", "led"):
        hs = list(p["pins"].values())
        rows.append(("Parts", p["ref"], f'{p["label"]} {p["kind"].replace("ecap", "electrolytic, + leg first").replace("res", "resistor").replace("cap", "capacitor")}',
                     hname(hs[0]), hname(hs[1]), " / ".join(n for n in (nets_of_hole(hs[0]), nets_of_hole(hs[1])) if n)))
for w in wires:
    n = nets_of_hole(w["a"]) if w["a"][0] != "off" else nets_of_hole(w["b"])
    rows.append(("Wires", "", "jumper", hname(w["a"]), hname(w["b"]), n))
table = "".join(
    f'<tr data-nets="{esc(r[5])}"><td>{esc(r[1])}</td><td>{esc(r[2])}</td><td class="mono">{esc(r[3])}</td>'
    f'<td class="mono">{esc(r[4])}</td><td class="mono">{esc(r[5])}</td></tr>' for r in rows)

seg_map = (
    "Breadboard segment map (the firmware uses this table for this build): "
    "left digit of each dual QA=A, QB=B, QC=E, QD=D, QE=C, QF=DP, QG=F, QH=G; "
    "right digit QA=A, QB=E, QC=D, QD=G, QE=C, QF=DP, QG=F, QH=B."
)

stats = dict(parts=len(parts), wires=len(wires), resistors=sum(1 for p in parts if p["kind"] == "res"))

tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "breadboard_template.html")).read()
out = (tpl.replace("{{SVG}}", svg_markup).replace("{{TABLE}}", table).replace("{{SEGMAP}}", esc(seg_map))
          .replace("{{STATS}}", esc(f'{stats["parts"]} parts, {stats["resistors"]} resistors, {stats["wires"]} jumper wires')))
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "breadboard.html"), "w").write(out)
print("wrote sim/breadboard.html")
