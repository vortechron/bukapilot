from math import isclose
from types import SimpleNamespace
from unittest.mock import patch

from openpilot.selfdrive.car.proton import carcontroller as proton_carcontroller
from openpilot.selfdrive.car.proton.carcontroller import CarController, get_sng_resume_delay_frames
from openpilot.selfdrive.car.proton.carstate import get_valid_distance_bar
from openpilot.selfdrive.car.proton.interface import CarInterface
from openpilot.selfdrive.car.proton.values import CAR


def make_controller_update_state(distance_val=1, stock_acc_cmd=-20.0, cruise_standstill=False):
  controller = CarController.__new__(CarController)
  controller.CP = SimpleNamespace(carFingerprint=CAR.S70)
  controller.frame = 0
  controller.packer = object()
  controller.params = SimpleNamespace(STEER_MAX=530, STEER_DELTA_UP=15, STEER_DELTA_DOWN=35)
  controller.last_steer = 0
  controller.always_lks_tactile = False
  controller.openpilot_long = True
  controller.close_follow_enabled = True
  controller.prev_steer_enabled = False
  controller.last_steer_disable = 0
  controller.sng_next_press_frame = 0
  controller.resume_counter = 0
  controller.is_sng_check = False
  controller.resume = False
  controller.cancel_press_cnt = 0
  controller.last_cancel_press = 0
  controller._prev_accel_cmd = 0.0
  controller._dbg = SimpleNamespace(log=lambda _: None)

  actuators = SimpleNamespace(accel=0.8, steer=0.0)
  actuators.copy = lambda: SimpleNamespace(accel=actuators.accel, steer=actuators.steer)
  car_control = SimpleNamespace(
    latActive=False,
    longActive=True,
    actuators=actuators,
    cruiseControl=SimpleNamespace(cancel=False),
  )
  car_state = SimpleNamespace(
    out=SimpleNamespace(
      gasPressed=False,
      brakePressed=False,
      rightBlinker=False,
      leftBlinker=False,
      standstill=False,
      vEgo=0.0,
    ),
    stock_ldp_cmd=0,
    stock_ldp_right=False,
    stock_ldp_left=False,
    hand_on_wheel_warning=False,
    hand_on_wheel_warning_2=False,
    is_icc_on=True,
    lks_aux=False,
    lks_audio=False,
    lks_tactile=False,
    lks_assist_mode=False,
    lka_enable=True,
    stock_ldw_steering=False,
    cruise_standstill=cruise_standstill,
    res_btn_pressed=False,
    stock_acc_cmd=stock_acc_cmd,
    distance_val=distance_val,
  )
  return controller, car_control, car_state


def test_invalid_distance_bar_keeps_previous_selection():
  for distance_bar in (1, 2, 3):
    assert get_valid_distance_bar(distance_bar, 2) == distance_bar

  assert get_valid_distance_bar(0, 2) == 2
  assert get_valid_distance_bar(4, 2) == 2


def test_all_bars_use_bounded_throttle_ramp():
  expected_rates = {
    0.0: 0.25,
    22.0: 0.28,
    25.0: 0.32,
    33.0: 0.40,
  }

  for distance_bar in (1, 2, 3):
    for v_ego, expected_rate in expected_rates.items():
      throttle_rate = CarController.get_long_blend_params(v_ego, distance_bar).throttle_rate
      assert throttle_rate == expected_rate


def test_only_one_bar_uses_close_follow_blend():
  for v_ego in (0.0, 10.0, 22.0, 25.0):
    one_bar = CarController.get_long_blend_params(v_ego, 1, close_follow_enabled=True)
    two_bar = CarController.get_long_blend_params(v_ego, 2, close_follow_enabled=True)
    three_bar = CarController.get_long_blend_params(v_ego, 3, close_follow_enabled=True)
    disabled_one_bar = CarController.get_long_blend_params(v_ego, 1, close_follow_enabled=False)

    assert one_bar != two_bar
    assert two_bar == three_bar == disabled_one_bar


def test_controller_enables_close_follow_only_for_s70_platform():
  def car_params(fingerprint, steer_max):
    return SimpleNamespace(carFingerprint=fingerprint, lateralParams=SimpleNamespace(torqueV=[steer_max]))

  with patch.object(proton_carcontroller, "CANPacker"), patch.object(proton_carcontroller, "Features") as features:
    features.return_value.has.return_value = False

    x50_fl_controller = CarController(None, car_params(CAR.S70, 530), None)
    pre_fl_controller = CarController(None, car_params(CAR.X50, 545), None)

  assert x50_fl_controller.close_follow_enabled
  assert not pre_fl_controller.close_follow_enabled


def test_close_follow_ignores_gap_nag_but_blends_real_braking():
  gap_nag_cmd, gap_nag_urgent, _ = CarController.blend_longitudinal_command(
    accel_raw=12.0,
    previous_accel=0.0,
    stock_scaled=-4.0,
    v_ego=0.0,
    distance_val=1,
    close_follow_enabled=True,
  )
  assert gap_nag_cmd == 0.25
  assert not gap_nag_urgent

  braking_cmd, braking_urgent, _ = CarController.blend_longitudinal_command(
    accel_raw=12.0,
    previous_accel=0.0,
    stock_scaled=-10.0,
    v_ego=0.0,
    distance_val=1,
    close_follow_enabled=True,
  )
  assert braking_cmd == -0.45
  assert not braking_urgent

  urgent_cmd, urgent, _ = CarController.blend_longitudinal_command(
    accel_raw=12.0,
    previous_accel=0.0,
    stock_scaled=-20.0,
    v_ego=0.0,
    distance_val=1,
    close_follow_enabled=True,
  )
  assert urgent_cmd == -20.0
  assert urgent


def test_non_close_modes_keep_release_stock_blend():
  for distance_val, close_follow_enabled in ((2, True), (3, True), (1, False)):
    low_speed_cmd, urgent, _ = CarController.blend_longitudinal_command(
      accel_raw=12.0,
      previous_accel=0.0,
      stock_scaled=-4.0,
      v_ego=0.0,
      distance_val=distance_val,
      close_follow_enabled=close_follow_enabled,
    )
    road_speed_cmd, _, _ = CarController.blend_longitudinal_command(
      accel_raw=12.0,
      previous_accel=0.0,
      stock_scaled=-4.0,
      v_ego=10.0,
      distance_val=distance_val,
      close_follow_enabled=close_follow_enabled,
    )

    assert low_speed_cmd == 4.0
    assert road_speed_cmd == -4.0
    assert not urgent


def test_controller_update_emits_urgent_stock_brake_without_rate_limit():
  controller, car_control, car_state = make_controller_update_state()

  with patch.object(proton_carcontroller, "create_can_steer_command", return_value="steer"), \
       patch.object(proton_carcontroller, "create_acc_cmd", return_value="acc") as create_acc:
    new_actuators, _ = controller.update(car_control, car_state, 0)

  assert create_acc.call_args.args[1] == -20.0
  assert new_actuators.accel == -20.0 / 18.0


def test_stock_brake_threshold_stays_below_gap_nagging():
  # Stock ACC targets a ~1.5s gap, so at the custom one-bar follow it commands negative all
  # the time and gets louder as the gap closes. Drive logs on the X50 FL put that
  # gap nagging around -4 with lead acceleration flat at zero, so the threshold
  # where stock is allowed to add braking has to sit well clear of it. If this
  # creeps back up, stock silently caps throttle again and the car cannot close
  # to T_FOLLOW.
  for v_ego in (0.0, 2.0, 5.0, 10.0, 16.0, 22.0, 25.0, 33.0):
    params = CarController.get_long_blend_params(v_ego, 1, close_follow_enabled=True)

    assert params.stock_brake_threshold <= -8.0, \
      f"one bar at {v_ego} m/s lets stock brake from {params.stock_brake_threshold} CAN"
    assert params.hard_override <= params.stock_brake_threshold - 6.0


def test_only_x50_fl_one_bar_gets_fast_sng_resume():
  assert get_sng_resume_delay_frames(1, close_follow_enabled=True) == 50
  assert get_sng_resume_delay_frames(2, close_follow_enabled=True) == 310
  assert get_sng_resume_delay_frames(3, close_follow_enabled=True) == 310
  assert get_sng_resume_delay_frames(1, close_follow_enabled=False) == 310


def test_stronger_stopping_params_are_s70_platform_only():
  x50_fl_params = CarInterface.get_non_essential_params(CAR.S70)
  pre_fl_params = CarInterface.get_non_essential_params(CAR.X50)

  assert isclose(x50_fl_params.stopAccel, -1.0, abs_tol=1e-6)
  assert isclose(x50_fl_params.stoppingDecelRate, 0.4, abs_tol=1e-6)
  assert isclose(pre_fl_params.stopAccel, -0.8, abs_tol=1e-6)
  assert isclose(pre_fl_params.stoppingDecelRate, 0.3, abs_tol=1e-6)


def test_controller_update_uses_fast_sng_resume_only_for_one_bar():
  with patch.object(proton_carcontroller, "create_can_steer_command", return_value="steer"), \
       patch.object(proton_carcontroller, "create_acc_cmd", return_value="acc"), \
       patch.object(proton_carcontroller, "send_buttons", return_value="resume") as send_buttons:
    controller, car_control, car_state = make_controller_update_state(stock_acc_cmd=0.0, cruise_standstill=True)
    for frame in range(51):
      controller.update(car_control, car_state, frame)

    assert send_buttons.call_count == 1
    assert send_buttons.call_args.args[1] == 0

    send_buttons.reset_mock()
    controller, car_control, car_state = make_controller_update_state(distance_val=2, stock_acc_cmd=0.0, cruise_standstill=True)
    for frame in range(51):
      controller.update(car_control, car_state, frame)

    send_buttons.assert_not_called()
