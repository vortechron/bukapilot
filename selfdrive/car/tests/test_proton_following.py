from openpilot.selfdrive.car.proton.carcontroller import CarController
from openpilot.selfdrive.car.proton.carstate import get_valid_distance_bar


def test_invalid_distance_bar_keeps_previous_selection():
  for distance_bar in (1, 2, 3):
    assert get_valid_distance_bar(distance_bar, 2) == distance_bar

  assert get_valid_distance_bar(0, 2) == 2
  assert get_valid_distance_bar(4, 2) == 2


def test_all_bars_use_responsive_bounded_throttle_ramp():
  expected_rates = {
    0.0: 0.25,
    22.0: 0.28,
    25.0: 0.32,
    33.0: 0.40,
  }

  for distance_bar in (1, 2, 3):
    for v_ego, expected_rate in expected_rates.items():
      throttle_rate = CarController.get_long_blend_params(v_ego, distance_bar)[0]
      assert throttle_rate == expected_rate


def test_closer_bars_keep_stock_brake_overrides():
  for v_ego in (0.0, 10.0, 22.0, 25.0):
    one_bar = CarController.get_long_blend_params(v_ego, 1)
    two_bar = CarController.get_long_blend_params(v_ego, 2)

    assert one_bar[1:] == two_bar[1:]
    _, _, stock_coast_threshold, stock_brake_threshold, hard_override, _ = one_bar
    assert hard_override < stock_brake_threshold < stock_coast_threshold


def test_throttle_taper_band_survives_integer_stock_dither():
  # ACC_CMD.CMD is an 8 bit signal with scale 1, so the stock advisory only
  # moves in whole CAN units. The taper between the brake and coast thresholds
  # must span more than one unit, otherwise a 1 unit dither swings throttle
  # authority from full to none and the car hunts.
  for distance_bar in (1, 2):
    for v_ego in (0.0, 2.0, 5.0, 10.0, 16.0, 22.0, 25.0, 33.0):
      _, _, stock_coast_threshold, stock_brake_threshold, _, _ = \
        CarController.get_long_blend_params(v_ego, distance_bar)

      taper_band = stock_coast_threshold - stock_brake_threshold
      assert taper_band >= 1.5, f"bar {distance_bar} at {v_ego} m/s tapers over only {taper_band} CAN"
