"""Flask UI for the BJT common-emitter DC bias analysis."""

from flask import Flask, render_template, request

from bjt import MODES, ValidationError, analyze

MODE_TITLES = {
    "divider": "Voltage Divider Bias",
    "fixed": "Fixed Bias",
    "emitter": "Emitter Bias",
}

MODE_LINKS = tuple((mode, MODE_TITLES[mode]) for mode in MODES)

DEFAULTS = {
    "divider": {
        "vcc": "12",
        "r1": "47000",
        "r2": "10000",
        "rc": "4700",
        "re": "1000",
        "beta": "150",
        "vbe": "0.7",
    },
    "fixed": {
        "vcc": "12",
        "rb": "470000",
        "rc": "2200",
        "beta": "150",
        "vbe": "0.7",
    },
    "emitter": {
        "vcc": "12",
        "rb": "470000",
        "rc": "2200",
        "re": "1000",
        "beta": "150",
        "vbe": "0.7",
    },
}

FIELDS = {
    "divider": (
        ("vcc", "VCC", "V"),
        ("r1", "R1", "\u03a9"),
        ("r2", "R2", "\u03a9"),
        ("rc", "RC", "\u03a9"),
        ("re", "RE", "\u03a9"),
        ("beta", "beta", ""),
        ("vbe", "VBE", "V"),
    ),
    "fixed": (
        ("vcc", "VCC", "V"),
        ("rb", "RB", "\u03a9"),
        ("rc", "RC", "\u03a9"),
        ("beta", "beta", ""),
        ("vbe", "VBE", "V"),
    ),
    "emitter": (
        ("vcc", "VCC", "V"),
        ("rb", "RB", "\u03a9"),
        ("rc", "RC", "\u03a9"),
        ("re", "RE", "\u03a9"),
        ("beta", "beta", ""),
        ("vbe", "VBE", "V"),
    ),
}


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


def build_warnings(result):
    warnings = []
    if result["region"] == "cutoff":
        warnings.append(
            "Transistor is in cutoff: VBB does not exceed VBE, "
            "so no collector current flows."
        )
    elif result["region"] == "saturation":
        warnings.append(
            "Transistor is in saturation: VCE is below 0.2 V, "
            "so the active-region formulas no longer apply."
        )
    if result.get("reliable") is False:
        warnings.append(
            "Approximation differs from the exact solution by more than 5%; "
            "the divider is too lightly loaded or beta is too low."
        )
    return warnings


def _normalize_mode(mode):
    return mode if mode in MODES else "divider"


def create_app():
    app = Flask(__name__)
    app.jinja_env.filters["voltage"] = format_voltage
    app.jinja_env.filters["current"] = format_current
    app.jinja_env.filters["milliamps"] = format_milliamps
    app.jinja_env.filters["power"] = format_power
    app.jinja_env.filters["percent"] = format_percent

    @app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "GET":
            mode = _normalize_mode(request.args.get("mode", "divider"))
            return render_template(
                "index.html",
                mode=mode,
                mode_title=MODE_TITLES[mode],
                modes=MODE_LINKS,
                values=DEFAULTS[mode],
                fields=FIELDS[mode],
                errors=[],
                result=None,
                comparison=None,
                warnings=[],
            )

        mode = _normalize_mode(request.form.get("mode", "divider"))
        fields = FIELDS[mode]
        values = {key: request.form.get(key, "") for key, _, _ in fields}
        try:
            result = analyze(mode, request.form)
        except ValidationError as exc:
            return render_template(
                "index.html",
                mode=mode,
                mode_title=MODE_TITLES[mode],
                modes=MODE_LINKS,
                values=values,
                fields=fields,
                errors=exc.errors,
                result=None,
                comparison=None,
                warnings=[],
            )

        return render_template(
            "index.html",
            mode=mode,
            mode_title=MODE_TITLES[mode],
            modes=MODE_LINKS,
            values=values,
            fields=fields,
            errors=[],
            result=result,
            comparison=result if mode == "divider" else None,
            warnings=build_warnings(result),
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
