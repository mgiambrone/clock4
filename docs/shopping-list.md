# Shopping list

Two stages: **breadboard first**, then the **PCB build** once the breadboard
has answered the open questions (digit pinout, GPS PPS/NMEA behaviour). Prices
are rough US figures from October 2026 and will move. Where I checked a
listing, it's linked.

## Stage 1: breadboard (about $45–75 total, less if you have the tools)

### Order A: DigiKey or Mouser (genuine chips, ships in 1–3 days)

| Qty | Part | Example part number | ~$ each | Why |
|---|---|---|---|---|
| 1 | **NUCLEO-G031K8** dev board | [DigiKey 497-19569-ND](https://www.digikey.com/en/products/detail/stmicroelectronics/NUCLEO-G031K8/10321671) | ~20 | Same family as the G030, ST-Link built in, breadboard-friendly. Easiest start. |
| *or* 3 | STM32G030F6P6 + a TSSOP-20-to-DIP adapter each | STM32G030F6P6 | ~1 + ~1 | Cheaper, and tests the exact chip on the PCB. Needs your ST-Link and fine soldering. |
| 10 | 74HCT595 in DIP-16 (must be **HCT**) | TI SN74HCT595N | ~0.6–1.0 | One spare. |
| 1 | 470 Ω resistor pack/strip, ¼ W through-hole | any | ~5/100 | Segments. |
| 10 | 33 Ω and 10 kΩ through-hole resistors | any | cheap | Series resistors and pull-ups. |
| 10 | 100 nF ceramic capacitors, through-hole | any | cheap | One per '595. |
| 2 | 10 µF capacitors | any | cheap | Bulk. |
| 6 | 3 mm red LEDs | any | cheap | Colons. |

Ask for the cut-tape/loose parts, not reels. DigiKey and Mouser both ship free
over about $50 in the US. Mouser stocks most of the same parts.

### Order B: Amazon or AliExpress (modules and tools)

| Qty | Part | ~$ | Notes |
|---|---|---|---|
| 1–2 | **ATGM336H GPS breakout with a PPS pin**, antenna included | 5–12 | Check the listing photos for a pin labelled PPS. Many have only VCC/GND/TX/RX. Amazon examples: [DORHEA ATGM336H](https://www.amazon.com/Dual-Mode-Satellite-Positioning-Navigator-Replacement/dp/B0GSZY9ZYB) (mentions PPS pins). |
| 1 | Active GPS antenna, SMA, 3–5 m cable, plus a u.FL→SMA pigtail if the breakout uses u.FL | 6–10 | For indoor testing near a window. Skip it if the breakout's antenna locks where you test. |
| 1 pack | **0.56" single-digit 7-segment, common cathode, red ("5161AS")** | 6–8 for 10 | Generic. Checking its pinout is one of the main breadboard jobs. A name-brand alternative is Kingbright SC56-11SRWA (DigiKey, ~$2 each, [listed as obsolete](https://www.digikey.com/en/products/detail/kingbright/SC56-11SRWA/2163730), so treat it as a reference part). |
| 2–3 | Full-size breadboards + jumper wire kit | 10–15 | Nine digits need roughly three boards. |
| 1 | USB-serial adapter, 3.3 V (CP2102 or CH340) | 5 | To watch NMEA from the GPS on its own. (The Nucleo's ST-Link serial can do it too.) |
| 1 | **Logic analyser**, 8 channel 24 MHz "Saleae clone" | 10–15 | Works with free PulseView/sigrok. This is how you measure PPS → RMC timing and PPS → latch delay. |

You already have an ST-Link and the Mk IV. Use the Mk IV as a visual reference
(film both clocks in slow motion).

## Stage 2: PCB build (per board ≈ $10 of parts, see `bom-draft.md`)

| What | Where | Notes |
|---|---|---|
| Bare PCB (+ stencil if you'll reflow) | **PCBWay** (your choice) | 2-layer, 1.6 mm, ~150 × 40 mm. Get a quote with and without assembly; at 1–5 boards, assembly fees usually exceed the parts. |
| ATGM336H-5N31 module, STM32G030F6P6, 74HCT595 (SOIC), passives, USB-C, AP2112K | **LCSC** | Cheapest and stocks everything in the BOM (C90770, C724040…). Shipping to the US costs ~$10–25, and I can't predict current tariffs or brokerage fees, so check at checkout. |
| Same parts, faster/simpler | DigiKey / Mouser | Costs more for the Chinese parts (ATGM336H may not be stocked; LCSC is the reliable source). |
| 0.56" digits, antenna, 3 mm LEDs | Amazon/AliExpress, or reuse spares from stage 1 | Buy digits from the same seller as the breadboard batch once you've confirmed their pinout. |
| Polyfuse 750 mA, inductor 47 nH (RF-rated), oscillator | LCSC or DigiKey | Pick these when finalising the BOM. |

If you use PCBWay assembly, they source parts themselves (or accept parts you
consign). Check on their quote whether they'll get the ATGM336H, or plan to
send it.

## Order of operations

1. Place orders A and B together; they arrive in roughly a week (AliExpress
   2–3 weeks).
2. Breadboard: GPS alone → one digit + '595 → MCU + 3 digits (see the
   breadboard plan).
3. Update the schematic with whatever the breadboard teaches (digit pinout,
   anything odd about the GPS).
4. Then order PCBs from PCBWay and parts from LCSC.
