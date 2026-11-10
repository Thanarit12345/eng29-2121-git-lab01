# BJT Common-Emitter DC Bias

A small Flask app that solves the DC operating point of an NPN
common-emitter stage with voltage-divider bias, and cross-checks the
answer with the textbook approximation.

Built for the ENG29 2121 lab.

## What it does

Enter seven parameters — `VCC`, `R1`, `R2`, `RC`, `RE`, `beta`, `VBE` — and
the app returns the Q-point:

| Quantity | Unit |
|----------|------|
| `IB`, `IC`, `IE` | µA / mA |
| `VB`, `VC`, `VE`, `VCE` | V |
| `PQ` (transistor dissipation) | mW |

It also reports the region (**Active**, **Cutoff**, **Saturation**), lists
validation errors instead of failing, and shows an independent
cross-check:

- **Exact** — the base loop solved through the divider's Thévenin
  equivalent: `IB = (VBB − VBE) / (RTH + (1 + β)RE)`.
- **Approximate** — the rule-of-thumb that ignores base current:
  `IE ≈ (VCC·R2/(R1+R2) − VBE) / RE`.

The page shows both `IC` and `VCE` plus the percentage divergence. Above
5% the app warns that the approximation is unreliable — the divider is
too lightly loaded or beta is too low.

## Requirements

- Python 3.12
- Flask 3.x (installed from `requirements.txt`)

## Setup

```powershell
python -m venv .venv
```

Activate the environment for your OS:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate
```

Then install the dependency:

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python -m flask --app app run --debug
```

Open <http://127.0.0.1:5000/> in your browser.

## Test

In another terminal, from the same environment:

```powershell
python -m unittest discover -s tests -v
```

`tests/test_bjt.py` covers validation, the exact solution, region
classification, and the cross-check. `tests/test_app.py` drives the Flask
route with its test client.

## Worked example

`VCC = 12 V`, `R1 = 47 kΩ`, `R2 = 10 kΩ`, `RC = 4.7 kΩ`, `RE = 1 kΩ`,
`beta = 150`, `VBE = 0.7 V`.

| Result | Exact | Approximate |
|--------|-------|-------------|
| `IC` | 1.324 mA | 1.405 mA |
| `VCE` | 4.446 V | 3.990 V |

The exact solution puts the stage in the active region with
`VB = 2.033 V`, `VE = 1.333 V`, `VC = 5.778 V`. The approximation is off by
6.2%, so the app flags it as unreliable — a deliberate teaching case.

## Scope

DC bias only. No AC analysis, gain, frequency response, transient
simulation, circuit editor, or FET support.

## Files

```
app.py                  Flask app factory, route, unit formatting
bjt.py                  Engineering logic (no Flask imports)
templates/index.html    Form and results
static/style.css        Stylesheet
tests/                  unittest suite
```
