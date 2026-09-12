#!/usr/bin/env python3
import itertools
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from parameterized import parameterized_class

from openpilot.common.params import Params
from openpilot.common.realtime import DT_MDL
from cereal import log

from openpilot.selfdrive.controls.lib import longitudinal_planner as longitudinal_planner_module
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import LEAD_PERSIST_FRAMES, LongitudinalFollowProfile, LongitudinalMpc, \
                                                                    desired_follow_distance, get_approach_t_follow_boost, get_follow_profile, \
                                                                    get_jerk_factor, get_lead_obstacle_offset, get_stop_distance, get_T_FOLLOW, \
                                                                    project_missing_lead
from openpilot.selfdrive.test.longitudinal_maneuvers.maneuver import Maneuver


def run_following_distance_simulation(v_lead, t_end=100.0, e2e=False):
  man = Maneuver(
    '',
    duration=t_end,
    initial_speed=float(v_lead),
    lead_relevancy=True,
    initial_distance_lead=100,
    speed_lead_values=[v_lead],
    breakpoints=[0.],
    e2e=e2e,
  )
  valid, output = man.evaluate()
  assert valid
  return output[-1,2] - output[-1,1]


class TestFollowGapTuning(unittest.TestCase):
  BAR_PERSONALITIES = {
    1: log.LongitudinalPersonality.aggressive,
    2: log.LongitudinalPersonality.standard,
    3: log.LongitudinalPersonality.relaxed,
  }
  FOLLOW_PROFILE = LongitudinalFollowProfile.proton_x50_fl

  def test_bar_follow_times(self):
    follow_times = {bar: get_T_FOLLOW(personality, self.FOLLOW_PROFILE) for bar, personality in self.BAR_PERSONALITIES.items()}

    self.assertEqual(follow_times, {1: 0.90, 2: 1.02, 3: 1.25})

  def test_default_follow_times_remain_unchanged(self):
    follow_times = {bar: get_T_FOLLOW(personality) for bar, personality in self.BAR_PERSONALITIES.items()}

    self.assertEqual(follow_times, {1: 1.20, 2: 1.25, 3: 1.40})

  def test_bar_gap_steps_at_90_kph(self):
    v_ego = v_lead = 25.0
    gaps = [desired_follow_distance(v_ego, v_lead, get_T_FOLLOW(personality, self.FOLLOW_PROFILE),
                                    get_stop_distance(personality, self.FOLLOW_PROFILE))
            for personality in self.BAR_PERSONALITIES.values()]

    self.assertEqual(gaps, [26.5, 30.0, 36.75])
    self.assertEqual(get_lead_obstacle_offset(log.LongitudinalPersonality.aggressive, self.FOLLOW_PROFILE), 1.5)
    self.assertEqual(get_lead_obstacle_offset(log.LongitudinalPersonality.standard, self.FOLLOW_PROFILE), 1.0)
    self.assertEqual(get_lead_obstacle_offset(log.LongitudinalPersonality.relaxed, self.FOLLOW_PROFILE), 0.0)

  def test_stop_targets_and_steady_gap_order(self):
    self.assertEqual([get_stop_distance(p, self.FOLLOW_PROFILE) for p in self.BAR_PERSONALITIES.values()], [4.0, 4.5, 5.5])
    self.assertEqual([get_stop_distance(p) for p in self.BAR_PERSONALITIES.values()], [5.5, 5.5, 5.5])
    for speed in (0.0, 5.0, 15.0, 25.0, 35.0):
      gaps = [desired_follow_distance(speed, speed, get_T_FOLLOW(p, self.FOLLOW_PROFILE), get_stop_distance(p, self.FOLLOW_PROFILE))
              for p in self.BAR_PERSONALITIES.values()]
      self.assertLess(gaps[0], gaps[1])
      self.assertLess(gaps[1], gaps[2])

  def test_three_bar_matches_previous_standard_settings(self):
    three_bar = log.LongitudinalPersonality.relaxed
    old_two_bar = log.LongitudinalPersonality.standard
    for setting in (get_T_FOLLOW, get_stop_distance, get_jerk_factor):
      self.assertEqual(setting(three_bar, self.FOLLOW_PROFILE), setting(old_two_bar))
    self.assertEqual(get_jerk_factor(three_bar), 1.0)

  def test_one_bar_headway_keeps_minimum_candidate_margin(self):
    # Guard against accidentally restoring the rejected 0.28s / 2.5m tune.
    # This is a static margin check, not a test of closed-loop stability.
    personality = log.LongitudinalPersonality.aggressive
    t_follow = get_T_FOLLOW(personality, self.FOLLOW_PROFILE)
    stop_distance = get_stop_distance(personality, self.FOLLOW_PROFILE)

    self.assertGreaterEqual(t_follow, 0.85)
    self.assertGreaterEqual(stop_distance, 3.5)

    for kph in (30.0, 50.0, 70.0, 90.0, 110.0):
      v = kph / 3.6
      gap = desired_follow_distance(v, v, t_follow, stop_distance)
      self.assertGreaterEqual(gap / v, 1.0, f"only {gap / v:.2f}s of headway at {kph:.0f} km/h")

  def test_approach_boost_is_limited_to_custom_one_bar(self):
    radarstate = SimpleNamespace(
      leadOne=SimpleNamespace(status=True, dRel=12.0, vLead=15.0, aLeadK=-3.0),
      leadTwo=SimpleNamespace(status=False),
    )

    boosts = {bar: get_approach_t_follow_boost(25.0, radarstate, personality, self.FOLLOW_PROFILE)
              for bar, personality in self.BAR_PERSONALITIES.items()}

    self.assertEqual(boosts, {1: 0.20, 2: 0.0, 3: 0.0})

  def test_approach_boost_preserves_extra_one_bar_margin(self):
    scenarios = [
      # Steady lead, moderate closing, and close braking lead.
      (20.0, 20.0, 0.0, 20.0),
      (25.0, 23.0, -0.8, 25.0),
      (12.0, 21.5, -2.0, 25.0),
    ]

    for d_rel, v_lead, a_lead, v_ego in scenarios:
      with self.subTest(d_rel=d_rel, v_lead=v_lead, a_lead=a_lead, v_ego=v_ego):
        radarstate = SimpleNamespace(
          leadOne=SimpleNamespace(status=True, dRel=d_rel, vLead=v_lead, aLeadK=a_lead),
          leadTwo=SimpleNamespace(status=False),
        )
        actual_follow_times = []
        for personality in self.BAR_PERSONALITIES.values():
          actual_follow_times.append(get_T_FOLLOW(personality, self.FOLLOW_PROFILE) +
                                     get_approach_t_follow_boost(v_ego, radarstate, personality, self.FOLLOW_PROFILE))

        # One bar may briefly ask for more room than the new, closer two-bar
        # target. Do not reduce its approach margin just to enforce bar order.
        self.assertGreaterEqual(actual_follow_times[0], get_T_FOLLOW(self.BAR_PERSONALITIES[1], self.FOLLOW_PROFILE))
        self.assertLess(actual_follow_times[0], actual_follow_times[2])
        self.assertEqual(actual_follow_times[1], 1.02)
        self.assertEqual(actual_follow_times[2], 1.25)
        self.assertLess(actual_follow_times[1], actual_follow_times[2])

  def test_lead_persistence_is_isolated_per_slot(self):
    mpc = LongitudinalMpc.__new__(LongitudinalMpc)
    mpc.x0 = np.array([0.0, 20.0, 0.0])
    mpc._lead_persist_frames = LEAD_PERSIST_FRAMES
    mpc._last_lead_x = [0.0, 0.0]
    mpc._last_lead_v = [0.0, 0.0]
    mpc._last_lead_a = [0.0, 0.0]
    mpc._lead_gone_frames = [LEAD_PERSIST_FRAMES, LEAD_PERSIST_FRAMES]

    live_lead = SimpleNamespace(status=True, dRel=30.0, vLead=18.0, aLeadK=0.0, aLeadTau=1.5)
    missing_lead = SimpleNamespace(status=False)

    mpc.process_lead(live_lead, 0)
    missing_trajectory = mpc.process_lead(missing_lead, 1)
    self.assertGreaterEqual(missing_trajectory[0, 0], 50.0)
    self.assertEqual(mpc._lead_gone_frames, [0, LEAD_PERSIST_FRAMES])

    persisted_trajectory = mpc.process_lead(missing_lead, 0)
    self.assertLess(persisted_trajectory[0, 0], 50.0)
    self.assertEqual(mpc._lead_gone_frames, [1, LEAD_PERSIST_FRAMES])

  def test_lead_persistence_uses_real_planner_time_and_relative_motion(self):
    self.assertEqual(LEAD_PERSIST_FRAMES, round(3.0 / DT_MDL))

    d_rel, v_lead, a_lead = project_missing_lead(30.0, 20.0, 0.0, 20.0, 0.0)
    self.assertAlmostEqual(d_rel, 30.0)
    self.assertAlmostEqual(v_lead, 20.0)
    self.assertAlmostEqual(a_lead, 0.0)

    closing_d_rel, _, _ = project_missing_lead(30.0, 10.0, 0.0, 20.0, 0.0)
    self.assertAlmostEqual(closing_d_rel, 29.5)

    mpc = LongitudinalMpc.__new__(LongitudinalMpc)
    mpc.x0 = np.array([0.0, 20.0, 0.0])
    mpc._lead_persist_frames = LEAD_PERSIST_FRAMES
    mpc._last_lead_x = [0.0, 0.0]
    mpc._last_lead_v = [0.0, 0.0]
    mpc._last_lead_a = [0.0, 0.0]
    mpc._lead_gone_frames = [LEAD_PERSIST_FRAMES, LEAD_PERSIST_FRAMES]

    live_lead = SimpleNamespace(status=True, dRel=30.0, vLead=20.0, aLeadK=0.0, aLeadTau=1.5)
    missing_lead = SimpleNamespace(status=False)
    mpc.process_lead(live_lead, 0)
    for _ in range(LEAD_PERSIST_FRAMES):
      trajectory = mpc.process_lead(missing_lead, 0)

    self.assertAlmostEqual(trajectory[0, 0], 30.0)
    self.assertEqual(mpc._lead_gone_frames[0], LEAD_PERSIST_FRAMES)
    self.assertGreaterEqual(mpc.process_lead(missing_lead, 0)[0, 0], 50.0)

  def test_follow_profile_is_x50_fl_only(self):
    self.assertEqual(get_follow_profile("proton", "PROTON S70"), LongitudinalFollowProfile.proton_x50_fl)
    self.assertEqual(get_follow_profile("proton", "PROTON X50"), LongitudinalFollowProfile.default)
    self.assertEqual(get_follow_profile("honda", "HONDA CIVIC 2016"), LongitudinalFollowProfile.default)

  def test_planner_passes_selected_vehicle_profile_to_mpc(self):
    params = SimpleNamespace(get=lambda _: str(log.LongitudinalPersonality.standard))
    x50_fl_cp = SimpleNamespace(carName="proton", carFingerprint="PROTON S70")
    other_cp = SimpleNamespace(carName="proton", carFingerprint="PROTON X50")

    with patch.object(longitudinal_planner_module, "Params", return_value=params), \
         patch.object(longitudinal_planner_module, "LongitudinalMpc") as mpc_class:
      x50_fl_planner = longitudinal_planner_module.LongitudinalPlanner(x50_fl_cp)
      mpc_class.assert_called_once_with(follow_profile=LongitudinalFollowProfile.proton_x50_fl)
      self.assertEqual(x50_fl_planner.follow_profile, LongitudinalFollowProfile.proton_x50_fl)

      mpc_class.reset_mock()
      other_planner = longitudinal_planner_module.LongitudinalPlanner(other_cp)
      mpc_class.assert_called_once_with(follow_profile=LongitudinalFollowProfile.default)
      self.assertEqual(other_planner.follow_profile, LongitudinalFollowProfile.default)


@parameterized_class(("e2e", "personality", "speed"), itertools.product(
                      [True, False], # e2e
                      [log.LongitudinalPersonality.relaxed, # personality
                       log.LongitudinalPersonality.standard,
                       log.LongitudinalPersonality.aggressive],
                      [0,10,35])) # speed
class TestFollowingDistance(unittest.TestCase):
  def test_following_distance(self):
    params = Params()
    params.put("LongitudinalPersonality", str(self.personality))
    v_lead = float(self.speed)
    simulation_steady_state = run_following_distance_simulation(v_lead, e2e=self.e2e)
    correct_steady_state = desired_follow_distance(v_lead, v_lead, get_T_FOLLOW(self.personality))
    err_ratio = 0.2 if self.e2e else 0.1
    self.assertAlmostEqual(simulation_steady_state, correct_steady_state, delta=(err_ratio * correct_steady_state + .5))


if __name__ == "__main__":
  unittest.main()
