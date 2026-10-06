# Firmware features (plan)

The planned feature list for the schematic rev 0.2 hardware: STM32G030F6, ten
statically driven digits on five DC56-11 duals, two buttons (MODE on PC15,
BRIGHT on PA1). No code exists yet. This is what the code should do, so it can
be checked before writing it.

## 1. Timekeeping core

- **PPS capture:** TIM3_CH1 (PA6) timestamps each PPS edge. A PPS only counts
  after an RMC sentence has reported status `A` (the Mk IV does the same). Right
  after a cold start the receiver can pulse while still guessing the UTC
  offset.
- **Oscillator measurement:** each second, the number of timer counts between
  PPS edges gives the real oscillator frequency. The sub-second counter is
  scaled by it, so a cheap oscillator's static error cancels out.
- **Tick and latch:** a 10 kHz tick (0.1 ms) from the same timer, re-phased on
  every PPS. TIM3_CH3 (PB0) pulses RCLK in hardware, so all ten '595s change on
  the same edge. The next value is shifted in over SPI (80 bits, ~10 µs) right
  after each latch.
- **Second label:** at .900, compute the next second's digits from the last RMC
  time + 1 and stage them, so they go out on the latch that coincides with PPS.
- **Precision hiding** (from the Mk IV), measured from the last good PPS:

  | Time since last PPS | Shows |
  |---|---|
  | < T0.1ms (default ~30 s, tune after measuring drift) | `.mmmm` |
  | < T1ms (default ~60–300 s) | `.mmm-` |
  | < T10ms | `.mm--` |
  | < T100ms | `.m---` |
  | longer | `.----` (no decimal point) |

  Before the first valid fix after power-up, everything shows dashes
  (`--:--:--.----`).

## 2. Display modes

The MODE button steps through the enabled modes. The physical colons sit
after digits 2 and 4, and decimal points are available on every other digit.

| Mode | Example (10 digits) | Colons | Notes |
|---|---|---|---|
| Local time | `14:07:33.1234` | on | America/New_York. US rule since 2007: DST from the 2nd Sunday in March at 02:00 to the 1st Sunday in November at 02:00. Optional 12 h format with a blank leading zero. |
| UTC | `18:07:33.1234` | on | DP on the last digit lit as a "UTC" marker. |
| Unix time | `1791310053` | off | Exactly 10 digits until 2286. |
| ISO date | `2026-10-06` | off | Dashes drawn with segment G. |
| Day of year | `2026-279` | off | |
| ISO week | `2026-41-2` | off | 7-seg can't draw "W", so it's left out. |
| Modified Julian Date | `61319.75524` | off | The DP doesn't use a digit, so 5 + 5 digits. |
| **Seconds alive** | `1123456789` | off | See section 3. |
| Days alive | `13002.43217` | off | Days with a fraction. |
| Next milestone | `-12345678` | off | Seconds until the next whole 10⁸ / 10⁹ of seconds alive. |
| Countdown | `03:12:45.6789` | on | To a set moment. Below 100 h it shows HH:MM:SS; above that, days with a fraction. |
| Status | `SAt 9`, `PPS 0.21` | off | Satellites, measured oscillator error in ppm, time since the last PPS, time to first fix. |
| Display test | `8.8.8.8.…` | on | All segments at reduced brightness (≤ 50% /OE duty, current limit). |

Characters 7-segment can show: `0–9 A b C d E F G H I J L n o P r S t U y - _`
and blank. `K M V W X` can't be drawn. `Z` would look like `2`.

## 3. Seconds alive (custom epoch)

- Set at build time in `config.h`, with the UTC offset in force at the time and
  place of birth:
  `#define BIRTH "1990-05-17T14:32:00-04:00"`
  The firmware converts this to UTC once. 64-bit maths, so pre-1970 dates work.
- **Count type:** a choice in `config.h`:
  - `UNIX`: like `now − birth` on a computer. Leap seconds are ignored.
  - `SI` (default): adds every leap second inserted between birth and now, from
    a built-in table (27 entries, 1972–2016). None have been added since 2017,
    and they're due to be abolished by 2035. A surprise new one means a
    reflash.
- **Milestones:** at each whole 10⁸ seconds, and especially 10⁹, flash the
  display for a minute. 1,000,000,000 s is about 31 years 8 months.
- **Several epochs:** up to e.g. 4 named epochs (birthdays, anniversaries),
  each its own mode.
- Honest precision: you probably know the birth time to the minute, so the
  count is right to ±30 s even though it ticks exactly on PPS.

## 4. Buttons

| Action | MODE (SW2) | BRIGHT (SW1) |
|---|---|---|
| Short press | next mode | next brightness step (including "auto" if the light sensor is fitted) |
| Long press (1 s) | previous mode | toggle colons solid/blinking |
| Both held 3 s | settings: enable/disable modes, 12/24 h, local/UTC default | |

The current mode and brightness are saved in the last flash page (with simple
wear levelling) a few seconds after the last button press, so they survive
power cuts.

## 5. Build-time settings (`config.h`)

Time zone rule (offset + DST rule), `BIRTH` and other epochs, count type,
countdown target, enabled modes, precision thresholds, brightness levels and
PWM frequency, default mode.

## 6. Debug output (UART on J4, 115200)

Once a second: fix status, satellites, PPS-to-PPS counts, measured ppm, time
since the last PPS and the current precision level. Raw NMEA passthrough can be
turned on or off.

## 7. Size check

32 KB flash on the G030F6. Estimates: HAL/LL init ~6–8 KB, date maths and modes
~4–6 KB, NMEA parsing ~2 KB, display and fonts ~1 KB, settings ~1 KB. That's
comfortably under 32 KB without the Mk IV's time zone database or USB stack.
The pin-compatible 64 KB G030F8 is the fallback (check the part number and
price before switching).

## Not included (cut in the analysis)

Automatic time zone from position, config.txt over USB, USB firmware update
(flash over SWD), coin-cell RTC, and showing the date and time at once.
