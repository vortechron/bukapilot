#!/usr/bin/env python3
import itertools
import unittest
from types import SimpleNamespace

import numpy as np
from parameterized import parameterized_class

from openpilot.common.params import Params
from cereal import log

from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import LEAD_PERSIST_FRAMES, LongitudinalMpc, desired_follow_distance, \
                                                                    get_approach_t_follow_boost, get_T_FOLLOW
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

  def test_bar_follow_times(self):
    follow_times = {bar: get_T_FOLLOW(personality) for bar, personality in self.BAR_PERSONALITIES.items()}

    # One bar stays at the lowest high-speed value that passes the planner
    # simulation. Two bar moves almost to the same steady target, while its
    # small base step keeps it more conservative.
    self.assertEqual(follow_times, {1: 0.45, 2: 0.46, 3: 0.75})

  def test_bar_gap_steps_at_90_kph(self):
    v_ego = v_lead = 25.0
    gaps = [desired_follow_distance(v_ego, v_lead, get_T_FOLLOW(personality)) for personality in self.BAR_PERSONALITIES.values()]

    self.assertGreaterEqual(gaps[0], 15.25)
    self.assertAlmostEqual(gaps[1] - gaps[0], 0.25)
    self.assertAlmostEqual(gaps[2] - gaps[1], 7.25)

  def test_approach_boost_caps_keep_close_bars_closer(self):
    radarstate = SimpleNamespace(
      leadOne=SimpleNamespace(status=True, dRel=12.0, vLead=15.0, aLeadK=-3.0),
      leadTwo=SimpleNamespace(status=False),
    )

    boosts = {bar: get_approach_t_follow_boost(25.0, radarstate, personality) for bar, personality in self.BAR_PERSONALITIES.items()}

    self.assertEqual(boosts, {1: 0.58, 2: 0.58, 3: 0.60})

  def test_approach_boost_preserves_bar_order(self):
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
          actual_follow_times.append(get_T_FOLLOW(personality) + get_approach_t_follow_boost(v_ego, radarstate, personality))

        self.assertLess(actual_follow_times[0], actual_follow_times[1])
        self.assertLess(actual_follow_times[1], actual_follow_times[2])

  def test_lead_persistence_is_isolated_per_slot(self):
    mpc = LongitudinalMpc.__new__(LongitudinalMpc)
    mpc.x0 = np.array([0.0, 20.0, 0.0])
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
