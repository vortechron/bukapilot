#!/usr/bin/env python3
from enum import IntEnum
import os
import time
import numpy as np
from cereal import log
from openpilot.common.numpy_fast import clip
from openpilot.common.realtime import DT_MDL
from openpilot.common.swaglog import cloudlog
from openpilot.common.debug_logger import DebugLogger
# WARNING: imports outside of constants will not trigger a rebuild
from openpilot.selfdrive.modeld.constants import index_function
from openpilot.selfdrive.car.interfaces import ACCEL_MIN
from openpilot.selfdrive.controls.radard import _LEAD_ACCEL_TAU

if __name__ == '__main__':  # generating code
  from openpilot.third_party.acados.acados_template import AcadosModel, AcadosOcp, AcadosOcpSolver
else:
  from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.c_generated_code.acados_ocp_solver_pyx import AcadosOcpSolverCython

from casadi import SX, vertcat

MODEL_NAME = 'long'
LONG_MPC_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(LONG_MPC_DIR, "c_generated_code")
JSON_FILE = os.path.join(LONG_MPC_DIR, "acados_ocp_long.json")

SOURCES = ['lead0', 'lead1', 'cruise', 'e2e']

X_DIM = 3
U_DIM = 1
PARAM_DIM = 6
COST_E_DIM = 5
COST_DIM = COST_E_DIM + 1
CONSTR_DIM = 4

X_EGO_OBSTACLE_COST = 3.
X_EGO_COST = 0.
V_EGO_COST = 0.
A_EGO_COST = 0.
J_EGO_COST = 5.0
A_CHANGE_COST = 200.
DANGER_ZONE_COST = 100.
CRASH_DISTANCE = .25
LEAD_DANGER_FACTOR = 0.75
LIMIT_COST = 1e6
ACADOS_SOLVER_TYPE = 'SQP_RTI'


# Fewer timestamps don't hurt performance and lead to
# much better convergence of the MPC with low iterations
N = 12
MAX_T = 10.0
T_IDXS_LST = [index_function(idx, max_val=MAX_T, max_idx=N) for idx in range(N+1)]

T_IDXS = np.array(T_IDXS_LST)
FCW_IDXS = T_IDXS < 5.0
T_DIFFS = np.diff(T_IDXS, prepend=[0.])
COMFORT_BRAKE = 2.5
# This value is embedded in the generated solver. Per-profile stop distances
# are applied as an obstacle offset so Python and the generated C stay aligned.
STOP_DISTANCE = 5.5


class LongitudinalFollowProfile(IntEnum):
  default = 0
  proton_x50_fl = 1


PROTON_X50_FL_FINGERPRINT = "PROTON S70"
# The earlier 0.28s / 2.5m tune oscillated on the road. 0.90s / 4.0m was then
# road-tested as acceptable and 10% too far, so the follow time is 0.81s. The
# controller config includes 0.4-0.5s actuator delay; road validation is still
# required for every change here.
PROTON_X50_FL_ONE_BAR_T_FOLLOW = 0.81
PROTON_X50_FL_ONE_BAR_STOP_DISTANCE = 4.0
# Keep the gap penalty at the full target. In the delayed-loop simulation the
# stock 0.75 / 100 penalty braked later and harder and collided in stop cases.
PROTON_X50_FL_ONE_BAR_DANGER_ZONE_COST = 10000.
PROTON_X50_FL_ONE_BAR_DANGER_FACTOR = 1.0
# The boost grows the target while closing, which the driver felt as braking
# harder than the lead and dropping back. Halved from 0.20s after road feedback.
PROTON_X50_FL_ONE_BAR_MAX_APPROACH_BOOST = 0.10
# At 90 km/h: 1.02 * 25 + 4.5 = 30m. Three bars takes the old two-bar target.
PROTON_X50_FL_TWO_BAR_T_FOLLOW = 1.02
PROTON_X50_FL_TWO_BAR_STOP_DISTANCE = 4.5
PROTON_X50_FL_THREE_BAR_T_FOLLOW = 1.25


def get_follow_profile(car_name, car_fingerprint):
  if car_name == "proton" and car_fingerprint == PROTON_X50_FL_FINGERPRINT:
    return LongitudinalFollowProfile.proton_x50_fl
  return LongitudinalFollowProfile.default


def is_x50_fl_one_bar(personality, follow_profile):
  return follow_profile == LongitudinalFollowProfile.proton_x50_fl and personality == log.LongitudinalPersonality.aggressive


def get_jerk_factor(personality=log.LongitudinalPersonality.standard, follow_profile=LongitudinalFollowProfile.default):
  if personality==log.LongitudinalPersonality.relaxed:
    # X50 FL three-bar inherits the old two-bar acceleration smoothing too.
    return 0.5 if follow_profile == LongitudinalFollowProfile.proton_x50_fl else 1.0
  elif personality==log.LongitudinalPersonality.standard:
    return 0.5
  elif personality==log.LongitudinalPersonality.aggressive:
    return 0.5
  else:
    raise NotImplementedError("Longitudinal personality not supported")


def get_T_FOLLOW(personality=log.LongitudinalPersonality.standard, follow_profile=LongitudinalFollowProfile.default):
  if is_x50_fl_one_bar(personality, follow_profile):
    return PROTON_X50_FL_ONE_BAR_T_FOLLOW
  if follow_profile == LongitudinalFollowProfile.proton_x50_fl:
    if personality == log.LongitudinalPersonality.standard:
      return PROTON_X50_FL_TWO_BAR_T_FOLLOW
    elif personality == log.LongitudinalPersonality.relaxed:
      return PROTON_X50_FL_THREE_BAR_T_FOLLOW
  if personality==log.LongitudinalPersonality.relaxed:
    return 1.40
  elif personality==log.LongitudinalPersonality.standard:
    return 1.25
  elif personality==log.LongitudinalPersonality.aggressive:
    return 1.20
  else:
    raise NotImplementedError("Longitudinal personality not supported")


def get_stop_distance(personality=log.LongitudinalPersonality.standard, follow_profile=LongitudinalFollowProfile.default):
  if is_x50_fl_one_bar(personality, follow_profile):
    return PROTON_X50_FL_ONE_BAR_STOP_DISTANCE
  if follow_profile == LongitudinalFollowProfile.proton_x50_fl and personality == log.LongitudinalPersonality.standard:
    return PROTON_X50_FL_TWO_BAR_STOP_DISTANCE
  return STOP_DISTANCE


def get_lead_obstacle_offset(personality=log.LongitudinalPersonality.standard,
                             follow_profile=LongitudinalFollowProfile.default):
  return STOP_DISTANCE - get_stop_distance(personality, follow_profile)


def get_approach_t_follow_boost(v_ego, radarstate, personality=log.LongitudinalPersonality.standard,
                                follow_profile=LongitudinalFollowProfile.default, fallback_lead=None):
  if not is_x50_fl_one_bar(personality, follow_profile):
    return 0.0

  leads = [(lead.dRel, lead.vLead, lead.aLeadK) for lead in (radarstate.leadOne, radarstate.leadTwo) if lead.status]
  if not leads and fallback_lead is not None:
    leads.append(fallback_lead)
  if not leads:
    return 0.0

  d_rel, v_lead, a_lead = min(leads, key=lambda l: l[0])
  closing_speed = max(v_ego - v_lead, 0.0)
  lead_brake = max(-a_lead, 0.0)
  if closing_speed < 0.3 and lead_brake < 0.4:
    return 0.0

  # Limit target movement while closing or when the lead brakes. The speed
  # boost is continuous at 0.3 m/s; the independent brake boost can also apply
  # while the lead pulls away. The cap is a road-tuning candidate only.
  max_boost = PROTON_X50_FL_ONE_BAR_MAX_APPROACH_BOOST
  speed_boost = np.interp(closing_speed, [0.3, 3.5], [0.0, max_boost])
  brake_boost = np.interp(lead_brake, [0.4, 2.0], [0.0, max_boost * 0.45])
  distance_factor = np.interp(d_rel, [12.0, 50.0], [1.0, 0.0])
  return float(min(max_boost, speed_boost + brake_boost) * distance_factor)

def get_stopped_equivalence_factor(v_lead):
  return (v_lead**2) / (2 * COMFORT_BRAKE)

def get_safe_obstacle_distance(v_ego, t_follow, stop_distance=STOP_DISTANCE):
  return (v_ego**2) / (2 * COMFORT_BRAKE) + t_follow * v_ego + stop_distance

def desired_follow_distance(v_ego, v_lead, t_follow=None, stop_distance=STOP_DISTANCE):
  if t_follow is None:
    t_follow = get_T_FOLLOW()
  return get_safe_obstacle_distance(v_ego, t_follow, stop_distance) - get_stopped_equivalence_factor(v_lead)


def gen_long_model():
  model = AcadosModel()
  model.name = MODEL_NAME

  # set up states & controls
  x_ego = SX.sym('x_ego')
  v_ego = SX.sym('v_ego')
  a_ego = SX.sym('a_ego')
  model.x = vertcat(x_ego, v_ego, a_ego)

  # controls
  j_ego = SX.sym('j_ego')
  model.u = vertcat(j_ego)

  # xdot
  x_ego_dot = SX.sym('x_ego_dot')
  v_ego_dot = SX.sym('v_ego_dot')
  a_ego_dot = SX.sym('a_ego_dot')
  model.xdot = vertcat(x_ego_dot, v_ego_dot, a_ego_dot)

  # live parameters
  a_min = SX.sym('a_min')
  a_max = SX.sym('a_max')
  x_obstacle = SX.sym('x_obstacle')
  prev_a = SX.sym('prev_a')
  lead_t_follow = SX.sym('lead_t_follow')
  lead_danger_factor = SX.sym('lead_danger_factor')
  model.p = vertcat(a_min, a_max, x_obstacle, prev_a, lead_t_follow, lead_danger_factor)

  # dynamics model
  f_expl = vertcat(v_ego, a_ego, j_ego)
  model.f_impl_expr = model.xdot - f_expl
  model.f_expl_expr = f_expl
  return model


def gen_long_ocp():
  ocp = AcadosOcp()
  ocp.model = gen_long_model()

  Tf = T_IDXS[-1]

  # set dimensions
  ocp.dims.N = N

  # set cost module
  ocp.cost.cost_type = 'NONLINEAR_LS'
  ocp.cost.cost_type_e = 'NONLINEAR_LS'

  QR = np.zeros((COST_DIM, COST_DIM))
  Q = np.zeros((COST_E_DIM, COST_E_DIM))

  ocp.cost.W = QR
  ocp.cost.W_e = Q

  x_ego, v_ego, a_ego = ocp.model.x[0], ocp.model.x[1], ocp.model.x[2]
  j_ego = ocp.model.u[0]

  a_min, a_max = ocp.model.p[0], ocp.model.p[1]
  x_obstacle = ocp.model.p[2]
  prev_a = ocp.model.p[3]
  lead_t_follow = ocp.model.p[4]
  lead_danger_factor = ocp.model.p[5]

  ocp.cost.yref = np.zeros((COST_DIM, ))
  ocp.cost.yref_e = np.zeros((COST_E_DIM, ))

  desired_dist_comfort = get_safe_obstacle_distance(v_ego, lead_t_follow)

  # The main cost in normal operation is how close you are to the "desired" distance
  # from an obstacle at every timestep. This obstacle can be a lead car
  # or other object. In e2e mode we can use x_position targets as a cost
  # instead.
  costs = [((x_obstacle - x_ego) - (desired_dist_comfort)) / (v_ego + 10.),
           x_ego,
           v_ego,
           a_ego,
           a_ego - prev_a,
           j_ego]
  ocp.model.cost_y_expr = vertcat(*costs)
  ocp.model.cost_y_expr_e = vertcat(*costs[:-1])

  # Constraints on speed, acceleration and desired distance to
  # the obstacle, which is treated as a slack constraint so it
  # behaves like an asymmetrical cost.
  constraints = vertcat(v_ego,
                        (a_ego - a_min),
                        (a_max - a_ego),
                        ((x_obstacle - x_ego) - lead_danger_factor * (desired_dist_comfort)) / (v_ego + 10.))
  ocp.model.con_h_expr = constraints

  x0 = np.zeros(X_DIM)
  ocp.constraints.x0 = x0
  ocp.parameter_values = np.array([-1.2, 1.2, 0.0, 0.0, get_T_FOLLOW(), LEAD_DANGER_FACTOR])


  # We put all constraint cost weights to 0 and only set them at runtime
  cost_weights = np.zeros(CONSTR_DIM)
  ocp.cost.zl = cost_weights
  ocp.cost.Zl = cost_weights
  ocp.cost.Zu = cost_weights
  ocp.cost.zu = cost_weights

  ocp.constraints.lh = np.zeros(CONSTR_DIM)
  ocp.constraints.uh = 1e4*np.ones(CONSTR_DIM)
  ocp.constraints.idxsh = np.arange(CONSTR_DIM)

  # The HPIPM solver can give decent solutions even when it is stopped early
  # Which is critical for our purpose where compute time is strictly bounded
  # We use HPIPM in the SPEED_ABS mode, which ensures fastest runtime. This
  # does not cause issues since the problem is well bounded.
  ocp.solver_options.qp_solver = 'PARTIAL_CONDENSING_HPIPM'
  ocp.solver_options.hessian_approx = 'GAUSS_NEWTON'
  ocp.solver_options.integrator_type = 'ERK'
  ocp.solver_options.nlp_solver_type = ACADOS_SOLVER_TYPE
  ocp.solver_options.qp_solver_cond_N = 1

  # More iterations take too much time and less lead to inaccurate convergence in
  # some situations. Ideally we would run just 1 iteration to ensure fixed runtime.
  ocp.solver_options.qp_solver_iter_max = 10
  ocp.solver_options.qp_tol = 1e-3

  # set prediction horizon
  ocp.solver_options.tf = Tf
  ocp.solver_options.shooting_nodes = T_IDXS

  ocp.code_export_directory = EXPORT_DIR
  return ocp


LEAD_PERSIST_SECONDS = 3.0
LEAD_PERSIST_FRAMES = round(LEAD_PERSIST_SECONDS / DT_MDL)


def project_missing_lead(d_rel, v_lead, a_lead, v_ego, a_ego):
  lead_v_next = max(v_lead + a_lead * DT_MDL, 0.0)
  ego_v_next = max(v_ego + a_ego * DT_MDL, 0.0)
  relative_speed_now = v_lead - v_ego
  relative_speed_next = lead_v_next - ego_v_next
  d_rel += (relative_speed_now + relative_speed_next) * 0.5 * DT_MDL
  return d_rel, lead_v_next, a_lead * 0.8


class LongitudinalMpc:
  def __init__(self, mode='acc', follow_profile=LongitudinalFollowProfile.default):
    self.mode = mode
    self.follow_profile = LongitudinalFollowProfile(follow_profile)
    self._lead_persist_frames = LEAD_PERSIST_FRAMES if self.follow_profile == LongitudinalFollowProfile.proton_x50_fl else 0
    self.solver = AcadosOcpSolverCython(MODEL_NAME, ACADOS_SOLVER_TYPE, N)
    self.reset()
    self.source = SOURCES[2]
    self.t_follow_actual = get_T_FOLLOW(follow_profile=self.follow_profile)
    self._dbg = DebugLogger("long_mpc")

  def reset(self):
    # self.solver = AcadosOcpSolverCython(MODEL_NAME, ACADOS_SOLVER_TYPE, N)
    self.solver.reset()
    # self.solver.options_set('print_level', 2)
    self.v_solution = np.zeros(N+1)
    self.a_solution = np.zeros(N+1)
    self.prev_a = np.array(self.a_solution)
    self.j_solution = np.zeros(N)
    self.yref = np.zeros((N+1, COST_DIM))
    for i in range(N):
      self.solver.cost_set(i, "yref", self.yref[i])
    self.solver.cost_set(N, "yref", self.yref[N][:COST_E_DIM])
    self.x_sol = np.zeros((N+1, X_DIM))
    self.u_sol = np.zeros((N,1))
    self.params = np.zeros((N+1, PARAM_DIM))
    for i in range(N+1):
      self.solver.set(i, 'x', np.zeros(X_DIM))
    self.last_cloudlog_t = 0
    self.status = False
    self.crash_cnt = 0.0
    self.solution_status = 0
    # X50 FL is camera-only. Keep each lead slot independently across short
    # detection gaps, and expire both slots on an MPC reset.
    self._last_lead_x = [0.0, 0.0]
    self._last_lead_v = [0.0, 0.0]
    self._last_lead_a = [0.0, 0.0]
    self._lead_gone_frames = [self._lead_persist_frames, self._lead_persist_frames]
    # timers
    self.solve_time = 0.0
    self.time_qp_solution = 0.0
    self.time_linearization = 0.0
    self.time_integrator = 0.0
    self.x0 = np.zeros(X_DIM)
    self.set_weights()

  def set_cost_weights(self, cost_weights, constraint_cost_weights):
    W = np.asfortranarray(np.diag(cost_weights))
    for i in range(N):
      # TODO don't hardcode A_CHANGE_COST idx
      # reduce the cost on (a-a_prev) later in the horizon.
      W[4,4] = cost_weights[4] * np.interp(T_IDXS[i], [0.0, 1.0, 2.0], [1.0, 1.0, 0.0])
      self.solver.cost_set(i, 'W', W)
    # Setting the slice without the copy make the array not contiguous,
    # causing issues with the C interface.
    self.solver.cost_set(N, 'W', np.copy(W[:COST_E_DIM, :COST_E_DIM]))

    # Set L2 slack cost on lower bound constraints
    Zl = np.array(constraint_cost_weights)
    for i in range(N):
      self.solver.cost_set(i, 'Zl', Zl)

  def set_weights(self, prev_accel_constraint=True, personality=log.LongitudinalPersonality.standard):
    jerk_factor = get_jerk_factor(personality, self.follow_profile)
    if self.mode == 'acc':
      a_change_cost = A_CHANGE_COST if prev_accel_constraint else 0
      cost_weights = [X_EGO_OBSTACLE_COST, X_EGO_COST, V_EGO_COST, A_EGO_COST, jerk_factor * a_change_cost, jerk_factor * J_EGO_COST]
      # At the shorter one-bar target, penalize using up the gap before a late
      # stop is needed. Keep the acceleration/jerk smoothing costs unchanged.
      danger_zone_cost = PROTON_X50_FL_ONE_BAR_DANGER_ZONE_COST if is_x50_fl_one_bar(personality, self.follow_profile) else DANGER_ZONE_COST
      constraint_cost_weights = [LIMIT_COST, LIMIT_COST, LIMIT_COST, danger_zone_cost]
    elif self.mode == 'blended':
      a_change_cost = 40.0 if prev_accel_constraint else 0
      cost_weights = [0., 0.1, 0.2, 5.0, a_change_cost, 1.0]
      constraint_cost_weights = [LIMIT_COST, LIMIT_COST, LIMIT_COST, 50.0]
    else:
      raise NotImplementedError(f'Planner mode {self.mode} not recognized in planner cost set')
    self.set_cost_weights(cost_weights, constraint_cost_weights)

  def set_cur_state(self, v, a):
    v_prev = self.x0[1]
    self.x0[1] = v
    self.x0[2] = a
    if abs(v_prev - v) > 2.:  # probably only helps if v < v_prev
      for i in range(N+1):
        self.solver.set(i, 'x', self.x0)

  @staticmethod
  def extrapolate_lead(x_lead, v_lead, a_lead, a_lead_tau):
    a_lead_traj = a_lead * np.exp(-a_lead_tau * (T_IDXS**2)/2.)
    v_lead_traj = np.clip(v_lead + np.cumsum(T_DIFFS * a_lead_traj), 0.0, 1e8)
    x_lead_traj = x_lead + np.cumsum(T_DIFFS * v_lead_traj)
    lead_xv = np.column_stack((x_lead_traj, v_lead_traj))
    return lead_xv

  def process_lead(self, lead, lead_idx):
    v_ego = self.x0[1]
    if lead is not None and lead.status:
      x_lead = lead.dRel
      v_lead = lead.vLead
      a_lead = lead.aLeadK
      a_lead_tau = lead.aLeadTau
      # Remember this lead for persistence
      self._last_lead_x[lead_idx] = x_lead
      self._last_lead_v[lead_idx] = v_lead
      self._last_lead_a[lead_idx] = a_lead
      self._lead_gone_frames[lead_idx] = 0
    elif self._lead_gone_frames[lead_idx] < self._lead_persist_frames:
      # dRel is relative to ego, so advance it with relative speed at the real
      # 20 Hz planner interval. Advancing by absolute lead speed makes the ghost
      # incorrectly run away when both cars are moving.
      self._lead_gone_frames[lead_idx] += 1
      self._last_lead_x[lead_idx], self._last_lead_v[lead_idx], self._last_lead_a[lead_idx] = project_missing_lead(
        self._last_lead_x[lead_idx], self._last_lead_v[lead_idx], self._last_lead_a[lead_idx], v_ego, self.x0[2],
      )
      x_lead = self._last_lead_x[lead_idx]
      v_lead = self._last_lead_v[lead_idx]
      a_lead = self._last_lead_a[lead_idx]
      a_lead_tau = _LEAD_ACCEL_TAU
    else:
      # Fake a fast lead car, so mpc can keep running in the same mode
      x_lead = 50.0
      v_lead = v_ego + 10.0
      a_lead = 0.0
      a_lead_tau = _LEAD_ACCEL_TAU

    # MPC will not converge if immediate crash is expected
    # Clip lead distance to what is still possible to brake for
    min_x_lead = ((v_ego + v_lead)/2) * (v_ego - v_lead) / (-ACCEL_MIN * 2)
    x_lead = clip(x_lead, min_x_lead, 1e8)
    v_lead = clip(v_lead, 0.0, 1e8)
    a_lead = clip(a_lead, -10., 5.)
    lead_xv = self.extrapolate_lead(x_lead, v_lead, a_lead, a_lead_tau)
    return lead_xv

  def set_accel_limits(self, min_a, max_a):
    # TODO this sets a max accel limit, but the minimum limit is only for cruise decel
    # needs refactor
    self.cruise_min_a = min_a
    self.max_a = max_a

  def update(self, radarstate, v_cruise, x, v, a, j, personality=log.LongitudinalPersonality.standard):
    v_ego = self.x0[1]
    base_t_follow = get_T_FOLLOW(personality, self.follow_profile)
    stop_distance = get_stop_distance(personality, self.follow_profile)
    self.status = radarstate.leadOne.status or radarstate.leadTwo.status

    lead_xv_0 = self.process_lead(radarstate.leadOne, 0)
    lead_xv_1 = self.process_lead(radarstate.leadTwo, 1)
    persisted_leads = [
      (self._last_lead_x[i], self._last_lead_v[i], self._last_lead_a[i])
      for i in range(2) if self._lead_gone_frames[i] < self._lead_persist_frames
    ]
    fallback_lead = None if self.status or not persisted_leads else min(persisted_leads, key=lambda lead: lead[0])
    approach_t_follow_boost = get_approach_t_follow_boost(v_ego, radarstate, personality, self.follow_profile, fallback_lead)
    t_follow = base_t_follow + approach_t_follow_boost

    # To estimate a safe distance from a moving lead, we calculate how much stopping
    # distance that lead needs as a minimum. We can add that to the current distance
    # and then treat that as a stopped car/obstacle at this new distance.
    # The generated solver embeds STOP_DISTANCE. Shift only the selected
    # profile's lead obstacles so its effective stop distance can differ without
    # letting Python constants drift from generated C again.
    lead_obstacle_offset = get_lead_obstacle_offset(personality, self.follow_profile)
    lead_0_obstacle = lead_xv_0[:,0] + get_stopped_equivalence_factor(lead_xv_0[:,1]) + lead_obstacle_offset
    lead_1_obstacle = lead_xv_1[:,0] + get_stopped_equivalence_factor(lead_xv_1[:,1]) + lead_obstacle_offset

    self.params[:,0] = ACCEL_MIN
    self.params[:,1] = self.max_a

    # Update in ACC mode or ACC/e2e blend
    if self.mode == 'acc':
      # The normal 0.75 factor permits undershooting the desired gap. One bar
      # has less spare distance, so start the stronger penalty at its full
      # target. This is still a soft constraint, not a collision guarantee.
      self.params[:,5] = PROTON_X50_FL_ONE_BAR_DANGER_FACTOR if is_x50_fl_one_bar(personality, self.follow_profile) else LEAD_DANGER_FACTOR

      # Fake an obstacle for cruise, this ensures smooth acceleration to set speed
      # when the leads are no factor.
      v_lower = v_ego + (T_IDXS * self.cruise_min_a * 1.05)
      v_upper = v_ego + (T_IDXS * self.max_a * 1.05)
      v_cruise_clipped = np.clip(v_cruise * np.ones(N+1),
                                 v_lower,
                                 v_upper)
      cruise_obstacle = np.cumsum(T_DIFFS * v_cruise_clipped) + get_safe_obstacle_distance(v_cruise_clipped, t_follow)

      x_obstacles = np.column_stack([lead_0_obstacle, lead_1_obstacle, cruise_obstacle])
      self.source = SOURCES[np.argmin(x_obstacles[0])]

      # These are not used in ACC mode
      x[:], v[:], a[:], j[:] = 0.0, 0.0, 0.0, 0.0

    elif self.mode == 'blended':
      self.params[:,5] = 1.0

      x_obstacles = np.column_stack([lead_0_obstacle,
                                     lead_1_obstacle])
      cruise_target = T_IDXS * np.clip(v_cruise, v_ego - 2.0, 1e3) + x[0]
      xforward = ((v[1:] + v[:-1]) / 2) * (T_IDXS[1:] - T_IDXS[:-1])
      x = np.cumsum(np.insert(xforward, 0, x[0]))

      x_and_cruise = np.column_stack([x, cruise_target])
      x = np.min(x_and_cruise, axis=1)

      self.source = 'e2e' if x_and_cruise[1,0] < x_and_cruise[1,1] else 'cruise'

    else:
      raise NotImplementedError(f'Planner mode {self.mode} not recognized in planner update')

    self.yref[:,1] = x
    self.yref[:,2] = v
    self.yref[:,3] = a
    self.yref[:,5] = j
    for i in range(N):
      self.solver.set(i, "yref", self.yref[i])
    self.solver.set(N, "yref", self.yref[N][:COST_E_DIM])

    self.params[:,2] = np.min(x_obstacles, axis=1)
    self.params[:,3] = np.copy(self.prev_a)
    self.params[:,4] = t_follow
    self.t_follow_actual = t_follow

    self.run()
    if (np.any(lead_xv_0[FCW_IDXS,0] - self.x_sol[FCW_IDXS,0] < CRASH_DISTANCE) and
            radarstate.leadOne.modelProb > 0.9):
      self.crash_cnt += 1
    else:
      self.crash_cnt = 0

    lead = radarstate.leadOne
    self._dbg.log({
      "tF": round(self.t_follow_actual, 3),
      "tFBase": round(base_t_follow, 3),
      "tFBoost": round(approach_t_follow_boost, 3),
      "stopD": round(stop_distance, 2),
      "profile": int(self.follow_profile),
      "dRel": round(lead.dRel, 2) if lead.status else -1,
      "vLead": round(lead.vLead, 2) if lead.status else -1,
      "aLead": round(lead.aLeadK, 2) if lead.status else -1,
      "leadSt": lead.status,
      "src": self.source,
      "aS0": round(self.a_solution[0], 3),
      "aS1": round(self.a_solution[1], 3),
      "vEgo": round(v_ego, 2),
      "solSt": self.solution_status,
    })

    # Check if it got within lead comfort range
    # TODO This should be done cleaner
    if self.mode == 'blended':
      if any((lead_0_obstacle - get_safe_obstacle_distance(self.x_sol[:,1], t_follow))- self.x_sol[:,0] < 0.0):
        self.source = 'lead0'
      if any((lead_1_obstacle - get_safe_obstacle_distance(self.x_sol[:,1], t_follow))- self.x_sol[:,0] < 0.0) and \
         (lead_1_obstacle[0] - lead_0_obstacle[0]):
        self.source = 'lead1'

  def run(self):
    # t0 = time.monotonic()
    # reset = 0
    for i in range(N+1):
      self.solver.set(i, 'p', self.params[i])
    self.solver.constraints_set(0, "lbx", self.x0)
    self.solver.constraints_set(0, "ubx", self.x0)

    self.solution_status = self.solver.solve()
    self.solve_time = float(self.solver.get_stats('time_tot')[0])
    self.time_qp_solution = float(self.solver.get_stats('time_qp')[0])
    self.time_linearization = float(self.solver.get_stats('time_lin')[0])
    self.time_integrator = float(self.solver.get_stats('time_sim')[0])

    # qp_iter = self.solver.get_stats('statistics')[-1][-1] # SQP_RTI specific
    # print(f"long_mpc timings: tot {self.solve_time:.2e}, qp {self.time_qp_solution:.2e}, lin {self.time_linearization:.2e}, \
    # integrator {self.time_integrator:.2e}, qp_iter {qp_iter}")
    # res = self.solver.get_residuals()
    # print(f"long_mpc residuals: {res[0]:.2e}, {res[1]:.2e}, {res[2]:.2e}, {res[3]:.2e}")
    # self.solver.print_statistics()

    for i in range(N+1):
      self.x_sol[i] = self.solver.get(i, 'x')
    for i in range(N):
      self.u_sol[i] = self.solver.get(i, 'u')

    self.v_solution = self.x_sol[:,1]
    self.a_solution = self.x_sol[:,2]
    self.j_solution = self.u_sol[:,0]

    self.prev_a = np.interp(T_IDXS + 0.05, T_IDXS, self.a_solution)

    t = time.monotonic()
    if self.solution_status != 0:
      if t > self.last_cloudlog_t + 5.0:
        self.last_cloudlog_t = t
        cloudlog.warning(f"Long mpc reset, solution_status: {self.solution_status}")
      self.reset()
      # reset = 1
    # print(f"long_mpc timings: total internal {self.solve_time:.2e}, external: {(time.monotonic() - t0):.2e} qp {self.time_qp_solution:.2e}, \
    # lin {self.time_linearization:.2e} qp_iter {qp_iter}, reset {reset}")


if __name__ == "__main__":
  ocp = gen_long_ocp()
  AcadosOcpSolver.generate(ocp, json_file=JSON_FILE)
  # AcadosOcpSolver.build(ocp.code_export_directory, with_cython=True)
