#include <cassert>
#include <sstream>

#include "system/loggerd/loggerd.h"
#include "system/loggerd/encoder/jpeg_encoder.h"
#include "common/timing.h"

#if defined(__TICI__) || defined(QCOM2)
#include "system/loggerd/encoder/v4l_encoder.h"
#define Encoder V4LEncoder
#elif defined(RK3588)
#include "system/loggerd/encoder/mpp_encoder.h"
#define Encoder MppEncoder
#else
#include "system/loggerd/encoder/ffmpeg_encoder.h"
#define Encoder FfmpegEncoder
#endif

ExitHandler do_exit;
constexpr int ENCODER_VIPC_STALL_TIMEOUT_MS = 300;
constexpr int ENCODER_OUTPUT_STALL_TIMEOUT_MS = 1000;
constexpr int ENCODER_REOPEN_FAILURE_THRESHOLD = 10;
constexpr int ENCODER_RECONNECT_BACKOFF_MS = 50;
constexpr int ENCODER_HEALTH_LOG_PERIOD_MS = 5000;
constexpr int ENCODER_FAILURE_LOG_PERIOD_MS = 1000;
constexpr int ENCODER_FAILURE_LOG_BATCH_SIZE = 30;

std::vector<int> parse_affinity_cores(const char *env_val) {
  std::vector<int> cores;
  if (env_val == nullptr || env_val[0] == '\0') return cores;

  std::stringstream ss(env_val);
  std::string token;
  while (std::getline(ss, token, ',')) {
    try {
      if (!token.empty()) cores.push_back(std::stoi(token));
    } catch (const std::exception&) {
      // Ignore invalid affinity token and continue parsing.
    }
  }
  return cores;
}

const char *stream_affinity_env(VisionStreamType stream_type) {
  switch (stream_type) {
    case VISION_STREAM_ROAD:
      return "ENCODERD_ROAD_AFFINITY";
    case VISION_STREAM_WIDE_ROAD:
      return "ENCODERD_WIDE_AFFINITY";
    case VISION_STREAM_DRIVER:
      return "ENCODERD_DRIVER_AFFINITY";
    default:
      return "ENCODERD_STREAM_AFFINITY";
  }
}

struct EncoderdState {
  int max_waiting = 0;

  // Sync logic for startup
  std::atomic<int> encoders_ready = 0;
  std::atomic<uint32_t> start_frame_id = 0;
  bool camera_ready[VISION_STREAM_WIDE_ROAD + 1] = {};
  bool camera_synced[VISION_STREAM_WIDE_ROAD + 1] = {};
};

// Handle initial encoder syncing by waiting for all encoders to reach the same frame id
bool sync_encoders(EncoderdState *s, VisionStreamType cam_type, uint32_t frame_id) {
  if (s->camera_synced[cam_type]) return true;

  if (s->max_waiting > 1 && s->encoders_ready != s->max_waiting) {
    // add a small margin to the start frame id in case one of the encoders already dropped the next frame
    update_max_atomic(s->start_frame_id, frame_id + 2);
    if (std::exchange(s->camera_ready[cam_type], true) == false) {
      ++s->encoders_ready;
      LOGD("camera %d encoder ready", cam_type);
    }
    return false;
  } else {
    if (s->max_waiting == 1) update_max_atomic(s->start_frame_id, frame_id);
    bool synced = frame_id >= s->start_frame_id;
    s->camera_synced[cam_type] = synced;
    if (!synced) LOGD("camera %d waiting for frame %d, cur %d", cam_type, (int)s->start_frame_id, frame_id);
    return synced;
  }
}

void reset_sync_for_camera(EncoderdState *s, VisionStreamType cam_type) {
  if (s->camera_ready[cam_type]) {
    int prev = s->encoders_ready.fetch_sub(1);
    if (prev <= 0) {
      s->encoders_ready = 0;
    }
  }
  s->camera_ready[cam_type] = false;
  s->camera_synced[cam_type] = false;
}


void encoder_thread(EncoderdState *s, const LogCameraInfo &cam_info) {
  util::set_thread_name(cam_info.thread_name);
  if (!Hardware::PC()) {
    std::vector<int> stream_affinity = parse_affinity_cores(getenv(stream_affinity_env(cam_info.stream_type)));
    if (!stream_affinity.empty()) {
      int ret = util::set_core_affinity(stream_affinity);
      if (ret != 0) {
        LOGW("failed to set affinity for stream %s", cam_info.thread_name);
      }
    }
  }

  std::vector<std::unique_ptr<Encoder>> encoders;
  std::vector<int> encode_failure_counts;
  std::vector<int> encode_failure_burst_counts;
  std::vector<double> encode_failure_last_log_tms;
  VisionIpcClient vipc_client = VisionIpcClient("camerad", cam_info.stream_type, false);

  std::unique_ptr<JpegEncoder> jpeg_encoder;

  int cur_seg = 0;

  auto close_and_reset_encoders = [&]() {
    for (auto &e : encoders) {
      e->encoder_close();
    }
    encoders.clear();
    encode_failure_counts.clear();
    encode_failure_burst_counts.clear();
    encode_failure_last_log_tms.clear();
    jpeg_encoder.reset();
    cur_seg = 0;
    reset_sync_for_camera(s, cam_info.stream_type);
  };

  auto reopen_all_encoders = [&]() {
    for (size_t i = 0; i < encoders.size(); ++i) {
      encoders[i]->encoder_close();
      encoders[i]->encoder_open();
      encode_failure_counts[i] = 0;
    }
  };

  while (!do_exit) {
    if (!vipc_client.connect(false)) {
      util::sleep_for(5);
      continue;
    }

    // Always start with a clean encoder state after (re)connect.
    close_and_reset_encoders();

    // init encoders
    if (encoders.empty()) {
      const VisionBuf &buf_info = vipc_client.buffers[0];
      LOGW("encoder %s init %zux%zu", cam_info.thread_name, buf_info.width, buf_info.height);
      if (buf_info.width == 0 || buf_info.height == 0) {
        LOGE("encoder %s got invalid buffer dimensions %zux%zu, reconnecting",
             cam_info.thread_name, buf_info.width, buf_info.height);
        break;
      }

      for (const auto &encoder_info : cam_info.encoder_infos) {
        auto &e = encoders.emplace_back(new Encoder(encoder_info, buf_info.width, buf_info.height));
        e->encoder_open();
        encode_failure_counts.emplace_back(0);
        encode_failure_burst_counts.emplace_back(0);
        encode_failure_last_log_tms.emplace_back(0.0);
      }

      // Only one thumbnail can be generated per camera stream
      if (auto thumbnail_name = cam_info.encoder_infos[0].thumbnail_name) {
        jpeg_encoder = std::make_unique<JpegEncoder>(thumbnail_name, buf_info.width / 4, buf_info.height / 4);
      }
    }

    bool lagging = false;
    double last_frame_seen_tms = millis_since_boot();
    double last_encode_success_tms = last_frame_seen_tms;
    double last_health_log_tms = last_frame_seen_tms;
    uint32_t last_encoded_frame_id = 0;
    uint64_t encoded_frames = 0;
    uint64_t recoveries = 0;
    while (!do_exit) {
      VisionIpcBufExtra extra;
      VisionBuf* buf = vipc_client.recv(&extra);
      if (buf == nullptr) {
        const double now_tms = millis_since_boot();
        const bool stalled = (now_tms - last_frame_seen_tms) > ENCODER_VIPC_STALL_TIMEOUT_MS;
        if (!vipc_client.is_connected() || stalled) {
          LOGE("encoder %s reconnecting vipc (%s, no frame for %.1f ms)",
               cam_info.thread_name,
               vipc_client.is_connected() ? "stalled" : "disconnected",
               (now_tms - last_frame_seen_tms));
          break;
        }
        continue;
      }
      last_frame_seen_tms = millis_since_boot();

      // detect loop around and drop the frames
      if (buf->get_frame_id() != extra.frame_id) {
        if (!lagging) {
          LOGE("encoder %s lag  buffer id: %" PRIu64 " extra id: %d", cam_info.thread_name, buf->get_frame_id(), extra.frame_id);
          lagging = true;
        }
        continue;
      }
      lagging = false;

      if (!sync_encoders(s, cam_info.stream_type, extra.frame_id)) {
        continue;
      }
      if (do_exit) break;

      // do rotation if required
      const int frames_per_seg = SEGMENT_LENGTH * MAIN_FPS;
      if (cur_seg >= 0 && extra.frame_id >= ((cur_seg + 1) * frames_per_seg) + s->start_frame_id) {
        for (auto &e : encoders) {
          e->encoder_close();
          e->encoder_open();
        }
        ++cur_seg;
      }

      // encode a frame
      bool frame_encoded = false;
      for (size_t i = 0; i < encoders.size(); ++i) {
        int out_id = encoders[i]->encode_frame(buf, &extra);

        if (out_id == -1) {
          encode_failure_counts[i]++;
          encode_failure_burst_counts[i]++;
          const double now_tms = millis_since_boot();
          if ((now_tms - encode_failure_last_log_tms[i]) >= ENCODER_FAILURE_LOG_PERIOD_MS ||
              encode_failure_burst_counts[i] >= ENCODER_FAILURE_LOG_BATCH_SIZE) {
            LOGE("encoder %s stream %zu failures=%d consecutive=%d last_frame=%d",
                 cam_info.thread_name, i, encode_failure_burst_counts[i], encode_failure_counts[i], extra.frame_id);
            encode_failure_last_log_tms[i] = now_tms;
            encode_failure_burst_counts[i] = 0;
          }
          if (encode_failure_counts[i] >= ENCODER_REOPEN_FAILURE_THRESHOLD) {
            LOGE("encoder %s stream %zu exceeded failure threshold (%d), reopening",
                 cam_info.thread_name, i, ENCODER_REOPEN_FAILURE_THRESHOLD);
            encoders[i]->encoder_close();
            encoders[i]->encoder_open();
            encode_failure_counts[i] = 0;
            encode_failure_burst_counts[i] = 0;
            recoveries++;
          }
        } else {
          encode_failure_counts[i] = 0;
          encode_failure_burst_counts[i] = 0;
          frame_encoded = true;
        }
      }

      const double now_tms = millis_since_boot();
      if (frame_encoded) {
        last_encode_success_tms = now_tms;
        last_encoded_frame_id = extra.frame_id;
        encoded_frames++;
      } else if ((now_tms - last_encode_success_tms) > ENCODER_OUTPUT_STALL_TIMEOUT_MS) {
        LOGE("encoder %s output stalled for %.1f ms, reopening all streams",
             cam_info.thread_name, (now_tms - last_encode_success_tms));
        reopen_all_encoders();
        last_encode_success_tms = now_tms;
        recoveries++;
      }

      if ((now_tms - last_health_log_tms) > ENCODER_HEALTH_LOG_PERIOD_MS) {
        LOGD("encoder %s health: encoded=%" PRIu64 " last_frame=%u recoveries=%" PRIu64,
             cam_info.thread_name, encoded_frames, last_encoded_frame_id, recoveries);
        last_health_log_tms = now_tms;
      }

      if (jpeg_encoder && (extra.frame_id % 1200 == 100)) {
        jpeg_encoder->pushThumbnail(buf, extra);
      }
    }

    close_and_reset_encoders();
    if (!do_exit) {
      util::sleep_for(ENCODER_RECONNECT_BACKOFF_MS);
    }
  }
}

template <size_t N>
void encoderd_thread(const LogCameraInfo (&cameras)[N]) {
  EncoderdState s;

  std::set<VisionStreamType> streams;
  while (!do_exit) {
    streams = VisionIpcClient::getAvailableStreams("camerad", false);
    if (!streams.empty()) {
      break;
    }
    util::sleep_for(100);
  }

  if (!streams.empty()) {
    std::vector<std::thread> encoder_threads;
    for (auto stream : streams) {
      auto it = std::find_if(std::begin(cameras), std::end(cameras),
                             [stream](auto &cam) { return cam.stream_type == stream; });
      assert(it != std::end(cameras));
      ++s.max_waiting;
      encoder_threads.push_back(std::thread(encoder_thread, &s, *it));
    }

    for (auto &t : encoder_threads) t.join();
  }
}

int main(int argc, char* argv[]) {
  if (!Hardware::PC()) {
    int ret = util::set_realtime_priority(52);
    if (ret != 0) {
      LOGW("failed to set encoderd realtime priority: %d", ret);
    }

    std::vector<int> affinity_cores = parse_affinity_cores(getenv("ENCODERD_AFFINITY"));
    if (affinity_cores.empty()) {
      // Avoid single-core pinning; default to a wider core set for better tail latency.
      affinity_cores = {2, 3, 4, 5};
    }
    ret = util::set_core_affinity(affinity_cores);
    if (ret != 0) {
      LOGW("failed to set encoderd core affinity");
    }
  }
  if (argc > 1) {
    std::string arg1(argv[1]);
    if (arg1 == "--stream") {
      encoderd_thread(stream_cameras_logged);
    } else {
      LOGE("Argument '%s' is not supported", arg1.c_str());
    }
  } else {
    encoderd_thread(cameras_logged);
  }
  return 0;
}
