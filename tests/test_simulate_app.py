import unittest
from unittest import mock

from app import create_app
from ce_spice import SpiceUnavailable


class TestSimulateRoute(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_simulate_renders_spice_sections(self):
        fake = {
            "meta": {"amplitude_mv_peak": 10.0, "frequency_hz": 1000.0},
            "analytical": {"ic_a": 0.001, "vce_v": 5.0, "region": "active", "vb_v": 2.0, "ve_v": 1.3, "vc_v": 6.3, "ib_a": 6.67e-6, "ie_a": 0.001007, "assumptions": "Analytical reference"},
            "spice": {
                "dc": {"vb_v": 1.9, "ve_v": 1.3, "vc_v": 9.1, "vce_v": 7.8, "ic_a": 0.0013, "ib_a": 0.000004, "ie_a": 0.001304, "region": "active"},
                "ac": {"gain_vv": 2.0, "gain_db": 6.02, "phase_deg": -179.0, "low_cutoff_hz": None, "high_cutoff_hz": None, "rows": [{"frequency_hz": 1000.0, "vdb_out": 6.02, "vp_out": -179.0}]},
                "tran": {"vin_peak_v": 0.01, "vout_peak_v": 0.02, "vin_pp_mv": 20.0, "vout_pp_mv": 40.0, "gain_vv": 2.0, "phase_deg": -179.0, "phase_inverted": True, "rows": [{"time_s": 0.0, "v_source": 0.0, "v_out": 0.0}, {"time_s": 0.001, "v_source": 0.01, "v_out": -0.02}]},
            },
            "warnings": [],
        }
        with mock.patch("app.simulate_reference", return_value=fake):
            body = self.client.post("/simulate", data={"amplitude_mv": "10", "frequency_hz": "1000"}).get_data(as_text=True)
        self.assertIn("SPICE DC operating point (.op)", body)
        self.assertIn("Analytical reference", body)
        self.assertIn("<svg", body)

    def test_missing_ngspice_shows_error(self):
        with mock.patch("app.simulate_reference", side_effect=SpiceUnavailable("missing ngspice")):
            body = self.client.post("/simulate", data={"amplitude_mv": "10", "frequency_hz": "1000"}).get_data(as_text=True)
        self.assertIn("missing ngspice", body)
        self.assertNotIn("Traceback", body)
