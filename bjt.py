"""DC bias analysis for a voltage-divider NPN common-emitter stage.

Pure engineering logic: no Flask, no formatting, no HTML.
"""

from dataclasses import dataclass
from typing import Mapping

import math

FIELDS = {
    "vcc": "VCC",
    "r1": "R1",
    "r2": "R2",
    "rc": "RC",
    "re": "RE",
    "beta": "beta",
    "vbe": "VBE",
}

RESISTOR_FIELDS = (("r1", "R1"), ("r2", "R2"), ("rc", "RC"), ("re", "RE"))

MODE_DIVIDER = "divider"
MODE_FIXED = "fixed"
MODE_EMITTER = "emitter"

MODES = (MODE_DIVIDER, MODE_FIXED, MODE_EMITTER)

MODE_FIELDS = {
    MODE_DIVIDER: ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"),
    MODE_FIXED: ("vcc", "rb", "rc", "beta", "vbe"),
    MODE_EMITTER: ("vcc", "rb", "rc", "re", "beta", "vbe"),
}

MODE_RESISTOR_FIELDS = {
    MODE_DIVIDER: RESISTOR_FIELDS,
    MODE_FIXED: (("rb", "RB"), ("rc", "RC")),
    MODE_EMITTER: (("rb", "RB"), ("rc", "RC"), ("re", "RE")),
}

FIELD_LABELS = {
    "vcc": "VCC",
    "r1": "R1",
    "r2": "R2",
    "rc": "RC",
    "re": "RE",
    "rb": "RB",
    "beta": "beta",
    "vbe": "VBE",
}

NON_FINITE_MESSAGE = "Inputs are too large to produce a finite result"


class ValidationError(ValueError):
    """Raised when form input cannot describe a physical bias circuit."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class BiasInputs:
    vcc_v: float
    r1_ohm: float
    r2_ohm: float
    rc_ohm: float
    re_ohm: float
    beta: float
    vbe_v: float


@dataclass(frozen=True)
class FixedBiasInputs:
    vcc_v: float
    rb_ohm: float
    rc_ohm: float
    beta: float
    vbe_v: float


@dataclass(frozen=True)
class EmitterBiasInputs:
    vcc_v: float
    rb_ohm: float
    rc_ohm: float
    re_ohm: float
    beta: float
    vbe_v: float


@dataclass(frozen=True)
class OperatingPoint:
    vbb_v: float
    rth_ohm: float
    ib_a: float
    ic_a: float
    ie_a: float
    vb_v: float
    vc_v: float
    ve_v: float
    vce_v: float
    pq_w: float
    region: str


@dataclass(frozen=True)
class Comparison:
    ic_approx_a: float
    vce_approx_a: float
    divergence_pct: float
    reliable: bool


def validate(raw: Mapping[str, str]) -> BiasInputs:
    """Parse and validate raw form strings, collecting every problem."""
    errors = []
    values = {}

    for key, label in FIELDS.items():
        text = str(raw.get(key, "")).strip()
        try:
            value = float(text)
        except ValueError:
            errors.append(f"Enter a number for {label}")
            values[key] = None
            continue
        if not math.isfinite(value):
            errors.append(f"Enter a finite number for {label}")
            values[key] = None
            continue
        values[key] = value

    if values["vcc"] is not None and values["vcc"] <= 0:
        errors.append("VCC must be greater than 0 V")

    for key, label in RESISTOR_FIELDS:
        if values[key] is not None and values[key] <= 0:
            errors.append(f"{label} must be greater than 0 \u03a9")

    if values["beta"] is not None and values["beta"] < 1:
        errors.append("beta must be at least 1")

    if (
        values["vcc"] is not None
        and values["vbe"] is not None
        and not 0 < values["vbe"] < values["vcc"]
    ):
        errors.append("VBE must be between 0 V and VCC")

    if errors:
        raise ValidationError(errors)

    return BiasInputs(
        vcc_v=values["vcc"],
        r1_ohm=values["r1"],
        r2_ohm=values["r2"],
        rc_ohm=values["rc"],
        re_ohm=values["re"],
        beta=values["beta"],
        vbe_v=values["vbe"],
    )


def _checked(point: OperatingPoint) -> OperatingPoint:
    values = (
        point.vbb_v, point.rth_ohm, point.ib_a, point.ic_a, point.ie_a,
        point.vb_v, point.vc_v, point.ve_v, point.vce_v, point.pq_w,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValidationError([NON_FINITE_MESSAGE])
    return point


def solve_exact(inputs: BiasInputs) -> OperatingPoint:
    """Solve the base loop through the divider's Thevenin equivalent."""
    vbb_v = inputs.vcc_v * inputs.r2_ohm / (inputs.r1_ohm + inputs.r2_ohm)
    rth_ohm = inputs.r1_ohm * inputs.r2_ohm / (inputs.r1_ohm + inputs.r2_ohm)

    if vbb_v <= inputs.vbe_v:
        return _checked(OperatingPoint(
            vbb_v=vbb_v,
            rth_ohm=rth_ohm,
            ib_a=0.0,
            ic_a=0.0,
            ie_a=0.0,
            vb_v=vbb_v,
            vc_v=inputs.vcc_v,
            ve_v=0.0,
            vce_v=inputs.vcc_v,
            pq_w=0.0,
            region="cutoff",
        ))

    ib_a = (vbb_v - inputs.vbe_v) / (rth_ohm + (1 + inputs.beta) * inputs.re_ohm)
    ic_a = inputs.beta * ib_a
    ie_a = (1 + inputs.beta) * ib_a

    ve_v = ie_a * inputs.re_ohm
    vb_v = inputs.vbe_v + ve_v
    vc_v = inputs.vcc_v - ic_a * inputs.rc_ohm
    vce_v = vc_v - ve_v
    pq_w = vce_v * ic_a

    return _checked(OperatingPoint(
        vbb_v=vbb_v,
        rth_ohm=rth_ohm,
        ib_a=ib_a,
        ic_a=ic_a,
        ie_a=ie_a,
        vb_v=vb_v,
        vc_v=vc_v,
        ve_v=ve_v,
        vce_v=vce_v,
        pq_w=pq_w,
        region="saturation" if vce_v < 0.2 else "active",
    ))


def solve_fixed_bias(inputs: FixedBiasInputs) -> OperatingPoint:
    """Solve a fixed-bias NPN stage where RB connects VCC to base."""
    vbb_v = inputs.vcc_v
    rth_ohm = inputs.rb_ohm

    if vbb_v <= inputs.vbe_v:
        return _checked(OperatingPoint(
            vbb_v=vbb_v,
            rth_ohm=rth_ohm,
            ib_a=0.0,
            ic_a=0.0,
            ie_a=0.0,
            vb_v=vbb_v,
            vc_v=inputs.vcc_v,
            ve_v=0.0,
            vce_v=inputs.vcc_v,
            pq_w=0.0,
            region="cutoff",
        ))

    ib_a = (vbb_v - inputs.vbe_v) / inputs.rb_ohm
    ic_a = inputs.beta * ib_a
    ie_a = (1 + inputs.beta) * ib_a
    ve_v = 0.0
    vb_v = inputs.vbe_v
    vc_v = inputs.vcc_v - ic_a * inputs.rc_ohm
    vce_v = vc_v - ve_v
    pq_w = vce_v * ic_a

    return _checked(OperatingPoint(
        vbb_v=vbb_v,
        rth_ohm=rth_ohm,
        ib_a=ib_a,
        ic_a=ic_a,
        ie_a=ie_a,
        vb_v=vb_v,
        vc_v=vc_v,
        ve_v=ve_v,
        vce_v=vce_v,
        pq_w=pq_w,
        region="saturation" if vce_v < 0.2 else "active",
    ))


def solve_emitter_bias(inputs: EmitterBiasInputs) -> OperatingPoint:
    """Solve an emitter-stabilized bias stage with RB from VCC to base."""
    vbb_v = inputs.vcc_v
    rth_ohm = inputs.rb_ohm

    if vbb_v <= inputs.vbe_v:
        return _checked(OperatingPoint(
            vbb_v=vbb_v,
            rth_ohm=rth_ohm,
            ib_a=0.0,
            ic_a=0.0,
            ie_a=0.0,
            vb_v=vbb_v,
            vc_v=inputs.vcc_v,
            ve_v=0.0,
            vce_v=inputs.vcc_v,
            pq_w=0.0,
            region="cutoff",
        ))

    ib_a = (vbb_v - inputs.vbe_v) / (inputs.rb_ohm + (1 + inputs.beta) * inputs.re_ohm)
    ic_a = inputs.beta * ib_a
    ie_a = (1 + inputs.beta) * ib_a
    ve_v = ie_a * inputs.re_ohm
    vb_v = inputs.vbe_v + ve_v
    vc_v = inputs.vcc_v - ic_a * inputs.rc_ohm
    vce_v = vc_v - ve_v
    pq_w = vce_v * ic_a

    return _checked(OperatingPoint(
        vbb_v=vbb_v,
        rth_ohm=rth_ohm,
        ib_a=ib_a,
        ic_a=ic_a,
        ie_a=ie_a,
        vb_v=vb_v,
        vc_v=vc_v,
        ve_v=ve_v,
        vce_v=vce_v,
        pq_w=pq_w,
        region="saturation" if vce_v < 0.2 else "active",
    ))


def compare(inputs: BiasInputs, exact: OperatingPoint) -> Comparison:
    """Cross-check the exact solution with the textbook approximation."""
    vb_approx_v = inputs.vcc_v * inputs.r2_ohm / (inputs.r1_ohm + inputs.r2_ohm)
    ve_approx_v = vb_approx_v - inputs.vbe_v

    if ve_approx_v <= 0:
        ic_approx_a = 0.0
        vce_approx_v = inputs.vcc_v
    else:
        ic_approx_a = ve_approx_v / inputs.re_ohm
        vce_approx_v = inputs.vcc_v - ic_approx_a * (inputs.rc_ohm + inputs.re_ohm)

    if exact.ic_a == 0:
        divergence_pct = 0.0
    else:
        divergence_pct = abs(exact.ic_a - ic_approx_a) / abs(exact.ic_a) * 100

    result = Comparison(
        ic_approx_a=ic_approx_a,
        vce_approx_a=vce_approx_v,
        divergence_pct=divergence_pct,
        reliable=divergence_pct <= 5.0,
    )
    if not all(
        math.isfinite(value)
        for value in (result.ic_approx_a, result.vce_approx_a, result.divergence_pct)
    ):
        raise ValidationError([NON_FINITE_MESSAGE])
    return result


def _parse_mode_fields(raw: Mapping[str, str], mode: str):
    """Parse the numeric fields for a mode, collecting every problem."""
    values = {}
    errors = []

    for key in MODE_FIELDS[mode]:
        label = FIELD_LABELS[key]
        text = str(raw.get(key, "")).strip()
        try:
            value = float(text)
        except ValueError:
            errors.append(f"Enter a number for {label}")
            values[key] = None
            continue
        if not math.isfinite(value):
            errors.append(f"Enter a finite number for {label}")
            values[key] = None
            continue
        values[key] = value

    return values, errors


def _validate_mode_values(values, errors, mode):
    """Apply the supply, resistor, beta, and VBE rules shared by all modes."""
    if values["vcc"] is not None and values["vcc"] <= 0:
        errors.append("VCC must be greater than 0 V")

    for key, label in MODE_RESISTOR_FIELDS[mode]:
        if values[key] is not None and values[key] <= 0:
            errors.append(f"{label} must be greater than 0 \u03a9")

    if values["beta"] is not None and values["beta"] < 1:
        errors.append("beta must be at least 1")

    if (
        values["vcc"] is not None
        and values["vbe"] is not None
        and not 0 < values["vbe"] < values["vcc"]
    ):
        errors.append("VBE must be between 0 V and VCC")


def validate_fixed(raw: Mapping[str, str]) -> FixedBiasInputs:
    """Parse and validate raw form strings for a fixed-bias stage."""
    values, errors = _parse_mode_fields(raw, MODE_FIXED)
    _validate_mode_values(values, errors, MODE_FIXED)
    if errors:
        raise ValidationError(errors)

    return FixedBiasInputs(
        vcc_v=values["vcc"],
        rb_ohm=values["rb"],
        rc_ohm=values["rc"],
        beta=values["beta"],
        vbe_v=values["vbe"],
    )


def validate_emitter(raw: Mapping[str, str]) -> EmitterBiasInputs:
    """Parse and validate raw form strings for an emitter-bias stage."""
    values, errors = _parse_mode_fields(raw, MODE_EMITTER)
    _validate_mode_values(values, errors, MODE_EMITTER)
    if errors:
        raise ValidationError(errors)

    return EmitterBiasInputs(
        vcc_v=values["vcc"],
        rb_ohm=values["rb"],
        rc_ohm=values["rc"],
        re_ohm=values["re"],
        beta=values["beta"],
        vbe_v=values["vbe"],
    )


def _checked_result(result):
    numeric = [value for value in result.values() if isinstance(value, float)]
    if not all(math.isfinite(value) for value in numeric):
        raise ValidationError([NON_FINITE_MESSAGE])
    return result


def solve_fixed(inputs: FixedBiasInputs) -> dict:
    """Solve a single-supply fixed-bias stage and return SI-unit results."""
    ib_a = (inputs.vcc_v - inputs.vbe_v) / inputs.rb_ohm
    ic_a = inputs.beta * ib_a
    ie_a = (1 + inputs.beta) * ib_a

    ve_v = 0.0
    vb_v = inputs.vbe_v
    vc_v = inputs.vcc_v - ic_a * inputs.rc_ohm
    vce_v = vc_v
    pq_w = vce_v * ic_a

    return _checked_result({
        "mode": MODE_FIXED,
        "ib_a": ib_a,
        "ic_a": ic_a,
        "ie_a": ie_a,
        "vb_v": vb_v,
        "vc_v": vc_v,
        "ve_v": ve_v,
        "vce_v": vce_v,
        "pq_w": pq_w,
        "region": "saturation" if vce_v < 0.2 else "active",
    })


def solve_emitter(inputs: EmitterBiasInputs) -> dict:
    """Solve a single-supply emitter-bias stage and return SI-unit results."""
    ib_a = (inputs.vcc_v - inputs.vbe_v) / (
        inputs.rb_ohm + (1 + inputs.beta) * inputs.re_ohm
    )
    ic_a = inputs.beta * ib_a
    ie_a = (1 + inputs.beta) * ib_a

    ve_v = ie_a * inputs.re_ohm
    vb_v = inputs.vbe_v + ve_v
    vc_v = inputs.vcc_v - ic_a * inputs.rc_ohm
    vce_v = vc_v - ve_v
    pq_w = vce_v * ic_a

    return _checked_result({
        "mode": MODE_EMITTER,
        "ib_a": ib_a,
        "ic_a": ic_a,
        "ie_a": ie_a,
        "vb_v": vb_v,
        "vc_v": vc_v,
        "ve_v": ve_v,
        "vce_v": vce_v,
        "pq_w": pq_w,
        "region": "saturation" if vce_v < 0.2 else "active",
    })


def _point_to_dict(point: OperatingPoint) -> dict:
    return {
        "ib_a": point.ib_a,
        "ic_a": point.ic_a,
        "ie_a": point.ie_a,
        "vb_v": point.vb_v,
        "vc_v": point.vc_v,
        "ve_v": point.ve_v,
        "vce_v": point.vce_v,
        "pq_w": point.pq_w,
        "region": point.region,
    }


def analyze(mode: str, raw: Mapping[str, str]) -> dict:
    """Validate and solve the requested bias mode, returning SI units.

    The divider path calls the existing solver and comparison unchanged, so
    its Q-point and cross-check values stay identical.
    """
    if mode not in MODES:
        raise ValidationError([f"Unknown bias mode: {mode}"])

    if mode == MODE_DIVIDER:
        inputs = validate(raw)
        point = solve_exact(inputs)
        comparison = compare(inputs, point)
        result = _point_to_dict(point)
        result.update({
            "mode": mode,
            "vbb_v": point.vbb_v,
            "rth_ohm": point.rth_ohm,
            "ic_approx_a": comparison.ic_approx_a,
            "vce_approx_a": comparison.vce_approx_a,
            "divergence_pct": comparison.divergence_pct,
            "reliable": comparison.reliable,
        })
        return result

    if mode == MODE_FIXED:
        return solve_fixed(validate_fixed(raw))

    return solve_emitter(validate_emitter(raw))
