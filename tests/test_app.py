import unittest

from app import create_app

EXAMPLE = {
    "vcc": "12", "r1": "47000", "r2": "10000",
    "rc": "4700", "re": "1000", "beta": "150", "vbe": "0.7",
}


class TestRoutes(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_get_renders_prefilled_form(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('name="vcc"', body)
        self.assertIn('value="12"', body)
        self.assertIn("Common-Emitter", body)

    def test_valid_post_shows_q_point_with_units(self):
        body = self.client.post("/", data=EXAMPLE).get_data(as_text=True)
        self.assertIn("1.324 mA", body)
        self.assertIn("4.446 V", body)
        self.assertIn("Active", body)
        self.assertIn("6.2%", body)

    def test_invalid_post_keeps_values_and_names_field(self):
        body = self.client.post("/", data={**EXAMPLE, "vcc": "abc"}).get_data(as_text=True)
        self.assertIn("Enter a number for VCC", body)
        self.assertIn('value="abc"', body)

    def test_cutoff_post_shows_zero_currents(self):
        body = self.client.post("/", data={**EXAMPLE, "r2": "1000"}).get_data(as_text=True)
        self.assertIn("Cutoff", body)
        self.assertIn("0.000 \u00b5A", body)
        self.assertIn("0.000 mA", body)
        self.assertIn("12.000 V", body)

    def test_saturation_post_warns(self):
        body = self.client.post("/", data={**EXAMPLE, "rc": "22000"}).get_data(as_text=True)
        self.assertIn("Saturation", body)
        self.assertIn("active-region formulas no longer apply", body)

    def test_extreme_magnitudes_stay_readable(self):
        body = self.client.post("/", data={
            **EXAMPLE, "vcc": "1000", "r1": "1000000000",
            "r2": "100000000", "rc": "1000000000", "re": "100000000",
        }).get_data(as_text=True)
        self.assertNotIn("nan", body.lower())
        self.assertNotIn("inf", body.lower())
        self.assertIn(" V", body)

    def test_non_finite_post_is_rejected(self):
        body = self.client.post("/", data={**EXAMPLE, "vcc": "1e309"}).get_data(as_text=True)
        self.assertIn("Enter a finite number for VCC", body)
        self.assertNotIn("nan", body.lower())

    def test_overflowing_divider_post_is_rejected(self):
        body = self.client.post(
            "/", data={**EXAMPLE, "r1": "1e308", "r2": "1e308"}
        ).get_data(as_text=True)
        self.assertIn("Inputs are too large to produce a finite result", body)
        self.assertNotIn("nan", body.lower())


class TestLayout(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_get_renders_three_column_workspace(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('class="workspace"', body)
        self.assertIn('class="panel panel-inputs"', body)
        self.assertIn('class="panel panel-diagram"', body)
        self.assertIn('class="panel panel-results"', body)

    def test_circuit_diagram_loads_from_static(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('src="/static/bjt-circuit.svg"', body)
        self.assertIn('alt="NPN BJT common-emitter amplifier', body)

    def test_circuit_diagram_is_served_from_static(self):
        response = self.client.get("/static/bjt-circuit.svg")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIn("image/svg+xml", response.content_type)
        finally:
            response.close()

    def test_results_panel_holds_q_point_and_cross_check(self):
        body = self.client.post("/", data=EXAMPLE).get_data(as_text=True)
        results = body.split('class="panel panel-results"', 1)[1]
        self.assertIn("Q-point", results)
        self.assertIn("Independent cross-check", results)
        self.assertIn("Active", results)
