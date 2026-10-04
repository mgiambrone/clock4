# Cheap GPS millisecond wall clock: analysis of the Mk IV and a plan

Reference: mitxela Precision Clock Mk IV, `clock4` repo, snapshot at commit
`e9d03b2` ("tzrules and tzmap to 2026d").

Everything here comes from reading the firmware. The Mk IV schematic is **not** in
the repo, so anything I say about the analog side (LED drivers, DAC dimming
circuit) is inferred from what the firmware does. I've marked those parts.

---

## Step 1: The reference repo

### Getting it

`git clone https://git.mitxela.com/clock4.git` was **blocked** by this cloud
environment's network policy (`git.mitxela.com` is not on the allowed list; so was
`mitxela.com`). However, this repo (`mgiambrone/clock4`) is already a mirror of
upstream: all 52 commits are authored by mitxela, and the tree matches the
upstream layout. So I made `./reference/clock4` as a local clone of this mirror.
`reference/` is git-ignored so we don't commit a second copy of the whole tree.

If you want to be sure you have the latest upstream, run the clone on your own
machine, or add `git.mitxela.com` to the environment's allowed domains (see
https://code.claude.com/docs/en/cloud-environments#network-access).

### License: what you're allowed to reuse

**There is no LICENSE file for mitxela's own work.** No license file at the root,
none in `mk4-time/`, `mk4-date/`, `mk4-bootloader/`, `qspi/` or `cad/`, and GitHub
shows no license for `mitxela/clock4`. The readme says nothing about licensing
either.

What's in the tree, by origin:

| Part | Origin | License |
|---|---|---|
| `mk4-time/Core/Src/main.c`, `stm32l4xx_it.c`, `mk4-date/Core/Src/main.c`, `chainloader.c`, `qspi_drv.c`, the qspi scripts | mitxela's code. Some of it sits inside STM32CubeMX-generated files that carry ST's BSD-3 header. | **None stated** for mitxela's parts. The ST header covers ST's generated skeleton, not code mitxela wrote in the `USER CODE` sections. |
| `Drivers/STM32*_HAL_Driver` | ST | BSD-3-Clause |
| `Drivers/CMSIS` | ARM/ST | Apache-2.0 |
| `Middlewares/ST/STM32_USB_Device_Library` | ST | ST "Ultimate Liberty" SLA0044 (only allowed on ST MCUs) |
| `Middlewares/Third_Party/FatFs` | ChaN | FatFs license (BSD-style, very permissive) |
| `zonedetect.c/.h` | Bertold Van den Bergh | BSD-3-Clause |
| `qspi/output/tzmap.bin` | data from timezone-boundary-builder | ODbL (attribution and share-alike on the data) |
| `cad/` (STL, STEP, FreeCAD, SCAD, SVG) | mitxela | **None stated** |

In practice:

- **No license means all rights reserved.** You can read, study and learn from
  mitxela's code. You don't have permission to copy it into your own project and
  redistribute it. For one private clock on your own wall the practical risk is
  basically zero, but if you ever publish your firmware or sell boards, write your
  own code (or ask mitxela; he has released older clocks under CC BY-SA, so he may
  well be happy to state a license).
- **Ideas and techniques aren't covered by copyright.** "PPS re-phases the
  millisecond timer", "precompute the next second at .900 and latch it on the edge",
  "hide digits as the error bound grows": you're free to reimplement all of these
  in your own code. That's the plan here anyway, since the target MCU is different.
- The ST HAL, CMSIS, FatFs and ZoneDetect parts are permissively licensed and
  reusable, but we won't need any of them except ST's HAL/LL (which you'd get from
  ST directly).
- Not legal advice, just how these defaults normally work.

### Are the schematics / PCB files in the repo?

**No.** The repo has:

- firmware for three targets (time MCU, date MCU, bootloader)
- QSPI flash image tools (tz rules generator, firmware CRC, disk image script)
- `cad/`: 3D-print and laser-cut parts only (colon diffusers, light-sensor and
  switch covers, wall hangers, shelf stand, acrylic case, antenna case, hinge)
- `brightness-curve.htm`, a small tool for editing the light-sensor-to-brightness
  curve

No KiCad, Eagle, Gerber, schematic PDF or BOM files. A web search found
statements that "the PCB files will also be published", but they aren't in this
snapshot. That doesn't matter much: we'll design our own board.

---

## Step 2: How the Mk IV works

### Hardware overview (as far as the firmware shows)

- **Time side:** STM32L476RG at 80 MHz. The clock comes from a **10 MHz external
  source on HSE** (the `.ioc` says `HSE_VALUE=10000000`; this is the TCXO) through
  the PLL. There's also a 32.768 kHz LSE crystal for the RTC.
- **GPS:** UART1 at 9600 baud, NMEA only. The firmware never sends configuration
  commands, so it relies on the module's default output. PPS goes to pin PC7
  (EXTI, rising edge). Web sources say it's a u-blox 8-series module; the firmware
  doesn't name it, and you'll know from your kit.
- **Date side:** STM32L010 at 32 MHz, linked over UART2 (115200, 8E1).
- **Storage:** 16 MB QSPI flash holding config.txt, tz rules, the 12.6 MB tz map,
  and firmware images. It's exposed over USB as a mass-storage device.
- **Coin cell:** keeps the RTC and its backup registers alive.
- **Light sensor:** phototransistor on ADC (PA5). A DAC (PA4) sets the LED drive
  level (probably analog current control; schematic not available).

### The display: "4 matrices × 5 digits"

There are 20 digit positions in four multiplexed matrices, each with 5 columns:

| Matrix | Driven by | GPIO | Digits |
|---|---|---|---|
| B | time MCU | GPIOB: segments PB2–PB8, column selects PB9, PB12–PB15 | H H M M S (tens) |
| C | time MCU | GPIOC: segments PC0–PC6, DP on PC12, columns PC8–PC11 | S (units) . d c m. The 5th slot is a blank "all columns off" entry, so C has the same 5-step timing as B. |
| A, B (date) | date MCU | GPIOA / GPIOB | YYYY-MM-DD, 10 characters |

**How the time side refreshes:** each matrix has a small RAM array
(`buffer_b[]`, `buffer_c[]`) where each 16-bit entry is the *entire GPIO port
value* for one column: which column is on, plus which segments are lit. A timer
(TIM1 for B, TIM7 for C) fires a **DMA** request on every update, and the DMA
copies the next entry straight into `GPIOx->ODR` in a circular loop. The CPU does
no refresh work at all.

- `MATRIX_FREQUENCY` in config.txt is the full-frame rate. The default is
  20 kHz, and the allowed range is 1 kHz to 100 kHz. The timer runs at 5× that, so
  at the default each column is lit for 10 µs and every digit is redrawn every
  50 µs.
- `setDisplayPWM(n)` changes the DMA length. Entries 5 and up are zero, so a
  length above 5 adds dark slots, which works as PWM dimming. In practice the
  firmware keeps it at 5 (full duty) and dims with the DAC instead (see below).
- To change a digit, the CPU just writes one array entry. The next DMA pass
  (≤50 µs later at 20 kHz) shows it.

That fast refresh is the point. A millisecond digit only means something if the
whole display redraws much faster than 1 kHz. Otherwise a photo at 1/1000 s
catches a digit that's dark, or still showing the old value.

**Date side:** the L010 has no DMA-to-GPIO path in this design. A TIM2 interrupt
writes `GPIOA->ODR` and `GPIOB->ODR` for one column per interrupt, with the frame
rate set by the time MCU over the UART (`CMD_SET_FREQUENCY`).

### From PPS to a millisecond-accurate display

The core is small. The pieces:

1. **SysTick at 1 kHz** from the 80 MHz TCXO-derived clock. The SysTick handler
   runs a software counter `millisec`/`centisec`/`decisec` and writes those
   three digits straight into `buffer_c[1..3]`, so the DMA shows them within
   one refresh.
2. **PPS rising edge → EXTI interrupt at top priority.** The handler (`PPS()`):
   - writes `SysTick->VAL`, which resets SysTick so the next 1 ms tick is exactly
     1 ms after the PPS edge. This re-phases the millisecond counter to GPS every
     second.
   - sets the sub-second digits to `.000`
   - calls `loadNextTimestamp()`, which copies the **pre-computed** next
     HH:MM:S digits from `next7seg` into the live DMA buffers, and sends the
     latch byte `0xFE` to the date MCU
   - zeroes the counters
3. **Pre-computation at .900:** when SysTick reaches 900 ms, it does
   `currentTime++` and calls `setNextTimestamp()`. That applies the timezone
   offset, converts to BCD and 7-segment patterns, and stores them in `next7seg`
   (the second buffer). It also sends the next date text to the date MCU, ending
   in `'\n'` (meaning "load but don't show yet"). This takes about 32 µs, so the
   slow work happens 100 ms before it's needed.
4. **The latch:** at the PPS edge, step 2 copies the buffer into place and sends
   `0xFE` over the UART. The date MCU spins on its RX pin as a plain GPIO and
   switches its display on the **falling edge of the start bit**. Both MCUs
   change digits within microseconds of the PPS edge.
5. **Which second is it?** NMEA `$GxRMC` sentences arrive some hundreds of ms
   *after* the PPS they describe. UART1 uses character-match on `'\n'` plus DMA,
   so each full sentence triggers `decodeRMC()`. That sets `currentTime` from the
   sentence. If parsing happens at or after .900 (a late sentence), it
   recomputes the pending timestamp itself. RMC status `A` sets `data_valid`.
   Until then, PPS edges are ignored for "had_pps" purposes, because right after
   a cold start the GPS can output PPS while its UTC leap-second offset is still
   a guess (the firmware comment says time can be 2–3 s off).
6. **If PPS is missing**, SysTick reaching 1000 ms calls `loadNextTimestamp()`
   itself, so the clock free-runs on the TCXO. If the TCXO is slightly fast or
   slow, whichever of SysTick or PPS comes first does the latch, and the other
   is harmless. The mismatch is microseconds.

The interrupt vectors live in RAM, so the firmware swaps the SysTick and PPS
handlers by writing function pointers (`SetSysTick()`, `SetPPS()`). That's how it
switches between count-up, count-down, and "show 3/2/1/0 sub-second digits"
without branching in the hot path.

**Error budget with PPS present:** GPS PPS is about 30 ns RMS. Interrupt latency
is under 1 µs. The display shows a change within one refresh (≤50 µs at 20 kHz).
TCXO error accumulated over one second at 1 ppm is 1 µs. **The total is well
under 0.1 ms.** The 1 ms digit is honest with lots of margin.

### What the TCXO is for, vs. what PPS alone gives

With PPS present, the oscillator barely matters. It's re-phased every second, so
the worst-case error at .999 is (frequency error × 1 s). Even a cheap ±50 ppm
crystal gives 50 µs, which is invisible at 1 ms resolution.

Note that the Mk IV does **not** measure or correct the TCXO frequency against
GPS. It only re-phases SysTick. So the TCXO matters in two situations:

1. **Holdover (lost fix):** the clock free-runs, so drift = absolute frequency
   error × time. The config comment spells it out: at 1 ppm it takes 1000 s to
   drift 1 ms. That's where the default `Tolerance_time_1ms = 1000` comes from. A
   TCXO stays near 1 ppm over temperature, while a plain crystal may be 10–50 ppm
   off.
2. **The coin-cell RTC** isn't TCXO-based: it runs from the 32.768 kHz LSE. Each
   PPS, `calibrateRTC()` counts LSE cycles on LPTIM1 over 63 s and writes a
   smooth-calibration value to `RTC->CALR`. After a power cut, the clock comes back
   up within a fraction of a second of correct, even before GPS lock.

### Precision tolerance (hiding digits when the fix is lost)

Once per second, PendSV runs `setPrecision()`, which compares elapsed time to
three config values (seconds):

| Condition | Shows | SysTick handler |
|---|---|---|
| `now − last_pps < Tolerance_time_1ms` (default 1000) | `.mmm` | `SysTick_CountUp_P3` |
| `now − last_pps < Tolerance_time_10ms` (default 10000) | `.mm-` | `_P2` |
| `now − rtc_last_calibration < Tolerance_time_100ms` (default 100000) | `.m--` | `_P1` |
| otherwise | `--` with no decimal point | `_P0` |

Hidden digits show a single middle segment (`0b01000000`). Each handler only
updates the digits it's allowed to show. `last_pps_time` is updated only when a
PPS arrives *and* the last RMC was valid. On power-up with a weak coin cell
(< 2.70 V) the RTC calibration time is deliberately invalidated, so the clock
won't claim accuracy it doesn't have.

It's a simple rule: "assume X ppm, hide a digit once accumulated error could
exceed it." It's entirely software, so it costs nothing to keep.

---

## Step 3: Keep, cut or simplify

Price deltas are rough single-quantity figures (LCSC-style) and assume 2-layer
PCB area scales with what's removed. "Complexity" is mostly firmware and board
routing.

| Feature | Verdict | What it saves / notes |
|---|---|---|
| **Date side** (STM32L010, 10 digits, hinge, inter-MCU UART, buttons on date board) | **Cut.** Agreed. | Saves the second MCU (~$0.6), 10 digits and their drivers (~$2–5), a second PCB/hinge, and the entire latch protocol. This is the biggest simplification. |
| **ZoneDetect + 12.6 MB tz map + tzrules + 16 MB QSPI flash** | **Cut.** Agreed. | Saves the QSPI chip (~$0.5–1), FatFs, ZoneDetect, and the rules parser. Replace with a compile-time rule: UTC−5, DST from the 2nd Sunday of March at 02:00 local to the 1st Sunday of November at 02:00 local. That's about 30 lines of C. If the US ever changes DST law, you reflash. |
| **USB mass storage, custom bootloader, config.txt** | **Cut.** Agreed. | USB becomes power-only. You lose field updates and config-by-file; settings become `#define`s, flashed over SWD. Saves a lot of firmware. Hardware saving is small (the USB data lines and ESD part). |
| **USB CDC NMEA passthrough** | **Cut.** | Comes with the USB cut. Add a 3-pin UART debug header (TX/RX/GND) instead, which costs nothing. |
| **Light sensor + DAC analog dimming** | **Simplify.** | Analog current dimming exists so the display looks flicker-free on high-speed cameras. You don't need that. Use one PWM signal on the driver's output-enable pin. Optionally add an LDR/phototransistor on an ADC pin (~$0.05–0.10) for auto-brightness. Saves the DAC drive circuit and some firmware. |
| **Coin cell + LSE RTC + LPTIM calibration + backup registers** | **Cut.** | Saves the coin holder (~$0.2–0.5), LSE crystal, and a chunk of firmware. Cost: after a power cut the clock shows dashes until GPS re-locks. Without battery backup on the GPS either, every power-up is a cold start: roughly 30–60 s with a decent antenna view, longer indoors. Fine for a wall clock that's rarely unplugged. |
| **Extra display modes** (Unix, Julian, ISO week, countdown, sat view, text, TZ name, offset, debug modes) | **Cut.** | Almost all of them only make sense on the date display. Firmware-only saving. Keep one optional debug/self-test (all segments on). |
| **Colon animations** (TIM2 PWM + TIM5 DMA, slow fade, heartbeat…) | **Simplify.** | Solid colons, or toggled on each PPS as a "fix OK" heartbeat (free status indicator). |
| **Buttons** | **Cut or 1 button.** | The Mk IV's buttons are on the date board. One optional button for brightness is plenty. |
| **Precision tolerance (hide digits)** | **Keep, simplified.** | Pure software. Without an RTC, the "100 ms" tier becomes "show `--:--:--.---` until the first valid fix after power-up". Then `.mmm` → `.mm-` → `.m--` → `.---` as time since the last PPS grows. Tune the thresholds to whichever oscillator you fit (below). |
| **Pre-compute at .900 + latch on PPS** | **Keep.** | This is the core idea, and it's cheap. |
| **Fast refresh** | **Keep, or remove the need for it** | Either multiplex fast (≥5–10 kHz frame) like the Mk IV, or drive the digits **statically** so there's nothing to refresh. The plan below does the latter. |
| **TCXO** | **Optional.** See below. | ~$0.5–1.5 vs ~$0.15 for a plain oscillator. |

### Is the TCXO needed for 1 ms?

**Not while the GPS has a fix.** As shown above, a ±50 ppm part is re-phased
every second and contributes at most 50 µs.

**It only buys holdover time**, i.e. how long the `.mmm` digit stays honest after
losing PPS. Estimates (please treat these as estimates):

| Oscillator | Freq. error during holdover | Time until 1 ms of drift |
|---|---|---|
| Plain crystal/XO, uncorrected | 10–50 ppm | 20–100 s |
| Plain XO, **frequency measured against PPS** while locked (see below), room temperature | maybe 1–5 ppm (temperature and aging drift since the last measurement) | ~200–1000 s |
| TCXO (±2.5 ppm part listed on LCSC), uncorrected | ≤2.5 ppm | ≥400 s |
| TCXO, measured against PPS | < 0.5 ppm, probably | ≥2000 s |

There's an easy improvement over the Mk IV here. **Measure the oscillator
against PPS every second** (input capture of the PPS edge on a free-running
timer gives "this oscillator ran N counts in the last GPS second"), then scale
the millisecond tick by that measurement. That cancels the crystal's static
error, which is most of it, so a cheap XO in a room that doesn't swing much in
temperature probably holds 1 ms for several minutes. I'm not sure of the real
figure, and it depends on your room. It's easy to measure on the prototype by
logging the captured counts.

**Recommendation:** use a plain 3.3 V CMOS oscillator with a footprint that a
CMOS-output TCXO can also fit (both are 4-pad 3225 parts). Set the 1 ms tolerance
to ~60 s at first and lengthen it once you've measured drift on your own board.
If you're happy with `.mm-` during short outages, the TCXO isn't needed.

---

## Step 4: Proposed cheap design

### Block diagram

```
USB-C (5V, power only) ──┬── LDO 3.3V ──┬── MCU (STM32G030F6)
                         │              ├── GPS module (ATGM336H) ── active antenna (u.FL/SMA)
                         │              └── 16 MHz CMOS oscillator (or TCXO) → MCU OSC_IN
                         │
                         └── 5V ── 9× 74HCT595 (daisy chain, static drive) ── 9× 7-seg digits + 4 colon LEDs

MCU pins: SPI SCK/MOSI → shift chain;  RCLK (latch) ← timer output;  /OE ← PWM (brightness)
          USART RX ← GPS TX;  PPS → timer input capture;  SWD header;  optional LDR → ADC;  optional button
```

### Display: 9 digits, statically driven by shift registers

Show **HH:MM:SS.mmm**: 9 digits, two colons, and the decimal point from the
seconds digit's DP.

**Recommended driver: one 74HCT595 per digit, daisy-chained, static drive (no
multiplexing).**

Why this fits the 1 ms goal well:

- **Every digit is lit 100% of the time**, so refresh rate doesn't matter. A photo
  at any shutter speed shows complete digits.
- **The '595's storage register is the double buffer.** Shift the *next* value
  into all nine chips over SPI (72 bits at 8 MHz ≈ 9 µs), then pulse RCLK
  and all nine digits change on the same edge. Drive RCLK from a **timer output**
  and that edge is hardware-timed, with no interrupt jitter. This replaces the
  Mk IV's `next7seg` → `loadNextTimestamp()` mechanism and the date-side latch
  trick.
- Every millisecond: latch, then shift in the value for the next millisecond.
  About 9 µs of SPI per ms (1% bus utilisation; DMA optional).
- **Brightness:** one PWM signal on the shared `/OE` pin dims every digit
  at once. Use ≥20 kHz to avoid audible/visible artifacts.
- **Few MCU pins** (SCK, MOSI, RCLK, /OE), so a 20-pin MCU is enough.
- **HCT, not HC:** the '595s run at 5 V for LED headroom, and HCT inputs accept
  3.3 V logic (VIH = 2.0 V). Plain 74HC595 at 5 V needs 3.5 V, so it's marginal
  from a 3.3 V MCU.
- **Current:** at ~5 mA per segment static (as bright as ~45 mA peak on a 1/9
  multiplex), a digit is ≤40 mA, within the '595's 70 mA package limit. Worst case
  is all digits showing "8." = ~360 mA from 5 V. Fine for USB.
- **Colons:** the DP outputs of digits 2 (H units) and 4 (M units) aren't needed
  as decimal points, so wire those to the colon LEDs. No extra chip needed.

Cost: 9× '595 at ~$0.10–0.20, plus 72 segment resistors (cheap 0603s, or
18× 4-resistor arrays to cut placement count).

**Alternatives considered:**

- **Direct GPIO multiplex, Mk IV-style:** ~18 GPIOs (8 segments + 10 columns),
  plus ~18 transistors. Similar parts cost, but it needs a bigger MCU package and
  a fast refresh loop. Also, the STM32G0's GPIO is on the Cortex-M0+ IOPORT bus,
  and **I'm not sure the G0 DMA can write to GPIO ODR** the way the L4 does, so
  you might need an ISR-driven refresh (like the Mk IV date side). That works,
  but it's more firmware with tighter timing. A valid plan B.
- **TM1640 (~$0.10) / MAX7219 (~$1.50+):** cheap and easy, but they multiplex
  internally on their own clock. The MAX7219 scans at about 800 Hz (1.25 ms per
  frame), which is too slow for an honest ms digit. I couldn't find a reliable
  scan-rate figure for the TM1640. Either way you can't latch these exactly on
  PPS. **Rejected for the sub-second digits.**

**Digit size:** a 0.56" digit (~14 mm tall) is readable at about 3 m. For across
a room, 0.8"–1.0" single digits are much better. Pick a **single-digit,
common-cathode** part (so a '595 sources each segment) and use the same part 9
times for a uniform look. The exact part depends on your size choice. Single
0.56" CC digits are cheap (~$0.15–0.30, unverified); 1" ones are more like
$0.5–1 each (unverified). Check the common-cathode pinout in the datasheet: some
listings get the CA/CC suffixes wrong. **Colour:** red has the lowest Vf (~2 V),
which leaves the most headroom from 5 V. Other colours work but need recalculated
resistors.

### MCU

**Recommended: STM32G030F6P6** (TSSOP-20, Cortex-M0+ 64 MHz, 32 KB flash, 8 KB RAM).
About $0.62 at 10 pcs on LCSC. Programs over SWD with the ST-Link you already have
(or any CMSIS-DAP probe), and uses the same STM32Cube HAL/LL ecosystem as the
Mk IV.

What it needs to do, and why it's comfortable:

- PPS → **timer input capture**, hardware-timestamped to one timer tick. A
  timer's slave "reset" mode can even re-phase the ms timer on the PPS edge in
  hardware, which is the hardware version of the Mk IV's `SysTick->VAL` trick.
  (The G030 has no 32-bit timer, only 16-bit TIM1/3/14/16/17. That's fine:
  count prescaled ticks and handle overflow.)
- 1 kHz tick + timer-driven RCLK + PWM /OE: two or three timer channels.
- SPI (+ optional DMA) for the '595 chain.
- USART RX at 9600 for NMEA. Parse RMC only.
- DST rule + `gmtime`-style date math: a few KB.

**Clock-source caveat (verified on ST's forum):** in the **TSSOP-20 package the
G030 has no HSE OSC_OUT pin, so it can't drive a crystal directly.** It only
supports an external clock in *bypass* mode on PC14 (OSC_IN). That's why the
design uses a **3.3 V CMOS oscillator** (~$0.15–0.30) instead of a bare crystal.
It also makes the TCXO upgrade a simple part swap, as long as you pick a
**CMOS/square-wave-output** TCXO, not clipped-sine (I'm not sure G0 bypass mode
accepts clipped sine reliably). Alternatively, run from the internal 16 MHz HSI
and measure it against PPS every second. Within a second that's probably fine,
but holdover would be poor (seconds, not minutes) because RC oscillators drift
with temperature. I'd spend the ~$0.20 on the oscillator.

Other MCUs considered:

| MCU | Price (approx.) | Verdict |
|---|---|---|
| STM32C011F4/F6 (TSSOP-20) | ~$1.07 @10 for F4 | Works, and C0 parts can use an HSE crystal on small packages. But it costs more than G030 at LCSC right now, the F4 has only 16 KB flash, and it runs at 48 MHz. Fine fallback. |
| CH32V003 (RISC-V, TSSOP-20) | ~$0.10–0.20 | Cheapest, and supports a crystal. But it uses WCH's own 1-wire debug (needs a WCH-LinkE, ~$5), not SWD, and the toolchain is less polished. Only 2 KB RAM. Workable if you want to save ~$0.50. |
| RP2040 | ~$0.70 + ~$0.20 QSPI flash + 12 MHz crystal + more passives | PIO is lovely for display timing, but it needs external flash and more support parts. Overkill here. |
| STM32G030K6/K8 (LQFP-32) | ~$0.70–0.90 | Pick this if you go with direct GPIO multiplexing (more pins). I couldn't confirm whether the LQFP-32 package has HSE OSC_OUT for a crystal. The ST forum answer only mentions LQFP-48, so assume a CMOS oscillator here too. |

### GPS module

**Recommended: ATGM336H-5N31** (Zhongke Weixing; GPS + BeiDou), about $1.8 on
LCSC (C90770). It's a 9.7×10.1 mm module with castellated pads, so you can
hand-solder it with an iron. I haven't confirmed that PCBWay's assembly service
stocks it; ask when quoting, or consign the part.

- Datasheet: 1PPS rising edge aligned to UTC, timing precision **< 30 ns (1σ)**.
  That's more than 30,000× better than you need.
- Defaults: 9600 baud NMEA, same as how the Mk IV uses its module.
- **Things I'm unsure about that need testing on a dev board before the PCB
  order:**
  1. Whether PPS is output before a fix, and whether `RMC` status goes `A` before
     the leap-second (GPS–UTC) offset is known. The Mk IV works around the u-blox
     version of this problem, and the ATGM336H may behave differently.
  2. Whether the RMC timestamp refers to the PPS *before* it (as on u-blox). The
     whole "which second is it" logic depends on this.
  3. Variants: LCSC lists 5N11, 5N31 and 5N71. One listing implies PPS is a
     5N11 feature, but the 5N-series datasheet shows a 1PPS pin for the series.
     **Confirm the PPS pin on the exact variant's datasheet before ordering.**
  4. Active-antenna bias: check the datasheet's reference circuit (antenna supply
     pin, series resistor/inductor).
- A ~$3–5 ATGM336H breakout with a PPS pin (sold on AliExpress etc.) is a cheap
  way to answer all four questions with a dev board before committing to a PCB.

**Upgrade option: u-blox MAX-M10S** (~$9.5–10.6 on LCSC). Better documented,
timepulse 30 ns RMS, and well-known behaviour. It can also output a **1 kHz
timepulse**, which could drive the ms digit directly from GPS while locked. I
wouldn't pay +$8 for it unless the ATGM336H misbehaves in testing.

Avoid cheap "NEO-6M" modules: many are counterfeit or relabelled, with unreliable
behaviour.

**Antenna:** a wall clock is indoors, and a ceramic patch on the board will
struggle away from a window. Plan for an **active patch antenna on a 3 m cable**
(~$2–4) placed at a window, plugged into a **u.FL** (~$0.10) or **edge SMA**
(~$0.30–0.50) connector. The Mk IV takes the same approach (`cad/antenna-case`).
Put a ground pour under the RF trace, keep it short, and route it as 50 Ω
coplanar waveguide. PCBWay can do controlled impedance, but a short trace on
1.6 mm 2-layer FR4 is forgiving.

### Power

- USB-C receptacle, **power-only 6-pin** type (~$0.10–0.25), with 2× 5.1 kΩ
  pull-downs on CC1/CC2 so C-to-C chargers supply 5 V.
- Optional 500 mA polyfuse.
- 3.3 V LDO for MCU, GPS and oscillator (~40–60 mA total). AP2112K-3.3 or
  ME6211C33 (~$0.05–0.15). An AMS1117 also works but is bigger and wastes more
  quiescent current.
- '595s and LEDs run directly from 5 V. Total worst case is ≲ 450 mA, so any USB
  port or phone charger is fine.
- Usual decoupling: 100 nF per IC and 10 µF bulk at the connector and LDO.

### Firmware outline (for later, not written yet)

1. PPS input capture → record the timer count. Compute "oscillator counts per
   GPS second", optionally filtered.
2. Millisecond tick from a timer, re-phased on PPS and optionally scaled by the
   measured frequency.
3. At each ms tick, a hardware RCLK pulse latches the pre-shifted value. Then
   compute and shift in the next ms value.
4. At .900, compute the next HH:MM:SS (UTC from RMC + 1, New York DST rule) and
   stage it so it goes out with the ms shift that lands exactly on the PPS edge.
5. `setPrecision`-style tolerance logic, with thresholds as `#define`s.
6. Brightness: PWM duty on /OE, fixed or from the LDR.

### Things still open

- Digit size (0.56" vs 0.8"/1"). This sets the board size, and board size drives
  PCB cost more than anything else here.
- Whether to add a small battery or supercap on the GPS backup pin for faster
  re-lock after power cuts. Cheap, but adds a part. Decide after seeing how
  slow cold starts are where you hang it.
- PCBWay assembly for 1–5 boards: setup, stencil and per-part fees can cost more
  than the parts themselves. I don't have current figures; get a quote with the
  BOM. With this part count (mostly SOIC/TSSOP + 0603), hand assembly is quite
  doable.

Sources for prices and specs: LCSC product pages for
[ATGM336H-5N31](https://www.lcsc.com/product-detail/C90770.html),
[MAX-M10S-00B](https://www.lcsc.com/product-detail/C4153167.html),
[STM32G030F6P6](https://www.lcsc.com/product-detail/Microcontrollers-MCU-MPU-SOC_STMicroelectronics-STM32G030F6P6_C724040.html),
[STM32C011F4P6](https://www.lcsc.com/product-detail/C5452432.html),
[TM1640](https://lcsc.com/product-detail/LED-Drivers_TM-Shenzhen-Titan-Micro-Elec-TM1640_C41327.html),
[YXC 16 MHz TCXO](https://www.lcsc.com/product-detail/Temperature-Compensated-Crystal-Oscillators-TCXO_YXC-Crystal-Oscillators-OW2EL89CENUXFMYLC-16M_C22434891.html);
[ATGM336H-5N datasheet](https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/1810261521_ZHONGKEWEI-ATGM336H-5N31_C90770.pdf);
[ST forum: G030F6 TSSOP-20 has no HSE crystal support](https://community.st.com/t5/stm32-mcus-products/stm32g030f6p6-tssop20-crystal-oscillator/td-p/702629);
[MAX-M10S datasheet](https://content.u-blox.com/sites/default/files/MAX-M10S_DataSheet_UBX-20035208.pdf).
Prices were checked in October 2026 and move around.
