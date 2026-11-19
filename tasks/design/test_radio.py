"""Independent identities and blind-spot checks for the stage adapter."""
import math

from radio import evaluate


def test_range_doubling():
    near = evaluate({}, 30, 30, 600_000, 0)
    far = evaluate({}, 30, 30, 1_200_000, 0)
    assert math.isclose(near["cn0_dbhz"] - far["cn0_dbhz"], 20 * math.log10(2))
    assert math.isclose(2 * near["delay_s"], far["delay_s"])


def test_power_doubling():
    low = evaluate({"tx_w": 0.5}, 20, 0, 1_000_000, 0)
    high = evaluate({"tx_w": 1.0}, 20, 0, 1_000_000, 0)
    assert math.isclose(high["cn0_dbhz"] - low["cn0_dbhz"], 10 * math.log10(2))
    assert high["rate_bps"] > low["rate_bps"]


def test_minimum_elevation():
    assert evaluate({}, 9.99, 0, 1_000_000, 0)["rate_bps"] == 0
    assert evaluate({}, 10.01, 0, 1_000_000, 0)["rate_bps"] > 0


def test_phy_goodput_bound():
    for power in (0.01, 0.1, 1, 10):
        sample = evaluate({"tx_w": power, "modes": ["QPSK_1/2"]}, 20, 0, 1_000_000, 0)
        nominal = 1e6 * 2 * 0.5 / 1.2
        assert 0 <= sample["rate_bps"] <= math.ceil(nominal)
        if sample["rate_bps"]:
            assert math.isclose(sample["rate_bps"], (1 - sample["bler"]) * nominal, abs_tol=0.5)
