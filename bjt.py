"""DC bias analysis for a voltage-divider NPN common-emitter stage.

Pure engineering logic: no Flask, no formatting, no HTML.
"""

from dataclasses import dataclass
from typing import Mapping

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


def validate(raw: Mapping[str, str]) -> BiasInputs:
    """Parse and validate raw form strings, collecting every problem."""
    errors = []
    values = {}

    for key, label in FIELDS.items():
        text = str(raw.get(key, "")).strip()
        try:
            values[key] = float(text)
        except ValueError:
            errors.append(f"Enter a number for {label}")
            values[key] = None

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


def solve_exact(inputs: BiasInputs) -> OperatingPoint:
    """Solve the base loop through the divider's Thevenin equivalent."""
    vbb_v = inputs.vcc_v * inputs.r2_ohm / (inputs.r1_ohm + inputs.r2_ohm)
    rth_ohm = inputs.r1_ohm * inputs.r2_ohm / (inputs.r1_ohm + inputs.r2_ohm)

    ib_a = (vbb_v - inputs.vbe_v) / (rth_ohm + (1 + inputs.beta) * inputs.re_ohm)
    ic_a = inputs.beta * ib_a
    ie_a = (1 + inputs.beta) * ib_a

    ve_v = ie_a * inputs.re_ohm
    vb_v = inputs.vbe_v + ve_v
    vc_v = inputs.vcc_v - ic_a * inputs.rc_ohm
    vce_v = vc_v - ve_v
    pq_w = vce_v * ic_a

    return OperatingPoint(
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
    )
