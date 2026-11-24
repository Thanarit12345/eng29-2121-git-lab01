"""Server-rendered SVG charts for CE simulator. No JS dependencies."""

from __future__ import annotations

import math


def _fmt_num(value):
    if abs(value) >= 1000 or (0 < abs(value) < 0.01):
        return f"{value:.3g}"
    return f"{value:.4g}"


def _scale_linear(value, vmin, vmax, out_min, out_max):
    if vmax == vmin:
        return (out_min + out_max) / 2
    ratio = (value - vmin) / (vmax - vmin)
    return out_min + ratio * (out_max - out_min)


def _polyline(points, color):
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}" />'


def _line_chart(title, x_label, y_label, series, x_to_px, x_ticks, y_ticks, width=720, height=280):
    pad_l, pad_r, pad_t, pad_b = 58, 20, 34, 44
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    y_min = min(v for _, ys, _, _ in series for v in ys)
    y_max = max(v for _, ys, _, _ in series for v in ys)
    if y_min == y_max:
        y_min -= 1
        y_max += 1
    def y_px(v):
        return pad_t + ih - _scale_linear(v, y_min, y_max, 0, ih)

    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart-svg" role="img" aria-label="{title}">']
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fff" rx="8" />')
    parts.append(f'<text x="{pad_l}" y="20" font-size="13" font-weight="600" fill="#123658">{title}</text>')
    for y, label in y_ticks:
        py = y_px(y)
        parts.append(f'<line x1="{pad_l}" y1="{py:.2f}" x2="{width-pad_r}" y2="{py:.2f}" stroke="#e6eef6" />')
        parts.append(f'<text x="{pad_l-8}" y="{py+4:.2f}" text-anchor="end" font-size="11" fill="#52657a">{label}</text>')
    for x, label in x_ticks:
        px = x_to_px(x, pad_l, iw)
        parts.append(f'<line x1="{px:.2f}" y1="{pad_t}" x2="{px:.2f}" y2="{pad_t+ih}" stroke="#f1f6fb" />')
        parts.append(f'<text x="{px:.2f}" y="{height-12}" text-anchor="middle" font-size="11" fill="#52657a">{label}</text>')
    parts.append(f'<rect x="{pad_l}" y="{pad_t}" width="{iw}" height="{ih}" fill="none" stroke="#d6e2ee" />')
    for name, ys, color, xs in series:
        points = [(x_to_px(x, pad_l, iw), y_px(y)) for x, y in zip(xs, ys)]
        parts.append(_polyline(points, color))
    legend_x = pad_l + 8
    for i, (name, _, color, _) in enumerate(series):
        lx = legend_x + i * 120
        parts.append(f'<line x1="{lx}" y1="{pad_t+12}" x2="{lx+18}" y2="{pad_t+12}" stroke="{color}" stroke-width="2" />')
        parts.append(f'<text x="{lx+22}" y="{pad_t+16}" font-size="11" fill="#123658">{name}</text>')
    parts.append(f'<text x="{pad_l + iw/2:.1f}" y="{height-2}" text-anchor="middle" font-size="11" fill="#52657a">{x_label}</text>')
    parts.append(f'<text x="14" y="{pad_t + ih/2:.1f}" transform="rotate(-90 14 {pad_t + ih/2:.1f})" text-anchor="middle" font-size="11" fill="#52657a">{y_label}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def ac_chart_svg(rows, selected_hz=None):
    if not rows:
        return ""
    freqs = [max(float(r["frequency_hz"]), 1e-12) for r in rows]
    log_min, log_max = math.log10(min(freqs)), math.log10(max(freqs))
    def x_to_px(x, pad_l, iw):
        lx = math.log10(max(float(x), 1e-12))
        return pad_l + _scale_linear(lx, log_min, log_max, 0, iw)
    x_ticks = []
    for exp in range(int(math.floor(log_min)), int(math.ceil(log_max)) + 1):
        f = 10 ** exp
        if min(freqs) <= f <= max(freqs):
            label = "1" if exp == 0 else f"10^{exp}" if exp not in (3,6,9) else {3:"1k",6:"1M",9:"1G"}[exp]
            x_ticks.append((f, label))
    db_vals = [float(r["vdb_out"]) for r in rows]
    db_min, db_max = min(db_vals), max(db_vals)
    db_step = 10 if db_max - db_min > 20 else 5
    y_start = math.floor(db_min / db_step) * db_step
    y_end = math.ceil(db_max / db_step) * db_step
    y_ticks = [(y, f"{y:g}") for y in range(int(y_start), int(y_end) + 1, int(db_step))]
    mag = _line_chart("AC magnitude (SPICE)", "Frequency (Hz)", "Gain (dB)", [("vdb(out)", db_vals, "#0f5f8f", freqs)], x_to_px, x_ticks, y_ticks)
    ph_vals = [float(r["vp_out"]) for r in rows]
    ph_min, ph_max = min(ph_vals), max(ph_vals)
    ph_step = 45 if ph_max - ph_min > 90 else 15
    p_start = math.floor(ph_min / ph_step) * ph_step
    p_end = math.ceil(ph_max / ph_step) * ph_step
    p_ticks = [(y, f"{y:g}") for y in range(int(p_start), int(p_end) + 1, int(ph_step))]
    phase = _line_chart("AC phase (SPICE)", "Frequency (Hz)", "Phase (deg)", [("vp(out)", ph_vals, "#c2620a", freqs)], x_to_px, x_ticks, p_ticks)
    return mag + "\n" + phase


def tran_chart_svg(rows):
    if not rows:
        return ""
    times = [float(r["time_s"]) * 1000.0 for r in rows]
    vin = [float(r["v_source"]) * 1000.0 for r in rows]
    vout = [float(r["v_out"]) * 1000.0 for r in rows]
    x_min, x_max = min(times), max(times)
    def x_to_px(x, pad_l, iw):
        return pad_l + _scale_linear(x, x_min, x_max, 0, iw)
    tick_count = 6
    x_ticks = [(x_min + (x_max - x_min) * i / tick_count, _fmt_num(x_min + (x_max - x_min) * i / tick_count)) for i in range(tick_count + 1)]
    all_y = vin + vout
    y_min, y_max = min(all_y), max(all_y)
    span = y_max - y_min or 1.0
    step = span / 4
    y_ticks = [(y_min + step * i, _fmt_num(y_min + step * i)) for i in range(5)]
    return _line_chart(
        "Transient response (SPICE)", "Time (ms)", "Voltage (mV)",
        [("Vin", vin, "#0f8a8a", times), ("Vout", vout, "#6d4aff", times)],
        x_to_px, x_ticks, y_ticks,
    )
