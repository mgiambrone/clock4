# Draft BOM: cheap GPS ms wall clock

This is for the design in `analysis.md` and the schematic in
`hardware/gpsclock/` (rev 0.2): STM32G030F6, ATGM336H, 10× 74HCT595 static
drive, five 0.56" dual digits (HH:MM:SS.mmmm), two buttons, USB-C power only.

**Reference designators match the schematic.** They were generated from the
KiCad netlist. If the schematic changes, regenerate this list from it (`kicad-cli
sch export netlist`) rather than editing by hand.

Prices are rough **single-board / 10-piece LCSC-style** figures in USD. Where I
checked a live listing, it's marked ✓ (checked Oct 2026). Everything else is an
estimate and could be off by ±50%. Get a real quote before ordering. Part
numbers marked "e.g." are examples, not verified picks.

## Core parts

| Refs | Qty | Part | Footprint | Unit $ | Line $ | Notes |
|---|---|---|---|---|---|---|
| U1 | 1 | STM32G030F6P6 | TSSOP-20 | 0.62 ✓ (@10) | 0.62 | LCSC C724040. 0.75 at qty 1. |
| Y1 | 1 | 16 MHz 3.3 V CMOS oscillator | 3225 4-pad (Abracon ASE) | ~0.15–0.30 | 0.25 | Or a CMOS-output TCXO, e.g. YXC OW2EL89CENUXFMYLC-16M (±2.5 ppm) at 0.95 ✓. Pin 1 must be EN or NC, not VC. |
| U3 | 1 | ATGM336H-5N31 GNSS module | u-blox MAX | 1.82 ✓ | 1.82 | LCSC C90770. Confirm the PPS pin on this exact variant. |
| J2 | 1 | u.FL receptacle (Hirose U.FL-R-SMT-1 or clone) | U.FL vertical | ~0.10 | 0.10 | |
| — | 1 | Active GPS patch antenna, 3 m cable, SMA, plus a u.FL→SMA bulkhead pigtail | off-board | ~2–4 | 3.00 | AliExpress-type items. |
| L1 | 1 | 47 nH RF inductor, SRF well above 1.6 GHz (e.g. Murata LQW18AN47N) | 0603 | ~0.05 | 0.05 | Per the ATGM336H-5N manual, section 2.7.1. |
| R8 | 1 | 0 Ω | 0603 | ~0.002 | 0.00 | Option pad in the antenna feed. |
| U11–U20 | 10 | 74HCT595 (must be **HCT**) | SOIC-16 | ~0.10–0.20 | 1.50 | |
| DS1–DS5 | 5 | **Kingbright DC56-11EWA**, 0.56" dual digit, common cathode, red, 18 pins | DA56-11 (2×9, 15.24 mm rows) | 3.64 ✓ (qty 1), 2.13 ✓ (qty 10, Mouser) | 12.00 | In stock at Mouser/DigiKey (Oct 2026). Generic 10-pin multiplexed duals won't work. This is now the most expensive part. |
| D1–D4 | 4 | Red LED, 3 mm | THT | ~0.02 | 0.08 | Colons. |
| R11–R18, R21–R29, R31–R38, R41–R49, R51–R58, R61–R68, R71–R78, R81–R88, R91–R98, R101–R108 | 82 | 470 Ω | 0603 | ~0.002 | 0.17 | Segments, DPs and colons. R28/R29 and R48/R49 feed the colon LEDs. |
| R120, R121 | 2 | 33 Ω | 0603 | ~0.002 | 0.01 | Series resistors on SR_CLK / SR_LATCH. |

## Power

| Refs | Qty | Part | Footprint | Unit $ | Line $ | Notes |
|---|---|---|---|---|---|---|
| J1 | 1 | USB-C receptacle, 6-pin power-only | GCT USB4125 land pattern | ~0.10–0.25 | 0.20 | Pick a clone with the same land pattern. |
| R1, R2 | 2 | 5.1 kΩ | 0603 | ~0.002 | 0.01 | CC pull-downs. |
| F1 | 1 | Polyfuse, **750 mA hold** (e.g. 1206L075-class) | 1206 | ~0.03–0.06 | 0.05 | 500 mA was too close to the worst-case load. |
| U2 | 1 | AP2112K-3.3 | SOT-23-5 | ~0.05–0.15 | 0.10 | |
| C3, C8, C21 | 3 | 10 µF | 0805 | ~0.01 | 0.03 | LDO out, GPS, display bulk. |
| C1, C5 | 2 | 4.7 µF | 0805 | ~0.01 | 0.02 | USB input, MCU. |
| C2 | 1 | 1 µF | 0603 | ~0.005 | 0.01 | LDO input. |
| C4, C6, C7, C9–C20 | 15 | 100 nF | 0603 | ~0.002 | 0.03 | Decoupling, NRST, light-sensor filter. |

## Small stuff / optional

| Refs | Qty | Part | Footprint | Unit $ | Line $ | Notes |
|---|---|---|---|---|---|---|
| R3, R5, R6, R7, R10 | 5 | 10 kΩ | 0603 | ~0.002 | 0.01 | Pull-ups and light-sensor load. |
| R4 | 1 | 22 Ω | 0603 | ~0.002 | 0.00 | Oscillator output series. |
| R9 | 1 | 1 kΩ | 0603 | ~0.002 | 0.00 | Status LED. |
| D5 | 1 | Green LED | 0603 | ~0.01 | 0.01 | Status. |
| J3 | 1 | 1×5 pin header 2.54 mm (SWD) | THT | ~0.03 | 0.03 | |
| J4 | 1 | 1×3 pin header 2.54 mm (debug UART) | THT | ~0.02 | 0.02 | Optional. |
| SW1, SW2 | 2 | 6 mm tactile switch | THT | ~0.03 | 0.06 | Brightness and mode. |
| Q1 | 1 | Phototransistor | **TBD** | ~0.05–0.10 | 0.10 | Optional. Part and footprint not chosen yet. |
| TP1, TP2 | 2 | Test pads | 1 mm pad | 0 | 0.00 | PPS and latch. |
| — | — | GPS backup cell on VBAT (instead of tying it to VCC) | — | ~0.30–1.00 | — | Optional, not in the total. |
| — | — | RF ESD diode on GPS_RF, ≤ 0.3 pF (e.g. Infineon ESD0P2RF-02LS) | — | ~0.10–0.20 | — | Optional, not on the schematic yet. |

## Totals per board (parts only)

| Variant | Approx. total |
|---|---|
| As listed (5 DC56-11 duals at the 10-off price, plain oscillator, antenna) | **≈ $20** |
| Same, buying the duals one at a time (~$3.65 each) | ≈ $27 |
| With TCXO | add ≈ $0.70 |
| Rev 0.1 for comparison (nine generic single digits) | ≈ $10 |
| Without the antenna (if you already have one) | subtract ~$3 |

These exclude:

- **PCB:** 2-layer, 1.6 mm, about 150–160 × 40 mm for five 0.56" duals
  (each ~25 mm wide) plus colon gaps. PCBWay pricing jumps above 100 × 100 mm. I don't have a current quote;
  expect roughly $10–30 for 5 boards plus shipping, but check.
- **Assembly**, if you use PCBWay assembly: setup, stencil and handling fees tend
  to dominate at 1–5 boards. Everything here is hand-solderable (smallest pitch
  is 0.65 mm TSSOP; the GPS module has castellated edges), so ordering the bare
  PCB + stencil and assembling yourself is likely cheapest.
- **Enclosure / mounting:** front filter (e.g. red-tinted acrylic) and hanger.
- Shipping and tax.
- **Power supply:** use a phone charger (≥ 1 A). The worst-case load (~0.55–0.6 A)
  is above what a PC USB 2.0 port has to supply.

## Parts removed compared with the Mk IV (for reference)

Second MCU (STM32L010) and the date board, 10 date digits and their drivers,
the hinge, 16 MB QSPI flash, the 32.768 kHz crystal and coin cell holder, the
light-sensor DAC drive circuit, USB data/ESD parts, the date-board buttons, and
the STM32L476 itself (replaced by a ~$0.62 part).
