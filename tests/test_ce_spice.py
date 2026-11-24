import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ce_spice import (
    SpiceParseError,
    SpiceRunError,
    SpiceUnavailable,
    analyze_ac,
    analyze_tran,
    build_reference_netlist,
    parse_op_log,
    parse_wrdata,
    simulate_reference,
)


class TestNetlist(unittest.TestCase):
    def test_contains_reference_values(self):
        net = build_reference_netlist(0.01, 1000.0, Path("spice/models/2N3904.lib"))
        self.assertIn("R1 vcc base 100k", net)
        self.assertIn("SIN(0 0.01 1000.0)", net)
        self.assertIn("ac dec 50 0.1 100meg", net)
        self.assertIn("wrdata", net)


class TestParse(unittest.TestCase):
    def test_parse_op_log(self):
        text = "v(base) = 1.976512e+00\nv(emitter) = 1.323593e+00\nv(collector) = 9.110961e+00\n"
        row = parse_op_log(text)
        self.assertAlmostEqual(row["base"], 1.976512, places=6)

    def test_parse_wrdata_rejects_short_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.dat"
            p.write_text("bad\n", encoding="utf-8")
            with self.assertRaises(SpiceParseError):
                parse_wrdata(p, ["frequency", "vdb(out)", "vp(out)"])


class TestAnalyze(unittest.TestCase):
    def test_analyze_ac_finds_selected_point(self):
        rows = [
            {"frequency_hz": 100.0, "vdb_out": 0.0, "vp_out": -170.0},
            {"frequency_hz": 1000.0, "vdb_out": 6.0, "vp_out": -179.0},
            {"frequency_hz": 10000.0, "vdb_out": 0.0, "vp_out": 170.0},
        ]
        result = analyze_ac(rows, 1000.0)
        self.assertAlmostEqual(result["gain_db"], 6.0, places=3)
        self.assertAlmostEqual(result["gain_vv"], 1.995262, places=5)
        self.assertAlmostEqual(result["phase_deg"], -179.0, places=3)

    def test_analyze_tran_estimates_gain_and_inversion(self):
        import math

        rows = []
        for i in range(500):
            t = i / 50000.0
            vin = 0.01 * math.sin(2 * math.pi * 1000.0 * t)
            vout = -0.02 * math.sin(2 * math.pi * 1000.0 * t)
            rows.append({"time_s": t, "v_source": vin, "v_out": vout})
        result = analyze_tran(rows, 1000.0)
        self.assertAlmostEqual(result["gain_vv"], 2.0, places=2)
        self.assertTrue(result["phase_inverted"])


class TestRunErrors(unittest.TestCase):
    def test_missing_binary_raises_unavailable(self):
        with mock.patch("ce_spice.resolve_ngspice", side_effect=SpiceUnavailable("missing")):
            with self.assertRaises(SpiceUnavailable):
                simulate_reference(0.01, 1000.0)

    def test_nonzero_exit_raises_run_error(self):
        fake = mock.Mock(returncode=1, stdout="bad", stderr="oops")
        with mock.patch("ce_spice.resolve_ngspice", return_value=Path("ngspice")), mock.patch(
            "subprocess.run", return_value=fake
        ):
            with self.assertRaises(SpiceRunError):
                simulate_reference(0.01, 1000.0)


@unittest.skipUnless(
    Path(".tools/Spice64/bin/ngspice_con.exe").exists() or shutil.which("ngspice_con") or shutil.which("ngspice"),
    "ngspice not installed",
)
class TestRealNgspice(unittest.TestCase):
    def test_reference_simulation(self):
        result = simulate_reference(0.01, 1000.0)
        self.assertIn("ac", result["spice"])
        self.assertGreater(result["spice"]["ac"]["gain_vv"], 1.0)
        self.assertTrue(result["spice"]["tran"]["phase_inverted"])
