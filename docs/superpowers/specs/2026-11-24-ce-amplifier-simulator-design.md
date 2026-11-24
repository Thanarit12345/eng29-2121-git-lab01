# CE Amplifier Simulator v1 — Design

**Course:** ENG29 2121 · **Date:** 2026-11-24 · **Status:** approved

## Intent

Extend the existing Flask BJT DC-bias app into a minimal common-emitter
amplifier simulator. The lab page must first match the three Lab 3
analytical bias modes shown by the instructor reference, then add a
separate panel that runs a real ngspice reference circuit for DC `.op`,
AC `.ac`, and transient `.tran` results.

## Goals

- Lab 3 parity: three tabs — Voltage Divider Bias, Fixed Bias, Emitter Bias.
- Keep the existing voltage-divider exact/approximate analysis and all 34 existing tests unchanged.
- Add a reference CE simulator with fixed circuit values from the instructor spec.
- Run real ngspice in batch mode; never fabricate gain, cutoff, or waveform data.
- Show engineering units everywhere and clearly separate SPICE results from analytical reference values.
- Surface every ngspice failure as visible text; never hide errors or fall back to invented data.

## Non-goals / anti-goals

- No circuit editor, FET support, JavaScript chart library, database, or login.
- No attempt to make SPICE equal the textbook approximation; they use different assumptions.
- No hard-coded expected gain, cutoff frequency, or waveform values.
- Failure looks like a blank graph, a silent fallback, or a page showing plausible numbers when ngspice failed.

## Constraints

- Python 3.12, Flask 3.x, stdlib `unittest`.
- No new PyPI runtime dependency. Charts are server-rendered SVG.
- ngspice is an external executable, resolved from `NGSPICE_EXE`, then PATH, then `.tools/Spice64/bin/ngspice_con.exe`.
- No instructor starter netlist/model was present in the repo. A documented 2N3904 fallback model is committed under `spice/models/2N3904.lib`; `SPICE_MODEL` overrides it.
- Local ngspice install lives under `.tools/` and is gitignored.
- Commit on `main`; push to `origin/main` at the end.

## Approaches considered

1. **Extend in place with pure Python modules and server-rendered SVG — chosen.** Preserves the existing architecture and adds no frontend dependencies.
2. **Add a JavaScript charting library.** Better interaction, but adds a dependency and breaks the existing no-JS pattern.
3. **Create a separate simulator app.** Cleaner boundary, but duplicates layout and risks replacing the Lab 3 app.

## Lab 3 analytical modes

### Voltage Divider Bias (existing, unchanged)

Fields: `VCC`, `R1`, `R2`, `RC`, `RE`, `beta`, `VBE`. Existing Thévenin solution and approximation cross-check remain.

### Fixed Bias (new)

Fields: `VCC`, `RB`, `RC`, `beta`, `VBE`. Defaults from reference: `12 V`, `470 kΩ`, `2.2 kΩ`, `150`, `0.7 V`.

```
IB  = (VCC - VBE) / RB
IC  = beta * IB
IE  = (1 + beta) * IB
VB  = VBE
VE  = 0
VC  = VCC - IC * RC
VCE = VC
PQ  = VCE * IC
```

Cutoff when `VCC <= VBE`: zero currents, `VB = VC = VCE = VCC`. Saturation when `VCE < 0.2 V`.

### Emitter Bias (new)

Fields: `VCC`, `RB`, `RC`, `RE`, `beta`, `VBE`. Defaults from reference: `12 V`, `470 kΩ`, `2.2 kΩ`, `1 kΩ`, `150`, `0.7 V`.

```
IB  = (VCC - VBE) / (RB + (1 + beta) * RE)
IC  = beta * IB
IE  = (1 + beta) * IB
VE  = IE * RE
VB  = VBE + VE
VC  = VCC - IC * RC
VCE = VC - VE
PQ  = VCE * IC
```

Cutoff when `VCC <= VBE`; saturation when `VCE < 0.2 V`.

## Reference CE simulator fixture

Fixed values: `VCC = 12 V`, `R1 = 100 kΩ`, `R2 = 22 kΩ`, `RC = 2.2 kΩ`, `RE = 1 kΩ`, `RL = 10 kΩ`, `Cin = Cout = 10 µF`, source `10 mV peak / 1 kHz`, temperature `27 °C`. User-editable inputs are amplitude and frequency only.

Circuit: divider at base, `RC` collector load, `RE` emitter degeneration, `Cin` from ideal source to base, `Cout` from collector to `RL`.

Analytical reference uses the existing `solve_exact()` with this fixture, `beta = BF` from the selected model (300 for fallback) and `VBE = 0.7 V`, labelled with those conditions.

## ngspice integration

One generated netlist runs `.op`, `.ac`, and `.tran` in a `.control` block. Data are written with `wrdata` as ASCII tables:

- `.op`: `print v(base) v(emitter) v(collector) v(out)`, parsed from the log.
- `.ac`: `frequency vdb(out) vp(out)`, with `AC 1` so `V(out)` is the transfer function. Sweep `0.1 Hz` to `100 MHz`, 50 points/decade.
- `.tran`: `time v(source) v(out)`, duration `5/f` (clamped to 5 s), 5000 points.

`IC` and `IB` for the SPICE DC table are derived from SPICE node voltages and resistor values; they are labelled as derived SPICE values. AC gain is `10^(dB/20)`. Phase is `vp(out)`. `-3 dB` crossings are found from the measured sweep; if absent, the UI says “not determined in sweep range”.

Transient amplitude and phase are estimated by fitting a sine at the requested frequency to the last 60% of samples. Phase difference is wrapped to `[-180°, 180°]`.

## Outputs and units

- DC SPICE table vs analytical reference: `VB, VE, VC, VCE, IC, IB, IE` in V/mA/µA.
- AC: gain in V/V and dB, phase in degrees, frequency in Hz/kHz/MHz as appropriate; two SVG charts.
- Transient: time in ms/s, Vin and Vout in mV, measured gain and phase difference; one SVG chart.
- All SPICE sections labelled “SPICE”; analytical section labelled “Analytical reference”.

## Error paths

- Binary missing → `SpiceUnavailable` with install/`NGSPICE_EXE` guidance.
- Non-zero exit → `SpiceRunError` with return code and log tail.
- Timeout → process killed and explicit timeout message.
- Missing or malformed `wrdata` vectors → `SpiceParseError`.
- Frequency outside sweep or degenerate amplitude → explicit error.
- Analytical values still render when SPICE fails; graphs are omitted, never faked.

## File layout

```
app.py                     mode-aware route, /simulate route, format filters
bjt.py                     existing voltage-divider logic + fixed/emitter solvers
charts.py                  server-side SVG line charts
ce_spice.py                netlist, subprocess, parsers, metrics, errors
spice/models/2N3904.lib    documented fallback BJT model
static/bjt-fixed-bias.svg  fixed-bias circuit
static/bjt-emitter-bias.svg emitter-bias circuit
templates/index.html       tabs, mode panels, simulator panel
static/style.css           tab and simulator styling
tests/                     existing tests + new tests
README.md                  updated run/test/simulator docs
```

## Decisions left to the implementer

- Exact SVG coordinates and palette, matching the existing circuit files.
- Internal helper names inside each new module.
- Number of decimal places in the simulator tables, following existing 3-decimal convention.
