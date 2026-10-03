"""Proton planner -> PID -> packed CAN regression with a delayed model of the car.

The actuator model is deliberately simple and is not a fit to drive logs. These
tests catch loop regressions; they do not establish safe road following gaps.
"""
from collections import deque
from types import SimpleNamespace

import numpy as np
import pytest
from cereal import car, log
from opendbc.can.parser import CANParser
from opendbc.can.tests.test_packer_parser import can_list_to_can_capnp

from openpilot.common.params import Params
from openpilot.common.realtime import DT_CTRL, DT_MDL
from openpilot.selfdrive.car.proton.carcontroller import CarController
from openpilot.selfdrive.car.proton.interface import CarInterface
from openpilot.selfdrive.car.proton.protoncan import create_acc_cmd
from openpilot.selfdrive.car.proton.values import CAR, DBC
from openpilot.selfdrive.car.tests.test_proton_following import make_controller_update_state
from openpilot.selfdrive.controls.lib.longcontrol import LongControl, LongCtrlState
from openpilot.selfdrive.controls.lib.drive_helpers import CONTROL_N
from openpilot.selfdrive.controls.lib.longitudinal_planner import LongitudinalPlanner
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import LongitudinalFollowProfile, desired_follow_distance, get_stop_distance, get_T_FOLLOW
from openpilot.selfdrive.modeld.constants import ModelConstants


class ProtonFollowingPlant:
  def __init__(self, speed, distance_bar=1, actuator_delay=0.4, lead_delay=0.1):
    personalities = {1: log.LongitudinalPersonality.aggressive, 2: log.LongitudinalPersonality.standard,
                     3: log.LongitudinalPersonality.relaxed}
    self.personality = personalities[distance_bar]
    self.distance_bar = distance_bar
    Params().put("LongitudinalPersonality", str(self.personality))
    self.cp = CarInterface.get_non_essential_params(CAR.S70)
    self.planner = LongitudinalPlanner(self.cp, init_v=speed)
    # run() resets solution_status to zero after a failed solve. Fail at the
    # reset itself so a later recovery cannot hide a bad frame.
    self.planner.mpc.reset = self.fail_on_solver_reset
    self.long_control = LongControl(self.cp)
    self.controller = CarController(DBC[CAR.S70]['pt'], self.cp, None)
    _, self.cc, self.cs = make_controller_update_state(distance_val=distance_bar, stock_acc_cmd=0.0)
    self.cs.out = car.CarState.new_message()
    self.parser = CANParser(DBC[CAR.S70]['pt'], [("ACC_CMD", 50)], 0)
    self.controls_state = SimpleNamespace(longControlState=LongCtrlState.pid, vCruise=(speed + 5.0) * 3.6,
                                          experimentalMode=False, forceDecel=False, enabled=True)
    self.plan = SimpleNamespace(speeds=[], accels=[], personality=self.personality)
    self.speed = float(speed)
    self.acceleration = 0.0
    self.gap = self.target_gap(speed) + 8.0
    self.frame = 0
    self.command = 0.0
    self.brake_mode = False
    self.actuator_commands = deque([0.0] * (round(actuator_delay / DT_CTRL) + 1),
                                   maxlen=round(actuator_delay / DT_CTRL) + 1)
    self.lead_samples = deque([(self.gap, speed)] * (round(lead_delay / DT_CTRL) + 1),
                              maxlen=round(lead_delay / DT_CTRL) + 1)
    # Avoid wall-clock debug logs during faster-than-real-time simulation.
    for obj in (self.planner, self.planner.mpc, self.controller):
      obj._dbg = SimpleNamespace(log=lambda _: None)

  def target_gap(self, speed):
    profile = self.planner.follow_profile
    return desired_follow_distance(speed, speed, get_T_FOLLOW(self.personality, profile), get_stop_distance(self.personality, profile))

  @staticmethod
  def fail_on_solver_reset():
    pytest.fail("MPC solver reset during Proton following simulation")

  def step(self, lead_speed, lead_visible=True, lead_speed_error=0.0, lead_distance_error=0.0):
    self.cs.out.vEgo = self.speed
    self.cs.out.aEgo = self.acceleration
    self.cs.out.standstill = self.speed < 0.01
    self.lead_samples.append((self.gap + lead_distance_error, lead_speed + lead_speed_error))
    if self.frame % round(DT_MDL / DT_CTRL) == 0:
      radar = log.RadarState.new_message()
      radar.leadOne.status = lead_visible
      radar.leadOne.dRel, radar.leadOne.vLead = self.lead_samples[0]
      radar.leadOne.aLeadK = 0.0  # Exercise camera speed updates without perfect lead acceleration.
      radar.leadOne.aLeadTau = 1.5
      radar.leadOne.modelProb = 1.0
      model = log.ModelDataV2.new_message()
      model.position.x = ((self.speed + 0.5) * np.array(ModelConstants.T_IDXS)).tolist()
      model.velocity.x = [self.speed + 0.5] * len(ModelConstants.T_IDXS)
      model.acceleration.x = [0.0] * len(ModelConstants.T_IDXS)
      self.planner.update({'carState': self.cs.out, 'controlsState': self.controls_state,
                           'radarState': radar, 'modelV2': model})
      assert self.planner.mpc.solution_status == 0
      self.plan.speeds = self.planner.v_desired_trajectory.tolist()
      self.plan.accels = self.planner.a_desired_trajectory.tolist()

    limits = CarInterface.get_pid_accel_limits(self.cp, self.speed, self.controls_state.vCruise / 3.6)
    elapsed = (self.frame % round(DT_MDL / DT_CTRL)) * DT_CTRL
    self.cc.actuators.accel = self.long_control.update(True, self.cs.out, self.plan, limits, elapsed,
                                                     experimental_mode=self.controls_state.experimentalMode)
    _, can_sends = self.controller.update(self.cc, self.cs, int(self.frame * DT_CTRL * 1e9))
    if self.frame % 2 == 0:
      self.parser.update_strings([can_list_to_can_capnp(can_sends, logMonoTime=int((self.frame + 1) * DT_CTRL * 1e9))])
      values = self.parser.vl["ACC_CMD"]
      assert values["ACC_REQ"] == 1
      assert values["CRUISE_DISABLED"] == 0
      assert values["NOT_GAS_OVERRIDE"] == 1
      command_can = values["CMD"]
      if self.cs.out.standstill:
        assert values["MOTION_CONTROL"] == 5
      elif command_can < 0.0:
        assert values["MOTION_CONTROL"] == 4
      elif command_can > 0.0:
        assert values["MOTION_CONTROL"] == 6
      else:
        assert values["MOTION_CONTROL"] in ((1,) if self.distance_bar == 1 else (1, 4, 6))
      self.command = command_can / (15.0 if command_can >= 0.0 else 18.0)
      self.brake_mode = self.parser.vl["ACC_CMD"]["MOTION_CONTROL"] == 4

    self.actuator_commands.append(self.command)
    # A 0.15s first-order response follows the configured pure command delay.
    self.acceleration += DT_CTRL / (0.15 + DT_CTRL) * (self.actuator_commands[0] - self.acceleration)
    previous_speed = self.speed
    self.speed = max(0.0, self.speed + self.acceleration * DT_CTRL)
    self.gap += (lead_speed - (self.speed + previous_speed) / 2.0) * DT_CTRL
    self.frame += 1
    return (self.frame * DT_CTRL, self.gap, self.speed, self.acceleration, self.command, self.brake_mode)


def run_proton_following(speed, lead_speed, duration=60.0, actuator_delay=0.4, lead_visible=lambda _: True):
  plant = ProtonFollowingPlant(speed, actuator_delay=actuator_delay)
  output = np.array([plant.step(float(lead_speed(frame * DT_CTRL)), lead_visible(frame * DT_CTRL))
                     for frame in range(round(duration / DT_CTRL))])
  return plant, output


@pytest.mark.parametrize("speed", [5.0, 15.0, 25.0])
@pytest.mark.parametrize("actuator_delay", [0.4, 0.5])
def test_proton_one_bar_settles_with_delayed_actuation(speed, actuator_delay):
  plant, output = run_proton_following(speed, lambda _: speed, actuator_delay=actuator_delay)
  tail = output[-1000:]
  assert np.min(output[:, 1]) > 4.0
  assert abs(np.mean(tail[:, 1]) - plant.target_gap(speed)) < 1.5
  assert np.ptp(tail[:, 1]) < 1.0, "gap keeps oscillating instead of settling"
  assert np.max(np.abs(tail[:, 2] - speed)) < 0.15
  assert np.max(np.abs(tail[:, 4])) < 0.2, "repeated acceleration/braking after settling"


def test_proton_one_bar_settles_after_lead_slows():
  def lead_speed(t):
    return float(np.interp(t, [0.0, 20.0, 25.0, 60.0], [25.0, 25.0, 15.0, 15.0]))
  # The stronger gap penalty can open extra room during a slowdown. Observe
  # convergence for the same 100s as the generic following test, while also
  # checking the transient so a late recovery cannot conceal unsafe behavior.
  plant, output = run_proton_following(25.0, lead_speed, duration=100.0)
  tail = output[-1000:]
  assert np.min(output[:, 1]) > 4.0
  assert np.min(output[:, 3]) > -3.0, "moderate lead slowdown caused excessive braking"
  assert np.max(np.abs(np.diff(output[:, 4]))) < 0.3, "ordinary braking command jumped abruptly"
  excess_gaps = [np.mean(output[start:start + 1000, 1]) - plant.target_gap(15.0) for start in (4000, 5000, 6000)]
  assert excess_gaps[0] > excess_gaps[1] > excess_gaps[2], "excess gap is not converging after the slowdown"
  assert abs(np.mean(tail[:, 1]) - plant.target_gap(15.0)) < 1.5
  assert np.ptp(tail[:, 1]) < 1.0
  assert np.max(np.abs(tail[:, 2] - 15.0)) < 0.15


@pytest.mark.parametrize("speed", [5.0, 15.0, 25.0])
@pytest.mark.parametrize("actuator_delay", [0.4, 0.5])
def test_proton_one_bar_recovers_promptly_after_speed_dip(speed, actuator_delay):
  def lead_speed(t):
    return float(np.interp(t, [0.0, 20.0, 22.0, 25.0, 29.0, 60.0], [speed, speed, speed - 2.0, speed - 2.0, speed, speed]))

  plant, output = run_proton_following(speed, lead_speed, actuator_delay=actuator_delay)
  slowdown = output[(output[:, 0] >= 20.0) & (output[:, 0] < 25.0)]
  recovery = output[(output[:, 0] >= 25.0) & (output[:, 0] < 40.0)]
  # A 1 m/s^2 lead slowdown should not turn into a deep brake and a long
  # catch-up. Bound both the transient and the later settled result.
  assert np.min(output[:, 1]) > 4.0
  # Allow one encoded brake-command step (1/18 m/s^2) around the 1.1 limit.
  # Pair peak braking with an actual-jerk guard so a softer onset cannot hide
  # behind a peak-only check. Stop/collision margins are tested separately.
  assert np.min(slowdown[:, 3]) > (-1.1 - 1.0 / 18.0 if speed >= 20.0 else -1.3)
  if speed >= 20.0:
    transition = output[(output[:, 0] >= 20.0) & (output[:, 0] < 40.0)]
    assert np.max(np.abs(np.diff(transition[:, 3]) / DT_CTRL)) < 1.45
  assert np.min(recovery[:, 2]) > speed - 2.65, "kept braking below the lead's new speed"
  steady_targets = np.array([plant.target_gap(v) for v in recovery[:, 2]])
  assert np.max(recovery[:, 1] - steady_targets) < 3.5, "left too much extra room after the lead recovered"
  after_recovery = output[(output[:, 0] >= 31.0) & (output[:, 0] < 40.0)]
  assert np.min(after_recovery[:, 2]) > speed - 0.25, "still falling behind two seconds after the lead reached its speed"
  assert np.max(np.abs(np.diff(slowdown[:, 4]))) < 0.2, "braking command jumped abruptly"
  tail = output[-1000:]
  assert abs(np.mean(tail[:, 1]) - plant.target_gap(speed)) < 1.0
  assert np.ptp(tail[:, 1]) < 0.5


@pytest.mark.parametrize("actuator_delay", [0.4, 0.5])
def test_proton_one_bar_recovers_after_approaching_a_slower_lead(actuator_delay):
  plant = ProtonFollowingPlant(25.0, actuator_delay=actuator_delay)
  plant.gap = 90.0
  plant.lead_samples.clear()
  plant.lead_samples.extend([(90.0, 15.0)] * plant.lead_samples.maxlen)
  rows = []
  for frame in range(6000):
    lead_speed = float(np.interp(frame * DT_CTRL, [0.0, 30.0, 34.0, 60.0], [15.0, 15.0, 18.0, 18.0]))
    rows.append(plant.step(lead_speed))
  output = np.array(rows)
  assert np.min(output[:, 1]) > 4.0
  assert output[0, 4] > -2.0, "lead acquisition amplified the planned braking"
  jerk = np.diff(output[:, 3], prepend=0.0) / DT_CTRL
  assert np.max(np.abs(jerk)) < 13.0, "lead acquisition caused a sharp brake onset"
  assert np.min(output[:, 3]) > -2.65
  # The suddenly acquired lead is 10 m/s slower. The existing initial solve
  # changes the command by 0.67 m/s^2; bound that separately from later follow.
  assert np.max(np.abs(np.diff(output[:, 4]))) < 0.7
  assert np.max(np.abs(np.diff(output[output[:, 0] >= 1.0, 4]))) < 0.3
  recovery = output[(output[:, 0] >= 34.0) & (output[:, 0] < 45.0)]
  steady_targets = np.array([plant.target_gap(v) for v in recovery[:, 2]])
  assert np.max(recovery[:, 1] - steady_targets) < 4.0
  assert output[round(36.0 / DT_CTRL) - 1, 2] > 17.75, "slow to re-follow after matching a slower lead"
  assert abs(np.mean(output[-1000:, 1]) - plant.target_gap(18.0)) < 1.0


@pytest.mark.parametrize("actuator_delay", [0.4, 0.5])
def test_proton_one_bar_acquires_slower_lead_after_cruising(actuator_delay):
  plant = ProtonFollowingPlant(25.0, actuator_delay=actuator_delay)
  plant.controls_state.vCruise = 90.0
  rows = [plant.step(25.0, lead_visible=False) for _ in range(2000)]
  before_command = rows[-1][4]
  plant.gap = 90.0
  plant.lead_samples.clear()
  plant.lead_samples.extend([(90.0, 15.0)] * plant.lead_samples.maxlen)
  rows.extend(plant.step(15.0) for _ in range(6000))
  output = np.array(rows)
  following = output[2000:]
  assert abs(following[0, 4] - before_command) < 2.0
  jerk = np.diff(output[1999:, 3]) / DT_CTRL
  assert np.max(np.abs(jerk)) < 13.0
  assert np.min(following[:, 3]) > -2.65
  assert np.min(following[:, 1]) > 4.0
  tail = following[-1000:]
  assert abs(np.mean(tail[:, 1]) - plant.target_gap(15.0)) < 1.0
  assert np.max(np.abs(tail[:, 2] - 15.0)) < 0.15


@pytest.mark.parametrize("speed", [5.0, 25.0])
def test_proton_one_bar_bounds_response_to_camera_distance_errors(speed):
  plant = ProtonFollowingPlant(speed, actuator_delay=0.5)
  rows = []
  for frame in range(6000):
    # Only the camera's distance changes; the physical lead stays steady.
    error = float(0.3 * np.sin(frame * DT_CTRL * 2.0 * np.pi * 2.0))
    rows.append(plant.step(speed, lead_distance_error=error))
  tail = np.array(rows)[-1000:]
  assert np.max(np.abs(tail[:, 4])) < 0.5
  assert np.max(np.abs(np.diff(tail[:, 3]) / DT_CTRL)) < 2.0
  assert np.max(np.abs(tail[:, 2] - speed)) < 0.15
  assert np.ptp(tail[:, 1]) < 0.5
  assert abs(np.mean(tail[:, 1]) - plant.target_gap(speed)) < 2.0


@pytest.mark.parametrize("planned_accel", [-1.5, 1.0])
@pytest.mark.parametrize(("model", "personality", "experimental_mode"), [
  (CAR.S70, log.LongitudinalPersonality.aggressive, False),
  (CAR.S70, log.LongitudinalPersonality.standard, False),
  (CAR.S70, log.LongitudinalPersonality.relaxed, False),
  (CAR.S70, log.LongitudinalPersonality.aggressive, True),
  (CAR.X50, log.LongitudinalPersonality.aggressive, False),
  (CAR.X70, log.LongitudinalPersonality.aggressive, False),
  (CAR.X90, log.LongitudinalPersonality.aggressive, False),
])
def test_proton_feedforward_bound_is_one_bar_acc_only(planned_accel, model, personality, experimental_mode):
  cp = CarInterface.get_non_essential_params(model)
  controller = LongControl(cp)
  state = car.CarState.new_message()
  state.vEgo = 25.0
  plan = log.LongitudinalPlan.new_message()
  times = np.array(ModelConstants.T_IDXS[:CONTROL_N])
  # Braking/throttle rises quickly then levels off. A constant-jerk
  # extrapolation invents a stronger command than this curve ever asks for.
  plan.accels = (planned_accel * (1.0 - np.exp(-times / 0.08))).tolist()
  plan.speeds = (25.0 + planned_accel * (times - 0.08 * (1.0 - np.exp(-times / 0.08)))).tolist()
  plan.personality = personality
  command = controller.update(True, state, plan, (-3.5, 3.0), 0.0, experimental_mode=experimental_mode)
  if model == CAR.S70 and personality == log.LongitudinalPersonality.aggressive and not experimental_mode:
    assert min(plan.accels) <= command <= max(plan.accels)
  else:
    # Measured outputs of this curve before the one-bar conversion fix.
    assert command == pytest.approx(-2.521060893 if planned_accel < 0.0 else 1.603441303)


@pytest.mark.parametrize(("planned_accel", "actual_speed"), [(-3.5, 25.0), (-1.5, 27.0)])
def test_proton_one_bar_feedforward_bound_preserves_braking_authority(planned_accel, actual_speed):
  cp = CarInterface.get_non_essential_params(CAR.S70)
  controller = LongControl(cp)
  state = car.CarState.new_message()
  state.vEgo = actual_speed
  plan = log.LongitudinalPlan.new_message()
  plan.personality = log.LongitudinalPersonality.aggressive
  plan.accels = [planned_accel] * CONTROL_N
  plan.speeds = (25.0 + planned_accel * np.array(ModelConstants.T_IDXS[:CONTROL_N])).tolist()
  command = controller.update(True, state, plan, (-3.5, 3.0), 0.0)
  if actual_speed == 25.0:
    assert command == pytest.approx(-3.5), "full planned braking was weakened"
  else:
    assert command < planned_accel, "speed-error feedback was incorrectly capped with feedforward"


@pytest.mark.parametrize("actuator_delay", [0.4, 0.5])
def test_proton_one_bar_repeated_slowdowns_do_not_grow_the_gap(actuator_delay):
  def lead_speed(t):
    phase = (t - 20.0) % 20.0
    return 25.0 if t < 20.0 else float(np.interp(phase, [0.0, 2.0, 5.0, 9.0, 20.0], [25.0, 23.0, 23.0, 25.0, 25.0]))

  plant, output = run_proton_following(25.0, lead_speed, duration=100.0, actuator_delay=actuator_delay)
  following = output[output[:, 0] >= 20.0]
  steady_targets = np.array([plant.target_gap(v) for v in following[:, 2]])
  assert np.min(following[:, 1]) > 4.0
  assert np.max(following[:, 1] - steady_targets) < 3.5, "successive speed dips opened a growing gap"
  assert np.min(following[:, 3]) > -1.3
  assert np.max(np.abs(np.diff(following[:, 4]))) < 0.2


@pytest.mark.parametrize("speed", [5.0, 25.0])
def test_proton_one_bar_bounds_response_to_small_camera_speed_errors(speed):
  plant = ProtonFollowingPlant(speed, actuator_delay=0.5)
  rows = []
  for frame in range(6000):
    # Perturb the observed speed only. The real lead continues at constant
    # speed, so this checks sensor sensitivity rather than lead acceleration.
    error = float(0.15 * np.sin(frame * DT_CTRL * 2.0 * np.pi * 2.0))
    rows.append(plant.step(speed, lead_speed_error=error))
  output = np.array(rows)
  tail = output[-1000:]
  assert np.min(output[:, 1]) > 4.0
  assert np.max(np.abs(tail[:, 4])) < 0.3, "small speed errors caused large brake/throttle corrections"
  assert np.max(np.abs(tail[:, 2] - speed)) < 0.15
  assert np.ptp(tail[:, 1]) < 0.5
  assert abs(np.mean(tail[:, 1]) - plant.target_gap(speed)) < 2.0


def test_proton_one_bar_recovers_after_brief_camera_dropout():
  plant, output = run_proton_following(25.0, lambda _: 25.0, lead_visible=lambda t: not 20.0 <= t < 20.5)
  tail = output[-1000:]
  assert np.min(output[:, 1]) > 4.0
  assert abs(np.mean(tail[:, 1]) - plant.target_gap(25.0)) < 1.5
  assert np.ptp(tail[:, 1]) < 1.0
  assert np.max(np.abs(tail[:, 2] - 25.0)) < 0.15


def test_proton_one_bar_stops_behind_a_lead_from_traffic_speed():
  def lead_speed(t):
    return float(np.interp(t, [0.0, 20.0, 25.0, 60.0], [5.0, 5.0, 0.0, 0.0]))

  plant, output = run_proton_following(5.0, lead_speed)
  tail = output[-1000:]
  assert np.min(output[:, 1]) > 3.5
  assert abs(np.mean(tail[:, 1]) - plant.target_gap(0.0)) < 0.5
  assert np.max(tail[:, 2]) < 0.01


@pytest.mark.parametrize(("speed", "lead_decel"), [(10.0, 1.0), (15.0, 1.0), (15.0, 2.0), (25.0, 2.0), (25.0, 3.0)])
def test_proton_one_bar_avoids_collision_when_lead_stops(speed, lead_decel):
  stop_time = 20.0 + speed / lead_decel

  def lead_speed(t):
    return float(np.interp(t, [0.0, 20.0, stop_time, 80.0], [speed, speed, 0.0, 0.0]))

  _, output = run_proton_following(speed, lead_speed, duration=80.0, actuator_delay=0.5)
  # Match the collision criterion used by the existing longitudinal maneuvers.
  # This broader check does not assert that the nominal 4m gap is always held.
  assert np.min(output[:, 1]) > 0.4
  assert np.max(output[-1000:, 2]) < 0.01


def test_proton_one_bar_tracks_cruise_changes_without_a_lead():
  plant = ProtonFollowingPlant(5.0)
  rows = []
  for frame in range(6000):
    plant.controls_state.vCruise = (10.0 if frame < 2000 else 5.0) * 3.6
    rows.append(plant.step(0.0, lead_visible=False))
  output = np.array(rows)
  assert np.max(np.abs(output[1500:2000, 2] - 10.0)) < 0.15
  assert np.max(np.abs(output[-1000:, 2] - 5.0)) < 0.15


@pytest.mark.parametrize("distance_bar", [1, 2, 3])
@pytest.mark.parametrize("profile", [LongitudinalFollowProfile.default, LongitudinalFollowProfile.proton_x50_fl])
def test_selected_bar_settings_reach_native_mpc(distance_bar, profile, monkeypatch):
  plant = ProtonFollowingPlant(5.0, distance_bar=distance_bar)
  mpc = plant.planner.mpc
  mpc.follow_profile = profile
  captured_constraints = []
  captured_costs = []
  original_set_weights = mpc.set_cost_weights

  def capture_weights(costs, constraints):
    captured_constraints.append(constraints)
    captured_costs.append(costs)
    original_set_weights(costs, constraints)

  monkeypatch.setattr(mpc, "set_cost_weights", capture_weights)
  # Make the lead the closest obstacle, so the generated solver's effective
  # stop-gap offset is checked rather than the synthetic cruise obstacle.
  plant.gap = 6.0
  plant.lead_samples.clear()
  plant.lead_samples.extend([(6.0, 5.0)] * plant.lead_samples.maxlen)
  plant.step(5.0)
  is_proton = profile == LongitudinalFollowProfile.proton_x50_fl
  follow_times = {1: 0.81, 2: 1.02, 3: 1.25} if is_proton else {1: 1.20, 2: 1.25, 3: 1.40}
  stop_offsets = {1: 1.5, 2: 1.0, 3: 0.0} if is_proton else {1: 0.0, 2: 0.0, 3: 0.0}
  assert np.all(mpc.params[:, 4] == follow_times[distance_bar])
  assert mpc.source == 'lead0'
  assert mpc.params[0, 2] == pytest.approx(6.0 + 5.0**2 / (2 * 2.5) + stop_offsets[distance_bar])
  custom_one_bar = profile == LongitudinalFollowProfile.proton_x50_fl and distance_bar == 1
  expected_smoothing = [200.0, 5.0] if distance_bar == 3 and not is_proton else [100.0, 2.5]
  assert captured_costs[-1][0] == (50.0 if custom_one_bar else 3.0)
  assert captured_costs[-1][4:] == expected_smoothing
  assert np.all(mpc.params[:, 5] == (1.0 if custom_one_bar else 0.75))
  assert captured_constraints[-1] == [1e6, 1e6, 1e6, 6000.0 if custom_one_bar else 100.0]
  for speed, stop_cost in ((0.0, 10000.0), (10.0, 2000.0), (25.0, 2000.0)):
    mpc.set_cur_state(speed, 0.0)
    mpc.set_weights(personality=plant.personality)
    assert captured_constraints[-1][-1] == (stop_cost if custom_one_bar else 100.0)

  mpc.mode = 'blended'
  mpc.set_weights(personality=plant.personality)
  assert captured_costs[-1] == [0.0, 0.1, 0.2, 5.0, 40.0, 1.0]
  assert captured_constraints[-1] == [1e6, 1e6, 1e6, 50.0]


@pytest.mark.parametrize("command", [-18.0, -0.6, -0.5, -0.49, -0.1, 0.0, 0.1, 0.49, 0.5, 0.6, 12.0])
def test_one_bar_motion_mode_matches_the_encoded_command(command):
  plant = ProtonFollowingPlant(25.0)
  plant.cs.out.vEgo = 25.0
  plant.cc.actuators.accel = command / (15.0 if command >= 0.0 else 18.0)
  plant.controller._prev_accel_cmd = command
  original_can = create_acc_cmd(plant.controller.packer, command, True, False, False, False, False)
  plant.parser.update_strings([can_list_to_can_capnp([original_can])])
  command_signals = ("CMD", "CMD_OFFSET1", "CMD_OFFSET2")
  original_amounts = [plant.parser.vl["ACC_CMD"][signal] for signal in command_signals]
  _, can_sends = plant.controller.update(plant.cc, plant.cs, 0)
  plant.parser.update_strings([can_list_to_can_capnp(can_sends)])
  values = plant.parser.vl["ACC_CMD"]
  expected_mode = 4 if values["CMD"] < 0.0 else 6 if values["CMD"] > 0.0 else 1
  assert values["MOTION_CONTROL"] == expected_mode
  assert [values[signal] for signal in command_signals] == original_amounts


def test_one_bar_keeps_fractional_throttle_ramp_state_before_can_rounding():
  plant = ProtonFollowingPlant(25.0)
  plant.cs.out.vEgo = 25.0
  plant.cc.actuators.accel = 1.2
  for frame in range(100):
    _, can_sends = plant.controller.update(plant.cc, plant.cs, int(frame * DT_CTRL * 1e9))
    if frame % 2 == 0:
      plant.parser.update_strings([can_list_to_can_capnp(can_sends)])
  assert plant.parser.vl["ACC_CMD"]["CMD"] > 10.0, "rounding discarded each small throttle increment"


@pytest.mark.parametrize("resume", [False, True])
def test_one_bar_rounding_preserves_stop_and_resume_flags(resume):
  plant = ProtonFollowingPlant(0.0)
  plant.cs.out.standstill = True
  plant.cs.cruise_standstill = resume
  plant.cs.res_btn_pressed = resume
  plant.cc.actuators.accel = 0.1 / 15.0
  plant.controller._prev_accel_cmd = 0.1
  _, can_sends = plant.controller.update(plant.cc, plant.cs, 0)
  plant.parser.update_strings([can_list_to_can_capnp(can_sends)])
  values = plant.parser.vl["ACC_CMD"]
  assert values["CMD"] == 0.0
  assert values["SET_ME_X6A"] == 0xFA  # The original positive request must retain this flag even when CMD rounds to zero.
  assert values["MOTION_CONTROL"] == (9 if resume else 5)
  assert values["ACC_REQ"] == (0 if resume else 1)


@pytest.mark.parametrize(("distance_bar", "close_follow_enabled"), [(2, True), (3, True), (1, False)])
def test_command_rounding_leaves_other_profiles_unchanged(distance_bar, close_follow_enabled):
  plant = ProtonFollowingPlant(25.0, distance_bar=distance_bar)
  plant.controller.close_follow_enabled = close_follow_enabled
  plant.cs.out.vEgo = 25.0
  plant.cc.actuators.accel = -0.1 / 18.0
  _, can_sends = plant.controller.update(plant.cc, plant.cs, 0)
  plant.parser.update_strings([can_list_to_can_capnp(can_sends)])
  assert plant.parser.vl["ACC_CMD"]["CMD"] == 0.0
  assert plant.parser.vl["ACC_CMD"]["MOTION_CONTROL"] == 4
