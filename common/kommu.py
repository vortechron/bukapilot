from openpilot.common.params import Params
from openpilot.system.hardware import HARDWARE

import requests

WEB_BASE="https://web.kommu.ai"
SESSION_PARAM_KEY = "KommuSessionToken"
LEGACY_SESSION_PARAM_KEY = "RsjSession"

class KommuAuthError(Exception):
  pass


# Backward-compatible alias while callers migrate.
AuthException = KommuAuthError

def refresh_session():
  params = Params()

  init = requests.get(WEB_BASE + "/self-service/login/api")
  if init.status_code != 200:
    raise Exception("can't init kratos login flow")

  data = {
      "method": "password",
      "password_identifier": params.get("DongleId"),
      "password": HARDWARE.get_imei(1) + HARDWARE.get_serial(),
  }
  resp = requests.post(init.json()["ui"]["action"], data=data)
  if resp.status_code != 200:
    raise KommuAuthError("can't login into system")

  params.put(SESSION_PARAM_KEY, resp.json()["session_token"])
  params.put(LEGACY_SESSION_PARAM_KEY, resp.json()["session_token"])


def _kommu_request_raw(func, *args, **kwargs):
  params = Params()
  auth = params.get(SESSION_PARAM_KEY)
  if auth is None:
    auth = params.get(LEGACY_SESSION_PARAM_KEY)
  auth = auth.decode("utf-8") if isinstance(auth, bytes) else (auth or "")

  if "headers" in kwargs:
    headers = kwargs["headers"]
  else:
    headers = {}

  headers["Authorization"] = "Bearer " + auth
  kwargs["headers"] = headers
  return func(*args, **kwargs)


def kommu_request(func, *args, **kwargs):
  resp = _kommu_request_raw(func, *args, **kwargs)
  if resp.status_code == 401:
    # one try only!
    refresh_session()
    return _kommu_request_raw(func, *args, **kwargs)
  return resp


# Backward-compatible aliases while callers migrate.
_kapi_raw = _kommu_request_raw
kapi = kommu_request
