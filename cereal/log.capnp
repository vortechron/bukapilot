using Cxx = import "./include/c++.capnp";
$Cxx.namespace("cereal");

using Car = import "car.capnp";
using Legacy = import "legacy.capnp";
using Custom = import "custom.capnp";

@0xf3b1f17e25a4285b;

const logVersion :Int32 = 1;

struct Map(Key, Value) {
  entries @0 :List(Entry);
  struct Entry {
    key @0 :Key;
    value @1 :Value;
  }
}

struct OnroadEvent @0xc4fa6047f024e718 {
  name @0 :EventName;

  # event types
  enable @1 :Bool;
  noEntry @2 :Bool;
  warning @3 :Bool;   # alerts presented only when  enabled or soft disabling
  userDisable @4 :Bool;
  softDisable @5 :Bool;
  immediateDisable @6 :Bool;
  preEnable @7 :Bool;
  permanent @8 :Bool; # alerts presented regardless of openpilot state
  overrideLongitudinal @9 :Bool;
  overrideLateral @10 :Bool;

  enum EventName @0x91f1992a1f77fb03 {
    canError @0;
    steerUnavailable @1;
    wrongGear @2;
    doorOpen @3;
    seatbeltNotLatched @4;
    espDisabled @5;
    wrongCarMode @6;
    steerTempUnavailable @7;
    reverseGear @8;
    buttonCancel @9;
    buttonEnable @10;
    pedalPressed @11;  # exits active state
    preEnableStandstill @12;  # added during pre-enable state with brake
    gasPressedOverride @13;  # added when user is pressing gas with no disengage on gas
    steerOverride @14;
    steerDisengage @15;  # exits active state
    cruiseDisabled @16;
    speedTooLow @17;
    outOfSpace @18;
    overheat @19;
    calibrationIncomplete @20;
    calibrationInvalid @21;
    calibrationRecalibrating @22;
    controlsMismatch @23;
    pcmEnable @24;
    pcmDisable @25;
    radarFault @26;
    radarTempUnavailable @27;
    brakeHold @28;
    parkBrake @29;
    manualRestart @30;
    joystickDebug @31;
    longitudinalManeuver @32;
    steerTempUnavailableSilent @33;
    resumeRequired @34;
    preDriverDistracted @35;
    promptDriverDistracted @36;
    driverDistracted @37;
    preDriverUnresponsive @38;
    promptDriverUnresponsive @39;
    driverUnresponsive @40;
    belowSteerSpeed @41;
    lowBattery @42;
    accFaulted @43;
    sensorDataInvalid @44;
    commIssue @45;
    commIssueAvgFreq @46;
    tooDistracted @47;
    posenetInvalid @48;
    preLaneChangeLeft @49;
    preLaneChangeRight @50;
    laneChange @51;
    lowMemory @52;
    stockAeb @53;
    stockLkas @54;
    ldw @55;
    carUnrecognized @56;
    invalidLkasSetting @57;
    speedTooHigh @58;
    laneChangeBlocked @59;
    relayMalfunction @60;
    stockFcw @61;
    startup @62;
    startupNoCar @63;
    startupNoControl @64;
    startupNoSecOcKey @65;
    startupMaster @66;
    fcw @67;
    steerSaturated @68;
    belowEngageSpeed @69;
    noGps @70;
    wrongCruiseMode @71;
    modeldLagging @72;
    deviceFalling @73;
    fanMalfunction @74;
    cameraMalfunction @75;
    cameraFrameRate @76;
    processNotRunning @77;
    dashcamMode @78;
    selfdriveInitializing @79;
    usbError @80;
    cruiseMismatch @81;
    canBusMissing @82;
    selfdrivedLagging @83;
    resumeBlocked @84;
    steerTimeLimit @85;
    vehicleSensorsInvalid @86;
    locationdTemporaryError @87;
    locationdPermanentError @88;
    paramsdTemporaryError @89;
    paramsdPermanentError @90;
    actuatorsApiUnavailable @91;
    espActive @92;
    personalityChanged @93;
    aeb @94;
    userBookmark @95;
    excessiveActuation @96;
    audioFeedback @97;
    blinkerSteerRequired @98;
  }
}

enum LongitudinalPersonality {
  aggressive @0;
  standard @1;
  relaxed @2;
}

struct InitData {
  kernelArgs @0 :List(Text);
  dongleId @1 :Text;
  deviceType @2 :DeviceType;
  version @3 :Text;
  androidBuildInfo @4 :AndroidBuildInfo;
  pandaInfo @5 :PandaInfo;
  dirty @6 :Bool;
  gitCommit @7 :Text;
  gitBranch @8 :Text;
  passive @9 :Bool;
  gitRemote @10 :Text;
  kernelVersion @11 :Text;
  androidProperties @12 :Map(Text, Text);
  params @13 :Map(Text, Data);
  osVersion @14 :Text;
  commands @15 :Map(Text, Data);
  wallTimeNanos @16 :UInt64;
  gitCommitDate @17 :Text;
  bootlogId @18 :Text;
  gitSrcCommit @19 :Text;
  gitSrcCommitDate @20 :Text;

  enum DeviceType {
    unknown @0;
    neo @1;
    chffrAndroid @2;
    chffrIos @3;
    tici @4;
    pc @5;
    tizi @6;
    mici @7;
    ka2 @8;
  }

  struct PandaInfo {
    hasPanda @0 :Bool;
    dongleId @1 :Text;
    stVersion @2 :Text;
    espVersion @3 :Text;
  }

  struct AndroidBuildInfo {
    board @0 :Text;
    bootloader @1 :Text;
    brand @2 :Text;
    device @3 :Text;
    display @4 :Text;
    fingerprint @5 :Text;
    hardware @6 :Text;
    host @7 :Text;
    id @8 :Text;
    manufacturer @9 :Text;
    model @10 :Text;
    product @11 :Text;
    radioVersion @12 :Text;
    serial @13 :Text;
    supportedAbis @14 :List(Text);
    tags @15 :Text;
    time @16 :Int64;
    type @17 :Text;
    user @18 :Text;

    versionCodename @19 :Text;
    versionRelease @20 :Text;
    versionSdk @21 :Int32;
    versionSecurityPatch @22 :Text;
  }

  struct AndroidSensor {
    id @0 :Int32;
    name @1 :Text;
    vendor @2 :Text;
    version @3 :Int32;
    handle @4 :Int32;
    type @5 :Int32;
    maxRange @6 :Float32;
    resolution @7 :Float32;
    power @8 :Float32;
    minDelay @9 :Int32;
    fifoReservedEventCount @10 :UInt32;
    fifoMaxEventCount @11 :UInt32;
    stringType @12 :Text;
    maxDelay @13 :Int32;
  }

  struct ChffrAndroidExtra {
    allCameraCharacteristics @0 :Map(Text, Text);
  }

  struct IosBuildInfo {
    appVersion @0 :Text;
    appBuild @1 :UInt32;
    osVersion @2 :Text;
    deviceModel @3 :Text;
  }
}

struct FrameData {
  frameId @0 :UInt32;
  encodeId @1 :UInt32;
  timestampEof @2 :UInt64;
  integLines @3 :Int32;
  image @4 :Data;
  transform @5 :List(Float32);
  timestampSof @6 :UInt64;
  gain @7 :Float32; # This includes highConversionGain if enabled
  highConversionGain @8 :Bool;
  processingTime @9 :Float32;
  measuredGreyFraction @10 :Float32;
  targetGreyFraction @11 :Float32;
  temperaturesC @12 :List(Float32);
  exposureValPercent @13 :Float32;
  frameIdSensor @14 :UInt32;
  sensor @15 :ImageSensor;
  requestId @16 :UInt32;
  enum ImageSensor {
    unknown @0;
    ar0231 @1;
    ox03c10 @2;
    os04c10 @3;
  }

}

struct Thumbnail {
  frameId @0 :UInt32;
  timestampEof @1 :UInt64;
  thumbnail @2 :Data;
  encoding @3 :Encoding;

  enum Encoding {
    unknown @0;
    jpeg @1;
    keyframe @2;
  }
}

struct GPSNMEAData {
  timestamp @0 :Int64;
  localWallTime @1 :UInt64;
  nmea @2 :Text;
}

# android sensor_event_t
struct SensorEventData {
  union {
    acceleration @0 :SensorVec;
    magnetic @1 :SensorVec;
    orientation @2 :SensorVec;
    gyro @3 :SensorVec;
    pressure @4 :SensorVec;
    magneticUncalibrated @5 :SensorVec;
    gyroUncalibrated @6 :SensorVec;
    proximity @7: Float32;
    light @8: Float32;
    temperature @9: Float32;
  }
  version @10 :Int32;
  sensor @11 :Int32;
  type @12 :Int32;
  timestamp @13 :Int64;
  source @14 :SensorSource;

  struct SensorVec {
    v @0 :List(Float32);
    status @1 :Int8;
  }

  enum SensorSource {
    android @0;
    iOS @1;
    fiber @2;
    velodyne @3;  # Velodyne IMU
    bno055 @4;    # Bosch accelerometer
    lsm6ds3 @5;   # includes LSM6DS3 and LSM6DS3TR, TR = tape reel
    bmp280 @6;    # barometer
    mmc3416x @7;  # magnetometer
    bmx055 @8;
    rpr0521 @9;
    lsm6ds3trc @10;
    mmc5603nj @11;
    icm42670 @12;
    lis2mdl @13;
  }
}

# android struct GpsLocation
struct GpsLocationData {
  # Contains module-specific flags.
  flags @0 :UInt16;

  # Represents latitude in degrees.
  latitude @1 :Float64;

  # Represents longitude in degrees.
  longitude @2 :Float64;

  # Represents altitude in meters above the WGS 84 reference ellipsoid.
  altitude @3 :Float64;

  # Represents speed in meters per second.
  speed @4 :Float32;

  # Represents heading in degrees.
  bearingDeg @5 :Float32;

  # Represents expected horizontal accuracy in meters.
  horizontalAccuracy @6 :Float32;

  unixTimestampMillis @7 :Int64;

  source @8 :SensorSource;

  # Represents NED velocity in m/s.
  vNED @9 :List(Float32);

  # Represents expected vertical accuracy in meters. (presumably 1 sigma?)
  verticalAccuracy @10 :Float32;

  # Represents bearing accuracy in degrees. (presumably 1 sigma?)
  bearingAccuracyDeg @11 :Float32;

  # Represents velocity accuracy in m/s. (presumably 1 sigma?)
  speedAccuracy @12 :Float32;

  hasFix @13 :Bool;
  satelliteCount @14 :Int8;

  enum SensorSource {
    android @0;
    iOS @1;
    car @2;
    velodyne @3;  # Velodyne IMU
    fusion @4;
    external @5;
    ublox @6;
    trimble @7;
    qcomdiag @8;
    unicore @9;
  }
}

enum Desire {
  none @0;
  turnLeft @1;
  turnRight @2;
  laneChangeLeft @3;
  laneChangeRight @4;
  keepLeft @5;
  keepRight @6;
}

enum LaneChangeState {
  off @0;
  preLaneChange @1;
  laneChangeStarting @2;
  laneChangeFinishing @3;
}

enum LaneChangeDirection {
  none @0;
  left @1;
  right @2;
}

struct CanData {
  address @0 :UInt32;
  dat     @1 :Data;
  src     @2 :UInt8;
}

struct DeviceState @0xa4d8b5af2aa492eb {
  deviceType @0 :InitData.DeviceType;
  networkType @1 :NetworkType;
  networkInfo @2 :NetworkInfo;
  networkStrength @3 :NetworkStrength;
  networkStats @4 :NetworkStats;
  networkMetered @5 :Bool;
  lastAthenaPingTime @6 :UInt64;
  started @7 :Bool;
  startedMonoTime @8 :UInt64;
  freeSpacePercent @9 :Float32;
  memoryUsagePercent @10 :Int8;
  gpuUsagePercent @11 :Int8;
  cpuUsagePercent @12 :List(Int8);  # per-core cpu usage
  npuUsagePercent @13 :List(Int8);  # per-core npu usage
  npuDriverVersion @32 :Text;       # NPU driver version (from RKNN, written by modeld/dmonitoringmodeld)
  offroadPowerUsageUwh @14 :UInt32;
  carBatteryCapacityUwh @15 :UInt32;
  powerDrawW @16 :Float32;
  somPowerDrawW @17 :Float32;
  cpuTempC @18 :List(Float32);
  gpuTempC @19 :List(Float32);
  dspTempC @20 :Float32;
  memoryTempC @21 :Float32;
  modemTempC @22 :List(Float32);
  pmicTempC @23 :List(Float32);
  intakeTempC @24 :Float32;
  exhaustTempC @25 :Float32;
  caseTempC @26 :Float32;
  maxTempC @27 :Float32;  # max of other temps, used to control fan
  thermalZones @28 :List(ThermalZone);
  thermalStatus @29 :ThermalStatus;
  fanSpeedPercentDesired @30 :UInt16;
  screenBrightnessPercent @31 :Int8;

  struct ThermalZone {
    name @0 :Text;
    temp @1 :Float32;
  }

  enum ThermalStatus {
    green @0;
    yellow @1;
    red @2;
    danger @3;
  }

  enum NetworkType {
    none @0;
    wifi @1;
    cell2G @2;
    cell3G @3;
    cell4G @4;
    cell5G @5;
    ethernet @6;
  }

  enum NetworkStrength {
    unknown @0;
    poor @1;
    moderate @2;
    good @3;
    great @4;
  }

  struct NetworkInfo {
    technology @0 :Text;
    operator @1 :Text;
    band @2 :Text;
    channel @3 :UInt16;
    extra @4 :Text;
    state @5 :Text;
  }

  struct NetworkStats {
    wwanTx @0 :Int64;
    wwanRx @1 :Int64;
  }

}

struct PandaState @0xa7649e2575e4591e {
  voltage @0 :UInt32;
  current @1 :UInt32;
  ignitionLine @2 :Bool;
  controlsAllowed @3 :Bool;
  rxBufferOverflow @4 :UInt32;
  txBufferOverflow @5 :UInt32;
  pandaType @6 :PandaType;
  ignitionCan @7 :Bool;
  faultStatus @8 :FaultStatus;
  powerSaveEnabled @9 :Bool;
  uptime @10 :UInt32;
  faults @11 :List(FaultType);
  heartbeatLost @12 :Bool;
  harnessStatus @13 :HarnessStatus;
  safetyModel @14 :Car.CarParams.SafetyModel;
  safetyRxInvalid @15 :UInt32;
  safetyTxBlocked @16 :UInt32;
  safetyParam @17 :UInt16;
  alternativeExperience @18 :Int16;
  safetyRxChecksInvalid @19 :Bool;
  canState0 @20 :PandaCanState;
  canState1 @21 :PandaCanState;
  canState2 @22 :PandaCanState;
  interruptLoad @23 :Float32;
  fanPower @24 :UInt8;
  spiErrorCount @25 :UInt16;
  sbu1Voltage @26 :Float32;
  sbu2Voltage @27 :Float32;

  enum FaultStatus {
    none @0;
    faultTemp @1;
    faultPerm @2;
  }

  enum FaultType {
    relayMalfunction @0;
    unusedInterruptHandled @1;
    interruptRateCan1 @2;
    interruptRateCan2 @3;
    interruptRateCan3 @4;
    interruptRateTach @5;
    interruptRateInterrupts @6;
    interruptRateSpiDma @7;
    interruptRateSpiCs @8;
    interruptRateUart1 @9;
    interruptRateUart2 @10;
    interruptRateUart3 @11;
    interruptRateUart5 @12;
    interruptRateUartDma @13;
    interruptRateUsb @14;
    interruptRateTim1 @15;
    interruptRateTim3 @16;
    registerDivergent @17;
    interruptRateKlineInit @18;
    interruptRateClockSource @19;
    interruptRateTick @20;
    interruptRateExti @21;
    interruptRateSpi @22;
    interruptRateUart7 @23;
    sirenMalfunction @24;
    heartbeatLoopWatchdog @25;
    # Update max fault type in boardd when adding faults
  }

  enum PandaType @0x8a58adf93e5b3751 {
    unknown @0;
    whitePanda @1;
    greyPanda @2;
    blackPanda @3;
    pedal @4;
    uno @5;
    dos @6;
    redPanda @7;
    redPandaV2 @8;
    tres @9;
    cuatro @10;
    kedua @11;
  }

  enum HarnessStatus {
    notConnected @0;
    normal @1;
    flipped @2;
  }

  struct PandaCanState {
    busOff @0 :Bool;
    busOffCnt @1 :UInt32;
    errorWarning @2 :Bool;
    errorPassive @3 :Bool;
    lastError @4 :LecErrorCode;
    lastStoredError @5 :LecErrorCode;
    lastDataError @6 :LecErrorCode;
    lastDataStoredError @7 :LecErrorCode;
    receiveErrorCnt @8 :UInt8;
    transmitErrorCnt @9 :UInt8;
    totalErrorCnt @10 :UInt32;
    totalTxLostCnt @11 :UInt32;
    totalRxLostCnt @12 :UInt32;
    totalTxCnt @13 :UInt32;
    totalRxCnt @14 :UInt32;
    totalFwdCnt @15 :UInt32;
    canSpeed @16 :UInt16;
    canDataSpeed @17 :UInt16;
    canfdEnabled @18 :Bool;
    brsEnabled @19 :Bool;
    canfdNonIso @20 :Bool;
    irq0CallRate @21 :UInt32;
    irq1CallRate @22 :UInt32;
    irq2CallRate @23 :UInt32;
    canCoreResetCnt @24 :UInt32;

    enum LecErrorCode {
      noError @0;
      stuffError @1;
      formError @2;
      ackError @3;
      bit1Error @4;
      bit0Error @5;
      crcError @6;
      noChange @7;
    }
  }

}

struct PeripheralState {
  pandaType @0 :PandaState.PandaType;
  voltage @1 :UInt32;
  current @2 :UInt32;
  fanSpeedRpm @3 :UInt16;
}

struct RadarState @0x9a185389d6fdd05f {
  leadOne @0 :LeadData;
  leadTwo @1 :LeadData;
  mdMonoTime @2 :UInt64;
  carStateMonoTime @3 :UInt64;
  radarErrors @4 :Car.RadarData.Error;

  struct LeadData {
    dRel @0 :Float32;
    yRel @1 :Float32;
    vRel @2 :Float32;
    aRel @3 :Float32;
    vLead @4 :Float32;
    dPath @5 :Float32;
    vLat @6 :Float32;
    vLeadK @7 :Float32;
    aLeadK @8 :Float32;
    fcw @9 :Bool;
    status @10 :Bool;
    aLeadTau @11 :Float32;
    modelProb @12 :Float32;
    radar @13 :Bool;
    radarTrackId @14 :Int32 = -1;
  }
}

struct LiveCalibrationData {
  calCycle @0 :Int32;
  calPerc @1 :Int8;
  calStatus @2 :Status;
  extrinsicMatrix @3 :List(Float32);
  rpyCalib @4 :List(Float32);
  rpyCalibSpread @5 :List(Float32);
  wideFromDeviceEuler @6 :List(Float32);
  validBlocks @7 :Int32;
  height @8 :List(Float32);

  enum Status {
    uncalibrated @0;
    calibrated @1;
    invalid @2;
    recalibrating @3;
  }
}

struct SelfdriveState {
  state @0 :OpenpilotState;
  enabled @1 :Bool;
  active @2 :Bool;
  alertText1 @3 :Text;
  alertText2 @4 :Text;
  alertStatus @5 :AlertStatus;
  alertSize @6 :AlertSize;
  alertType @7 :Text;
  alertSound @8 :Car.CarControl.HUDControl.AudibleAlert;
  engageable @9 :Bool;  # can OP be engaged?
  experimentalMode @10 :Bool;
  personality @11 :LongitudinalPersonality;
  alertHudVisual @12 :Car.CarControl.HUDControl.VisualAlert;

  enum OpenpilotState @0xdbe58b96d2d1ac61 {
    disabled @0;
    preEnabled @1;
    enabled @2;
    softDisabling @3;
    overriding @4;  # superset of overriding with steering or accelerator
  }

  enum AlertStatus @0xa0d0dcd113193c62 {
    normal @0;
    userPrompt @1;
    critical @2;
  }

  enum AlertSize @0xe98bb99d6e985f64 {
    none @0;
    small @1;
    mid @2;
    full @3;
  }
}

struct ControlsState @0x97ff69c53601abf1 {
  lateralControlState :union {
    pidState @0 :LateralPIDState;
    angleState @1 :LateralAngleState;
    debugState @2 :LateralDebugState;
    torqueState @3 :LateralTorqueState;
    lqrStateDEPRECATED @4 :LateralLQRState;
  }
  upAccelCmd @5 :Float32;
  uiAccelCmd @6 :Float32;
  curvature @7 :Float32;  # path curvature from vehicle model
  longControlState @8 :Car.CarControl.Actuators.LongControlState;
  longitudinalPlanMonoTime @9 :UInt64;
  lateralPlanMonoTime @10 :UInt64;
  ufAccelCmd @11 :Float32;
  desiredCurvature @12 :Float32;  # lag adjusted curvatures used by lateral controllers
  forceDecel @13 :Bool;
  # deprecated, for replay migration from old logs (ordinals last)
  activeDEPRECATED @14 :Bool;
  alertSizeDEPRECATED @15 :SelfdriveState.AlertSize;
  alertSound2DEPRECATED @16 :Car.CarControl.HUDControl.AudibleAlert;
  alertStatusDEPRECATED @17 :SelfdriveState.AlertStatus;
  alertText1DEPRECATED @18 :Text;
  alertText2DEPRECATED @19 :Text;
  alertTypeDEPRECATED @20 :Text;
  enabledDEPRECATED @21 :Bool;
  engageableDEPRECATED @22 :Bool;
  experimentalModeDEPRECATED @23 :Bool;
  personalityDEPRECATED @24 :LongitudinalPersonality;
  stateDEPRECATED @25 :SelfdriveState.OpenpilotState;

  struct LateralINDIState {
    active @0 :Bool;
    steeringAngleDeg @1 :Float32;
    steeringRateDeg @2 :Float32;
    steeringAccelDeg @3 :Float32;
    rateSetPoint @4 :Float32;
    accelSetPoint @5 :Float32;
    accelError @6 :Float32;
    delayedOutput @7 :Float32;
    delta @8 :Float32;
    output @9 :Float32;
    saturated @10 :Bool;
    steeringAngleDesiredDeg @11 :Float32;
    steeringRateDesiredDeg @12 :Float32;
  }

  struct LateralPIDState {
    active @0 :Bool;
    steeringAngleDeg @1 :Float32;
    steeringRateDeg @2 :Float32;
    angleError @3 :Float32;
    p @4 :Float32;
    i @5 :Float32;
    f @6 :Float32;
    output @7 :Float32;
    saturated @8 :Bool;
    steeringAngleDesiredDeg @9 :Float32;
   }

  struct LateralTorqueState {
    active @0 :Bool;
    error @1 :Float32;
    p @2 :Float32;
    i @3 :Float32;
    d @4 :Float32;
    f @5 :Float32;
    output @6 :Float32;
    saturated @7 :Bool;
    errorRate @8 :Float32;
    actualLateralAccel @9 :Float32;
    desiredLateralAccel @10 :Float32;
    desiredLateralJerk @11 :Float32;
    version @12 :Int32;
   }

  struct LateralLQRState {
    active @0 :Bool;
    steeringAngleDeg @1 :Float32;
    i @2 :Float32;
    output @3 :Float32;
    lqrOutput @4 :Float32;
    saturated @5 :Bool;
    steeringAngleDesiredDeg @6 :Float32;
  }

  struct LateralAngleState {
    active @0 :Bool;
    steeringAngleDeg @1 :Float32;
    output @2 :Float32;
    saturated @3 :Bool;
    steeringAngleDesiredDeg @4 :Float32;
  }

  struct LateralCurvatureState {
    active @0 :Bool;
    actualCurvature @1 :Float32;
    desiredCurvature @2 :Float32;
    error @3 :Float32;
    p @4 :Float32;
    i @5 :Float32;
    f @6 :Float32;
    output @7 :Float32;
    saturated @8 :Bool;
  }

  struct LateralDebugState {
    active @0 :Bool;
    steeringAngleDeg @1 :Float32;
    output @2 :Float32;
    saturated @3 :Bool;
  }

}

struct DrivingModelData {
  frameId @0 :UInt32;
  frameIdExtra @1 :UInt32;
  action @2 :ModelDataV2.Action;
  laneLineMeta @3 :LaneLineMeta;
  meta @4 :MetaData;
  path @5 :PolyPath;
  frameDropPerc @6 :Float32;
  modelExecutionTime @7 :Float32;


  struct PolyPath {
    xCoefficients @0 :List(Float32);
    yCoefficients @1 :List(Float32);
    zCoefficients @2 :List(Float32);
  }

  struct LaneLineMeta {
    leftY @0 :Float32;
    rightY @1 :Float32;
    leftProb @2 :Float32;
    rightProb @3 :Float32;
  }

  struct MetaData {
    laneChangeState @0 :LaneChangeState;
    laneChangeDirection @1 :LaneChangeDirection;
  }
}

# All SI units and in device frame
struct XYZTData @0xc3cbae1fd505ae80 {
  x @0 :List(Float32);
  y @1 :List(Float32);
  z @2 :List(Float32);
  t @3 :List(Float32);
  xStd @4 :List(Float32);
  yStd @5 :List(Float32);
  zStd @6 :List(Float32);
}

struct ModelDataV2 {
  frameId @0 :UInt32;
  frameAge @1 :UInt32;
  frameDropPerc @2 :Float32;
  timestampEof @3 :UInt64;
  position @4 :XYZTData;
  orientation @5 :XYZTData;
  velocity @6 :XYZTData;
  orientationRate @7 :XYZTData;
  laneLines @8 :List(XYZTData);
  laneLineProbs @9 :List(Float32);
  roadEdges @10 :List(XYZTData);
  leads @11 :List(LeadDataV2);
  meta @12 :MetaData;
  laneLineStds @13 :List(Float32);
  roadEdgeStds @14 :List(Float32);
  modelExecutionTime @15 :Float32;
  rawPredictions @16 :Data;
  leadsV3 @17 :List(LeadDataV3);
  acceleration @18 :XYZTData;
  frameIdExtra @19 :UInt32;
  confidence @20: ConfidenceClass;
  action @21: Action;

  struct LeadDataV2 {
    prob @0 :Float32; # probability that car is your lead at time t
    t @1 :Float32;

    # x and y are relative position in device frame
    # v is norm relative speed
    # a is norm relative acceleration
    xyva @2 :List(Float32);
    xyvaStd @3 :List(Float32);
  }

  struct LeadDataV3 {
    prob @0 :Float32; # probability that car is your lead at time t
    probTime @1 :Float32;
    t @2 :List(Float32);

    # x and y are relative position in device frame
    # v absolute norm speed
    # a is derivative of v
    x @3 :List(Float32);
    xStd @4 :List(Float32);
    y @5 :List(Float32);
    yStd @6 :List(Float32);
    v @7 :List(Float32);
    vStd @8 :List(Float32);
    a @9 :List(Float32);
    aStd @10 :List(Float32);
  }


  struct MetaData {
    engagedProb @0 :Float32;
    desirePrediction @1 :List(Float32);
    desireState @2 :List(Float32);
    disengagePredictions @3 :DisengagePredictions;
    hardBrakePredicted @4 :Bool;
    laneChangeState @5 :LaneChangeState;
    laneChangeDirection @6 :LaneChangeDirection;
  }

  enum ConfidenceClass {
    red @0;
    yellow @1;
    green @2;
  }

  struct DisengagePredictions {
    t @0 :List(Float32);
    brakeDisengageProbs @1 :List(Float32);
    gasDisengageProbs @2 :List(Float32);
    steerOverrideProbs @3 :List(Float32);
    brake3MetersPerSecondSquaredProbs @4 :List(Float32);
    brake4MetersPerSecondSquaredProbs @5 :List(Float32);
    brake5MetersPerSecondSquaredProbs @6 :List(Float32);
    gasPressProbs @7 :List(Float32);
    brakePressProbs @8 :List(Float32);
  }

  struct Pose {
    trans @0 :List(Float32); # m/s in device frame
    rot @1 :List(Float32); # rad/s in device frame
    transStd @2 :List(Float32); # std m/s in device frame
    rotStd @3 :List(Float32); # std rad/s in device frame
  }

  struct LateralPlannerSolution {
    x @0 :List(Float32);
    y @1 :List(Float32);
    yaw @2 :List(Float32);
    yawRate @3 :List(Float32);
    xStd @4 :List(Float32);
    yStd @5 :List(Float32);
    yawStd @6 :List(Float32);
    yawRateStd @7 :List(Float32);
  }

  struct Action {
    desiredCurvature @0 :Float32;
    desiredAcceleration @1 :Float32;
    shouldStop @2 :Bool;
  }
}

struct EncodeIndex {
  # picture from camera
  frameId @0 :UInt32;
  type @1 :Type;
  # index of encoder from start of route
  encodeId @2 :UInt32;
  # minute long segment this frame is in
  segmentNum @3 :Int32;
  # index into camera file in segment in presentation order
  segmentId @4 :UInt32;
  # index into camera file in segment in encode order
  segmentIdEncode @5 :UInt32;
  timestampSof @6 :UInt64;
  timestampEof @7 :UInt64;

  # encoder metadata
  flags @8 :UInt32;
  len @9 :UInt32;

  enum Type {
    bigBoxLossless @0;
    fullHEVC @1;
    qcameraH264 @2;
    livestreamH264 @3;
  }
}

struct AndroidLogEntry {
  id @0 :UInt8;
  ts @1 :UInt64;
  priority @2 :UInt8;
  pid @3 :Int32;
  tid @4 :Int32;
  tag @5 :Text;
  message @6 :Text;
}

struct DriverAssistance {
  # Lane Departure Warnings
  leftLaneDeparture @0 :Bool;
  rightLaneDeparture @1 :Bool;

  # FCW, AEB, etc. will go here
}

struct LongitudinalPlan @0xe00b5b3eba12876c {
  hasLead @0 :Bool;
  fcw @1 :Bool;
  modelMonoTime @2 :UInt64;
  aTarget @3 :Float32;
  longitudinalPlanSource @4 :LongitudinalPlanSource;
  solverExecutionTime @5 :Float32;
  processingDelay @6 :Float32;
  accels @7 :List(Float32);
  speeds @8 :List(Float32);
  jerks @9 :List(Float32);
  shouldStop @10: Bool;
  allowThrottle @11: Bool;
  allowBrake @12: Bool;

  enum LongitudinalPlanSource {
    cruise @0;
    lead0 @1;
    lead1 @2;
    lead2 @3;
    e2e @4;
  }

  struct GpsTrajectory {
    x @0 :List(Float32);
    y @1 :List(Float32);
  }
}
struct UiPlan {
  frameId @2 :UInt32;
  position @0 :XYZTData;
  accel @1 :List(Float32);
}

struct LateralPlan @0xe1e9318e2ae8b51e {
  modelMonoTime @0 :UInt64;
  mpcSolutionValid @1 :Bool;
  dPathPoints @2 :List(Float32);
  desire @3 :Desire;
  laneChangeState @4 :LaneChangeState;
  laneChangeDirection @5 :LaneChangeDirection;
  psis @6 :List(Float32);
  curvatures @7 :List(Float32);
  curvatureRates @8 :List(Float32);
  solverExecutionTime @9 :Float32;
  useLaneLines @10 :Bool;
  solverCost @11 :Float32;
  solverState @12 :SolverState;

  struct SolverState {
    x @0 :List(List(Float32));
    u @1 :List(Float32);
  }
}

struct LiveLocationKalman {

  # More info on reference frames:
  # https://github.com/commaai/openpilot/tree/master/common/transformations

  positionECEF @0 : Measurement;
  positionGeodetic @1 : Measurement;
  velocityECEF @2 : Measurement;
  velocityNED @3 : Measurement;
  velocityDevice @4 : Measurement;
  accelerationDevice @5: Measurement;


  # These angles are all eulers and roll, pitch, yaw
  # orientationECEF transforms to rot matrix: ecef_from_device
  orientationECEF @6 : Measurement;
  calibratedOrientationECEF @20 : Measurement;
  orientationNED @7 : Measurement;
  angularVelocityDevice @8 : Measurement;

  # orientationNEDCalibrated transforms to rot matrix: NED_from_calibrated
  calibratedOrientationNED @9 : Measurement;

  # Calibrated frame is simply device frame
  # aligned with the vehicle
  velocityCalibrated @10 : Measurement;
  accelerationCalibrated @11 : Measurement;
  angularVelocityCalibrated @12 : Measurement;

  gpsWeek @13 :Int32;
  gpsTimeOfWeek @14 :Float64;
  status @15 :Status;
  unixTimestampMillis @16 :Int64;
  inputsOK @17 :Bool = true;
  posenetOK @18 :Bool = true;
  gpsOK @19 :Bool = true;
  sensorsOK @21 :Bool = true;
  deviceStable @22 :Bool = true;
  timeSinceReset @23 :Float64;
  excessiveResets @24 :Bool;
  timeToFirstFix @25 :Float32;

  filterState @26 : Measurement;

  enum Status {
    uninitialized @0;
    uncalibrated @1;
    valid @2;
  }

  struct Measurement {
    value @0 : List(Float64);
    std @1 : List(Float64);
    valid @2 : Bool;
  }
}


struct LivePose {
  # More info on reference frames:
  # https://github.com/commaai/openpilot/tree/master/common/transformations
  orientationNED @0 :XYZMeasurement;
  velocityDevice @1 :XYZMeasurement;
  accelerationDevice @2 :XYZMeasurement;
  angularVelocityDevice @3 :XYZMeasurement;

  inputsOK @4 :Bool = false;
  posenetOK @5 :Bool = false;
  sensorsOK @6 :Bool = false;

  debugFilterState @7 :FilterState;

  struct XYZMeasurement {
    x @0 :Float32;
    y @1 :Float32;
    z @2 :Float32;
    xStd @3 :Float32;
    yStd @4 :Float32;
    zStd @5 :Float32;
    valid @6 :Bool;
  }

  struct FilterState {
    value @0 : List(Float64);
    std @1 : List(Float64);
    valid @2 : Bool;

    observations @3 :List(Observation);

    struct Observation {
      kind @0 :Int32;
      value @1 :List(Float32);
      error @2 :List(Float32);
    }
  }
}

struct ProcLog {
  cpuTimes @0 :List(CPUTimes);
  mem @1 :Mem;
  procs @2 :List(Process);

  struct Process {
    pid @0 :Int32;
    name @1 :Text;
    state @2 :UInt8;
    ppid @3 :Int32;

    cpuUser @4 :Float32;
    cpuSystem @5 :Float32;
    cpuChildrenUser @6 :Float32;
    cpuChildrenSystem @7 :Float32;
    priority @8 :Int64;
    nice @9 :Int32;
    numThreads @10 :Int32;
    startTime @11 :Float64;

    memVms @12 :UInt64;
    memRss @13 :UInt64;

    processor @14 :Int32;

    cmdline @15 :List(Text);
    exe @16 :Text;
  }

  struct CPUTimes {
    cpuNum @0 :Int64;
    user @1 :Float32;
    nice @2 :Float32;
    system @3 :Float32;
    idle @4 :Float32;
    iowait @5 :Float32;
    irq @6 :Float32;
    softirq @7 :Float32;
  }

  struct Mem {
    total @0 :UInt64;
    free @1 :UInt64;
    available @2 :UInt64;
    buffers @3 :UInt64;
    cached @4 :UInt64;
    active @5 :UInt64;
    inactive @6 :UInt64;
    shared @7 :UInt64;
  }
}

struct GnssMeasurements {
  measTime @0 :UInt64;
  gpsWeek @1 :Int16;
  gpsTimeOfWeek @2 :Float64;

  correctedMeasurements @3 :List(CorrectedMeasurement);
  ephemerisStatuses @9 :List(EphemerisStatus);

  kalmanPositionECEF @4 :LiveLocationKalman.Measurement;
  kalmanVelocityECEF @5 :LiveLocationKalman.Measurement;
  positionECEF @6 :LiveLocationKalman.Measurement;
  velocityECEF @7 :LiveLocationKalman.Measurement;
  timeToFirstFix @8 :Float32;
  # Todo sync this with timing pulse of ublox

  struct EphemerisStatus {
    constellationId @0 :ConstellationId;
    svId @1 :UInt8;
    type @2 :EphemerisType;
    source @3 :EphemerisSource;
    gpsWeek @4 : UInt16;
    tow @5 :Float64;
  }

  struct CorrectedMeasurement {
    constellationId @0 :ConstellationId;
    svId @1 :UInt8;
    # Is 0 when not Glonass constellation.
    glonassFrequency @2 :Int8;
    pseudorange @3 :Float64;
    pseudorangeStd @4 :Float64;
    pseudorangeRate @5 :Float64;
    pseudorangeRateStd @6 :Float64;
    # Satellite position and velocity [x,y,z]
    satPos @7 :List(Float64);
    satVel @8 :List(Float64);
  }

  enum ConstellationId {
    # Satellite Constellation using the Ublox gnssid as index
    gps @0;
    sbas @1;
    galileo @2;
    beidou @3;
    imes @4;
    qznss @5;
    glonass @6;
  }

  enum EphemerisType {
    nav @0;
    # Different ultra-rapid files:
    nasaUltraRapid @1;
    glonassIacUltraRapid @2;
    qcom @3;
  }

  enum EphemerisSource {
    gnssChip @0;
    internet @1;
    cache @2;
    unknown @3;
  }
}

struct UbloxGnss {
  union {
    measurementReport @0 :MeasurementReport;
    ephemeris @1 :Ephemeris;
    ionoData @2 :IonoData;
    hwStatus @3 :HwStatus;
    hwStatus2 @4 :HwStatus2;
    glonassEphemeris @5 :GlonassEphemeris;
    satReport @6 :SatReport;
  }

  struct SatReport {
    #received time of week in gps time in seconds and gps week
    iTow @0 :UInt32;
    svs @1 :List(SatInfo);

    struct SatInfo {
      svId @0 :UInt8;
      gnssId @1 :UInt8;
      flagsBitfield @2 :UInt32;
      cno @3 :UInt8;
      elevationDeg @4 :Int8;
      azimuthDeg @5 :Int16;
      pseudorangeResidual @6 :Float32;
    }
  }

  struct MeasurementReport {
    #received time of week in gps time in seconds and gps week
    rcvTow @0 :Float64;
    gpsWeek @1 :UInt16;
    # leap seconds in seconds
    leapSeconds @2 :UInt16;
    # receiver status
    receiverStatus @3 :ReceiverStatus;
    # num of measurements to follow
    numMeas @4 :UInt8;
    measurements @5 :List(Measurement);

    struct ReceiverStatus {
      # leap seconds have been determined
      leapSecValid @0 :Bool;
      # Clock reset applied
      clkReset @1 :Bool;
    }

    struct Measurement {
      svId @0 :UInt8;
      trackingStatus @1 :TrackingStatus;
      # pseudorange in meters
      pseudorange @2 :Float64;
      # carrier phase measurement in cycles
      carrierCycles @3 :Float64;
      # doppler measurement in Hz
      doppler @4 :Float32;
      # GNSS id, 0 is gps
      gnssId @5 :UInt8;
      glonassFrequencyIndex @6 :UInt8;
      # carrier phase locktime counter in ms
      locktime @7 :UInt16;
      # Carrier-to-noise density ratio (signal strength) in dBHz
      cno @8 :UInt8;
      # pseudorange standard deviation in meters
      pseudorangeStdev @9 :Float32;
      # carrier phase standard deviation in cycles
      carrierPhaseStdev @10 :Float32;
      # doppler standard deviation in Hz
      dopplerStdev @11 :Float32;
      sigId @12 :UInt8;

      struct TrackingStatus {
        # pseudorange valid
        pseudorangeValid @0 :Bool;
        # carrier phase valid
        carrierPhaseValid @1 :Bool;
        # half cycle valid
        halfCycleValid @2 :Bool;
        # half cycle subtracted from phase
        halfCycleSubtracted @3 :Bool;
      }
    }
  }

  struct Ephemeris {
    # This is according to the rinex (2?) format
    svId @0 :UInt16;
    year @1 :UInt16;
    month @2 :UInt16;
    day @3 :UInt16;
    hour @4 :UInt16;
    minute @5 :UInt16;
    second @6 :Float32;
    af0 @7 :Float64;
    af1 @8 :Float64;
    af2 @9 :Float64;

    iode @10 :Float64;
    crs @11 :Float64;
    deltaN @12 :Float64;
    m0 @13 :Float64;

    cuc @14 :Float64;
    ecc @15 :Float64;
    cus @16 :Float64;
    a @17 :Float64; # note that this is not the root!!

    toe @18 :Float64;
    cic @19 :Float64;
    omega0 @20 :Float64;
    cis @21 :Float64;

    i0 @22 :Float64;
    crc @23 :Float64;
    omega @24 :Float64;
    omegaDot @25 :Float64;

    iDot @26 :Float64;
    codesL2 @27 :Float64;
    l2 @28 :Float64;

    svAcc @29 :Float64;
    svHealth @30 :Float64;
    tgd @31 :Float64;
    iodc @32 :Float64;

    transmissionTime @33 :Float64;
    fitInterval @34 :Float64;

    toc @35 :Float64;

    ionoCoeffsValid @36 :Bool;
    ionoAlpha @37 :List(Float64);
    ionoBeta @38 :List(Float64);

    towCount @39 :UInt32;
    toeWeek @40 :UInt16;
    tocWeek @41 :UInt16;
  }

  struct IonoData {
    svHealth @0 :UInt32;
    tow  @1 :Float64;
    gpsWeek @2 :Float64;

    ionoAlpha @3 :List(Float64);
    ionoBeta @4 :List(Float64);

    healthValid @5 :Bool;
    ionoCoeffsValid @6 :Bool;
  }

  struct HwStatus {
    noisePerMS @0 :UInt16;
    agcCnt @1 :UInt16;
    aStatus @2 :AntennaSupervisorState;
    aPower @3 :AntennaPowerStatus;
    jamInd @4 :UInt8;
    flags @5 :UInt8;

    enum AntennaSupervisorState {
      init @0;
      dontknow @1;
      ok @2;
      short @3;
      open @4;
    }

    enum AntennaPowerStatus {
      off @0;
      on @1;
      dontknow @2;
    }
  }

  struct HwStatus2 {
    ofsI @0 :Int8;
    magI @1 :UInt8;
    ofsQ @2 :Int8;
    magQ @3 :UInt8;
    cfgSource @4 :ConfigSource;
    lowLevCfg @5 :UInt32;
    postStatus @6 :UInt32;

    enum ConfigSource {
      undefined @0;
      rom @1;
      otp @2;
      configpins @3;
      flash @4;
    }
  }

  struct GlonassEphemeris {
    svId @0 :UInt16;
    year @1 :UInt16;
    dayInYear @2 :UInt16;
    hour @3 :UInt16;
    minute @4 :UInt16;
    second @5 :Float32;

    x @6 :Float64;
    xVel @7 :Float64;
    xAccel @8 :Float64;
    y @9 :Float64;
    yVel @10 :Float64;
    yAccel @11 :Float64;
    z @12 :Float64;
    zVel @13 :Float64;
    zAccel @14 :Float64;

    svType @15 :UInt8;
    svURA @16 :Float32;
    age @17 :UInt8;

    svHealth @18 :UInt8;
    tb @19 :UInt16;

    tauN @20 :Float64;
    deltaTauN @21 :Float64;
    gammaN @22 :Float64;

    p1 @23 :UInt8;
    p2 @24 :UInt8;
    p3 @25 :UInt8;
    p4 @26 :UInt8;

    n4 @27 :UInt8;
    nt @28 :UInt16;
    freqNum @29 :Int16;
    tkSeconds @30 :UInt32;
  }
}

struct QcomGnss @0xde94674b07ae51c1 {
  logTs @0 :UInt64;
  union {
    measurementReport @1 :MeasurementReport;
    clockReport @2 :ClockReport;
    drMeasurementReport @3 :DrMeasurementReport;
    drSvPoly @4 :DrSvPolyReport;
    rawLog @5 :Data;
  }

  enum MeasurementSource @0xd71a12b6faada7ee {
    gps @0;
    glonass @1;
    beidou @2;
    unknown3 @3;
    unknown4 @4;
    unknown5 @5;
    sbas @6;
  }

  enum SVObservationState @0xe81e829a0d6c83e9 {
    idle @0;
    search @1;
    searchVerify @2;
    bitEdge @3;
    trackVerify @4;
    track @5;
    restart @6;
    dpo @7;
    glo10msBe @8;
    glo10msAt @9;
  }

  struct MeasurementStatus @0xe501010e1bcae83b {
    subMillisecondIsValid @0 :Bool;
    subBitTimeIsKnown @1 :Bool;
    satelliteTimeIsKnown @2 :Bool;
    bitEdgeConfirmedFromSignal @3 :Bool;
    measuredVelocity @4 :Bool;
    fineOrCoarseVelocity @5 :Bool;
    lockPointValid @6 :Bool;
    lockPointPositive @7 :Bool;
    lastUpdateFromDifference @8 :Bool;
    lastUpdateFromVelocityDifference @9 :Bool;
    strongIndicationOfCrossCorelation @10 :Bool;
    tentativeMeasurement @11 :Bool;
    measurementNotUsable @12 :Bool;
    sirCheckIsNeeded @13 :Bool;
    probationMode @14 :Bool;

    glonassMeanderBitEdgeValid @15 :Bool;
    glonassTimeMarkValid @16 :Bool;

    gpsRoundRobinRxDiversity @17 :Bool;
    gpsRxDiversity @18 :Bool;
    gpsLowBandwidthRxDiversityCombined @19 :Bool;
    gpsHighBandwidthNu4 @20 :Bool;
    gpsHighBandwidthNu8 @21 :Bool;
    gpsHighBandwidthUniform @22 :Bool;
    multipathIndicator @23 :Bool;

    imdJammingIndicator @24 :Bool;
    lteB13TxJammingIndicator @25 :Bool;
    freshMeasurementIndicator @26 :Bool;

    multipathEstimateIsValid @27 :Bool;
    directionIsValid @28 :Bool;
  }

  struct MeasurementReport @0xf580d7d86b7b8692 {
    source @0 :MeasurementSource;

    fCount @1 :UInt32;

    gpsWeek @2 :UInt16;
    glonassCycleNumber @3 :UInt8;
    glonassNumberOfDays @4 :UInt16;

    milliseconds @5 :UInt32;
    timeBias @6 :Float32;
    clockTimeUncertainty @7 :Float32;
    clockFrequencyBias @8 :Float32;
    clockFrequencyUncertainty @9 :Float32;

    sv @10 :List(SV);

    struct SV @0xf10c595ae7bb2c27 {
      svId @0 :UInt8;
      observationState @2 :SVObservationState;
      observations @3 :UInt8;
      goodObservations @4 :UInt8;
      gpsParityErrorCount @5 :UInt16;
      glonassFrequencyIndex @1 :Int8;
      glonassHemmingErrorCount @6 :UInt8;
      filterStages @7 :UInt8;
      carrierNoise @8 :UInt16;
      latency @9 :Int16;
      predetectInterval @10 :UInt8;
      postdetections @11 :UInt16;

      unfilteredMeasurementIntegral @12 :UInt32;
      unfilteredMeasurementFraction @13 :Float32;
      unfilteredTimeUncertainty @14 :Float32;
      unfilteredSpeed @15 :Float32;
      unfilteredSpeedUncertainty @16 :Float32;
      measurementStatus @17 :MeasurementStatus;
      multipathEstimate @18 :UInt32;
      azimuth @19 :Float32;
      elevation @20 :Float32;
      carrierPhaseCyclesIntegral @21 :Int32;
      carrierPhaseCyclesFraction @22 :UInt16;
      fineSpeed @23 :Float32;
      fineSpeedUncertainty @24 :Float32;
      cycleSlipCount @25 :UInt8;
    }

  }

  struct ClockReport @0xca965e4add8f4f0b {
    hasFCount @0 :Bool;
    fCount @1 :UInt32;

    hasGpsWeek @2 :Bool;
    gpsWeek @3 :UInt16;
    hasGpsMilliseconds @4 :Bool;
    gpsMilliseconds @5 :UInt32;
    gpsTimeBias @6 :Float32;
    gpsClockTimeUncertainty @7 :Float32;
    gpsClockSource @8 :UInt8;

    hasGlonassYear @9 :Bool;
    glonassYear @10 :UInt8;
    hasGlonassDay @11 :Bool;
    glonassDay @12 :UInt16;
    hasGlonassMilliseconds @13 :Bool;
    glonassMilliseconds @14 :UInt32;
    glonassTimeBias @15 :Float32;
    glonassClockTimeUncertainty @16 :Float32;
    glonassClockSource @17 :UInt8;

    bdsWeek @18 :UInt16;
    bdsMilliseconds @19 :UInt32;
    bdsTimeBias @20 :Float32;
    bdsClockTimeUncertainty @21 :Float32;
    bdsClockSource @22 :UInt8;

    galWeek @23 :UInt16;
    galMilliseconds @24 :UInt32;
    galTimeBias @25 :Float32;
    galClockTimeUncertainty @26 :Float32;
    galClockSource @27 :UInt8;

    clockFrequencyBias @28 :Float32;
    clockFrequencyUncertainty @29 :Float32;
    frequencySource @30 :UInt8;
    gpsLeapSeconds @31 :UInt8;
    gpsLeapSecondsUncertainty @32 :UInt8;
    gpsLeapSecondsSource @33 :UInt8;

    gpsToGlonassTimeBiasMilliseconds @34 :Float32;
    gpsToGlonassTimeBiasMillisecondsUncertainty @35 :Float32;
    gpsToBdsTimeBiasMilliseconds @36 :Float32;
    gpsToBdsTimeBiasMillisecondsUncertainty @37 :Float32;
    bdsToGloTimeBiasMilliseconds @38 :Float32;
    bdsToGloTimeBiasMillisecondsUncertainty @39 :Float32;
    gpsToGalTimeBiasMilliseconds @40 :Float32;
    gpsToGalTimeBiasMillisecondsUncertainty @41 :Float32;
    galToGloTimeBiasMilliseconds @42 :Float32;
    galToGloTimeBiasMillisecondsUncertainty @43 :Float32;
    galToBdsTimeBiasMilliseconds @44 :Float32;
    galToBdsTimeBiasMillisecondsUncertainty @45 :Float32;

    hasRtcTime @46 :Bool;
    systemRtcTime @47 :UInt32;
    fCountOffset @48 :UInt32;
    lpmRtcCount @49 :UInt32;
    clockResets @50 :UInt32;
  }

  struct DrMeasurementReport @0x8053c39445c6c75c {

    reason @0 :UInt8;
    seqNum @1 :UInt8;
    seqMax @2 :UInt8;
    rfLoss @3 :UInt16;

    systemRtcValid @4 :Bool;
    fCount @5 :UInt32;
    clockResets @6 :UInt32;
    systemRtcTime @7 :UInt64;

    gpsLeapSeconds @8 :UInt8;
    gpsLeapSecondsUncertainty @9 :UInt8;
    gpsToGlonassTimeBiasMilliseconds @10 :Float32;
    gpsToGlonassTimeBiasMillisecondsUncertainty @11 :Float32;

    gpsWeek @12 :UInt16;
    gpsMilliseconds @13 :UInt32;
    gpsTimeBiasMs @14 :UInt32;
    gpsClockTimeUncertaintyMs @15 :UInt32;
    gpsClockSource @16 :UInt8;

    glonassClockSource @17 :UInt8;
    glonassYear @18 :UInt8;
    glonassDay @19 :UInt16;
    glonassMilliseconds @20 :UInt32;
    glonassTimeBias @21 :Float32;
    glonassClockTimeUncertainty @22 :Float32;

    clockFrequencyBias @23 :Float32;
    clockFrequencyUncertainty @24 :Float32;
    frequencySource @25 :UInt8;

    source @26 :MeasurementSource;

    sv @27 :List(SV);

    struct SV @0xf08b81df8cbf459c {
      svId @0 :UInt8;
      glonassFrequencyIndex @1 :Int8;
      observationState @2 :SVObservationState;
      observations @3 :UInt8;
      goodObservations @4 :UInt8;
      filterStages @5 :UInt8;
      predetectInterval @6 :UInt8;
      cycleSlipCount @7 :UInt8;
      postdetections @8 :UInt16;

      measurementStatus @9 :MeasurementStatus;

      carrierNoise @10 :UInt16;
      rfLoss @11 :UInt16;
      latency @12 :Int16;

      filteredMeasurementFraction @13 :Float32;
      filteredMeasurementIntegral @14 :UInt32;
      filteredTimeUncertainty @15 :Float32;
      filteredSpeed @16 :Float32;
      filteredSpeedUncertainty @17 :Float32;

      unfilteredMeasurementFraction @18 :Float32;
      unfilteredMeasurementIntegral @19 :UInt32;
      unfilteredTimeUncertainty @20 :Float32;
      unfilteredSpeed @21 :Float32;
      unfilteredSpeedUncertainty @22 :Float32;

      multipathEstimate @23 :UInt32;
      azimuth @24 :Float32;
      elevation @25 :Float32;
      dopplerAcceleration @26 :Float32;
      fineSpeed @27 :Float32;
      fineSpeedUncertainty @28 :Float32;

      carrierPhase @29 :Float64;
      fCount @30 :UInt32;

      parityErrorCount @31 :UInt16;
      goodParity @32 :Bool;
    }
  }

  struct DrSvPolyReport @0xb1fb80811a673270 {
    svId @0 :UInt16;
    frequencyIndex @1 :Int8;

    hasPosition @2 :Bool;
    hasIono @3 :Bool;
    hasTropo @4 :Bool;
    hasElevation @5 :Bool;
    polyFromXtra @6 :Bool;
    hasSbasIono @7 :Bool;

    iode @8 :UInt16;
    t0 @9 :Float64;
    xyz0 @10 :List(Float64);
    xyzN @11 :List(Float64);
    other @12 :List(Float32);

    positionUncertainty @13 :Float32;
    ionoDelay @14 :Float32;
    ionoDot @15 :Float32;
    sbasIonoDelay @16 :Float32;
    sbasIonoDot @17 :Float32;
    tropoDelay @18 :Float32;
    elevation @19 :Float32;
    elevationDot @20 :Float32;
    elevationUncertainty @21 :Float32;
    velocityCoeff @22 :List(Float64);

    gpsWeek @23 :UInt16;
    gpsTow @24 :Float64;
  }
}

struct Clocks {
  wallTimeNanos @0 :UInt64;  # unix epoch time
}

struct LiveMpcData {
  x @0 :List(Float32);
  y @1 :List(Float32);
  psi @2 :List(Float32);
  curvature @3 :List(Float32);
  qpIterations @4 :UInt32;
  calculationTime @5 :UInt64;
  cost @6 :Float64;
}

struct LiveLongitudinalMpcData {
  xEgo @0 :List(Float32);
  vEgo @1 :List(Float32);
  aEgo @2 :List(Float32);
  xLead @3 :List(Float32);
  vLead @4 :List(Float32);
  aLead @5 :List(Float32);
  aLeadTau @6 :Float32;    # lead accel time constant
  qpIterations @7 :UInt32;
  mpcId @8 :UInt32;
  calculationTime @9 :UInt64;
  cost @10 :Float64;
}

struct Joystick {
  # convenient for debug and live tuning
  axes @0: List(Float32);
  buttons @1: List(Bool);
}

struct DriverStateV2 {
  frameId @0 :UInt32;
  modelExecutionTime @1 :Float32;
  rawPredictions @2 :Data;
  wheelOnRightProb @3 :Float32;
  leftDriverData @4 :DriverData;
  rightDriverData @5 :DriverData;
  gpuExecutionTime @6 :Float32;

  struct DriverData {
    faceOrientation @0 :List(Float32);
    faceOrientationStd @1 :List(Float32);
    facePosition @2 :List(Float32);
    facePositionStd @3 :List(Float32);
    faceProb @4 :Float32;
    leftEyeProb @5 :Float32;
    rightEyeProb @6 :Float32;
    leftBlinkProb @7 :Float32;
    rightBlinkProb @8 :Float32;
    sunglassesProb @9 :Float32;
    phoneProb @10 :Float32;
  }
}

struct DriverMonitoringState @0xb83cda094a1da284 {
  faceDetected @0 :Bool;
  isDistracted @1 :Bool;
  awarenessStatus @2 :Float32;
  isRHD @3 :Bool;
  posePitchOffset @4 :Float32;
  posePitchValidCount @5 :UInt32;
  poseYawOffset @6 :Float32;
  poseYawValidCount @7 :UInt32;
  stepChange @8 :Float32;
  awarenessActive @9 :Float32;
  awarenessPassive @10 :Float32;
  isLowStd @11 :Bool;
  hiStdCount @12 :UInt32;
  distractedType @13 :UInt32;
  isActiveMode @14 :Bool;
  uncertainCount @15 :UInt32;
  events @16 :List(OnroadEvent);
  phoneProbOffset @17 :Float32;
  phoneProbValidCount @18 :UInt32;
}

struct Boot {
  wallTimeNanos @0 :UInt64;
  launchLog @1 :Text;
  pstore @2 :Map(Text, Data);
  commands @3 :Map(Text, Data);
}

struct LiveParametersData {
  valid @0 :Bool;
  gyroBias @1 :Float32;
  angleOffsetDeg @2 :Float32;
  angleOffsetAverageDeg @3 :Float32;
  stiffnessFactor @4 :Float32;
  steerRatio @5 :Float32;
  sensorValid @6 :Bool;
  posenetSpeed @7 :Float32;
  posenetValid @8 :Bool;
  angleOffsetFastStd @9 :Float32;
  angleOffsetAverageStd @10 :Float32;
  stiffnessFactorStd @11 :Float32;
  steerRatioStd @12 :Float32;
  roll @13 :Float32;
  debugFilterState @14 :FilterState;
  angleOffsetValid @15 :Bool = true;
  angleOffsetAverageValid @16 :Bool = true;
  steerRatioValid @17 :Bool = true;
  stiffnessFactorValid @18 :Bool = true;

  struct FilterState {
    value @0 : List(Float64);
    std @1 : List(Float64);
  }
}

struct LiveTorqueParametersData {
  liveValid @0 :Bool;
  latAccelFactorRaw @1 :Float32;
  latAccelOffsetRaw @2 :Float32;
  frictionCoefficientRaw @3 :Float32;
  latAccelFactorFiltered @4 :Float32;
  latAccelOffsetFiltered @5 :Float32;
  frictionCoefficientFiltered @6 :Float32;
  totalBucketPoints @7 :Float32;
  decay @8 :Float32;
  maxResets @9 :Float32;
  points @10 :List(List(Float32));
  version @11 :Int32;
  useParams @12 :Bool;
  calPerc @13 :Int8;
}

struct LiveDelayData {
  lateralDelay @0 :Float32;
  validBlocks @1 :Int32;
  status @2 :Status;
  lateralDelayEstimate @3 :Float32;
  points @4 :List(Float32);
  lateralDelayEstimateStd @5 :Float32;
  calPerc @6 :Int8;

  enum Status {
    unestimated @0;
    estimated @1;
    invalid @2;
  }
}

struct CameraOdometry {
  trans @0 :List(Float32); # m/s in device frame
  rot @1 :List(Float32); # rad/s in device frame
  transStd @2 :List(Float32); # std m/s in device frame
  rotStd @3 :List(Float32); # std rad/s in device frame
  frameId @4 :UInt32;
  timestampEof @5 :UInt64;
  wideFromDeviceEuler @6 :List(Float32);
  wideFromDeviceEulerStd @7 :List(Float32);
  roadTransformTrans @8 :List(Float32);
  roadTransformTransStd @9 :List(Float32);
}

struct Sentinel {
  enum SentinelType {
    endOfSegment @0;
    endOfRoute @1;
    startOfSegment @2;
    startOfRoute @3;
  }
  type @0 :SentinelType;
  signal @1 :Int32;
}

struct UIDebug {
  drawTimeMillis @0 :Float32;
}

struct ManagerState {
  processes @0 :List(ProcessState);

  struct ProcessState {
    name @0 :Text;
    pid @1 :Int32;
    running @2 :Bool;
    exitCode @3 :Int32;
    shouldBeRunning @4 :Bool;
  }
}

struct UploaderState {
  immediateQueueSize @0 :UInt32;
  immediateQueueCount @1 :UInt32;
  rawQueueSize @2 :UInt32;
  rawQueueCount @3 :UInt32;

  # stats for last successfully uploaded file
  lastTime @4 :Float32;  # s
  lastSpeed @5 :Float32; # MB/s
  lastFilename @6 :Text;
}

struct NavInstruction {
  maneuverPrimaryText @0 :Text;
  maneuverSecondaryText @1 :Text;
  maneuverDistance @2 :Float32;  # m
  maneuverType @3 :Text; # TODO: Make Enum
  maneuverModifier @4 :Text; # TODO: Make Enum

  distanceRemaining @5 :Float32; # m
  timeRemaining @6 :Float32; # s
  timeRemainingTypical @7 :Float32; # s

  lanes @8 :List(Lane);
  showFull @9 :Bool;

  speedLimit @10 :Float32; # m/s
  speedLimitSign @11 :SpeedLimitSign;

  allManeuvers @12 :List(Maneuver);

  struct Lane {
    directions @0 :List(Direction);
    active @1 :Bool;
    activeDirection @2 :Direction;
  }

  enum Direction {
    none @0;
    left @1;
    right @2;
    straight @3;
    slightLeft @4;
    slightRight @5;
  }

  enum SpeedLimitSign {
    mutcd @0; # US Style
    vienna @1; # EU Style
  }

  struct Maneuver {
    distance @0 :Float32;
    type @1 :Text;
    modifier @2 :Text;
  }
}

struct NavRoute {
  coordinates @0 :List(Coordinate);

  struct Coordinate {
    latitude @0 :Float32;
    longitude @1 :Float32;
  }
}

struct MapRenderState {
  locationMonoTime @0 :UInt64;
  renderTime @1 :Float32;
  frameId @2: UInt32;
}

struct NavModelData {
  frameId @0 :UInt32;
  modelExecutionTime @1 :Float32;
  dspExecutionTime @2 :Float32;
  features @3 :List(Float32);
  position @4 :XYData;
  desirePrediction @5 :List(Float32);
  locationMonoTime @6 :UInt64;

  # All SI units and in device frame
  struct XYData {
    x @0 :List(Float32);
    y @1 :List(Float32);
    xStd @2 :List(Float32);
    yStd @3 :List(Float32);
  }
}

struct EncodeData {
  idx @0 :EncodeIndex;
  data @1 :Data;
  header @2 :Data;
  unixTimestampNanos @3 :UInt64;
  width @4 :UInt32;
  height @5 :UInt32;
}

struct DebugAlert {
  alertText1 @0 :Text;
  alertText2 @1 :Text;
}

struct UserBookmark @0xfe346a9de48d9b50 {
}

struct SoundPressure @0xdc24138990726023 {
  soundPressure @0 :Float32;
  soundPressureWeightedDb @1 :Float32;
  # uncalibrated, A-weighted
  soundPressureWeighted @2 :Float32;
}

struct AudioData {
  data @0 :Data;
  sampleRate @1 :UInt32;
}

struct AudioFeedback {
  audio @0 :AudioData;
  blockNum @1 :UInt16;
}

struct Touch {
  sec @0 :Int64;
  usec @1 :Int64;
  type @2 :UInt8;
  code @3 :Int32;
  value @4 :Int32;
}

struct Event {
  logMonoTime @0 :UInt64;  # nanoseconds
  valid @1 :Bool = true;

  union {
    initData @2 :InitData;
    sentinel @3 :Sentinel;
    roadCameraState @4 :FrameData;
    gpsNMEA @5 :GPSNMEAData;
    can @6 :List(CanData);
    deviceState @7 :DeviceState;
    logMessage @8 :Text;
    controlsState @9 :ControlsState;
    roadEncodeIdx @10 :EncodeIndex;
    model @11 :Legacy.ModelData;
    androidLog @12 :AndroidLogEntry;
    gpsLocation @13 :GpsLocationData;
    sendcan @14 :List(CanData);
    radarState @15 :RadarState;
    liveCalibration @16 :LiveCalibrationData;
    longitudinalPlan @17 :LongitudinalPlan;
    ubloxGnss @18 :UbloxGnss;
    qcomGnss @19 :QcomGnss;
    carState @20 :Car.CarState;
    carControl @21 :Car.CarControl;
    carOutput @22 :Car.CarOutput;
    driverAssistance @23 :DriverAssistance;
    ubloxRaw @24 :Data;
    liveParameters @25 :LiveParametersData;
    cameraOdometry @26 :CameraOdometry;
    driverCameraState @27 :FrameData;
    wideRoadCameraState @28 :FrameData;
    driverEncodeIdx @29 :EncodeIndex;
    wideRoadEncodeIdx @30 :EncodeIndex;
    carParams @31 :Car.CarParams;
    driverMonitoringState @32 :DriverMonitoringState;
    procLog @33 :ProcLog;
    clocks @34 :Clocks;
    gnssMeasurements @35 :GnssMeasurements;
    gpsLocationExternal @36 :GpsLocationData;
    liveTorqueParameters @37 :LiveTorqueParametersData;
    boot @38 :Boot;
    driverStateV2 @39 :DriverStateV2;
    livePose @40 :LivePose;
    pandaStates @41 :List(PandaState);
    peripheralState @42 :PeripheralState;
    managerState @43 :ManagerState;
    uploaderState @44 :UploaderState;
    navInstruction @45 :NavInstruction;
    navRoute @46 :NavRoute;
    navThumbnail @47 :Thumbnail;
    mapRenderState @48 :MapRenderState;
    roadEncodeData @49 :EncodeData;
    driverEncodeData @50 :EncodeData;
    wideRoadEncodeData @51 :EncodeData;
    qRoadEncodeData @52 :EncodeData;
    errorLogMessage @53 :Text;
    testJoystick @54 :Joystick;
    thumbnail @55 :Thumbnail;
    onroadEvents @56 :List(OnroadEvent);
    modelV2 @57 :ModelDataV2;
    drivingModelData @58 :DrivingModelData;
    liveDelay @59 :LiveDelayData;
    uiDebug @60 :UIDebug;
    soundPressure @61 :SoundPressure;
    rawAudioData @62 :AudioData;
    liveTracks @63 :Car.RadarData;
    selfdriveState @64 :SelfdriveState;
    gyroscope @65 :SensorEventData;
    accelerometer @66 :SensorEventData;
    magnetometer @67 :SensorEventData;
    lightSensor @68 :SensorEventData;
    temperatureSensor @69 :SensorEventData;
    userBookmark @70 :UserBookmark;
    bookmarkButton @71 :UserBookmark;
    audioFeedback @72 :AudioFeedback;
    livestreamRoadEncodeIdx @73 :EncodeIndex;
    livestreamWideRoadEncodeIdx @74 :EncodeIndex;
    livestreamDriverEncodeIdx @75 :EncodeIndex;
    alertDebug @76 :DebugAlert;
    livestreamRoadEncodeData @77 :EncodeData;
    livestreamWideRoadEncodeData @78 :EncodeData;
    livestreamDriverEncodeData @79 :EncodeData;
    touch @80 :List(Touch);
    qRoadEncodeIdx @81 :EncodeIndex;
    customReserved0 @82 :Custom.CustomReserved0;
    customReserved1 @83 :Custom.CustomReserved1;
    customReserved2 @84 :Custom.CustomReserved2;
    customReserved3 @85 :Custom.CustomReserved3;
    customReserved4 @86 :Custom.CustomReserved4;
    customReserved5 @87 :Custom.CustomReserved5;
    customReserved6 @88 :Custom.CustomReserved6;
    customReserved7 @89 :Custom.CustomReserved7;
    customReserved8 @90 :Custom.CustomReserved8;
    customReserved9 @91 :Custom.CustomReserved9;
    customReservedRawData0 @92 :Data;
    customReservedRawData1 @93 :Data;
    customReservedRawData2 @94 :Data;
    customReserved10 @95 :Custom.CustomReserved10;
    customReserved11 @96 :Custom.CustomReserved11;
    customReserved12 @97 :Custom.CustomReserved12;
    customReserved13 @98 :Custom.CustomReserved13;
    customReserved14 @99 :Custom.CustomReserved14;
    customReserved15 @100 :Custom.CustomReserved15;
    customReserved16 @101 :Custom.CustomReserved16;
    customReserved17 @102 :Custom.CustomReserved17;
    customReserved18 @103 :Custom.CustomReserved18;
    customReserved19 @104 :Custom.CustomReserved19;
  }
}
