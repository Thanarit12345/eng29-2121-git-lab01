# Browser Acceptance Validation — BJT CE Simulator v1

**Date:** 2026-11-24  
**App URL:** `http://127.0.0.1:5000/`  
**Method:** OpenCode in-app **Browser Tool** (real Chromium navigation, snapshot, fill, click, snapshot, evaluate, screenshot). Playwright MCP was not available in this session; the handout permits Browser Tool as interim verification. No result below is claimed unless the browser action actually executed.  
**Engine evidence:** real ngspice runs from `.tools/Spice64/bin/ngspice_con.exe` (ngspice-47), model `spice/models/2N3904.lib` (`.model QREF NPN ... BF=300`). Raw logs and parsed rows are in `docs/validation/`.

## Results

| Case | Method | Input | Expected / Reference | Observed (browser) | Evidence | Status |
|------|--------|-------|----------------------|--------------------|----------|--------|
| B1 · Regression | Navigate `/?mode=fixed`, `/?mode=emitter`, `/`; fill each Lab 3 parameter set; click **Run Simulation**; snapshot result card | Fixed: `VCC=12, RB=470000, RC=2200, beta=150, VBE=0.7`. Emitter: same + `RE=1000`. Divider: `VCC=12, R1=47000, R2=10000, RC=4700, RE=1000, beta=150, VBE=0.7` | Fixed `IC=3.606 mA, VCE=4.066 V, Active`; Emitter `IC=2.729 mA, VCE=3.248 V, Active`; Divider `IC=1.324 mA, VCE=4.446 V, Active, divergence 6.2%` (existing Lab 3 tests) | Fixed: `IC 3.606 mA`, `VCE 4.066 V`, `ACTIVE REGION`. Emitter: `IC 2.729 mA`, `VCE 3.248 V`, `ACTIVE REGION`. Divider: `IC 1.324 mA`, `VCE 4.446 V`, `6.2%`, `ACTIVE REGION`. Modes switched correctly | `b1-fixed.jpeg`, `b1-emitter.jpeg`, `b1-divider.jpeg` | **PASS** |
| B2 · DC SPICE | Navigate `/`; fill CE source `10 mV / 1000 Hz`; click **Run SPICE simulation**; read SPICE DC table; compare with direct ngspice log | `Vin=10 mV peak`, `f=1 kHz`, fixed CE fixture | Display VB/VE/VC/VCE/IC from ngspice; identify Model and Run Status | Table showed `VB 1.977 V`, `VE 1.324 V`, `VC 9.111 V`, `VCE 7.787 V`, `IC 1.313 mA`, `IB 10.393 µA`, region `Active` — matches `ngspice-b2-b5.json` (`1.976512, 1.323593, 9.110961, 7.787368, 0.001313 A`). **However** page only says generic `2N3904 model`; it does not show `QREF`/model file path and shows no explicit Run Status | `b2-spice-dc.jpeg`, `ngspice-b2-b5.log`, `ngspice-b2-b5.json` | **FAIL** |
| B3 · Change RE | Attempt to change RE in CE Reference; then change RE in Divider form and re-run; compare before/after | CE RE expected editable; analytical check `RE 1000 → 2000 Ω` | Operating point and/or gain must change with RE, not hard-coded | CE panel exposes only `amplitude_mv`, `frequency_hz`; lede fixes `RE=1 kΩ` — no RE control to run. Divider form RE change worked: `IC 1.324 → 0.679 mA`, `VCE 4.446 → 7.439 V`, matching independent `bjt.solve_exact` (`IC=0.679 mA, VCE=7.439 V`). This does **not** change the SPICE fixture | `b3-re-change-analytical.jpeg`, `b1-divider.jpeg`, `ngspice-b2-b5.json` | **FAIL** |
| B4 · AC | Click **AC Response** tab after the B2 run; read chart SVG polyline counts and displayed metrics; compare with direct ngspice rows | same `10 mV / 1 kHz` run | Frequency axis / gain magnitude / phase with units and values from a real run | Chart labels `AC magnitude (SPICE)` / `AC phase (SPICE)`, axes `Frequency (Hz)`, `Gain (dB)`, `Phase (deg)`. Displayed `1.754 V/V (4.879 dB)`, `-179.87 deg`, `Low -3 dB 1.738 Hz`, `High -3 dB not determined`. SVG polylines each have **451 points**; direct ngspice run has **451 AC rows** (`ngspice-b2-b5-rows.json`), gain/phase match JSON (`4.879469 dB`, `-179.870398 deg`) | `b4-ac.jpeg`, `ngspice-b2-b5-rows.json`, `ngspice-b2-b5.log` | **PASS** |
| B5 · Transient | Click **Transient** tab after B2 run; read waveform chart, metrics, polyline counts; compare with direct ngspice rows | `Vin=10 mV peak`, `f=1 kHz` | Vin/Vout vs time with time and voltage units; phase inversion from real run | Chart label `Transient response (SPICE)`, axes `Time (ms)` / `Voltage (mV)`, legend `Vin`/`Vout`, two polylines with **5008 points** each = direct ngspice **5008 tran rows**. Metrics `Vin 10 mV peak`, `Vout 17.5 mV peak`, `Gain 1.754 V/V`, `Phase 179.87 deg (inverted)`; direct run gives `gain 1.753759`, `phase 179.870383 deg` | `b5-tran.jpeg`, `ngspice-b2-b5-rows.json`, `ngspice-b2-b5.json` | **PASS** |
| B6 · Change Source | Navigate `/`; clear and fill CE source `20 mV / 2000 Hz`; run; compare B2/B5 values and chart counts with direct ngspice run | `Vin 10→20 mV`, `f 1000→2000 Hz` | Waveform/metrics change with input, not hard-coded | Observed `Vin 20 mV peak`, `Vout 34.94 mV peak`, `Gain 1.754 V/V`, `Phase 179.94 deg (inverted)`, time axis `0–2.5 ms`; transient polylines **2508 points** = direct ngspice **2508 rows** for 20 mV/2 kHz. Direct metrics `gain 1.753769`, `phase 179.937969 deg`, `Vin 20 mV`, expected Vout ≈ 35.1 mV — agrees. AC phase also changed `-179.87 → -179.94 deg` | `b6-source-change.jpeg`, `ngspice-b6-rows.json`, `ngspice-b6.json` | **PASS** |
| B7 · Invalid / Fail | (a) Divider form `RE=0`, click **Run Simulation**. (b) CE form amplitude `Engine`, click **Run SPICE simulation** | `RE=0 Ω`; `amplitude=Engine` | Clear error message, no fabricated result | (a) Error `RE must be greater than 0 Ω`; result card shows only placeholder, submitted `0` preserved. (b) Error `Enter a number for amplitude`; `.chart-svg` count = **0**, no SPICE DC table, submitted `Engine` preserved. No traceback | `b7-re-zero.jpeg`, `b7-engine-amplitude.jpeg` | **PASS** |
| B8 · UI | Open `/?mode=emitter` at desktop 1440×900 full page and phone 390×844 full page; inspect mode tabs, controls, results layout | Desktop + phone, mode switching | Readable charts/units/buttons, no clipped content | Desktop: 3-column workspace, all controls and Results cards fully visible. Phone: sidebar, schematic, configuration, results, SPICE form stack vertically; text remains readable, no horizontal clipping observed in full-page capture. Mode tab `Emitter Bias` active in both | `b8-desktop/1440x900-full.png`, `b8-mobile/390x844-full.png` | **PASS** |

## Summary

- **PASS:** B1, B4, B5, B6, B7, B8 (6)
- **FAIL:** B2, B3 (2)
- **NOT RUN:** none

## Findings before any code change

1. **B2 — missing model identity and run status (FAIL).** The SPICE DC values are genuine and match the direct ngspice log, but the page only states a generic `2N3904 model` and never identifies the actual model name/path (`QREF`, `spice/models/2N3904.lib`) or an explicit run status such as `ngspice run OK`. The handout requires both to be shown.
2. **B3 — CE RE is not editable (FAIL).** The CE reference simulator intentionally exposes only amplitude and frequency; `RE=1 kΩ` is a fixed fixture. Changing RE in the analytical Divider mode works and matches independent calculation, but it cannot exercise the CE SPICE operating point/gain sensitivity required by B3.
3. **B4/B5/B6 are evidence-backed, not hard-coded.** The rendered SVG polyline point counts equal the row counts from independent ngspice `wrdata` runs (451 AC, 5008/2508 transient), and displayed gain/phase/amplitudes match those rows. No mock plot or constant trace was observed.
4. **B7 confirms honest failure handling.** Invalid input produces a visible error and zero charts/results; no plausible fake numbers are displayed.

**No application code was changed during this acceptance run.** Only this report and evidence files under `docs/validation/` were added.

## Evidence files

- `docs/validation/b1-fixed.jpeg`, `b1-emitter.jpeg`, `b1-divider.jpeg`
- `docs/validation/b2-spice-dc.jpeg`
- `docs/validation/b3-re-change-analytical.jpeg`
- `docs/validation/b4-ac.jpeg`, `b5-tran.jpeg`, `b6-source-change.jpeg`
- `docs/validation/b7-re-zero.jpeg`, `b7-engine-amplitude.jpeg`
- `docs/validation/b8-desktop/1440x900-full.png`, `docs/validation/b8-mobile/390x844-full.png`
- `docs/validation/ngspice-b2-b5.log`, `ngspice-b2-b5.json`, `ngspice-b2-b5-rows.json`
- `docs/validation/ngspice-b6.log`, `ngspice-b6.json`, `ngspice-b6-rows.json`
