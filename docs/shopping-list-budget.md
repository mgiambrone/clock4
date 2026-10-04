# Shopping list: budget breadboard

A cheaper alternative to `shopping-list.md`, stage 1. It tests the same
things: GPS PPS/NMEA behaviour, the digit pinout, and PPS-to-latch timing on
three digits (`.mmm`). It assumes you already have an **ST-Link** and the Mk IV
as a visual reference. Prices are rough US figures from October 2026.

**Total: about $20–30, or ~$15 if you already have a breadboard and a scope or
logic analyser.**

## What's different from the full list

- **No Nucleo board.** Use the real STM32G030F6P6 on a TSSOP-20-to-DIP adapter,
  programmed with your ST-Link (saves ~$18, and tests the exact chip that goes
  on the PCB). You need to drag-solder a 0.65 mm pitch chip once, and supply
  3.3 V yourself (an LDO is on the list).
- **No USB-serial adapter.** The logic analyser decodes the GPS's UART output
  directly in PulseView, so you can read NMEA and see its timing against PPS
  on the same screen.
- **No separate antenna.** Use the one that comes with the GPS breakout, by a
  window.
- **Three digits, not nine.** Three '595s + three digits prove the whole
  timing chain; the rest are copies.

## The list

| Qty | Part | Where | ~$ | Notes |
|---|---|---|---|---|
| 2 | STM32G030F6P6 (TSSOP-20) | DigiKey / Mouser / LCSC | 1–1.5 each | One spare for soldering mishaps. |
| 1 pack | TSSOP-20 to DIP adapter boards (SSOP/TSSOP 0.65 mm) | Amazon / AliExpress | 2–5 | Packs of 5–10. |
| 4 | 74HCT595N, DIP-16 (**HCT**) | DigiKey / Mouser / LCSC | 0.6–1.0 each | Three + a spare. |
| 1 pack | 0.56" single-digit 7-segment, common cathode, red, "5161AS" | Amazon / AliExpress | 6 for 10 | Spares go to the PCB build if the pinout checks out. |
| 1 | ATGM336H GPS breakout **with a PPS pin**, antenna included | AliExpress (~$4) / Amazon (~$8) | 4–8 | Check the photos for a pin labelled PPS. |
| 1 | 3.3 V regulator, through-hole, e.g. LD1117V33 (TO-220) or MCP1700-3302E (TO-92) | DigiKey / Mouser | 0.5 | Powers MCU + GPS (~100 mA peak) from 5 V. Don't run the GPS off the ST-Link's 3.3 V pin. |
| ~30 | Resistors: 470 Ω ×24, 33 Ω ×2, 10 kΩ ×4 | same order, or an assortment you have | 1–3 | |
| ~10 | Capacitors: 100 nF ×6, 10 µF ×3 (for the LDO and bulk) | same order, or what you have | 1–2 | |
| 1 | 5 V source: a USB breakout board, or the ST-Link's 5 V pin | Amazon / AliExpress | 0–2 | The ST-Link 5 V pin is fine for 3 digits. |
| 1 | Full-size breadboard + jumpers | Amazon | 5–8 | Skip it if you have one. |
| 1 | Logic analyser, 8 ch 24 MHz (Saleae clone, PulseView) | Amazon / AliExpress | 10 | Skip it if you have a scope or analyser. This is the one tool worth buying. |

## Tips to keep the cost down

- **Shipping costs more than the parts here.** Put the chips (G030, '595s,
  LDO) and passives in one distributor order. DigiKey/Mouser charge roughly
  $5–8 shipping under their free threshold, and LCSC charges ~$10+ to the US
  (check tariffs/fees at checkout). Or add these chips to the eventual LCSC PCB
  parts order and breadboard later.
- **AliExpress** is cheapest for the GPS breakout, adapters, digits and logic
  analyser, but takes 2–3 weeks. Amazon is a few dollars more, and arrives in
  days.
- You don't need the colon LEDs, oscillator, button, light sensor or USB-C part
  to breadboard. The internal 16 MHz oscillator is fine for proving the timing
  while PPS is present.

## What you can test with this

1. GPS alone, read through the logic analyser: when PPS starts, which RMC
   second it belongs to, how long after PPS the RMC arrives, cold start time,
   and `ANTENNA OK`.
2. One digit + one '595: pinout and brightness at 470 Ω.
3. MCU + GPS + three digits: real firmware for PPS capture, ms tick and the
   hardware latch. Measure PPS → latch on the analyser, and film it next to
   the Mk IV.
