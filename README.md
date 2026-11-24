# BJT CE Bias & Amplifier Simulator

ENG29 2121 Lab 3/CE extension: a Flask app for analytical NPN DC bias analysis and a minimal reference common-emitter amplifier simulation backed by real ngspice.

## Lab 3 analytical DC bias modes

The app preserves all three Lab 3 analytical modes:

| Mode | Inputs | Notes |
|------|--------|-------|
| Voltage Divider Bias | `VCC, R1, R2, RC, RE, beta, VBE` | Exact Thévenin solution + textbook approximation cross-check |
| Fixed Bias | `VCC, RB, RC, beta, VBE` | `IB=(VCC-VBE)/RB`, `IC=beta*IB`, `VCE=VCC-IC*RC` |
| Emitter Bias | `VCC, RB, RC, RE, beta, VBE` | `IB=(VCC-VBE)/(RB+(1+beta)*RE)` |

Outputs include `IB, IC, IE, VB, VC, VE, VCE, PQ`, region (`Active/Cutoff/Saturation`), and validation errors with units.

## CE Amplifier Simulator v1 (ngspice)

A separate reference panel runs real ngspice on a fixed circuit:

- `VCC=12 V`, `R1=100 kΩ`, `R2=22 kΩ`, `RC=2.2 kΩ`, `RE=1 kΩ`, `RL=10 kΩ`
- `Cin=Cout=10 µF`, 2N3904 model, `27 °C`
- User inputs: amplitude (mV peak) and frequency (Hz)

Simulations:
- **DC `.op`**: SPICE node voltages/currents vs analytical reference (`solve_exact`, `beta=300`, `VBE=0.7 V`). SPICE and analytical values may differ because models/assumptions differ.
- **AC `.ac`**: gain magnitude (V/V, dB) and phase (deg), -3 dB points when found in sweep; otherwise `not determined in sweep range`.
- **Transient `.tran`**: Vin/Vout waveforms, measured peak amplitude, gain, and phase/inversion.

No traces, gains, or cutoff values are hard-coded. ngspice errors are shown directly in the UI.

## ngspice setup

The app looks for ngspice in this order:

1. `NGSPICE_EXE` environment variable
2. `ngspice_con` / `ngspice` on PATH
3. `.tools/Spice64/bin/ngspice_con.exe` (local install, gitignored)

Model file: `spice/models/2N3904.lib` (documented fallback). Override with `SPICE_MODEL`.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```powershell
.venv\Scripts\python.exe -m flask --app app run --debug
```

Open <http://127.0.0.1:5000/>.

## Test

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

## Scope

Analytical DC bias modes plus one fixed reference CE ngspice simulation. No circuit editor, no FET, no arbitrary netlist upload.
