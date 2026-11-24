"""ngspice-backed reference CE amplifier simulation.

No Flask imports. All SPICE execution, parsing, and error types live here.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

from bjt import BiasInputs, ValidationError, solve_exact

REFERENCE = {
    "vcc_v": 12.0,
    "r1_ohm": 100_000.0,
    "r2_ohm": 22_000.0,
    "rc_ohm": 2_200.0,
    "re_ohm": 1_000.0,
    "rl_ohm": 10_000.0,
    "cin_f": 10e-6,
    "cout_f": 10e-6,
    "beta": 300.0,
    "vbe_v": 0.7,
    "ac_start_hz": 0.1,
    "ac_stop_hz": 100e6,
    "ac_points_per_decade": 50,
}


class SpiceUnavailable(RuntimeError):
    pass


class SpiceRunError(RuntimeError):
    pass


class SpiceParseError(RuntimeError):
    pass


def _model_path(model_path=None) -> Path:
    if model_path:
        return Path(model_path).resolve()
    env = os.environ.get("SPICE_MODEL")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent / "spice" / "models" / "2N3904.lib"


def build_reference_netlist(amplitude_v_peak: float, frequency_hz: float, model_path=None) -> str:
    model = _model_path(model_path)
    return "\n".join([
        "Reference CE voltage-divider amplifier",
        f".include \"{model.as_posix()}\"",
        "VCC vcc 0 12",
        "R1 vcc base 100k",
        "R2 base 0 22k",
        "RC vcc collector 2.2k",
        "RE emitter 0 1k",
        "CIN source base 10u",
        "COUT collector out 10u",
        "RL out 0 10k",
        f"VIN source 0 DC 0 AC 1 SIN(0 {amplitude_v_peak} {frequency_hz})",
        "Q1 collector base emitter QREF",
        ".control",
        "set wr_singlescale",
        "set wr_vecnames",
        "op",
        "print v(base) v(emitter) v(collector) v(out)",
        "ac dec 50 0.1 100meg",
        "wrdata ac.dat frequency vdb(out) vp(out)",
        f"tran {max(frequency_hz and (1 / frequency_hz / 1000), 1e-6)} {max(5 / frequency_hz, 1e-3)}",
        "wrdata tran.dat time v(source) v(out)",
        ".endc",
        ".end",
        "",
    ])


def parse_op_log(text: str) -> dict[str, float]:
    values = {}
    for match in re.finditer(r"v\(([^)]+)\)\s*=\s*([+-]?\d+(?:\.\d+)?(?:e[+-]?\d+)?)", text, re.IGNORECASE):
        values[match.group(1).lower()] = float(match.group(2))
    required = {"base", "emitter", "collector"}
    missing = [name for name in required if name not in values]
    if missing:
        raise SpiceParseError(f"ngspice .op output missing node(s): {', '.join(missing)}")
    return values


def parse_wrdata(path: Path, columns: list[str]) -> list[dict[str, float]]:
    path = Path(path)
    if not path.exists():
        raise SpiceParseError(f"ngspice output file not found: {path.name}")
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    if not lines:
        raise SpiceParseError(f"ngspice output file is empty: {path.name}")

    data_lines = lines
    header = None
    if re.search(r"[A-Za-z_]", lines[0]):
        header = lines[0].split()
        data_lines = lines[1:]

    rows = []
    for line in data_lines:
        parts = line.split()
        try:
            nums = [float(part) for part in parts]
        except ValueError as exc:
            raise SpiceParseError(f"Malformed numeric data in {path.name}") from exc
        if not nums:
            continue
        if header and len(header) == len(nums):
            by_name = {}
            for name, value in zip(header, nums):
                key = name.lower()
                by_name.setdefault(key, value)
            row = {}
            for col in columns:
                key = col.lower()
                if key in by_name:
                    row[col] = by_name[key]
                else:
                    matches = [v for k, v in by_name.items() if k.endswith(key) or key.endswith(k) or key in k or k in key]
                    if matches:
                        row[col] = matches[0]
            if len(row) == len(columns):
                rows.append(row)
                continue
        # Fallback: wrdata often repeats scale; take last N columns.
        if len(nums) < len(columns):
            raise SpiceParseError(f"Not enough columns in {path.name}")
        values = nums[-len(columns):]
        rows.append(dict(zip(columns, values)))

    if not rows:
        raise SpiceParseError(f"No data rows parsed from {path.name}")
    return rows


def analyze_ac(rows: list[dict[str, float]], selected_frequency_hz: float) -> dict:
    if not rows:
        raise SpiceParseError("AC data is empty")
    def key(row):
        f = row["frequency_hz"]
        return abs(math.log10(f / selected_frequency_hz)) if f > 0 and selected_frequency_hz > 0 else float("inf")
    selected = min(rows, key=key)
    gain_db = float(selected["vdb_out"])
    gain_vv = 10 ** (gain_db / 20.0)
    phase_deg = float(selected["vp_out"])
    peak_db = max(float(row["vdb_out"]) for row in rows)
    threshold = peak_db - 3.0
    peak_idx = max(range(len(rows)), key=lambda i: float(rows[i]["vdb_out"]))
    low = None
    for i in range(peak_idx - 1, -1, -1):
        if float(rows[i]["vdb_out"]) < threshold:
            low = float(rows[i]["frequency_hz"])
            break
    high = None
    for i in range(peak_idx + 1, len(rows)):
        if float(rows[i]["vdb_out"]) < threshold:
            high = float(rows[i]["frequency_hz"])
            break
    return {
        "selected_frequency_hz": float(selected["frequency_hz"]),
        "gain_db": gain_db,
        "gain_vv": gain_vv,
        "phase_deg": phase_deg,
        "peak_gain_db": peak_db,
        "low_cutoff_hz": low,
        "high_cutoff_hz": high,
        "rows": rows,
    }


def _fit_sine(samples, frequency_hz):
    n = len(samples)
    if n == 0 or frequency_hz <= 0:
        return 0.0, 0.0
    a = 0.0
    b = 0.0
    for t, y in samples:
        angle = 2.0 * math.pi * frequency_hz * t
        a += y * math.cos(angle)
        b += y * math.sin(angle)
    a = 2.0 * a / n
    b = 2.0 * b / n
    amp = math.hypot(a, b)
    phase = math.degrees(math.atan2(b, a))
    return amp, phase


def _wrap_phase(deg):
    wrapped = (deg + 180.0) % 360.0 - 180.0
    if wrapped <= -180.0:
        wrapped += 360.0
    return wrapped


def analyze_tran(rows: list[dict[str, float]], frequency_hz: float) -> dict:
    if len(rows) < 10:
        raise SpiceParseError("Transient data is too short")
    start = int(len(rows) * 0.6)
    window = rows[start:] if start < len(rows) else rows
    vin_samples = [(float(r["time_s"]), float(r["v_source"])) for r in window]
    vout_samples = [(float(r["time_s"]), float(r["v_out"])) for r in window]
    vin_amp, vin_phase = _fit_sine(vin_samples, frequency_hz)
    vout_amp, vout_phase = _fit_sine(vout_samples, frequency_hz)
    gain_vv = (vout_amp / vin_amp) if vin_amp else 0.0
    phase_diff = _wrap_phase(vout_phase - vin_phase)
    return {
        "vin_peak_v": vin_amp,
        "vout_peak_v": vout_amp,
        "vin_pp_mv": vin_amp * 2.0 * 1000.0,
        "vout_pp_mv": vout_amp * 2.0 * 1000.0,
        "gain_vv": gain_vv,
        "phase_deg": phase_diff,
        "phase_inverted": abs(abs(phase_diff) - 180.0) <= 30.0,
        "rows": rows,
    }


def resolve_ngspice(ngspice_exe=None) -> Path:
    candidates = []
    if ngspice_exe:
        candidates.append(Path(ngspice_exe))
    env = os.environ.get("NGSPICE_EXE")
    if env:
        candidates.append(Path(env))
    for name in ("ngspice_con", "ngspice_con.exe", "ngspice", "ngspice.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    candidates.append(Path(__file__).resolve().parent / ".tools" / "Spice64" / "bin" / "ngspice_con.exe")
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise SpiceUnavailable(
        "ngspice executable not found. Install ngspice or set NGSPICE_EXE to the ngspice_con/ngspice binary."
    )


def run_ngspice(netlist: str, timeout_s: float = 30.0, ngspice_exe=None) -> dict:
    exe = resolve_ngspice(ngspice_exe)
    with tempfile.TemporaryDirectory(prefix="ce-spice-") as tmp:
        tmp_path = Path(tmp)
        cir = tmp_path / "input.cir"
        cir.write_text(netlist, encoding="utf-8")
        try:
            proc = subprocess.run(
                [str(exe), "-b", str(cir)],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
                timeout=timeout_s,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            raise SpiceRunError(f"ngspice timed out after {timeout_s:.0f} s") from exc
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        if proc.returncode != 0:
            tail = "\n".join(output.strip().splitlines()[-20:])
            raise SpiceRunError(f"ngspice exited with code {proc.returncode}:\n{tail}")

        op = parse_op_log(output)
        ac_rows = parse_wrdata(tmp_path / "ac.dat", ["frequency", "vdb(out)", "vp(out)"])
        tran_rows = parse_wrdata(tmp_path / "tran.dat", ["time", "v(source)", "v(out)"])
        ac = [{
            "frequency_hz": r["frequency"],
            "vdb_out": r["vdb(out)"],
            "vp_out": math.degrees(r["vp(out)"]),
        } for r in ac_rows]
        tran = [{"time_s": r["time"], "v_source": r["v(source)"], "v_out": r["v(out)"]} for r in tran_rows]
        return {"op": op, "ac_rows": ac, "tran_rows": tran, "output": output}


def simulate_reference(amplitude_v_peak: float, frequency_hz: float, model_path=None, ngspice_exe=None) -> dict:
    errors = []
    if not math.isfinite(amplitude_v_peak) or amplitude_v_peak <= 0:
        errors.append("Amplitude must be greater than 0 V peak")
    if not math.isfinite(frequency_hz) or frequency_hz <= 0:
        errors.append("Frequency must be greater than 0 Hz")
    if not errors and (frequency_hz < REFERENCE["ac_start_hz"] or frequency_hz > REFERENCE["ac_stop_hz"]):
        errors.append("Frequency must be within the AC sweep range (0.1 Hz to 100 MHz)")
    if errors:
        raise ValidationError(errors)

    netlist = build_reference_netlist(amplitude_v_peak, frequency_hz, model_path)
    raw = run_ngspice(netlist, ngspice_exe=ngspice_exe)
    op = raw["op"]

    vb = op["base"]
    ve = op["emitter"]
    vc = op["collector"]
    vout = op.get("out", 0.0)
    vce = vc - ve
    ic = (REFERENCE["vcc_v"] - vc) / REFERENCE["rc_ohm"]
    ie = ve / REFERENCE["re_ohm"]
    ib = ie - ic
    beta_eff = (ic / ib) if abs(ib) > 1e-18 else float("nan")
    dc_region = "cutoff" if vce <= 0.05 and ic <= 1e-9 else "saturation" if vce < 0.2 else "active"

    ac = analyze_ac(raw["ac_rows"], frequency_hz)
    tran = analyze_tran(raw["tran_rows"], frequency_hz)

    analytical = solve_exact(BiasInputs(
        vcc_v=REFERENCE["vcc_v"], r1_ohm=REFERENCE["r1_ohm"], r2_ohm=REFERENCE["r2_ohm"],
        rc_ohm=REFERENCE["rc_ohm"], re_ohm=REFERENCE["re_ohm"], beta=REFERENCE["beta"], vbe_v=REFERENCE["vbe_v"],
    ))

    return {
        "meta": {
            "amplitude_v_peak": amplitude_v_peak,
            "amplitude_mv_peak": amplitude_v_peak * 1000.0,
            "frequency_hz": frequency_hz,
            "model_path": str(_model_path(model_path)),
            "ngspice_exe": str(resolve_ngspice(ngspice_exe)),
            "reference": REFERENCE,
        },
        "analytical": {
            "vb_v": analytical.vb_v, "ve_v": analytical.ve_v, "vc_v": analytical.vc_v,
            "vce_v": analytical.vce_v, "ib_a": analytical.ib_a, "ic_a": analytical.ic_a,
            "ie_a": analytical.ie_a, "region": analytical.region,
            "assumptions": f"Analytical reference: solve_exact() with beta={REFERENCE['beta']:.0f}, VBE={REFERENCE['vbe_v']} V, fixed reference fixture.",
        },
        "spice": {
            "dc": {
                "vb_v": vb, "ve_v": ve, "vc_v": vc, "vce_v": vce, "vout_v": vout,
                "ib_a": ib, "ic_a": ic, "ie_a": ie, "beta_eff": beta_eff, "region": dc_region,
            },
            "ac": ac,
            "tran": tran,
        },
        "warnings": [],
    }
