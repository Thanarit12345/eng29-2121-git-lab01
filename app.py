"""Flask UI for the BJT common-emitter DC bias analysis."""

from flask import Flask, render_template, request

from bjt import ValidationError, compare, solve_exact, validate

DEFAULTS = {
    "vcc": "12",
    "r1": "47000",
    "r2": "10000",
    "rc": "4700",
    "re": "1000",
    "beta": "150",
    "vbe": "0.7",
}

FIELDS = (
    ("vcc", "VCC", "V"),
    ("r1", "R1", "\u03a9"),
    ("r2", "R2", "\u03a9"),
    ("rc", "RC", "\u03a9"),
    ("re", "RE", "\u03a9"),
    ("beta", "beta", ""),
    ("vbe", "VBE", "V"),
)


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
    if not comparison.reliable:
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

    @app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "GET":
            return render_template(
                "index.html",
                values=DEFAULTS,
                fields=FIELDS,
                errors=[],
                point=None,
                comparison=None,
                warnings=[],
            )

        values = {key: request.form.get(key, "") for key, _, _ in FIELDS}
        try:
            inputs = validate(request.form)
        except ValidationError as exc:
            return render_template(
                "index.html",
                values=values,
                fields=FIELDS,
                errors=exc.errors,
                point=None,
                comparison=None,
                warnings=[],
            )

        point = solve_exact(inputs)
        comparison = compare(inputs, point)
        return render_template(
            "index.html",
            values=values,
            fields=FIELDS,
            errors=[],
            point=point,
            comparison=comparison,
            warnings=build_warnings(point, comparison),
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
