from openpilot.selfdrive.car.proton.carcontroller import CarController
from openpilot.selfdrive.car.proton.carstate import get_valid_distance_bar


def test_invalid_distance_bar_keeps_previous_selection():
  for distance_bar in (1, 2, 3):
    assert get_valid_distance_bar(distance_bar, 2) == distance_bar

  assert get_valid_distance_bar(0, 2) == 2
  assert get_valid_distance_bar(4, 2) == 2


def test_one_and_two_bar_blend_match():
  # Two bar should retain the complete controller-side behavior of the
  # previous 1-bar tune, not only its MPC time-gap target.
  for v_ego in (0.0, 10.0, 22.0, 25.0, 33.0):
    assert CarController.get_long_blend_params(v_ego, 1) == CarController.get_long_blend_params(v_ego, 2)
