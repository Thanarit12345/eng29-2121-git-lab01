import unittest

from bjt import BiasInputs, ValidationError, solve_exact, validate

EXAMPLE = {
    "vcc": "12", "r1": "47000", "r2": "10000",
    "rc": "4700", "re": "1000", "beta": "150", "vbe": "0.7",
}


class TestValidate(unittest.TestCase):
    def test_valid_inputs_become_floats(self):
        inputs = validate(EXAMPLE)
        self.assertEqual(inputs.vcc_v, 12.0)
        self.assertEqual(inputs.beta, 150.0)

    def test_blank_field_is_reported_by_name(self):
        with self.assertRaises(ValidationError) as ctx:
            validate({**EXAMPLE, "vcc": ""})
        self.assertIn("Enter a number for VCC", ctx.exception.errors)

    def test_non_numeric_field_is_reported_by_name(self):
        with self.assertRaises(ValidationError) as ctx:
            validate({**EXAMPLE, "re": "abc"})
        self.assertIn("Enter a number for RE", ctx.exception.errors)

    def test_missing_key_counts_as_blank(self):
        raw = dict(EXAMPLE)
        del raw["beta"]
        with self.assertRaises(ValidationError) as ctx:
            validate(raw)
        self.assertIn("Enter a number for beta", ctx.exception.errors)

    def test_non_positive_resistances_are_rejected(self):
        for key, label in (("r1", "R1"), ("r2", "R2"), ("rc", "RC"), ("re", "RE")):
            for value in ("0", "-5"):
                with self.assertRaises(ValidationError) as ctx:
                    validate({**EXAMPLE, key: value})
                self.assertIn(f"{label} must be greater than 0 \u03a9", ctx.exception.errors)

    def test_zero_vcc_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate({**EXAMPLE, "vcc": "0"})
        self.assertIn("VCC must be greater than 0 V", ctx.exception.errors)

    def test_beta_below_one_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate({**EXAMPLE, "beta": "0.5"})
        self.assertIn("beta must be at least 1", ctx.exception.errors)

    def test_vbe_outside_open_interval_is_rejected(self):
        for vbe in ("0", "12", "13"):
            with self.assertRaises(ValidationError) as ctx:
                validate({**EXAMPLE, "vbe": vbe})
            self.assertIn("VBE must be between 0 V and VCC", ctx.exception.errors)

    def test_all_errors_are_collected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate({**EXAMPLE, "vcc": "0", "r1": "0"})
        self.assertIn("VCC must be greater than 0 V", ctx.exception.errors)
        self.assertIn("R1 must be greater than 0 \u03a9", ctx.exception.errors)

    def test_non_finite_vcc_is_rejected(self):
        for vcc in ("inf", "nan", "1e309"):
            with self.assertRaises(ValidationError) as ctx:
                validate({**EXAMPLE, "vcc": vcc})
            self.assertIn("Enter a finite number for VCC", ctx.exception.errors)

    def test_non_finite_beta_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate({**EXAMPLE, "beta": "nan"})
        self.assertIn("Enter a finite number for beta", ctx.exception.errors)

    def test_overflowing_divider_is_rejected(self):
        inputs = validate({**EXAMPLE, "r1": "1e308", "r2": "1e308"})
        with self.assertRaises(ValidationError) as ctx:
            solve_exact(inputs)
        self.assertIn("Inputs are too large to produce a finite result", ctx.exception.errors)


class TestSolveExact(unittest.TestCase):
    def test_worked_example(self):
        point = solve_exact(validate(EXAMPLE))
        self.assertAlmostEqual(point.vbb_v, 2.105263, places=6)
        self.assertAlmostEqual(point.rth_ohm, 8245.614035, places=6)
        self.assertAlmostEqual(point.ib_a, 8.824502e-6, places=9)
        self.assertAlmostEqual(point.ic_a, 1.323675e-3, places=6)
        self.assertAlmostEqual(point.ie_a, 1.332500e-3, places=6)
        self.assertAlmostEqual(point.ve_v, 1.332500, places=6)
        self.assertAlmostEqual(point.vb_v, 2.032500, places=6)
        self.assertAlmostEqual(point.vc_v, 5.7787264, places=6)
        self.assertAlmostEqual(point.vce_v, 4.4462267, places=6)
        self.assertAlmostEqual(point.pq_w, 5.8853e-3, places=6)

    def test_lower_vbe_raises_base_current(self):
        low = solve_exact(validate(EXAMPLE))
        high = solve_exact(validate({**EXAMPLE, "vbe": "0.6"}))
        self.assertGreater(high.ib_a, low.ib_a)


class TestRegion(unittest.TestCase):
    def test_worked_example_is_active(self):
        self.assertEqual(solve_exact(validate(EXAMPLE)).region, "active")

    def test_divider_below_vbe_is_cutoff(self):
        point = solve_exact(validate({**EXAMPLE, "r2": "1000"}))  # VBB = 0.25 V
        self.assertEqual(point.region, "cutoff")
        self.assertEqual(point.ib_a, 0.0)
        self.assertEqual(point.ic_a, 0.0)
        self.assertEqual(point.ie_a, 0.0)
        self.assertAlmostEqual(point.ve_v, 0.0, places=9)
        self.assertAlmostEqual(point.vb_v, 0.25, places=6)
        self.assertAlmostEqual(point.vc_v, 12.0, places=6)
        self.assertAlmostEqual(point.vce_v, 12.0, places=6)
        self.assertAlmostEqual(point.pq_w, 0.0, places=9)

    def test_large_collector_resistor_is_saturation(self):
        point = solve_exact(validate({**EXAMPLE, "rc": "22000"}))
        self.assertEqual(point.region, "saturation")
        self.assertLess(point.vce_v, 0.2)

    def test_huge_beta_approaches_approximation(self):
        point = solve_exact(validate({**EXAMPLE, "beta": "100000"}))
        self.assertEqual(point.region, "active")
        self.assertAlmostEqual(point.vce_v, 3.99, places=2)

    def test_tiny_emitter_resistor_is_saturation(self):
        point = solve_exact(validate({**EXAMPLE, "re": "1"}))
        self.assertEqual(point.region, "saturation")
        self.assertLess(point.vce_v, 0.2)


from bjt import compare


class TestCompare(unittest.TestCase):
    def test_worked_example_values_and_flag(self):
        inputs = validate(EXAMPLE)
        result = compare(inputs, solve_exact(inputs))
        self.assertAlmostEqual(result.ic_approx_a, 1.405263e-3, places=6)
        self.assertAlmostEqual(result.vce_approx_a, 3.990000, places=6)
        self.assertAlmostEqual(result.divergence_pct, 6.1637, places=3)
        self.assertFalse(result.reliable)

    def test_stiff_divider_agrees(self):
        inputs = validate({**EXAMPLE, "r1": "4700", "r2": "1000", "beta": "300"})
        result = compare(inputs, solve_exact(inputs))
        self.assertTrue(result.reliable)
        self.assertLess(result.divergence_pct, 5.0)

    def test_cutoff_gives_zero_approximation(self):
        inputs = validate({**EXAMPLE, "r2": "1000"})
        result = compare(inputs, solve_exact(inputs))
        self.assertEqual(result.ic_approx_a, 0.0)
        self.assertEqual(result.divergence_pct, 0.0)
        self.assertTrue(result.reliable)


if __name__ == "__main__":
    unittest.main()
