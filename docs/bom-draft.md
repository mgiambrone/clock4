# Draft BOM: cheap GPS ms wall clock

This is for the design in `analysis.md`: STM32G030F6, ATGM336H, 9× 74HCT595
static drive, 9 single digits, USB-C power only.

Prices are rough **single-board / 10-piece LCSC-style** figures in USD. Where I
checked a live listing, it's marked ✓ (checked Oct 2026). Everything else is my
estimate from typical prices and could easily be off by ±50%. Get a real quote
before ordering. Part numbers marked "e.g." are examples, not verified picks.

## Core parts

| # | Ref | Part | Qty | Unit $ | Line $ | Notes |
|---|---|---|---|---|---|---|
| 1 | U1 | STM32G030F6P6, TSSOP-20 | 1 | 0.62 ✓ (@10) | 0.62 | 0.75 at qty 1. No HSE crystal support in TSSOP-20, so it needs Y1 as an external clock. |
| 2 | Y1 | 16 MHz 3.3 V CMOS oscillator, 3225 4-pad | 1 | ~0.15–0.30 | ~0.25 | **Or** a CMOS-output TCXO in the same footprint, e.g. YXC OW2EL89CENUXFMYLC-16M (±2.5 ppm) at 0.95 ✓. Check the output type is CMOS, not clipped sine. |
| 3 | U2 | ATGM336H-5N31 GNSS module | 1 | 1.82 ✓ | 1.82 | **Confirm the PPS pin on this exact variant** before ordering (see analysis). |
| 4 | J2 | u.FL / IPEX connector (or edge SMA ~0.30–0.50) | 1 | ~0.10 | 0.10 | |
| 5 | — | Active GPS patch antenna, 3 m cable, SMA | 1 | ~2–4 | ~3.00 | Off-board. AliExpress-type item. Add a u.FL→SMA bulkhead pigtail (~0.50) if you use u.FL. |
| 6 | L1/R | Antenna bias parts (inductor + resistor per ATGM336H reference circuit) | 1 set | ~0.05 | 0.05 | Values from the datasheet. Not checked yet. |
| 7 | U3–U11 | 74HCT595, SOIC-16 or TSSOP-16 | 9 | ~0.10–0.20 | ~1.35 | Must be **HCT** (3.3 V logic in, 5 V supply). |
| 8 | DS1–DS9 | Single-digit 7-segment, **common cathode**, red | 9 | 0.56": ~0.15–0.30; 1": ~0.5–1.0 | 0.56": ~2.00; 1": ~6.50 | Pick one size. Same part ×9. Check the CC pinout on the datasheet. |
| 9 | D1–D4 | Colon LEDs, red (3 mm THT or 0805) | 4 | ~0.02 | 0.08 | Driven from the DP outputs of digits 2 and 4. |
| 10 | R1–R72 | Segment resistors, 0603, ~470 Ω for ~5–6 mA at 5 V with red LEDs | 72 | ~0.002 | 0.15 | Or 18× 4-resistor 0603 arrays (~0.01 each), with fewer placements but finer pads. Final value depends on the digits' Vf and the brightness you want. |
| 11 | R73–R76 | Colon LED resistors | 4 | ~0.002 | 0.01 | |

## Power

| # | Ref | Part | Qty | Unit $ | Line $ | Notes |
|---|---|---|---|---|---|---|
| 12 | J1 | USB-C receptacle, 6-pin power-only (schematic uses the GCT USB4125 footprint; pick a clone with the same land pattern) | 1 | ~0.10–0.25 | 0.20 | Through-hole shell pins help with hand soldering and strength. |
| 13 | R77–R78 | 5.1 kΩ CC pull-downs | 2 | ~0.002 | 0.01 | Required for C-to-C chargers to supply 5 V. |
| 14 | F1 | Polyfuse ~500 mA, 1206 | 1 | ~0.03–0.05 | 0.05 | Optional. |
| 15 | U12 | 3.3 V LDO, e.g. AP2112K-3.3 or ME6211C33, SOT-23-5 | 1 | ~0.05–0.15 | 0.10 | Load ~40–60 mA. |
| 16 | C | 10 µF 0805/0603 (USB in, LDO in/out, 5 V rail near the '595s) | 4 | ~0.01 | 0.04 | |
| 17 | C | 100 nF 0603 (one per IC + GPS + oscillator + NRST) | 14 | ~0.002 | 0.03 | |

## Small stuff / optional

| # | Ref | Part | Qty | Unit $ | Line $ | Notes |
|---|---|---|---|---|---|---|
| 18 | J3 | SWD header (2.54 mm 1×5: 3V3, SWDIO, SWCLK, NRST, GND) or bare pads | 1 | ~0.03 | 0.03 | Program/debug with your ST-Link. |
| 19 | J4 | UART debug header 1×3 (TX, RX, GND) | 1 | ~0.02 | 0.02 | Optional. Handy for watching NMEA / debug prints. |
| 20 | Q/LDR | Phototransistor or LDR + resistor for auto-brightness | 1 | ~0.05–0.10 | 0.10 | Optional. Fixed brightness works without it. |
| 21 | SW1 | Tactile button (brightness) | 1 | ~0.03 | 0.03 | Optional. |
| 22 | — | GPS backup: small supercap or ML-series cell on the module's V_BCKP pin | 1 | ~0.30–1.00 | — | Optional, not in the total. Only if cold-start time after a power cut annoys you. |

## Totals per board (parts only)

| Variant | Approx. total |
|---|---|
| 0.56" digits, plain oscillator, including antenna | **≈ $10** |
| 0.56" digits, TCXO | ≈ $10.70 |
| 1" digits, plain oscillator | ≈ $14.50 |
| Without the antenna (if you already have one) | subtract ~$3 |

These exclude:

- **PCB:** 2-layer, 1.6 mm. Board size is set by the digits: 9× 0.56" digits
  plus colons is about 150 × 40 mm; 1" digits push it to ~250 × 60 mm. PCBWay
  pricing jumps above 100 × 100 mm. I don't have a current quote; expect roughly
  $10–30 for 5 boards plus shipping, but check.
- **Assembly**, if you use PCBWay assembly: setup/stencil/handling fees tend to
  dominate at 1–5 boards. Everything here is hand-solderable (smallest pitch is
  0.65 mm TSSOP; the GPS module has castellated edges), so ordering the bare PCB +
  stencil and assembling yourself is likely cheapest.
- **Enclosure / mounting:** front filter (e.g. red-tinted acrylic) and hanger.
- Shipping and tax.

## Parts removed compared with the Mk IV (for reference)

Second MCU (STM32L010) and the date board, 10 date digits and their drivers,
the hinge, 16 MB QSPI flash, the 32.768 kHz crystal and coin cell holder, the
light-sensor DAC drive circuit, USB data/ESD parts, the date-board buttons, and
the STM32L476 itself (replaced by a ~$0.62 part).

## Changes from the schematic (rev 0.1)

The schematic (`docs/schematic-notes.md`) adds a few small parts not listed
above, all a cent or two each: R3 (oscillator EN pull-up), R4 (22 Ω oscillator
series), R5 (/OE pull-up), R6/R7 (GPS ON/OFF and RESET pull-ups), R8 + L1
(antenna bias), R9 + D5 (status LED), R10 + C10 (light sensor), C4–C10 MCU/GPS
decoupling, and TP1/TP2 test pads. The colons need four colon resistors (R28,
R29, R48, R49), so the segment resistor count is 74, not 72 + 4. None of this
changes the ~$10 total by more than about $0.20.
