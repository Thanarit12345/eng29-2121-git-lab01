def analyze_dc(voltage_v, resistance_ohm):
    current_a = voltage_v / resistance_ohm
    power_w = voltage_v * current_a
    return {"current_a": current_a, "power_w": power_w}


if __name__ == "__main__":
    print(analyze_dc(12, 6))