# CE Amplifier Simulator v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing Lab 3 Flask BJT bias app with three analytical bias modes and a reference CE amplifier simulator powered by real ngspice `.op`, `.ac`, and `.tran` runs.

**Architecture:** Preserve the existing `bjt.py`/`app.py`/Jinja architecture. Add small pure-Python modules for the new bias modes, SPICE execution/parsing, and server-rendered SVG charts, and extend the one-page UI with mode tabs plus a separate simulator panel. No new PyPI runtime dependency.

**Tech Stack:** Python 3.12, Flask 3.x, Jinja2, stdlib `unittest`, `subprocess`, `tempfile`, `math`, `re`, ngspice 47 (external binary).

**Spec:** `docs/superpowers/specs/2026-11-24-ce-amplifier-simulator-design.md`

## Global Constraints

- Python 3.12; runtime dependency remains `Flask>=3.0,<4`; tests use stdlib `unittest`.
- `bjt.py` must not import Flask or subprocess.
- `ce_spice.py` must not import Flask; it owns ngspice execution, parsing, and SPICE error types.
- Existing 34 tests and existing voltage-divider behavior must remain green.
- Every displayed number carries a unit; SPICE outputs are labelled `SPICE`; analytical references are labelled `Analytical reference`.
- No hard-coded gain, cutoff, or waveform values. Missing/unparseable SPICE data raises a visible error; cutoff outside sweep is reported as `not determined in sweep range`.
- Reference simulator uses the fixed spec fixture; user-editable inputs are amplitude and frequency only.
- No JavaScript chart library; charts are server-rendered SVG.
- Local ngspice install under `.tools/` is gitignored. Commit on `main`; push to `origin/main`.

## Review Focus

1. **Missing ngspice binary** — expect a visible `SpiceUnavailable` message with `NGSPICE_EXE`/PATH guidance; the page still renders and analytical DC bias still works.
2. **ngspice non-zero exit or malformed output** — expect the real return code/log excerpt or a `SpiceParseError` message; no blank charts, no fabricated numbers.
3. **Frequency outside AC sweep or zero/negative amplitude/frequency** — expect a validation error naming the field and keeping the submitted value; no `ZeroDivisionError` or 500.
4. **Existing Lab 3 voltage-divider path** — expect the same defaults, cross-check, validation messages, and 34 existing tests to pass unchanged.
5. **Cutoff below -3 dB at sweep edge or not crossed** — expect `not determined in sweep range`, never an extrapolated or hard-coded frequency.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `bjt.py` | Existing voltage-divider validation/solver and new `solve_fixed_bias`, `solve_emitter_bias` dataclasses/solvers. No Flask. |
| `ce_spice.py` | Reference fixture, netlist builder, ngspice discovery/run, `wrdata` and `.op` parsers, AC/tran metric extraction, SPICE exceptions. No Flask. |
| `charts.py` | Pure functions returning SVG strings for AC magnitude/phase and transient waveforms. |
| `app.py` | Mode-aware `/` route, `/simulate` POST route, engineering-format filters, SPICE error rendering. |
| `templates/index.html` | Tab bar, mode-specific form/circuit/results, simulator form/results/charts. |
| `static/style.css` | Tabs, simulator status, chart, and comparison-table styling. |
| `static/bjt-fixed-bias.svg` | Fixed-bias reference circuit. |
| `static/bjt-emitter-bias.svg` | Emitter-bias reference circuit. |
| `spice/models/2N3904.lib` | Documented fallback 2N3904 model; overridable by `SPICE_MODEL`. |
| `tests/test_bjt.py` | Existing tests plus fixed/emitter solver tests. |
| `tests/test_app.py` | Existing tests plus tab/mode route tests. |
| `tests/test_ce_spice.py` | Netlist, parser, metric, and real-ngspice integration tests. |
| `tests/test_simulate_app.py` | `/simulate` route tests with stubbed SPICE runner. |
| `README.md` | Run, test, ngspice setup, simulator scope, and fixed-model note. |
| `.gitignore` | Ignore `.tools/`. |

---

### Task 1: Add fixed and emitter analytical solvers

**Files:**
- Modify: `bjt.py`
- Modify: `tests/test_bjt.py`

**Interfaces:**
- Consumes: existing `ValidationError`, `NON_FINITE_MESSAGE`, `math.isfinite`.
- Produces: `@dataclass(frozen=True) class FixedBiasInputs(vcc_v, rb_ohm, rc_ohm, beta, vbe_v: float)`, `@dataclass(frozen=True) class EmitterBiasInputs(vcc_v, rb_ohm, rc_ohm, re_ohm, beta, vbe_v: float)`, `solve_fixed_bias(inputs: FixedBiasInputs) -> OperatingPoint`, `solve_emitter_bias(inputs: EmitterBiasInputs) -> OperatingPoint`.

- [ ] **Step 1: Write failing fixed/emitter tests**

Append to `tests/test_bjt.py`:

```python
from bjt import FixedBiasInputs, EmitterBiasInputs, solve_fixed_bias, solve_emitter_bias


class TestFixedBias(unittest.TestCase):
    def test_reference_values(self):
        point = solve_fixed_bias(FixedBiasInputs(12.0, 470000.0, 2200.0, 150.0, 0.7))
        self.assertAlmostEqual(point.ib_a, 24.042553e-6, places=10)
        self.assertAlmostEqual(point.ic_a, 3.606383e-3, places=7)
        self.assertAlmostEqual(point.vce_v, 4.065957, places=6)
        self.assertEqual(point.region, "active")

    def test_cutoff_when_vcc_below_vbe(self):
        point = solve_fixed_bias(FixedBiasInputs(0.5, 470000.0, 2200.0, 150.0, 0.7))
        self.assertEqual(point.region, "cutoff")
        self.assertEqual(point.ic_a, 0.0)
        self.assertAlmostEqual(point.vce_v, 0.5, places=6)


class TestEmitterBias(unittest.TestCase):
    def test_reference_values(self):
        point = solve_emitter_bias(EmitterBiasInputs(12.0, 470000.0, 2200.0, 1000.0, 150.0, 0.7))
        self.assertAlmostEqual(point.ib_a, 18.196202e-6, places=10)
        self.assertAlmostEqual(point.ic_a, 2.729430e-3, places=7)
        self.assertAlmostEqual(point.ve_v, 2.747627, places=6)
        self.assertAlmostEqual(point.vce_v, 3.247627, places=6)
        self.assertEqual(point.region, "active")

    def test_saturation(self):
        point = solve_emitter_bias(EmitterBiasInputs(12.0, 470000.0, 22000.0, 1000.0, 150.0, 0.7))
        self.assertEqual(point.region, "saturation")
        self.assertLess(point.vce_v, 0.2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_bjt.TestFixedBias tests.test_bjt.TestEmitterBias -v`
Expected: FAIL with import/attribute errors for `solve_fixed_bias` or `solve_emitter_bias`.

- [ ] **Step 3: Implement solvers in `bjt.py`**

Add `FixedBiasInputs` and `EmitterBiasInputs` dataclasses and the two solvers. Reuse `OperatingPoint`, `_checked`, `NON_FINITE_MESSAGE`, and cutoff/saturation conventions. Fixed bias uses `vbb_v = vcc_v` and `rth_ohm = rb_ohm` for the returned point. Emitter bias uses `vbb_v = vcc_v` and `rth_ohm = rb_ohm`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m unittest tests.test_bjt -v`
Expected: PASS, including all existing voltage-divider tests.

- [ ] **Step 5: Commit**

```bash
git add bjt.py tests/test_bjt.py
git commit -m "feat: add fixed and emitter bias solvers"
```

---

### Task 2: Add mode-aware Lab 3 route and UI

**Files:**
- Modify: `app.py`
- Modify: `templates/index.html`
- Modify: `static/style.css`
- Create: `static/bjt-fixed-bias.svg`
- Create: `static/bjt-emitter-bias.svg`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `solve_fixed_bias`, `solve_emitter_bias`, `FixedBiasInputs`, `EmitterBiasInputs`.
- Produces: `/` accepts `mode` query/form value `divider|fixed|emitter`; template renders tab bar and mode-specific fields/defaults/circuit; `app.py` exposes `MODE_CONFIG` or equivalent internal structure used by tests only through rendered HTML.

- [ ] **Step 1: Write failing mode UI tests**

Add to `tests/test_app.py`:

```python
class TestModes(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_get_renders_three_tabs(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('data-mode="divider"', body)
        self.assertIn('data-mode="fixed"', body)
        self.assertIn('data-mode="emitter"', body)

    def test_fixed_mode_defaults(self):
        body = self.client.get("/?mode=fixed").get_data(as_text=True)
        self.assertIn('name="rb"', body)
        self.assertIn('value="470000"', body)
        self.assertIn("/static/bjt-fixed-bias.svg", body)

    def test_emitter_mode_post(self):
        body = self.client.post("/?mode=emitter", data={
            "vcc": "12", "rb": "470000", "rc": "2200", "re": "1000", "beta": "150", "vbe": "0.7"
        }).get_data(as_text=True)
        self.assertIn("2.729 mA", body)
        self.assertIn("3.248 V", body)
        self.assertIn("Active", body)

    def test_fixed_mode_post(self):
        body = self.client.post("/?mode=fixed", data={
            "vcc": "12", "rb": "470000", "rc": "2200", "beta": "150", "vbe": "0.7"
        }).get_data(as_text=True)
        self.assertIn("3.606 mA", body)
        self.assertIn("4.066 V", body)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_app.TestModes -v`
Expected: FAIL because mode tabs and mode-specific fields are absent.

- [ ] **Step 3: Implement mode routing and templates**

In `app.py`, define per-mode defaults, fields, and solvers. Keep existing `DEFAULTS`/divider behavior intact. Parse `mode` from `request.args.get('mode', 'divider')` and validate against allowed modes. POST renders the same mode. Build warnings only for divider cross-check when comparison exists.

In `templates/index.html`, render a tab bar with links/buttons preserving mode and a mode-specific form action. Render `comparison` only when present. Add two SVG files matching the reference style of `static/bjt-circuit.svg`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m unittest tests.test_app -v`
Expected: PASS, including existing layout and route tests.

- [ ] **Step 5: Commit**

```bash
git add app.py templates/index.html static/style.css static/bjt-fixed-bias.svg static/bjt-emitter-bias.svg tests/test_app.py
git commit -m "feat: add Lab 3 fixed and emitter bias modes"
```

---

### Task 3: Build ngspice netlist, parsing, and metrics

**Files:**
- Create: `ce_spice.py`
- Create: `tests/test_ce_spice.py`
- Create: `spice/models/2N3904.lib`

**Interfaces:**
- Produces: `REFERENCE = {...}` or dataclass with fixed fixture values; `SpiceUnavailable`, `SpiceRunError`, `SpiceParseError`; `build_reference_netlist(amplitude_v_peak, frequency_hz, model_path) -> str`; `parse_op_log(text) -> dict`; `parse_wrdata(path, columns) -> list[dict]`; `analyze_ac(rows, selected_frequency_hz) -> dict`; `analyze_tran(rows, frequency_hz) -> dict`.

- [ ] **Step 1: Write failing parser and netlist tests**

Create `tests/test_ce_spice.py`:

```python
import tempfile
import unittest
from pathlib import Path

from ce_spice import build_reference_netlist, parse_op_log, parse_wrdata, analyze_ac, analyze_tran, SpiceParseError


class TestNetlist(unittest.TestCase):
    def test_contains_reference_values(self):
        net = build_reference_netlist(0.01, 1000.0, Path('spice/models/2N3904.lib'))
        self.assertIn('R1 vcc base 100k', net)
        self.assertIn('SIN(0 0.01 1000.0)', net)
        self.assertIn('.ac dec 50 0.1 100meg', net)
        self.assertIn('wrdata', net)


class TestParse(unittest.TestCase):
    def test_parse_op_log(self):
        text = 'v(base) = 1.976512e+00\nv(emitter) = 1.323593e+00\nv(collector) = 9.110961e+00\n'
        row = parse_op_log(text)
        self.assertAlmostEqual(row['base'], 1.976512, places=6)

    def test_parse_wrdata_rejects_short_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'x.dat'
            p.write_text('bad\n', encoding='utf-8')
            with self.assertRaises(SpiceParseError):
                parse_wrdata(p, ['frequency', 'vdb(out)', 'vp(out)'])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_ce_spice -v`
Expected: FAIL with `ModuleNotFoundError: ce_spice`.

- [ ] **Step 3: Implement netlist builder and parsers**

Create `spice/models/2N3904.lib` with the documented fallback model from the spec/comments. In `ce_spice.py`, implement:

- `build_reference_netlist`: fixed component values, `.include`/absolute-safe model path quoting, `.control` with `set wr_singlescale`, `set wr_vecnames`, `op`, `print`, `ac dec 50 0.1 100meg`, `wrdata ac.dat frequency vdb(out) vp(out)`, `tran ...`, `wrdata tran.dat time v(source) v(out)`, `.endc`.
- `parse_op_log`: regex for `v(node) = value`.
- `parse_wrdata`: read numeric rows, map last N columns by requested names, raise `SpiceParseError` if empty/malformed.
- `analyze_ac`: selected frequency nearest in sweep by log distance or exact match tolerance; gain linear from dB; `low_cutoff_hz`/`high_cutoff_hz` as first crossings below peak-3dB or `None`.
- `analyze_tran`: use last 60% samples, fit sine at requested frequency via least-squares projection to estimate amplitude/phase; compute gain and wrapped phase difference.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m unittest tests.test_ce_spice -v`
Expected: PASS for parser/netlist/metric unit tests.

- [ ] **Step 5: Commit**

```bash
git add ce_spice.py tests/test_ce_spice.py spice/models/2N3904.lib
git commit -m "feat: add CE ngspice netlist and parsers"
```

---

### Task 4: Run real ngspice and expose simulator API

**Files:**
- Modify: `ce_spice.py`
- Modify: `tests/test_ce_spice.py`

**Interfaces:**
- Produces: `resolve_ngspice() -> Path`, `run_ngspice(netlist: str, timeout_s: float = 30.0) -> dict`, `simulate_reference(amplitude_v_peak, frequency_hz, model_path=None, ngspice_exe=None) -> dict`.

- [ ] **Step 1: Write failing subprocess/error tests**

Add tests using a fake runner or monkeypatched `subprocess.run`:

```python
from unittest import mock
from ce_spice import simulate_reference, SpiceUnavailable, SpiceRunError


class TestRunErrors(unittest.TestCase):
    def test_missing_binary_raises_unavailable(self):
        with mock.patch('ce_spice.resolve_ngspice', side_effect=SpiceUnavailable('missing')):
            with self.assertRaises(SpiceUnavailable):
                simulate_reference(0.01, 1000.0)

    def test_nonzero_exit_raises_run_error(self):
        fake = mock.Mock(returncode=1, stdout='bad', stderr='oops')
        with mock.patch('ce_spice.resolve_ngspice', return_value=Path('ngspice')), \
             mock.patch('subprocess.run', return_value=fake):
            with self.assertRaises(SpiceRunError):
                simulate_reference(0.01, 1000.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_ce_spice.TestRunErrors -v`
Expected: FAIL because functions/errors are missing.

- [ ] **Step 3: Implement runner**

Implement `resolve_ngspice()` checking `NGSPICE_EXE`, `shutil.which('ngspice_con')/('ngspice')`, then `.tools/Spice64/bin/ngspice_con.exe`. `run_ngspice` writes netlist to a temp dir, runs `[exe, '-b', 'input.cir']`, captures text, enforces timeout, raises `SpiceRunError` on non-zero exit with tail of stdout/stderr, and returns parsed op/ac/tran. `simulate_reference` validates amplitude > 0 and frequency within AC sweep bounds, computes analytical reference via `bjt.solve_exact` and model BF metadata, and returns a dict with `spice`, `analytical`, `meta`, `warnings`.

- [ ] **Step 4: Add real ngspice integration test**

```python
@unittest.skipUnless(Path('.tools/Spice64/bin/ngspice_con.exe').exists() or shutil.which('ngspice_con'), 'ngspice not installed')
class TestRealNgspice(unittest.TestCase):
    def test_reference_simulation(self):
        result = simulate_reference(0.01, 1000.0)
        self.assertIn('ac', result['spice'])
        self.assertGreater(result['spice']['ac']['gain_vv'], 1.0)
        self.assertTrue(result['spice']['tran']['phase_inverted'])
```

Run: `.venv\Scripts\python.exe -m unittest tests.test_ce_spice -v`
Expected: PASS, including real integration test.

- [ ] **Step 5: Commit**

```bash
git add ce_spice.py tests/test_ce_spice.py
git commit -m "feat: run reference CE simulations with ngspice"
```

---

### Task 5: Add simulator UI, charts, and route wiring

**Files:**
- Create: `charts.py`
- Modify: `app.py`
- Modify: `templates/index.html`
- Modify: `static/style.css`
- Create: `tests/test_simulate_app.py`

**Interfaces:**
- Produces: `charts.ac_chart_svg(rows, selected_hz) -> str`, `charts.tran_chart_svg(rows) -> str`; `POST /simulate` accepts `amplitude_mv` and `frequency_hz`, renders simulator result or error.

- [ ] **Step 1: Write failing route tests with stubbed simulation**

Create `tests/test_simulate_app.py`:

```python
import unittest
from unittest import mock
from app import create_app
from ce_spice import SpiceUnavailable

class TestSimulateRoute(unittest.TestCase):
    def setUp(self):
        app = create_app(); app.config.update(TESTING=True); self.client = app.test_client()

    def test_simulate_renders_spice_sections(self):
        fake = {
            'meta': {'amplitude_mv': 10.0, 'frequency_hz': 1000.0},
            'analytical': {'ic_a': 0.001, 'vce_v': 5.0, 'region': 'active'},
            'spice': {
                'dc': {'vb_v': 1.9, 've_v': 1.3, 'vc_v': 9.1, 'vce_v': 7.8, 'ic_a': 0.0013, 'ib_a': 0.000004, 'ie_a': 0.001304, 'region': 'active'},
                'ac': {'gain_vv': 2.0, 'gain_db': 6.02, 'phase_deg': -179.0, 'low_cutoff_hz': None, 'high_cutoff_hz': None, 'rows': [{'frequency_hz': 1000.0, 'vdb_out': 6.02, 'vp_out': -179.0}]},
                'tran': {'vin_pp_mv': 20.0, 'vout_pp_mv': 40.0, 'gain_vv': 2.0, 'phase_deg': -179.0, 'rows': [{'time_s': 0.0, 'v_source': 0.0, 'v_out': 0.0}]},
            },
            'warnings': [],
        }
        with mock.patch('app.simulate_reference', return_value=fake):
            body = self.client.post('/simulate', data={'amplitude_mv': '10', 'frequency_hz': '1000'}).get_data(as_text=True)
        self.assertIn('SPICE DC operating point (.op)', body)
        self.assertIn('Analytical reference', body)
        self.assertIn('<svg', body)

    def test_missing_ngspice_shows_error(self):
        with mock.patch('app.simulate_reference', side_effect=SpiceUnavailable('missing ngspice')):
            body = self.client.post('/simulate', data={'amplitude_mv': '10', 'frequency_hz': '1000'}).get_data(as_text=True)
        self.assertIn('missing ngspice', body)
        self.assertNotIn('Traceback', body)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m unittest tests.test_simulate_app -v`
Expected: FAIL because `/simulate` and chart helpers do not exist.

- [ ] **Step 3: Implement charts and route**

Create `charts.py` with simple SVG line chart functions (axes, labels, polyline, no JS). In `app.py`, add `/simulate` POST. Validate amplitude/frequency; on validation error render page with `sim_errors` and preserved values. Catch `SpiceUnavailable`, `SpiceRunError`, `SpiceParseError`, `ValidationError` and render visible `sim_error`. On success pass `sim_result` and SVG strings to template.

Update template with a simulator panel below Lab 3 results: fixed circuit description, amplitude/frequency form, SPICE DC table, analytical comparison, AC metrics/chart, tran metrics/chart, and error box.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m unittest tests.test_simulate_app tests.test_app -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add charts.py app.py templates/index.html static/style.css tests/test_simulate_app.py
git commit -m "feat: add CE simulator UI and charts"
```

---

### Task 6: Docs, full verification, browser demo, and push

**Files:**
- Modify: `README.md`
- Modify: `.gitignore` (if not already done)

**Interfaces:**
- Consumes: completed app and test suite.
- Produces: updated docs, passing tests, running local demo, GitHub commit.

- [ ] **Step 1: Update README**

Document three Lab 3 modes, CE simulator inputs, fixed reference fixture, ngspice install/`NGSPICE_EXE`/`SPICE_MODEL`, and the fact that SPICE results come from real ngspice runs and may differ from analytical approximations.

- [ ] **Step 2: Run full automated verification**

Run: `.venv\Scripts\python.exe -m unittest discover -s tests -t . -v`
Expected: all tests PASS, including existing 34.

- [ ] **Step 3: Run real browser demo**

Start: `.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5000 --no-reload`
Use the browser tool to open `/`, switch modes, run `/simulate` with `10 mV`, `1 kHz`, and capture the visible SPICE DC/AC/tran sections. Confirm no traceback text appears.

- [ ] **Step 4: Commit and push**

```bash
git add -A
git status --short
git commit -m "feat: add CE amplifier simulator with ngspice"
git push origin main
```

- [ ] **Step 5: Report**

Include: changed files, test counts, ngspice version/path used, demo URL, and commit hash. Do not claim success without command output.