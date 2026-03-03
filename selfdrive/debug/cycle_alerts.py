#!/usr/bin/env python3
import time
import random

from cereal import car, log
import cereal.messaging as messaging
from opendbc.car.honda.interface import CarInterface
from openpilot.common.realtime import DT_CTRL
from openpilot.selfdrive.selfdrived.events import ET, Events
from openpilot.selfdrive.selfdrived.alertmanager import AlertManager
from openpilot.system.manager.process_config import managed_processes

EventName = log.OnroadEvent.EventName

def cycle_alerts(duration=200, is_metric=False):
  # this plays each type of audible alert
  '''
  alerts = [
    (EventName.buttonEnable, ET.ENABLE),
    (EventName.buttonCancel, ET.USER_DISABLE),
    (EventName.wrongGear, ET.NO_ENTRY),

    (EventName.locationdTemporaryError, ET.SOFT_DISABLE),
    (EventName.paramsdTemporaryError, ET.SOFT_DISABLE),
    (EventName.accFaulted, ET.IMMEDIATE_DISABLE),
    (EventName.preLaneChangeLeft, ET.WARNING),

    # DM sequence
    (EventName.preDriverDistracted, ET.WARNING),
    (EventName.promptDriverDistracted, ET.WARNING),
    (EventName.driverDistracted, ET.WARNING),
  ]
   '''

  alerts = [
    (EventName.startup, ET.PERMANENT),
    (EventName.wrongGear, ET.NO_ENTRY),
    (EventName.buttonEnable, ET.ENABLE),

    (EventName.steerSaturated, ET.WARNING),
    (None, None),
    (None, None),
    (EventName.buttonEnable, ET.ENABLE),
    (EventName.buttonEnable, ET.ENABLE),

    # DM sequence
    (EventName.preDriverDistracted, ET.WARNING),
    (EventName.promptDriverDistracted, ET.WARNING),
    (EventName.driverDistracted, ET.WARNING),
    (EventName.buttonCancel, ET.USER_DISABLE),


    (EventName.overheat, ET.PERMANENT),
    (EventName.overheat, ET.PERMANENT),
  ]
  '''
  # debug alerts
  alerts = [
    (EventName.highCpuUsage, ET.NO_ENTRY),
    (EventName.lowMemory, ET.PERMANENT),
    (EventName.overheat, ET.PERMANENT),
    (EventName.outOfSpace, ET.PERMANENT),
    (EventName.modeldLagging, ET.PERMANENT),
    (EventName.processNotRunning, ET.NO_ENTRY),
    (EventName.commIssue, ET.NO_ENTRY),
    (EventName.calibrationInvalid, ET.PERMANENT),
    (EventName.cameraMalfunction, ET.PERMANENT),
    (EventName.cameraFrameRate, ET.PERMANENT),
  ]
  '''

  CS = car.CarState.new_message()
  CP = CarInterface.get_non_essential_params("HONDA_CIVIC")
  cameras = []  # optional camera streams for SubMaster
  sm = messaging.SubMaster(['deviceState', 'pandaStates', 'roadCameraState', 'modelV2', 'liveCalibration',
                            'driverMonitoringState', 'longitudinalPlan', 'livePose',
                            'managerState'] + cameras)

  pm = messaging.PubMaster(['selfdriveState', 'pandaStates', 'deviceState'])

  events = Events()
  AM = AlertManager()

  frame = 0

  enabled = False
  while True:
    for al, et in alerts:
      events.clear()
      events.add(al)

      if al != None:
        a = events.create_alerts([et, ], [None, CS, sm, is_metric, 0])
        AM.add_many(frame, a)
        alert = AM.process_alerts(frame, [])
      else:
        alert = None
      print(alert)
      for _ in range(duration):
        dat = messaging.new_message('selfdriveState')
        dat.selfdriveState.enabled = False

        if alert:
          dat.selfdriveState.alertText1 = alert.alert_text_1
          dat.selfdriveState.alertText2 = alert.alert_text_2
          dat.selfdriveState.alertSize = alert.alert_size
          dat.selfdriveState.alertStatus = alert.alert_status
          dat.selfdriveState.alertType = alert.alert_type
          dat.selfdriveState.alertSound = alert.audible_alert
        pm.send('selfdriveState', dat)

        dat = messaging.new_message('deviceState')
        dat.deviceState.started = True
        pm.send('deviceState', dat)

        dat = messaging.new_message('pandaStates', 1)
        dat.pandaStates[0].ignitionLine = True
        dat.pandaStates[0].pandaType = log.PandaState.PandaType.uno
        pm.send('pandaStates', dat)

        frame += 1
        time.sleep(DT_CTRL)

if __name__ == '__main__':
  cycle_alerts()
