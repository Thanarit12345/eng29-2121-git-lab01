# BJT Common-Emitter DC Bias Web App — Design

**Course:** ENG29 2121 · **Date:** 2026-11-10 · **Status:** awaiting approval

## Intent

A small Flask web app that solves the DC operating point (Q-point) of an
NPN common-emitter amplifier with voltage-divider bias, for a short lab.
The student enters seven parameters, sees the Q-point with units, gets
input validation and region warnings, and can compare the exact result
against the textbook approximation so they can see when the rule of
thumb stops holding.

## Goals

- One page: parameter form in, Q-point out, no navigation.
- Engineering logic fully separate from Flask routes, templates, and CSS.
- Every output carries a unit.
- Invalid input produces a clear message, never a stack trace.
- Cutoff, saturation, and active region are reported explicitly.
- The independent calculation is visible on screen next to the exact one.

## Non-goals / anti-goals

- No AC analysis, gain, frequency response, or transient simulation.
- No circuit editor, schematic drawing, or component database.
- No FET, op-amp, or other topologies.
- No database, login, JavaScript framework, or REST API.
- Failure looks like: a single monolithic `app.py` that computes inside
  the route handler, or an app that renders a plausible answer for
  physically impossible input.

## Constraints

- Python 3.12.7, Flask (must be installed into a `.venv`; it is not
  currently available system-wide).
- Tests use stdlib `unittest`, matching the existing `test_electrical.py`.
- Existing `electrical.py` / `test_electrical.py` are left untouched.
- `README.md` currently describes a logic-gate simulator and is stale;
  it will be rewritten for this app.

## Approaches considered

1. **Exact vs. approximate divider — chosen.** Primary solution via the
   Thévenin equivalent; cross-check via the textbook approximation that
   ignores base current. Both shown with a % difference and a warning
   above 5%.
2. **Exact vs. numerical nodal solve.** Stronger algebraic independence,
   but ~60 extra lines of iteration that a short lab cannot justify.
3. **Formula only, independence in tests.** Smallest, but the required
   comparison would not be visible to the user.

## The calculation

Circuit: `VCC` → `R1` → base node → `R2` → ground; `RC` from `VCC` to
collector; `RE` from emitter to ground.

Exact (Thévenin):

```
VBB = VCC * R2 / (R1 + R2)
RTH = R1 * R2 / (R1 + R2)
IB  = (VBB - VBE) / (RTH + (1 + beta) * RE)
IC  = beta * IB
IE  = (1 + beta) * IB
VE  = IE * RE
VB  = VBE + VE
VC  = VCC - IC * RC
VCE = VC - VE
PQ  = VCE * IC
```

Approximate (independent cross-check, ignores `IB`):

```
VB  = VCC * R2 / (R1 + R2)
VE  = VB - VBE
IE  = VE / RE
IC  = IE
VCE = VCC - IC * (RC + RE)
```

Divergence = `|IC_exact - IC_approx| / IC_exact * 100`. Above 5% the app
says the approximation is unreliable (low beta or lightly loaded
divider).

### Regions

| Region | Condition | Reported result |
|--------|-----------|-----------------|
| Cutoff | `VBB <= VBE` | `IB = IC = IE = 0`, `VCE = VCC`, note that the transistor is off |
| Saturation | `VCE < 0.2 V` | values shown, warning that the active-region formula no longer applies |
| Active | otherwise | values shown, no warning |

### Worked example (used as the unit-test fixture)

`VCC=12, R1=47k, R2=10k, RC=4.7k, RE=1k, beta=150, VBE=0.7`

Exact: `IB=8.825 µA, IC=1.324 mA, IE=1.333 mA, VB=2.033 V, VC=5.778 V,
VE=1.333 V, VCE=4.446 V`. Approximate: `IC=1.405 mA, VCE=3.99 V`.
Divergence ≈ 6.2% → unreliable-approximation warning. Active region.

## Validation

| Rule | Message |
|------|---------|
| All seven fields present and numeric | "Enter a number for …" |
| `VCC > 0` | "VCC must be greater than 0 V" |
| `R1, R2, RC, RE > 0` | "<name> must be greater than 0 Ω" |
| `beta >= 1` | "beta must be at least 1" |
| `0 < VBE < VCC` | "VBE must be between 0 V and VCC" |

Cutoff is a physical outcome, not a validation error.

## File layout

```
app.py                  Flask app factory + one route (GET/POST "/")
bjt.py                  Pure engineering logic: validation, exact,
                        approximate, region, comparison. No Flask imports.
templates/index.html    Form + results, server-rendered
static/style.css        Small stylesheet
tests/test_bjt.py       Unit tests for engineering logic
tests/test_app.py       Route tests via Flask test client
requirements.txt        Flask
README.md               Rewritten: what it does, how to run, how to test
```

## Display

- Single page, form pre-filled with the worked example.
- Results table: `IB, IC, IE` in mA (µA for IB when < 1 mA), `VB, VC,
  VE, VCE` in V, `PQ` in mW, 3 decimals.
- Region shown as a labelled badge (Active / Cutoff / Saturation).
- Cross-check table: exact vs. approximate `IC`, `VCE`, and the
  divergence percentage, plus the reliability note.
- Validation errors listed above the form; the entered values are kept.

## Decisions left to the builder

- Exact CSS values and page typography.
- Whether `IB` is shown in µA or mA (µA below 1 mA is the intent).
- Test helper structure and how many cases per validation rule.

## Delivery

Local run: `.venv\Scripts\python app.py` → `http://127.0.0.1:5000`.
Commits on `main` in logical steps (design, logic + tests, routes +
templates, README), pushed to `origin/main` today.
