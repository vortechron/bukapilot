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


def test_one_bar_does_not_delay_planned_braking():
  # The camera planner can see a slowdown before stock ACC asks for a deep
  # brake. Its request must not wait for the previous throttle to ramp down.
  for v_ego in (0.0, 10.0, 25.0, 33.0):
    for previous_accel in (0.0, 12.0, 24.0, -1.0):
      for accel_raw in (-0.18, -3.6, -18.0, -54.0):
        command, urgent, _ = CarController.blend_longitudinal_command(
          accel_raw, previous_accel, -4.0, v_ego, 1, True,
        )
        assert command <= accel_raw
        assert not urgent  # No stock override was needed to honor the planner.


def test_one_bar_follows_gentle_throttle_reduction_and_brake_onset():
  previous_accel = 12.0
  # A smooth two-second slowdown must remain smooth at the CAN output while
  # removing the delay on faster brake requests.
  for frame in range(1, 101):
    accel_raw = 12.0 - frame * 0.15
    command, _, _ = CarController.blend_longitudinal_command(
      accel_raw, previous_accel, 0.0, 25.0, 1, True,
    )
    assert isclose(command, accel_raw, abs_tol=1e-9)
    previous_accel = command


def test_one_bar_cuts_throttle_when_coasting_is_requested():
  command, _, _ = CarController.blend_longitudinal_command(0.0, 12.0, 0.0, 25.0, 1, True)
  assert command == 0.0


def test_one_bar_stock_brake_starts_without_waiting_for_throttle_ramp():
  command, urgent, params = CarController.blend_longitudinal_command(12.0, 12.0, -10.0, 0.0, 1, True)
  assert command == -params.stock_brake_rate
  assert not urgent


def test_one_bar_does_not_extend_a_brief_planned_brake():
  for v_ego in (0.0, 10.0, 25.0, 33.0):
    for brake_request in (-3.6, -18.0, -54.0):
      command, _, _ = CarController.blend_longitudinal_command(brake_request, 0.0, 0.0, v_ego, 1, True)
      assert command == brake_request
      command, _, _ = CarController.blend_longitudinal_command(0.0, command, 0.0, v_ego, 1, True)
      assert command == 0.0, "braking continued after both controllers cleared their requests"


def test_one_bar_follows_planned_brake_release_without_adding_a_tail():
  command = -18.0
  for accel_raw in (-12.0, -6.0, -3.0, 0.0):
    command, _, _ = CarController.blend_longitudinal_command(accel_raw, command, 0.0, 25.0, 1, True)
    assert command == accel_raw


def test_one_bar_still_limits_throttle_after_releasing_brakes():
  for v_ego in (0.0, 10.0, 25.0, 33.0):
    command, _, params = CarController.blend_longitudinal_command(12.0, 0.0, 0.0, v_ego, 1, True)
    assert command == params.throttle_rate

    previous_accel = -18.0
    for _ in range(100):
      command, _, params = CarController.blend_longitudinal_command(12.0, previous_accel, 0.0, v_ego, 1, True)
      if previous_accel < 0.0:
        assert command == 0.0  # Release the brake before ramping positive throttle.
      else:
        assert command - previous_accel <= params.throttle_rate + 1e-9
      previous_accel = command


def test_one_bar_retains_stock_brake_floor_during_planned_release():
  command, urgent, params = CarController.blend_longitudinal_command(0.0, -18.0, -16.0, 25.0, 1, True)
  assert not urgent
  assert command == -18.0 + params.brake_release_rate
  assert command < 0.0


def test_one_bar_release_at_stock_threshold_and_adjacent_integer_commands():
  v_ego = 25.0
  params = CarController.get_long_blend_params(v_ego, 1, True)
  for stock_scaled in (params.stock_brake_threshold - 0.01, params.stock_brake_threshold, params.stock_brake_threshold + 0.01):
    command, _, _ = CarController.blend_longitudinal_command(-6.0, -18.0, stock_scaled, v_ego, 1, True)
    assert command <= -6.0  # Never release past the remaining planned brake.

  # Stock CMD is an integer before speed scaling. Exercise both neighboring
  # values across the threshold, including a renewed brake after release.
  mult = proton_carcontroller.interp(v_ego, [0.0, 28.3], [1.0, 0.6])
  command, _, _ = CarController.blend_longitudinal_command(0.0, -18.0, -22 * mult, v_ego, 1, True)
  assert command < 0.0
  command, _, _ = CarController.blend_longitudinal_command(0.0, command, -21 * mult, v_ego, 1, True)
  assert command == 0.0
  command, _, _ = CarController.blend_longitudinal_command(12.0, command, -22 * mult, v_ego, 1, True)
  assert command < 0.0


def test_non_close_modes_keep_release_blend_across_brake_transitions():
  for distance_val, close_follow_enabled in ((2, True), (3, True), (1, False)):
    for v_ego in (0.0, 2.49, 2.5, 10.0, 25.0):
      for previous_accel in (-30.0, 0.0, 24.0):
        for accel_raw in (-54.0, -3.6, 0.0, 12.0):
          for stock_scaled in (-30.0, -4.0, 0.0, 12.0):
            command, _, _ = CarController.blend_longitudinal_command(
              accel_raw, previous_accel, stock_scaled, v_ego, distance_val, close_follow_enabled,
            )
            expected = (stock_scaled + accel_raw) / 2.0 if v_ego < 2.5 else min(stock_scaled, accel_raw)
            assert command == expected


def test_controller_update_emits_planned_brake_on_first_can_frame():
  controller, car_control, car_state = make_controller_update_state(stock_acc_cmd=0.0)
  controller._prev_accel_cmd = 12.0
  car_control.actuators.accel = -1.0
  car_state.out.vEgo = 25.0

  with patch.object(proton_carcontroller, "create_can_steer_command", return_value="steer"), \
       patch.object(proton_carcontroller, "create_acc_cmd", return_value="acc") as create_acc:
    new_actuators, _ = controller.update(car_control, car_state, 0)

  assert create_acc.call_args.args[1] == -18.0
  assert new_actuators.accel == -1.0


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


def test_sng_resume_delays_are_scoped_to_x50_fl_bars():
  assert get_sng_resume_delay_frames(1, close_follow_enabled=True) == 50
  assert get_sng_resume_delay_frames(2, close_follow_enabled=True) == 150
  assert get_sng_resume_delay_frames(3, close_follow_enabled=True) == 310
  assert get_sng_resume_delay_frames(1, close_follow_enabled=False) == 310
  assert get_sng_resume_delay_frames(2, close_follow_enabled=False) == 310
  assert get_sng_resume_delay_frames(3, close_follow_enabled=False) == 310


def test_stronger_stopping_params_are_s70_platform_only():
  x50_fl_params = CarInterface.get_non_essential_params(CAR.S70)
  pre_fl_params = CarInterface.get_non_essential_params(CAR.X50)

  assert isclose(x50_fl_params.stopAccel, -1.0, abs_tol=1e-6)
  assert isclose(x50_fl_params.stoppingDecelRate, 0.4, abs_tol=1e-6)
  assert isclose(pre_fl_params.stopAccel, -0.8, abs_tol=1e-6)
  assert isclose(pre_fl_params.stoppingDecelRate, 0.3, abs_tol=1e-6)


def test_controller_update_waits_for_each_bars_resume_delay():
  with patch.object(proton_carcontroller, "create_can_steer_command", return_value="steer"), \
       patch.object(proton_carcontroller, "create_acc_cmd", return_value="acc"), \
       patch.object(proton_carcontroller, "send_buttons", return_value="resume") as send_buttons:
    for distance_bar, expected_frame in ((1, 50), (2, 150), (3, 310)):
      send_buttons.reset_mock()
      controller, car_control, car_state = make_controller_update_state(distance_val=distance_bar, stock_acc_cmd=0.0, cruise_standstill=True)
      for frame in range(expected_frame):
        controller.update(car_control, car_state, frame)
      send_buttons.assert_not_called()

      controller.update(car_control, car_state, expected_frame)
      send_buttons.assert_called_once()
      assert send_buttons.call_args.args[1] == 0
