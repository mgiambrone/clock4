#!/usr/bin/env python3
"""Generate the KiCad 7 schematic for the cheap GPS millisecond clock.

The schematic is written from this script rather than drawn by hand so the
netlist is reviewable as code. Every pin is connected with a short wire stub
and a net label (or a power symbol), so the drawing is a "labelled" schematic
rather than a wired one.

Usage: python3 hardware/tools/gen_schematic.py
Needs the KiCad 7 symbol libraries (Ubuntu: kicad-symbols) for the stock parts.
"""
import os
import re
import uuid

KICAD_SYM_DIR = os.environ.get("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "gpsclock"))
PROJECT = "gpsclock"
NS = uuid.UUID("6f1d3c52-8a8e-4c55-9d6b-2a8f3c1e7a10")


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


ROOT_UUID = uid("root")

# ---------------------------------------------------------------------------
# Symbol library handling
# ---------------------------------------------------------------------------

def _sexpr_block(text, start):
    """Return the balanced s-expression starting at text[start] == '('."""
    depth = 0
    i = start
    in_str = False
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\":
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise ValueError("unbalanced s-expression")


_lib_cache = {}


def lib_symbol(lib, name):
    """Return the flattened symbol definition named 'lib:name' for lib_symbols."""
    if lib not in _lib_cache:
        _lib_cache[lib] = open(os.path.join(KICAD_SYM_DIR, lib + ".kicad_sym")).read()
    text = _lib_cache[lib]
    m = re.search(r'\n  \(symbol "%s"' % re.escape(name), text)
    if not m:
        raise KeyError(f"{lib}:{name}")
    blk = _sexpr_block(text, m.start() + 3)
    ext = re.search(r'\(extends "([^"]+)"\)', blk)
    if ext:
        parent = ext.group(1)
        pblk = lib_symbol(lib, parent)
        # take the parent's graphics/pins, the child's properties
        pblk = pblk.replace(f'(symbol "{lib}:{parent}"', f'(symbol "{lib}:{name}"', 1)
        pblk = re.sub(r'\(symbol "%s_(\d+_\d+)"' % re.escape(parent),
                      lambda mm: f'(symbol "{name}_{mm.group(1)}"', pblk)
        for prop in re.finditer(r'\(property "([^"]+)" ', blk):
            child_prop = _sexpr_block(blk, prop.start())
            pm = re.search(r'\(property "%s" ' % re.escape(prop.group(1)), pblk)
            if pm:
                old = _sexpr_block(pblk, pm.start())
                pblk = pblk.replace(old, child_prop, 1)
        return pblk
    return blk.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)


def pin_table(sym_text):
    """{number: (x, y, angle, name)} in symbol coordinates (y up)."""
    pins = {}
    for m in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)\s*\(length [\d.]+\)'
                         r'(?:\s*hide)?\s*\(name "([^"]*)".*?\(number "([^"]*)"', sym_text, re.S):
        x, y, a, nm, num = m.groups()
        pins.setdefault(num, (float(x), float(y), int(a), nm))
    return pins


# ---------------------------------------------------------------------------
# Custom symbols (also written to gpsclock.kicad_sym)
# ---------------------------------------------------------------------------

def _pin(ptype, x, y, ang, name, num, length=2.54, hide=False):
    return (f'(pin {ptype} line (at {x} {y} {ang}) (length {length}){" hide" if hide else ""}\n'
            f'        (name "{name}" (effects (font (size 1.27 1.27))))\n'
            f'        (number "{num}" (effects (font (size 1.27 1.27)))))')


def _custom(name, props, body, pins, ref):
    p = "\n    ".join(
        f'(property "{k}" "{v}" (at 0 {y} 0) (effects (font (size 1.27 1.27)){" hide" if h else ""}))'
        for k, v, y, h in props)
    return (f'(symbol "{name}" (in_bom yes) (on_board yes)\n    {p}\n'
            f'    (symbol "{name.split(":")[-1]}_0_1"\n      {body})\n'
            f'    (symbol "{name.split(":")[-1]}_1_1"\n      ' + "\n      ".join(pins) + "))")


def atgm336h_symbol(prefix):
    pins = []
    left = [("8", "VCC", "power_in"), ("6", "VBAT", "power_in"), ("14", "VCC_RF", "power_out"),
            ("5", "ON/~{OFF}", "input"), ("9", "~{RESET}", "input"), ("3", "RXD", "input"),
            ("2", "TXD", "output"), ("4", "1PPS", "output")]
    for i, (num, nm, t) in enumerate(left):
        pins.append(_pin(t, -15.24, 10.16 - i * 2.54, 0, nm, num))
    right = [("11", "RF_IN", "input"), ("16", "SDA", "bidirectional"), ("17", "SCL", "bidirectional"),
             ("7", "NC", "no_connect"), ("13", "NC", "no_connect"), ("15", "RESERVED", "no_connect"),
             ("18", "NC", "no_connect")]
    for i, (num, nm, t) in enumerate(right):
        pins.append(_pin(t, 15.24, 10.16 - i * 2.54, 180, nm, num))
    for i, num in enumerate(["1", "10", "12"]):
        pins.append(_pin("power_in", -7.62 + i * 7.62, -15.24, 90, "GND", num))
    body = ('(rectangle (start -12.7 12.7) (end 12.7 -12.7) (stroke (width 0.254) (type default)) '
            '(fill (type background)))')
    props = [("Reference", "U", 13.97, False), ("Value", "ATGM336H-5N31", -26.67, False),
             ("Footprint", "RF_GPS:ublox_MAX", -19.05, True),
             ("Datasheet", "https://www.lcsc.com/product-detail/C90770.html", -21.59, True)]
    return _custom(f"{prefix}ATGM336H-5N31", props, body, pins, "U")


def seg7_symbol(prefix):
    # Common 0.56" single digit, common cathode, "5161AS" pinout:
    # 1 E, 2 D, 3 CC, 4 C, 5 DP, 6 B, 7 A, 8 CC, 9 F, 10 G
    pins = []
    left = [("7", "A"), ("6", "B"), ("4", "C"), ("2", "D"), ("1", "E"), ("9", "F"), ("10", "G"), ("5", "DP")]
    for i, (num, nm) in enumerate(left):
        pins.append(_pin("passive", -10.16, 8.89 - i * 2.54, 0, nm, num))
    pins.append(_pin("passive", 10.16, 1.27, 180, "CC", "3"))
    pins.append(_pin("passive", 10.16, -1.27, 180, "CC", "8"))
    # rectangle plus a sketch of the digit
    seg = ('(polyline (pts (xy -1.27 5.08) (xy 2.54 5.08) (xy 2.54 0) (xy -1.27 0) (xy -1.27 5.08)) '
           '(stroke (width 0.254) (type default)) (fill (type none)))\n      '
           '(polyline (pts (xy -1.27 0) (xy -1.27 -5.08) (xy 2.54 -5.08) (xy 2.54 0)) '
           '(stroke (width 0.254) (type default)) (fill (type none)))\n      '
           '(circle (center 3.81 -5.08) (radius 0.3) (stroke (width 0.254) (type default)) '
           '(fill (type outline)))')
    body = ('(rectangle (start -7.62 10.16) (end 7.62 -11.43) (stroke (width 0.254) (type default)) '
            '(fill (type background)))\n      ' + seg)
    props = [("Reference", "DS", 11.43, False), ("Value", "7SEG_0.56_CC_5161AS", -13.97, False),
             ("Footprint", "Display_7Segment:7SegmentLED_LTS6760_LTS6780", -16.51, True),
             ("Datasheet", "~", -19.05, True)]
    return _custom(f"{prefix}7SEG_CC_5161AS", props, body, pins, "DS")


CUSTOM_LIB = "gpsclock"
CUSTOM = {
    "ATGM336H-5N31": atgm336h_symbol,
    "7SEG_CC_5161AS": seg7_symbol,
}


def get_symbol(lib_id):
    lib, name = lib_id.split(":")
    if lib == CUSTOM_LIB:
        return CUSTOM[name](CUSTOM_LIB + ":")
    return lib_symbol(lib, name)


# ---------------------------------------------------------------------------
# Schematic model
# ---------------------------------------------------------------------------

STUB = 2.54
DIRS = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}  # outward, in schematic coords (y down)


def r2(v):
    return round(v, 2)


class Sheet:
    def __init__(self):
        self.lib_ids = []
        self.items = []
        self.pwr_n = 0
        self.refs = set()
        self.conns = {}  # ref -> {pin: net}, for check_netlist.py
        self.footprints = {}  # ref -> footprint, for check_netlist.py

    def _need(self, lib_id):
        if lib_id not in self.lib_ids:
            self.lib_ids.append(lib_id)
        return pin_table(get_symbol(lib_id))

    def text(self, x, y, s, size=2.54):
        s = s.replace('"', "'")
        self.items.append(f'(text "{s}" (at {x} {y} 0) (effects (font (size {size} {size})) '
                          f'(justify left bottom)) (uuid {uid("text", x, y, s)}))')

    def _wire(self, x1, y1, x2, y2):
        self.items.append(f'(wire (pts (xy {r2(x1)} {r2(y1)}) (xy {r2(x2)} {r2(y2)})) '
                          f'(stroke (width 0) (type default)) (uuid {uid("w", x1, y1, x2, y2)}))')

    def _label(self, x, y, d, net):
        ang = {(-1, 0): 180, (1, 0): 0, (0, 1): 270, (0, -1): 90}[d]
        just = "right" if ang in (180, 270) else "left"
        self.items.append(f'(label "{net}" (at {r2(x)} {r2(y)} {ang}) (fields_autoplaced) '
                          f'(effects (font (size 1.27 1.27)) (justify {just} bottom)) '
                          f'(uuid {uid("lbl", x, y, net)}))')

    def _power(self, x, y, net, d=None):
        """Power symbol whose pin sits at (x, y), pointing away along d."""
        lib_id = "power:" + net
        self._need(lib_id)
        self.pwr_n += 1
        ref = f"#PWR{self.pwr_n:03d}" if net != "PWR_FLAG" else f"#FLG{self.pwr_n:03d}"
        u = uid("pwr", x, y, net)
        base = (0, 1) if net == "GND" else (0, -1)
        d = d or base
        # KiCad rotates symbols counter-clockwise on screen
        rot = {((0, -1), (0, -1)): 0, ((0, -1), (-1, 0)): 90, ((0, -1), (0, 1)): 180, ((0, -1), (1, 0)): 270,
               ((0, 1), (0, 1)): 0, ((0, 1), (1, 0)): 90, ((0, 1), (0, -1)): 180, ((0, 1), (-1, 0)): 270}[(base, d)]
        off = 7.62 if d[0] else 5.08  # horizontal text needs more room
        tx, ty = x + d[0] * off, y + d[1] * off
        self.items.append(
            f'(symbol (lib_id "{lib_id}") (at {r2(x)} {r2(y)} {rot}) (unit 1) (in_bom yes) (on_board yes) '
            f'(dnp no) (uuid {u})\n'
            f'  (property "Reference" "{ref}" (at {r2(x)} {r2(y)} 0) (effects (font (size 1.27 1.27)) hide))\n'
            f'  (property "Value" "{net}" (at {r2(tx)} {r2(ty)} {90 if rot in (90, 270) else 0}) '
            f'(effects (font (size 1.27 1.27))))\n'
            f'  (property "Footprint" "" (at {r2(x)} {r2(y)} 0) (effects (font (size 1.27 1.27)) hide))\n'
            f'  (property "Datasheet" "" (at {r2(x)} {r2(y)} 0) (effects (font (size 1.27 1.27)) hide))\n'
            f'  (pin "1" (uuid {uid(u, "p1")}))\n'
            f'  (instances (project "{PROJECT}" (path "/{ROOT_UUID}" (reference "{ref}") (unit 1)))))')

    def flag(self, x, y, net):
        """PWR_FLAG on a net, drawn with its own label."""
        self._power(x, y, "PWR_FLAG")
        self._wire(x, y, x, y + STUB)
        self._power(x, y + STUB, net, (0, 1))

    def part(self, lib_id, ref, value, x, y, conns, footprint="", fields=None, dnp=False):
        """Place a symbol. conns maps pin number -> net name, 'NC' for no-connect.

        Nets '+5V', '+3V3', 'GND' become power symbols; everything else a label.
        """
        assert ref not in self.refs, ref
        self.refs.add(ref)
        self.conns[ref] = dict(conns)
        pins = self._need(lib_id)
        missing = set(pins) - set(conns)
        extra = set(conns) - set(pins)
        assert not missing and not extra, (ref, sorted(missing), sorted(extra))
        u = uid("sym", ref)
        if not footprint:
            # fall back to the library's default footprint instead of blanking it
            fm = re.search(r'\(property "Footprint" "([^"]*)"', get_symbol(lib_id))
            footprint = fm.group(1) if fm else ""
        self.footprints[ref] = footprint
        props = [("Reference", ref), ("Value", value), ("Footprint", footprint), ("Datasheet", "~")]
        props += list((fields or {}).items())
        sym = get_symbol(lib_id)
        prop_txt = ""
        for k, v in props:
            lm = re.search(r'\(property "%s" "[^"]*" \(at ([-\d.]+) ([-\d.]+) (\d+)\)' % k, sym)
            if k in ("Reference", "Value") and lm:
                # keep the library's placement for reference/value text
                eff = _sexpr_block(sym, sym.index("(effects", lm.end()))
                eff = eff.replace(" hide", "")
                px, py, pa = float(lm.group(1)), float(lm.group(2)), lm.group(3)
                prop_txt += (f'  (property "{k}" "{v}" (at {r2(x + px)} {r2(y - py)} {pa}) {eff})\n')
            else:
                prop_txt += (f'  (property "{k}" "{v}" (at {r2(x)} {r2(y)} 0) '
                             f'(effects (font (size 1.27 1.27)) hide))\n')
        pin_txt = "".join(f'  (pin "{n}" (uuid {uid(u, n)}))\n' for n in pins)
        self.items.append(
            f'(symbol (lib_id "{lib_id}") (at {r2(x)} {r2(y)} 0) (unit 1) (in_bom yes) (on_board yes) '
            f'(dnp {"yes" if dnp else "no"}) (uuid {u})\n{prop_txt}{pin_txt}'
            f'  (instances (project "{PROJECT}" (path "/{ROOT_UUID}" (reference "{ref}") (unit 1)))))')
        for num, net in conns.items():
            px, py, ang, _ = pins[num]
            ex, ey = x + px, y - py
            if net == "NC":
                self.items.append(f'(no_connect (at {r2(ex)} {r2(ey)}) (uuid {uid("nc", ref, num)}))')
                continue
            d = DIRS[ang]
            sx, sy = ex + d[0] * STUB, ey + d[1] * STUB
            self._wire(ex, ey, sx, sy)
            if net in ("+5V", "+3V3", "GND"):
                self._power(sx, sy, net, d)
            else:
                self._label(sx, sy, d, net)

    def write(self, path, title):
        libs = "\n".join("    " + get_symbol(l).replace("\n", "\n    ") for l in self.lib_ids)
        body = "\n  ".join(self.items)
        with open(path, "w") as f:
            f.write(f'(kicad_sch (version 20230121) (generator eeschema)\n'
                    f'  (uuid {ROOT_UUID})\n  (paper "A2")\n'
                    f'  (title_block (title "{title}") (date "2026-10-04") (rev "0.1")\n'
                    f'    (comment 1 "Generated by hardware/tools/gen_schematic.py - edit the script, not this file"))\n'
                    f'  (lib_symbols\n{libs}\n  )\n  {body}\n'
                    f'  (sheet_instances (path "/" (page "1")))\n)\n')


# ---------------------------------------------------------------------------
# The design
# ---------------------------------------------------------------------------

FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_C_BULK = "Capacitor_SMD:C_0805_2012Metric"
FP_LED = "LED_SMD:LED_0603_1608Metric"
FP_LED_COLON = "LED_THT:LED_D3.0mm"
FP_595 = "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"

SEGS = ["A", "B", "C", "D", "E", "F", "G", "DP"]
QS = ["QA", "QB", "QC", "QD", "QE", "QF", "QG", "QH"]
Q_PIN = {"QA": "15", "QB": "1", "QC": "2", "QD": "3", "QE": "4", "QF": "5", "QG": "6", "QH": "7"}
SEG_PIN = {"A": "7", "B": "6", "C": "4", "D": "2", "E": "1", "F": "9", "G": "10", "DP": "5"}

DIGIT_NAMES = {1: "H tens", 2: "H units", 3: "M tens", 4: "M units", 5: "S tens",
               6: "S units (DP = decimal point)", 7: "1/10 s", 8: "1/100 s", 9: "1/1000 s"}


def r(s, ref, val, x, y, n1, n2, fp=FP_R, **kw):
    s.part("Device:R", ref, val, x, y, {"1": n1, "2": n2}, fp, **kw)


def c(s, ref, val, x, y, n1, n2="GND", fp=FP_C, **kw):
    s.part("Device:C", ref, val, x, y, {"1": n1, "2": n2}, fp, **kw)


def build():
    s = Sheet()

    # ---------------- Power ----------------
    s.text(20, 22, "POWER: USB-C 5 V in, power only", 3)
    s.part("Connector:USB_C_Receptacle_PowerOnly_6P", "J1", "USB-C power", 35, 55,
           {"A5": "CC1", "B5": "CC2", "A9": "VBUS", "B9": "VBUS", "A12": "GND", "B12": "GND", "S1": "GND"},
           "Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal")
    r(s, "R1", "5.1k", 65, 70, "CC1", "GND")
    r(s, "R2", "5.1k", 75, 70, "CC2", "GND")
    s.part("Device:Polyfuse", "F1", "750mA hold", 65, 45, {"1": "VBUS", "2": "+5V"},
           "Fuse:Fuse_1206_3216Metric")
    c(s, "C1", "4.7u", 80, 45, "+5V", fp=FP_C_BULK)
    s.part("Regulator_Linear:AP2112K-3.3", "U2", "AP2112K-3.3", 115, 50,
           {"1": "+5V", "2": "GND", "3": "+5V", "4": "NC", "5": "+3V3"})
    c(s, "C2", "1u", 100, 65, "+5V")
    c(s, "C3", "10u", 135, 65, "+3V3", fp=FP_C_BULK)
    s.flag(150, 40, "+5V")
    s.flag(160, 40, "GND")

    # ---------------- MCU ----------------
    s.text(20, 100, "MCU: STM32G030F6P6 (TSSOP-20)", 3)
    s.text(20, 106, "HSE in BYPASS mode on PC14: this package has no OSC_OUT, so no crystal.", 2)
    s.part("MCU_ST_STM32G0:STM32G030F6Px", "U1", "STM32G030F6P6", 90, 140, {
        "1": "DBG_RX",        # PB7 = USART1_RX (PB8 bonded to same pin, keep it as input)
        "2": "HSE_IN",        # PC14 = RCC_OSC_IN (bypass)
        "3": "NC",            # PC15 spare
        "4": "+3V3", "5": "GND",
        "6": "NRST",
        "7": "LIGHT",         # PA0 = ADC1_IN0
        "8": "BTN",           # PA1 GPIO in, internal pull-up
        "9": "GPS_RXD",       # PA2 = USART2_TX -> GPS RXD
        "10": "GPS_TXD",      # PA3 = USART2_RX <- GPS TXD
        "11": "DISP_OE",      # PA4 = TIM14_CH1 PWM -> /OE
        "12": "SR_CLK_MCU",   # PA5 = SPI1_SCK, 33R series (R100) to the chain
        "13": "GPS_PPS",      # PA6 = TIM3_CH1 input capture
        "14": "SR_DATA",      # PA7 = SPI1_MOSI
        "15": "SR_LATCH_MCU", # PB0 = TIM3_CH3 output compare (PB1/PB2/PA8 bonded: keep them as inputs)
        "16": "LED_STATUS",   # PA11 GPIO
        "17": "GPS_RESET",    # PA12 GPIO, open-drain
        "18": "SWDIO",        # PA13
        "19": "SWCLK",        # PA14
        "20": "DBG_TX",       # PB6 = USART1_TX (PB3/PB4/PB5 bonded: keep them as inputs)
    }, "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm", {"LCSC": "C724040"})
    c(s, "C4", "100n", 130, 120, "+3V3")
    c(s, "C5", "4.7u", 140, 120, "+3V3", fp=FP_C_BULK)
    c(s, "C6", "100n", 150, 120, "NRST")

    s.text(20, 178, "Clock: 16 MHz 3.3 V CMOS oscillator.", 2)
    s.text(20, 183, "Same footprint fits a CMOS-output TCXO (check its pin 1 is EN or NC, not VC).", 2)
    s.part("Oscillator:ASE-xxxMHz", "Y1", "16MHz CMOS 3.3V", 45, 200,
           {"1": "OSC_EN", "2": "GND", "3": "OSC_OUT", "4": "+3V3"},
           "Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm")
    r(s, "R3", "10k", 25, 200, "+3V3", "OSC_EN")
    r(s, "R4", "22", 70, 200, "OSC_OUT", "HSE_IN")
    c(s, "C7", "100n", 80, 200, "+3V3")

    # ---------------- GPS ----------------
    s.text(20, 222, "GPS: ATGM336H-5N31", 3)
    s.text(20, 228, "Uses the u-blox MAX footprint (same 18-pad layout). Active antenna via u.FL.", 2)
    s.part(f"{CUSTOM_LIB}:ATGM336H-5N31", "U3", "ATGM336H-5N31", 75, 265, {
        "8": "+3V3", "6": "+3V3",          # VBAT tied to VCC: no backup battery (cold start after power loss)
        "14": "VCC_RF", "5": "GPS_ONOFF", "9": "GPS_RESET",
        "3": "GPS_RXD", "2": "GPS_TXD", "4": "GPS_PPS",
        "11": "GPS_RF", "16": "NC", "17": "NC", "7": "NC", "13": "NC", "15": "NC", "18": "NC",
        "1": "GND", "10": "GND", "12": "GND",
    }, "RF_GPS:ublox_MAX", {"LCSC": "C90770"})
    c(s, "C8", "10u", 25, 250, "+3V3", fp=FP_C_BULK)
    c(s, "C9", "100n", 35, 250, "+3V3")
    r(s, "R6", "10k", 25, 280, "+3V3", "GPS_ONOFF")
    r(s, "R7", "10k", 35, 280, "+3V3", "GPS_RESET")
    r(s, "R8", "0", 120, 245, "VCC_RF", "ANT_BIAS")  # ATGM336H-5N manual 2.7.1 shows only L1; pad kept as an option
    s.part("Device:L", "L1", "47nH", 120, 285, {"1": "ANT_BIAS", "2": "GPS_RF"},
           "Inductor_SMD:L_0603_1608Metric")
    s.part("Connector:Conn_Coaxial", "J2", "u.FL (active antenna)", 140, 275, {"1": "GPS_RF", "2": "GND"},
           "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical")
    s.part("Connector:TestPoint", "TP1", "PPS", 160, 280, {"1": "GPS_PPS"},
           "TestPoint:TestPoint_Pad_D1.0mm")

    # ---------------- Misc I/O ----------------
    s.text(20, 315, "I/O: SWD, debug UART, button, status LED, light sensor (optional)", 3)
    s.part("Connector_Generic:Conn_01x05", "J3", "SWD", 35, 340,
           {"1": "+3V3", "2": "SWDIO", "3": "SWCLK", "4": "NRST", "5": "GND"},
           "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical")
    s.part("Connector_Generic:Conn_01x03", "J4", "UART debug", 35, 370,
           {"1": "DBG_TX", "2": "DBG_RX", "3": "GND"},
           "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical")
    s.part("Switch:SW_Push", "SW1", "Brightness", 80, 335, {"1": "BTN", "2": "GND"},
           "Button_Switch_THT:SW_PUSH_6mm")
    r(s, "R9", "1k", 75, 360, "LED_STATUS", "LED_STATUS_A")
    s.part("Device:LED", "D5", "green", 100, 362, {"1": "GND", "2": "LED_STATUS_A"}, FP_LED)
    s.part("Device:Q_Photo_NPN", "Q1", "phototransistor (TBD)", 125, 340, {"1": "+3V3", "2": "LIGHT"},
           "", dnp=False)
    r(s, "R10", "10k", 140, 360, "LIGHT", "GND")
    c(s, "C10", "100n", 150, 360, "LIGHT")
    s.part("Connector:TestPoint", "TP2", "LATCH", 125, 380, {"1": "SR_LATCH"},
           "TestPoint:TestPoint_Pad_D1.0mm")

    # ---------------- Display ----------------
    s.text(190, 22, "DISPLAY: HH:MM:SS.mmm, 9 digits, each statically driven by a 74HCT595 (5 V).", 3)
    s.text(190, 28, "Chain: SR_DATA -> U11 -> U12 ... -> U19. All latch together on SR_LATCH. /OE = PWM brightness.", 2)
    s.text(190, 33, "Segment resistors 470R: ~5.7-6.4 mA per LED. 8 LEDs per 595 (~46-51 mA); U12/U14 drive 9 (~51-58 mA). Limit 70 mA.", 2)
    s.text(190, 38, "All 74 LEDs on: ~0.42-0.47 A from 5 V. Firmware must cap /OE duty for an all-segments self-test.", 2)
    r(s, "R5", "10k", 560, 22, "+3V3", "DISP_OE")  # keeps display dark until MCU drives /OE
    # Bulk for the /OE PWM load steps. Kept small: total on VBUS stays near the USB 10 uF limit.
    c(s, "C20", "10u", 540, 22, "+5V", fp=FP_C_BULK)
    # 33R series resistors at the MCU for the two nets that fan out to all nine '595s
    r(s, "R100", "33", 175, 150, "SR_CLK_MCU", "SR_CLK")
    r(s, "R101", "33", 182.62, 150, "SR_LATCH_MCU", "SR_LATCH")

    col_w, row_h = 130, 110
    for n in range(1, 10):
        bx = 190 + ((n - 1) % 3) * col_w
        by = 45 + ((n - 1) // 3) * row_h
        s.text(bx, by + 2, f"DS{n}: {DIGIT_NAMES[n]}", 2)
        ser = "SR_DATA" if n == 1 else f"SR_D{n}"
        qh_out = f"SR_D{n + 1}" if n < 9 else "NC"
        s.part("74xx:74HCT595", f"U1{n}", "74HCT595", bx + 22, by + 30, {
            "14": ser, "11": "SR_CLK", "12": "SR_LATCH", "13": "DISP_OE", "10": "+5V",
            "16": "+5V", "8": "GND", "9": qh_out,
            **{Q_PIN[q]: f"D{n}_{q}" for q in QS},
        }, FP_595)
        c(s, f"C1{n}", "100n", bx + 8, by + 66, "+5V")
        colon = n in (2, 4)
        for k, (q, seg) in enumerate(zip(QS, SEGS)):
            if colon and seg == "DP":
                # QH drives the two colon LEDs instead of this digit's DP
                cl = 1 if n == 2 else 2
                r(s, f"R{n}8", "470", bx + 50 + k * 7.62, by + 25, f"D{n}_QH", f"COL{cl}_1")
                r(s, f"R{n}9", "470", bx + 50 + (k + 1) * 7.62, by + 25, f"D{n}_QH", f"COL{cl}_2")
            else:
                r(s, f"R{n}{k + 1}", "470", bx + 50 + k * 7.62, by + 25, f"D{n}_{q}", f"D{n}_{seg}")
        seg_conns = {SEG_PIN[sg]: f"D{n}_{sg}" for sg in SEGS}
        if colon:
            seg_conns[SEG_PIN["DP"]] = "NC"
        seg_conns.update({"3": "GND", "8": "GND"})
        s.part(f"{CUSTOM_LIB}:7SEG_CC_5161AS", f"DS{n}", "0.56in CC red", bx + 108, by + 65, seg_conns,
               "Display_7Segment:7SegmentLED_LTS6760_LTS6780")

    s.text(190, 382, "Colons: between DS2|DS3 (COL1) and DS4|DS5 (COL2). Two 3 mm red LEDs each, driven from QH of U12 / U14.", 2)
    for i, (net, ref) in enumerate([("COL1_1", "D1"), ("COL1_2", "D2"), ("COL2_1", "D3"), ("COL2_2", "D4")]):
        s.part("Device:LED", ref, "red 3mm", 200 + i * 30, 400, {"1": "GND", "2": net}, FP_LED_COLON)

    return s


def write_custom_lib(path):
    syms = "\n  ".join(CUSTOM[n]("") for n in CUSTOM)
    with open(path, "w") as f:
        f.write(f"(kicad_symbol_lib (version 20220914) (generator gen_schematic)\n  {syms}\n)\n")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    s = build()
    s.write(os.path.join(OUT_DIR, f"{PROJECT}.kicad_sch"), "GPS ms wall clock")
    write_custom_lib(os.path.join(OUT_DIR, f"{PROJECT}.kicad_sym"))
    with open(os.path.join(OUT_DIR, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (lib (name "gpsclock")(type "KiCad")'
                '(uri "${KIPRJMOD}/gpsclock.kicad_sym")(options "")(descr "Custom parts"))\n)\n')
    pro = os.path.join(OUT_DIR, f"{PROJECT}.kicad_pro")
    if not os.path.exists(pro):
        with open(pro, "w") as f:
            f.write('{\n  "meta": {\n    "filename": "gpsclock.kicad_pro",\n    "version": 1\n  }\n}\n')
    print("wrote", OUT_DIR, "-", len(s.refs), "parts")


if __name__ == "__main__":
    main()
