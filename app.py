"""Flask UI for BJT DC bias analysis and CE amplifier simulation."""

import math
from dataclasses import asdict

from flask import Flask, render_template, request

from bjt import (
    FixedBiasInputs,
    EmitterBiasInputs,
    ValidationError,
    compare,
    solve_emitter_bias,
    solve_exact,
    solve_fixed_bias,
    validate,
)
from ce_spice import SpiceParseError, SpiceRunError, SpiceUnavailable, simulate_reference
from charts import ac_chart_svg, tran_chart_svg

MODES = {
    "divider": {
        "label": "Voltage Divider Bias",
        "title": "Voltage Divider Bias",
        "lede": "DC operating point, operating region, and independent cross-check for the NPN common-emitter stage.",
        "circuit": "bjt-circuit.svg",
        "circuit_alt": "NPN BJT common-emitter amplifier with voltage-divider bias: R1 and R2 set the base voltage, RC is the collector load, and RE is the emitter resistor.",
        "circuit_caption": "Voltage-divider biased NPN common-emitter stage.",
        "defaults": {
            "vcc": "12", "r1": "47000", "r2": "10000", "rc": "4700", "re": "1000", "beta": "150", "vbe": "0.7",
        },
        "fields": (
            ("vcc", "VCC", "V"), ("r1", "R1", "\u03a9"), ("r2", "R2", "\u03a9"),
            ("rc", "RC", "\u03a9"), ("re", "RE", "\u03a9"), ("beta", "beta", ""), ("vbe", "VBE", "V"),
        ),
    },
    "fixed": {
        "label": "Fixed Bias",
        "title": "Fixed Bias",
        "lede": "DC operating point for an NPN fixed-bias stage where RB connects VCC to the base.",
        "circuit": "bjt-fixed-bias.svg",
        "circuit_alt": "NPN BJT fixed-bias amplifier: RB connects VCC to base, RC connects VCC to collector, and emitter is grounded.",
        "circuit_caption": "Fixed-bias NPN common-emitter stage.",
        "defaults": {
            "vcc": "12", "rb": "470000", "rc": "2200", "beta": "150", "vbe": "0.7",
        },
        "fields": (
            ("vcc", "VCC", "V"), ("rb", "RB", "\u03a9"), ("rc", "RC", "\u03a9"),
            ("beta", "beta", ""), ("vbe", "VBE", "V"),
        ),
    },
    "emitter": {
        "label": "Emitter Bias",
        "title": "Emitter Bias",
        "lede": "DC operating point for an NPN emitter-stabilized bias stage with RB from VCC to base and RE from emitter to ground.",
        "circuit": "bjt-emitter-bias.svg",
        "circuit_alt": "NPN BJT emitter-bias amplifier: RB connects VCC to base, RC connects VCC to collector, and RE connects emitter to ground.",
        "circuit_caption": "Emitter-stabilized NPN common-emitter stage.",
        "defaults": {
            "vcc": "12", "rb": "470000", "rc": "2200", "re": "1000", "beta": "150", "vbe": "0.7",
        },
        "fields": (
            ("vcc", "VCC", "V"), ("rb", "RB", "\u03a9"), ("rc", "RC", "\u03a9"),
            ("re", "RE", "\u03a9"), ("beta", "beta", ""), ("vbe", "VBE", "V"),
        ),
    },
}

DEFAULTS = MODES["divider"]["defaults"]
FIELDS = MODES["divider"]["fields"]

SIM_DEFAULTS = {"amplitude_mv": "10", "frequency_hz": "1000"}


def format_voltage(value):
    return f"{value:.3f} V"


def format_current(value):
    if abs(value) < 1e-3:
        return f"{value * 1e6:.3f} \u00b5A"
    return f"{value * 1e3:.3f} mA"


def format_milliamps(value):
    return f"{value * 1e3:.3f} mA"


def format_power(value):
    return f"{value * 1e3:.3f} mW"


def format_percent(value):
    return f"{value:.1f}%"


def _parse_mode_fields(raw, fields):
    errors = []
    values = {}
    for key, label, _ in fields:
        text = str(raw.get(key, "")).strip()
        try:
            value = float(text)
        except ValueError:
            errors.append(f"Enter a number for {label}")
            values[key] = None
            continue
        if not value == value or value in (float("inf"), float("-inf")):
            errors.append(f"Enter a finite number for {label}")
            values[key] = None
            continue
        values[key] = value
    return values, errors


def validate_mode(mode, raw):
    config = MODES[mode]
    values, errors = _parse_mode_fields(raw, config["fields"])

    if values.get("vcc") is not None and values["vcc"] <= 0:
        errors.append("VCC must be greater than 0 V")
    for key, label, _ in config["fields"]:
        if key in {"r1", "r2", "rc", "re", "rb"} and values.get(key) is not None and values[key] <= 0:
            errors.append(f"{label} must be greater than 0 \u03a9")
    if values.get("beta") is not None and values["beta"] < 1:
        errors.append("beta must be at least 1")
    if values.get("vcc") is not None and values.get("vbe") is not None and not 0 < values["vbe"] < values["vcc"]:
        errors.append("VBE must be between 0 V and VCC")
    if errors:
        raise ValidationError(errors)

    if mode == "divider":
        return validate(raw)
    if mode == "fixed":
        return FixedBiasInputs(values["vcc"], values["rb"], values["rc"], values["beta"], values["vbe"])
    return EmitterBiasInputs(values["vcc"], values["rb"], values["rc"], values["re"], values["beta"], values["vbe"])


def solve_mode(mode, inputs):
    if mode == "divider":
        point = solve_exact(inputs)
        comparison = compare(inputs, point)
        return point, comparison
    if mode == "fixed":
        return solve_fixed_bias(inputs), None
    return solve_emitter_bias(inputs), None


def build_warnings(point, comparison):
    warnings = []
    if point.region == "cutoff":
        warnings.append(
            "Transistor is in cutoff: VBB does not exceed VBE, "
            "so no collector current flows."
        )
    elif point.region == "saturation":
        warnings.append(
            "Transistor is in saturation: VCE is below 0.2 V, "
            "so the active-region formulas no longer apply."
        )
    if comparison is not None and not comparison.reliable:
        warnings.append(
            "Approximation differs from the exact solution by more than 5%; "
            "the divider is too lightly loaded or beta is too low."
        )
    return warnings


def create_app():
    app = Flask(__name__)
    app.jinja_env.filters["voltage"] = format_voltage
    app.jinja_env.filters["current"] = format_current
    app.jinja_env.filters["milliamps"] = format_milliamps
    app.jinja_env.filters["power"] = format_power
    app.jinja_env.filters["percent"] = format_percent

    def _sim_context(sim_values=None, sim_result=None, sim_error=None, sim_errors=None):
        sim_ac_svg = ""
        sim_tran_svg = ""
        if sim_result:
            sim_ac_svg = ac_chart_svg(sim_result["spice"]["ac"]["rows"])
            sim_tran_svg = tran_chart_svg(sim_result["spice"]["tran"]["rows"])
        return {
            "sim_values": sim_values or SIM_DEFAULTS,
            "sim_result": sim_result,
            "sim_error": sim_error,
            "sim_errors": sim_errors or [],
            "sim_ac_svg": sim_ac_svg,
            "sim_tran_svg": sim_tran_svg,
        }

    def _page_context(mode, config, values, errors, point, comparison, warnings, **sim):
        ctx = {
            "mode": mode,
            "modes": MODES,
            "config": config,
            "values": values,
            "fields": config["fields"],
            "errors": errors,
            "point": point,
            "comparison": comparison,
            "warnings": warnings,
        }
        ctx.update(_sim_context(**sim))
        return ctx

    @app.route("/", methods=["GET", "POST"])
    def index():
        mode = request.values.get("mode", "divider")
        if mode not in MODES:
            mode = "divider"
        config = MODES[mode]

        if request.method == "GET":
            return render_template("index.html", **_page_context(
                mode, config, config["defaults"], [], None, None, [],
            ))

        values = {key: request.form.get(key, "") for key, _, _ in config["fields"]}
        try:
            inputs = validate_mode(mode, request.form)
            point, comparison = solve_mode(mode, inputs)
        except ValidationError as exc:
            return render_template("index.html", **_page_context(
                mode, config, values, exc.errors, None, None, [],
            ))

        return render_template("index.html", **_page_context(
            mode, config, values, [], point, comparison, build_warnings(point, comparison),
        ))

    @app.route("/simulate", methods=["POST"])
    def simulate():
        mode = request.values.get("mode", "divider")
        if mode not in MODES:
            mode = "divider"
        config = MODES[mode]
        sim_values = {
            "amplitude_mv": request.form.get("amplitude_mv", SIM_DEFAULTS["amplitude_mv"]),
            "frequency_hz": request.form.get("frequency_hz", SIM_DEFAULTS["frequency_hz"]),
        }
        sim_errors = []
        amplitude_v = None
        frequency_hz = None
        try:
            amplitude_v = float(str(sim_values["amplitude_mv"]).strip())
        except ValueError:
            sim_errors.append("Enter a number for amplitude")
        try:
            frequency_hz = float(str(sim_values["frequency_hz"]).strip())
        except ValueError:
            sim_errors.append("Enter a number for frequency")
        if amplitude_v is not None and (not math.isfinite(amplitude_v) or amplitude_v <= 0):
            sim_errors.append("Amplitude must be greater than 0 mV")
        if frequency_hz is not None and (not math.isfinite(frequency_hz) or frequency_hz <= 0):
            sim_errors.append("Frequency must be greater than 0 Hz")
        if sim_errors:
            return render_template("index.html", **_page_context(
                mode, config, config["defaults"], [], None, None, [],
                sim_values=sim_values, sim_errors=sim_errors,
            ))

        try:
            sim_result = simulate_reference(amplitude_v / 1000.0, frequency_hz)
        except ValidationError as exc:
            return render_template("index.html", **_page_context(
                mode, config, config["defaults"], [], None, None, [],
                sim_values=sim_values, sim_errors=exc.errors,
            ))
        except (SpiceUnavailable, SpiceRunError, SpiceParseError) as exc:
            return render_template("index.html", **_page_context(
                mode, config, config["defaults"], [], None, None, [],
                sim_values=sim_values, sim_error=str(exc),
            ))

        return render_template("index.html", **_page_context(
            mode, config, config["defaults"], [], None, None, [],
            sim_values=sim_values, sim_result=sim_result,
        ))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
