from opendbc.can.packer import CANPacker
from openpilot.selfdrive.car.interfaces import CarControllerBase
from openpilot.selfdrive.car.proton.protoncan import create_can_steer_command, send_buttons, create_acc_cmd
from openpilot.selfdrive.car.proton.values import DBC, CAR
from openpilot.common.numpy_fast import clip, interp
from openpilot.common.realtime import DT_CTRL
from openpilot.common.features import Features
from time import monotonic
from openpilot.common.debug_logger import DebugLogger

def apply_proton_steer_torque_limits(apply_torque, apply_torque_last, driver_torque, LIMITS):

  # limits due to driver torque
  driver_offset = driver_torque * 30
  max_steer_allowed = clip(LIMITS.STEER_MAX + driver_offset, 0, LIMITS.STEER_MAX)
  min_steer_allowed = clip(-LIMITS.STEER_MAX + driver_offset, -LIMITS.STEER_MAX, 0)
  apply_torque = clip(apply_torque, min_steer_allowed, max_steer_allowed)

  # slow rate if steer torque increases in magnitude
  if apply_torque_last > 0:
    apply_torque = clip(apply_torque, max(apply_torque_last - LIMITS.STEER_DELTA_DOWN, -LIMITS.STEER_DELTA_UP),
                        apply_torque_last + LIMITS.STEER_DELTA_UP)
  else:
    apply_torque = clip(apply_torque, apply_torque_last - LIMITS.STEER_DELTA_UP,
                        min(apply_torque_last + LIMITS.STEER_DELTA_DOWN, LIMITS.STEER_DELTA_UP))

  return round(apply_torque)

class CarControllerParams():
  def __init__(self, CP):

    self.STEER_MAX = CP.lateralParams.torqueV[0]
    # make sure Proton only has one max steer torque value
    assert(len(CP.lateralParams.torqueV) == 1)

    # for torque limit calculation
    if CP.carFingerprint == CAR.X90:
      self.STEER_DELTA_UP = 4
      self.STEER_DELTA_DOWN = 8
    else:
      self.STEER_DELTA_UP = 15
      self.STEER_DELTA_DOWN = 35

class CarController(CarControllerBase):
  def __init__(self, dbc_name, CP, VM):
    self.CP = CP
    self.frame = 0
    self.packer = CANPacker(DBC[CP.carFingerprint]['pt'])
    self.params = CarControllerParams(self.CP)

    self.last_steer = 0
    self.steering_direction = False
    f = Features()
    self.always_lks_tactile = f.has("lks-tactile")
    self.openpilot_long = not f.has("stock-acc")

    self.prev_steer_enabled = False
    self.last_steer_disable = 0

    self.sng_next_press_frame = 0 # The frame where the next resume press is allowed
    self.resume_counter = 0       # Counter for tracking the progress of a resume press
    self.is_sng_check = False
    self.resume = False

    self.cancel_press_cnt = 0
    self.last_cancel_press = 0
    self._prev_accel_cmd = 0.0
    self._dbg = DebugLogger("long_ctrl")

  @staticmethod
  def get_long_blend_params(v_ego, distance_val):
    if distance_val == 1:
      # City follow needs quick brake release, but gentle real throttle.
      return (
        interp(v_ego, [0., 22., 25., 33.], [0.08, 0.09, 0.12, 0.16]),
        interp(v_ego, [0., 22., 25., 33.], [0.45, 0.50, 0.60, 0.75]),
        interp(v_ego, [0., 10., 22., 25.], [-0.8, -1.5, -2.5, -3.0]),
        interp(v_ego, [0., 10., 22., 25.], [-2.8, -4.0, -5.0, -6.0]),
        interp(v_ego, [0., 10., 22., 25.], [-6.0, -7.0, -9.0, -10.0]),
        interp(v_ego, [0., 22., 25., 33.], [0.25, 0.30, 0.35, 0.45]),
      )

    if distance_val == 2:
      return (
        interp(v_ego, [0., 22., 25., 33.], [0.09, 0.10, 0.14, 0.18]),
        interp(v_ego, [0., 22., 25., 33.], [0.50, 0.55, 0.70, 0.85]),
        interp(v_ego, [0., 10., 22., 28.], [-0.8, -1.4, -2.8, -4.0]),
        interp(v_ego, [0., 10., 22., 28.], [-3.0, -4.0, -5.5, -7.0]),
        interp(v_ego, [0., 10., 22., 28.], [-5.0, -6.5, -9.0, -10.0]),
        interp(v_ego, [0., 22., 25., 33.], [0.25, 0.30, 0.40, 0.50]),
      )

    return (
      interp(v_ego, [0., 22., 25., 33.], [0.09, 0.10, 0.15, 0.25]),
      interp(v_ego, [0., 22., 25., 33.], [0.50, 0.55, 0.70, 0.85]),
      interp(v_ego, [20., 28.], [-8., -15.]),
      interp(v_ego, [20., 28.], [-8., -15.]),
      interp(v_ego, [20., 28.], [-18., -25.]),
      interp(v_ego, [0., 22., 25., 33.], [0.8, 1.0, 1.4, 2.0]),
    )

  def update(self, CC, CS, now_nanos):
    can_sends = []

    lat_active = CC.latActive
    actuators = CC.actuators
    pcm_cancel_cmd = CC.cruiseControl.cancel
    accel_cmd = actuators.accel

    # steer
    new_steer = round(actuators.steer * self.params.STEER_MAX)
    apply_steer = apply_proton_steer_torque_limits(new_steer, self.last_steer, 0, self.params)

    if not (steer_enabled := CC.latActive) and self.prev_steer_enabled:
      self.last_steer_disable = monotonic()
    self.prev_steer_enabled = steer_enabled

    # Stock Lane Departure Prevention / Centering Control (LKS Auxiliary / Blue line)
    if not steer_enabled and (stock_steer := CS.stock_ldp_cmd) > 0 and \
       not ((CS.out.rightBlinker and CS.stock_ldp_right) or (CS.out.leftBlinker and CS.stock_ldp_left)):
      # Prevents sudden pull from LDP/ICC/LKA Centering after steer disable
      mul = clip((monotonic() - self.last_steer_disable - 0.55) / 0.5, 0, 1)
      apply_steer = round(stock_steer * (-1 if CS.stock_steer_dir else 1) * mul) &~1 # Ensure cmd LSB 0
      lat_active = True

    if (self.frame % 2) == 0:

      # stock lane departure settings
      ldw_steering = CS.stock_ldw_steering
      if self.always_lks_tactile:
        ldw_steering = ldw_steering or CS.has_audio_ldw
        lks_audio, lks_tactile = False, True
      else:
        lks_audio, lks_tactile = CS.lks_audio, CS.lks_tactile

      # standstill logic
      standstill_request = CS.out.standstill and CC.longActive

      # SNG
      if not (CS.cruise_standstill and CC.longActive):
        self.is_sng_check = False
        self.resume = False
      else:
        self.resume = CS.out.gasPressed or CS.res_btn_pressed
        if not self.is_sng_check:
          self.is_sng_check = True
          self.sng_next_press_frame = self.frame + 310
          self.resume_counter = 0

        elif self.resume or self.resume_counter >= 2:
          self.sng_next_press_frame = max(self.sng_next_press_frame, self.frame + 110)
          self.resume_counter = 0

        elif actuators.accel > 0 and self.frame > self.sng_next_press_frame:
          # to disengage from stock cruise standstill
          self.resume = True
          can_sends.append(send_buttons(self.packer, 0))
          self.resume_counter += 1

      is_x90 = self.CP.carFingerprint == CAR.X90

      # TODO: Remove line below and test on X90 since stock LKA last bit is always 0 for any Proton car.
      steer_cmd = (round(apply_steer) * 2) if (is_x90 and CC.latActive) else apply_steer

      can_sends.append(create_can_steer_command(self.packer, steer_cmd, lat_active,
                       CS.hand_on_wheel_warning and CS.is_icc_on,
                       CS.hand_on_wheel_warning_2 and CS.is_icc_on,
                       CS.lks_aux, lks_audio, lks_tactile, CS.lks_assist_mode,
                       CS.lka_enable, ldw_steering, steer_enabled, is_x90))

      if self.openpilot_long:
        accel_cmd = accel_cmd * 15 if accel_cmd >= 0 else accel_cmd * 18
        accel_blocked = CS.out.gasPressed or not CC.longActive
        if accel_blocked:
          accel_cmd = 0
          self._prev_accel_cmd = 0.0

        mult = interp(CS.out.vEgo, [0, 28.3], [1.0, 0.6])
        stock_scaled = CS.stock_acc_cmd * mult
        accel_raw = accel_cmd
        distance_val = getattr(CS, "distance_val", 2)
        throttle_rate, brake_release_rate, stock_coast_threshold, stock_brake_threshold, hard_override, stock_brake_rate = self.get_long_blend_params(CS.out.vEgo, distance_val)

        if not accel_blocked:
          # For 1/2-bar, mild stock braking only blocks throttle. Stronger stock braking
          # adds smooth brake so close-follow does not dive into a slowing lead.
          if distance_val in (1, 2) and stock_scaled < stock_coast_threshold:
            accel_cmd = min(accel_raw, 0.0)
          if distance_val in (1, 2) and stock_scaled < stock_brake_threshold:
            stock_target = interp(stock_scaled, [hard_override, stock_brake_threshold], [hard_override, 0.0])
            accel_cmd = min(accel_raw, stock_target)

          if accel_cmd > self._prev_accel_cmd:
            if self._prev_accel_cmd < 0.0:
              accel_cmd = min(accel_cmd, min(0.0, self._prev_accel_cmd + brake_release_rate))
            else:
              accel_cmd = min(accel_cmd, self._prev_accel_cmd + throttle_rate)
          else:
            rate_down = stock_brake_rate if distance_val in (1, 2) and stock_scaled < stock_brake_threshold else 0.5
            accel_cmd = max(accel_cmd, self._prev_accel_cmd - rate_down)

          # Bar 3 keeps the older stock brake cap so relaxed follow stays stable.
          if distance_val not in (1, 2) and stock_scaled < stock_brake_threshold:
            stock_brake = min(stock_scaled, accel_raw)
            if stock_brake < hard_override:
              accel_cmd = stock_brake
            else:
              accel_cmd = max(stock_brake, self._prev_accel_cmd - stock_brake_rate)

          self._prev_accel_cmd = accel_cmd

        self._dbg.log({
          "vEgo": round(CS.out.vEgo, 2),
          "aRaw": round(accel_raw, 2),
          "aCmd": round(accel_cmd, 2),
          "aStock": round(stock_scaled, 2),
          "aPrev": round(self._prev_accel_cmd, 2),
          "gap": distance_val,
          "thrRate": round(throttle_rate, 2),
          "relRate": round(brake_release_rate, 2),
          "coastTh": round(stock_coast_threshold, 2),
          "stockTh": round(stock_brake_threshold, 2),
          "stkBrRate": round(stock_brake_rate, 2),
          "gas": CS.out.gasPressed,
          "stndstl": CS.out.standstill,
          "resume": self.resume,
          "longAct": CC.longActive,
        })

        can_sends.append(create_acc_cmd(self.packer, accel_cmd, CC.longActive, CS.out.gasPressed,
                                        standstill_request, self.resume, CS.out.brakePressed))

    # cancel stock cruise if error at openpilot
    if not pcm_cancel_cmd:
      self.cancel_press_cnt = 0
      self.last_cancel_press = 0
    elif self.frame > self.last_cancel_press + 15 and not (CS.out.brakePressed and not CS.cruise_standstill):
      can_sends.append(send_buttons(self.packer, 1))
      self.cancel_press_cnt += 1
      if self.cancel_press_cnt == 2:
        self.cancel_press_cnt = 0
        self.last_cancel_press = self.frame

    self.last_steer = apply_steer
    new_actuators = actuators.copy()
    new_actuators.accel = accel_cmd / 15 if accel_cmd >= 0 else accel_cmd / 18
    new_actuators.steer = apply_steer / self.params.STEER_MAX

    self.frame += 1
    return new_actuators, can_sends
