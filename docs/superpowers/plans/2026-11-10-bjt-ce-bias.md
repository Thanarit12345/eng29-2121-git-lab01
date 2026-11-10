# BJT Common-Emitter DC Bias Web App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A one-page Flask app that solves and cross-checks the DC Q-point of a voltage-divider-biased NPN common-emitter stage.

**Architecture:** `bjt.py` holds all engineering logic as pure functions over frozen dataclasses and imports nothing from Flask. `app.py` validates form input, calls `bjt.py`, formats units, and renders one Jinja template. Tests are stdlib `unittest`, split into logic tests and Flask test-client tests.

**Tech Stack:** Python 3.12, Flask 3.x, Jinja2 (via Flask), stdlib `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-10-bjt-ce-bias-design.md`

## Global Constraints

- Python 3.12; Flask only dependency (`Flask>=3.0,<4`); tests use stdlib `unittest`.
- `bjt.py` must not import Flask.
- `electrical.py` and `test_electrical.py` are not modified.
- No JavaScript, no database, no AC/transient/FET analysis.
- Every displayed number carries a unit: V (3 dp), mA (3 dp), µA (3 dp when |I| < 1 mA), mW (3 dp), % (1 dp).
- Saturation threshold `VCE < 0.2 V`; approximation-reliability threshold `> 5.0%` divergence; both exact.
- Validation messages are exactly the strings in the spec's table.
- Commit on `main`; push to `origin/main` at the end.

## Review Focus

1. **Blank or non-numeric field** — expect a message naming that field, the other entered values still in the form, HTTP 200, no traceback.
2. **`VBB ≤ VBE` (divider below turn-on)** — expect cutoff: zero currents, `VCE = VCC`, no negative current rendered.
3. **Zero/negative `R1`, `R2`, `RC`, `RE`, or `VCC`** — expect validation messages, never `ZeroDivisionError` or `ZeroDivisionError`-style 500.
4. **Very large `beta` or very small `RE`** — expect a saturation or unreliable-approximation warning with finite numbers, not an exception.
5. **Extreme magnitudes (`1e9 Ω`, `1000 V`)** — expect readable formatted numbers, never `nan` or `inf` in the page.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `bjt.py` | Parsing/validation, exact Q-point, region, approximation + divergence. No Flask. |
| `app.py` | `create_app()`, `/` route (GET/POST), unit-formatting filters, warning text. |
| `templates/index.html` | Form, results table, region badge, cross-check table, messages. |
| `static/style.css` | Minimal layout and badge colours. |
| `tests/__init__.py` | Makes `tests` importable for discovery. |
| `tests/test_bjt.py` | Engineering-logic tests. |
| `tests/test_app.py` | Route and rendering tests via Flask test client. |
| `requirements.txt` | `Flask>=3.0,<4`. |
| `README.md` | Rewritten for this app: purpose, run, test, example. |

---

### Task 1: Validation and exact Q-point

**Files:**
- Create: `bjt.py`
- Create: `tests/__init__.py` (empty)
- Test: `tests/test_bjt.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class ValidationError(ValueError)` with attribute `errors: list[str]`
  - `@dataclass(frozen=True) class BiasInputs` with `vcc_v, r1_ohm, r2_ohm, rc_ohm, re_ohm, beta, vbe_v: float`
  - `validate(raw: Mapping[str, str]) -> BiasInputs` (raises `ValidationError`)
  - `@dataclass(frozen=True) class OperatingPoint` with `vbb_v, rth_ohm, ib_a, ic_a, ie_a, vb_v, vc_v, ve_v, vce_v, pq_w: float`
  - `solve_exact(inputs: BiasInputs) -> OperatingPoint`
  - Field keys used by the form: `vcc, r1, r2, rc, re, beta, vbe`; labels `VCC, R1, R2, RC, RE, beta, VBE`.

- [ ] **Step 1: Write the failing tests**

Create `tests/__init__.py` empty. Create `tests/test_bjt.py`:

```python
import unittest

from bjt import BiasInputs, ValidationError, solve_exact, validate

EXAMPLE = {
    "vcc": "12", "r1": "47000", "r2": "10000",
    "rc": "4700", "re": "1000", "beta": "150", "vbe": "0.7",
}


class TestValidate(unittest.TestCase):
    def test_valid_inputs_become_floats(self):
        inputs = validate(EXAMPLE)
        self.assertEqual(inputs.vcc_v, 12.0)
        self.assertEqual(inputs.beta, 150.0)

    def test_blank_field_is_reported_by_name(self):
        with self.assertRaises(ValidationError) as ctx:
            validate({**EXAMPLE, "vcc": ""})
        self.assertIn("Enter a number for VCC", ctx.exception.errors)

    def test_non_numeric_field_is_reported_by_name(self):
        with self.assertRaises(ValidationError) as ctx:
            validate({**EXAMPLE, "re": "abc"})
        self.assertIn("Enter a number for RE", ctx.exception.errors)

    def test_missing_key_counts_as_blank(self):
        raw = dict(EXAMPLE)
        del raw["beta"]
        with self.assertRaises(ValidationError) as ctx:
            validate(raw)
        self.assertIn("Enter a number for beta", ctx.exception.errors)

    def test_non_positive_resistances_are_rejected(self):
        for key, label in (("r1", "R1"), ("r2", "R2"), ("rc", "RC"), ("re", "RE")):
            for value in ("0", "-5"):
                with self.assertRaises(ValidationError) as ctx:
                    validate({**EXAMPLE, key: value})
                self.assertIn(f"{label} must be greater than 0 \u03a9", ctx.exception.errors)

    def test_zero_vcc_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate({**EXAMPLE, "vcc": "0"})
        self.assertIn("VCC must be greater than 0 V", ctx.exception.errors)

    def test_beta_below_one_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate({**EXAMPLE, "beta": "0.5"})
        self.assertIn("beta must be at least 1", ctx.exception.errors)

    def test_vbe_outside_open_interval_is_rejected(self):
        for vbe in ("0", "12", "13"):
            with self.assertRaises(ValidationError) as ctx:
                validate({**EXAMPLE, "vbe": vbe})
            self.assertIn("VBE must be between 0 V and VCC", ctx.exception.errors)

    def test_all_errors_are_collected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate({**EXAMPLE, "vcc": "0", "r1": "0"})
        self.assertIn("VCC must be greater than 0 V", ctx.exception.errors)
        self.assertIn("R1 must be greater than 0 \u03a9", ctx.exception.errors)


class TestSolveExact(unittest.TestCase):
    def test_worked_example(self):
        point = solve_exact(validate(EXAMPLE))
        self.assertAlmostEqual(point.vbb_v, 2.105263, places=6)
        self.assertAlmostEqual(point.rth_ohm, 8245.614035, places=6)
        self.assertAlmostEqual(point.ib_a, 8.824502e-6, places=9)
        self.assertAlmostEqual(point.ic_a, 1.323675e-3, places=6)
        self.assertAlmostEqual(point.ie_a, 1.332500e-3, places=6)
        self.assertAlmostEqual(point.ve_v, 1.332500, places=6)
        self.assertAlmostEqual(point.vb_v, 2.032500, places=6)
        self.assertAlmostEqual(point.vc_v, 5.7787264, places=6)
        self.assertAlmostEqual(point.vce_v, 4.4462267, places=6)
        self.assertAlmostEqual(point.pq_w, 5.8853e-3, places=6)

    def test_lower_vbe_raises_base_current(self):
        low = solve_exact(validate(EXAMPLE))
        high = solve_exact(validate({**EXAMPLE, "vbe": "0.6"}))
        self.assertGreater(high.ib_a, low.ib_a)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_bjt -v`
Expected: `ModuleNotFoundError: No module named 'bjt'`.

- [ ] **Step 3: Implement `bjt.py`**

Dataclasses `BiasInputs` (as above), `ValidationError(errors)`, `validate`, `OperatingPoint`, `solve_exact` with the spec's exact formulas. `validate` strips each string, converts with `float()`, collects every failure into one `ValidationError`, and applies the VCC/VBE cross-rule only when `vcc_v` parsed successfully. `solve_exact` computes `vbb_v, rth_ohm, ib_a, ic_a, ie_a, ve_v, vb_v, vc_v, vce_v, pq_w` from the spec block; it does no clamping or region logic yet.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_bjt -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bjt.py tests/__init__.py tests/test_bjt.py
git commit -m "feat: add BJT bias validation and exact Q-point"
```

---

### Task 2: Region classification and cutoff clamp

**Files:**
- Modify: `bjt.py`
- Test: `tests/test_bjt.py`

**Interfaces:**
- Consumes: `BiasInputs`, `OperatingPoint`, `solve_exact` from Task 1.
- Produces: `OperatingPoint.region: str` with exactly `"active"`, `"cutoff"`, or `"saturation"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bjt.py`:

```python
class TestRegion(unittest.TestCase):
    def test_worked_example_is_active(self):
        self.assertEqual(solve_exact(validate(EXAMPLE)).region, "active")

    def test_divider_below_vbe_is_cutoff(self):
        point = solve_exact(validate({**EXAMPLE, "r2": "1000"}))  # VBB = 0.25 V
        self.assertEqual(point.region, "cutoff")
        self.assertEqual(point.ib_a, 0.0)
        self.assertEqual(point.ic_a, 0.0)
        self.assertEqual(point.ie_a, 0.0)
        self.assertAlmostEqual(point.ve_v, 0.0, places=9)
        self.assertAlmostEqual(point.vb_v, 0.25, places=6)
        self.assertAlmostEqual(point.vc_v, 12.0, places=6)
        self.assertAlmostEqual(point.vce_v, 12.0, places=6)
        self.assertAlmostEqual(point.pq_w, 0.0, places=9)

    def test_large_collector_resistor_is_saturation(self):
        point = solve_exact(validate({**EXAMPLE, "rc": "22000"}))
        self.assertEqual(point.region, "saturation")
        self.assertLess(point.vce_v, 0.2)

    def test_huge_beta_is_saturation(self):
        point = solve_exact(validate({**EXAMPLE, "beta": "100000"}))
        self.assertEqual(point.region, "saturation")

    def test_tiny_emitter_resistor_is_saturation(self):
        point = solve_exact(validate({**EXAMPLE, "re": "1"}))
        self.assertEqual(point.region, "saturation")
        self.assertLess(point.vce_v, 0.2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_bjt.TestRegion -v`
Expected: FAIL with `AttributeError: 'OperatingPoint' object has no attribute 'region'`.

- [ ] **Step 3: Implement region logic**

Add `region: str` to `OperatingPoint`. In `solve_exact`, after computing `vbb_v`: if `vbb_v <= vbe_v`, return the cutoff point (`ib_a = ic_a = ie_a = 0.0`, `ve_v = 0.0`, `vb_v = vbb_v`, `vc_v = vce_v = vcc_v`, `pq_w = 0.0`, `region = "cutoff"`), keeping `vbb_v` and `rth_ohm`. Otherwise compute the active formulas, then set `region = "saturation"` when `vce_v < 0.2` else `"active"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_bjt -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bjt.py tests/test_bjt.py
git commit -m "feat: classify BJT region and clamp cutoff"
```

---

### Task 3: Approximate cross-check

**Files:**
- Modify: `bjt.py`
- Test: `tests/test_bjt.py`

**Interfaces:**
- Consumes: `BiasInputs`, `OperatingPoint`, `solve_exact`.
- Produces:
  - `@dataclass(frozen=True) class Comparison` with `ic_approx_a: float, vce_approx_a: float, divergence_pct: float, reliable: bool`
  - `compare(inputs: BiasInputs, exact: OperatingPoint) -> Comparison`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bjt.py`:

```python
from bjt import compare


class TestCompare(unittest.TestCase):
    def test_worked_example_values_and_flag(self):
        inputs = validate(EXAMPLE)
        result = compare(inputs, solve_exact(inputs))
        self.assertAlmostEqual(result.ic_approx_a, 1.405263e-3, places=6)
        self.assertAlmostEqual(result.vce_approx_a, 3.990000, places=6)
        self.assertAlmostEqual(result.divergence_pct, 6.1637, places=3)
        self.assertFalse(result.reliable)

    def test_stiff_divider_agrees(self):
        inputs = validate({**EXAMPLE, "r1": "4700", "r2": "1000", "beta": "300"})
        result = compare(inputs, solve_exact(inputs))
        self.assertTrue(result.reliable)
        self.assertLess(result.divergence_pct, 5.0)

    def test_cutoff_gives_zero_approximation(self):
        inputs = validate({**EXAMPLE, "r2": "1000"})
        result = compare(inputs, solve_exact(inputs))
        self.assertEqual(result.ic_approx_a, 0.0)
        self.assertEqual(result.divergence_pct, 0.0)
        self.assertTrue(result.reliable)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_bjt.TestCompare -v`
Expected: `ImportError: cannot import name 'compare' from 'bjt'`.

- [ ] **Step 3: Implement `compare`**

Approximation from the spec (`VB = VCC*R2/(R1+R2)`, `VE = VB - VBE`, `IE = VE/RE`, `IC = IE`, `VCE = VCC - IC*(RC+RE)`). If `VE <= 0`, use `ic_approx_a = 0.0` and `vce_approx_a = vcc_v` so cutoff stays physical. Divergence is `abs(ic_exact - ic_approx) / abs(ic_exact) * 100`, or `0.0` when `ic_exact == 0`; `reliable = divergence_pct <= 5.0`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_bjt -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bjt.py tests/test_bjt.py
git commit -m "feat: add approximate bias cross-check"
```

---

### Task 4: Flask route, template, and stylesheet

**Files:**
- Create: `requirements.txt`
- Create: `app.py`
- Create: `templates/index.html`
- Create: `static/style.css`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `ValidationError`, `validate`, `solve_exact`, `compare`, `OperatingPoint`, `Comparison`.
- Produces: `create_app() -> Flask`; Jinja filters `voltage`, `current`, `power`, `percent`; module-level `app` for `python app.py`.

- [ ] **Step 1: Install Flask into a virtual environment**

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

`requirements.txt` contains one line: `Flask>=3.0,<4`.

- [ ] **Step 2: Write the failing route tests**

Create `tests/test_app.py`:

```python
import unittest

from app import create_app

EXAMPLE = {
    "vcc": "12", "r1": "47000", "r2": "10000",
    "rc": "4700", "re": "1000", "beta": "150", "vbe": "0.7",
}


class TestRoutes(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_get_renders_prefilled_form(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('name="vcc"', body)
        self.assertIn('value="12"', body)
        self.assertIn("Common-Emitter", body)

    def test_valid_post_shows_q_point_with_units(self):
        body = self.client.post("/", data=EXAMPLE).get_data(as_text=True)
        self.assertIn("1.324 mA", body)
        self.assertIn("4.446 V", body)
        self.assertIn("Active", body)
        self.assertIn("6.2%", body)

    def test_invalid_post_keeps_values_and_names_field(self):
        body = self.client.post("/", data={**EXAMPLE, "vcc": "abc"}).get_data(as_text=True)
        self.assertIn("Enter a number for VCC", body)
        self.assertIn('value="abc"', body)

    def test_cutoff_post_shows_zero_currents(self):
        body = self.client.post("/", data={**EXAMPLE, "r2": "1000"}).get_data(as_text=True)
        self.assertIn("Cutoff", body)
        self.assertIn("0.000 \u00b5A", body)
        self.assertIn("0.000 mA", body)
        self.assertIn("12.000 V", body)

    def test_saturation_post_warns(self):
        body = self.client.post("/", data={**EXAMPLE, "rc": "22000"}).get_data(as_text=True)
        self.assertIn("Saturation", body)
        self.assertIn("active-region formulas no longer apply", body)

    def test_extreme_magnitudes_stay_readable(self):
        body = self.client.post("/", data={
            **EXAMPLE, "vcc": "1000", "r1": "1000000000",
            "r2": "100000000", "rc": "1000000000", "re": "100000000",
        }).get_data(as_text=True)
        self.assertNotIn("nan", body.lower())
        self.assertNotIn("inf", body.lower())
        self.assertIn(" V", body)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m unittest tests.test_app -v`
Expected: `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 4: Implement `app.py`, the template, and the stylesheet**

`create_app()` registers `/` for GET and POST. GET renders the worked-example defaults (`12, 47000, 10000, 4700, 1000, 150, 0.7`). POST calls `validate(request.form)`; on `ValidationError` re-renders with `errors` and the submitted `values`. On success calls `solve_exact` then `compare`, and passes `point`, `comparison`, `values`, and `errors=[]`. Warnings are built in `app.py`:

- cutoff: `"Transistor is in cutoff: VBB does not exceed VBE, so no collector current flows."`
- saturation: `"Transistor is in saturation: VCE is below 0.2 V, so the active-region formulas no longer apply."`
- unreliable: `"Approximation differs from the exact solution by more than 5%; the divider is too lightly loaded or beta is too low."`

Filters: `voltage` → `f"{v:.3f} V"`; `current` → `µA` when `abs(a) < 1e-3` else `mA`, 3 dp; `power` → `f"{w*1000:.3f} mW"`; `percent` → `f"{p:.1f}%"`. Template shows the seven labelled inputs, a results table (`IB, IC, IE, VB, VC, VE, VCE, PQ`), a region badge, the cross-check table (`exact IC`, `approx IC`, `exact VCE`, `approx VCE`, divergence), and warning/error lists. `static/style.css` styles the form grid, tables, and three badge colours.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python -m unittest tests.test_app -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app.py templates/index.html static/style.css tests/test_app.py requirements.txt
git commit -m "feat: add Flask UI for BJT bias analysis"
```

---

### Task 5: README, end-to-end demo, and push

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: runnable instructions and a pushed `main`.

- [ ] **Step 1: Rewrite `README.md`**

Sections: what the app does (voltage-divider NPN CE DC bias, exact vs. approximate), requirements, setup (`python -m venv .venv`, `.venv\Scripts\python -m pip install -r requirements.txt`), run (`.venv\Scripts\python app.py` → `http://127.0.0.1:5000`), tests (`.venv\Scripts\python -m unittest discover -s tests -t . -v`), the worked example and its 6.2% divergence, and the scope limits (DC only, no AC/transient/FET).

- [ ] **Step 2: Run the full test suite**

Run: `.venv\Scripts\python -m unittest discover -s tests -t . -v`
Expected: all logic and route tests PASS, zero failures.

- [ ] **Step 3: Run the app and verify it serves**

Start `.venv\Scripts\python app.py` in the background, then:

```powershell
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/).StatusCode
```

Expected: `200`. Stop the server afterwards.

- [ ] **Step 4: Commit and push**

```bash
git add README.md
git commit -m "docs: document BJT bias app usage"
git push origin main
```

- [ ] **Step 5: Report the demo URL and the final `git log --oneline -5`**
