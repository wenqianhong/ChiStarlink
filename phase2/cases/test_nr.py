"""Unit tests for interpolation only. Tiny artificial counts are isolated from replay."""
import math
import tempfile
import unittest
from pathlib import Path

from nr import select_profile


class CurveLookupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "interpolation-test.csv"
        self.file.write_text(
            "snr_db,mcs,prbs,scs_hz,slot_s,tbs_bits,errors,trials,bler\n"
            "0,4,2,15000,.001,144,10,10,1\n"
            "10,4,2,15000,.001,144,0,10,0\n"
            "0,4,5,15000,.001,336,10,10,1\n"
            "10,4,5,15000,.001,336,0,10,0\n")
    def test_use_actual_tbs_and_occupied_bandwidth(self):
        out = select_profile(5+10*math.log10(900000),1e6,[4],self.file)
        self.assertEqual(out["prbs"],5)
        self.assertAlmostEqual(out["bler"],.5)
        self.assertEqual(out["rate_bps"],168000)
        self.assertEqual(out["lower_trials"],10)
    def test_no_numeric_extrapolation(self):
        with self.assertRaises(ValueError):
            select_profile(80,500000,[4],self.file)
    def test_no_fictitious_fractional_prb(self):
        with self.assertRaises(ValueError):
            select_profile(55,100000,[4],self.file)


if __name__ == "__main__":
    unittest.main()
