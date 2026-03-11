// RK3588 hardware video encoder (Rockchip MPP + RGA for downscale).
// Analogous to V4LEncoder on TICI and FfmpegEncoder elsewhere; same VideoEncoder interface.

#include <cassert>
#include <cstdio>
#include <cstdlib>

#define __STDC_CONSTANT_MACROS

#include "system/loggerd/encoder/mpp_encoder.h"

#include "common/swaglog.h"
#include "common/util.h"

#define MPP_ALIGN(x, a) (((x) + ((a) - 1)) & ~((a) - 1))

const int env_debug_encoder = (getenv("DEBUG_ENCODER") != NULL) ? atoi(getenv("DEBUG_ENCODER")) : 0;

MppEncoder::MppEncoder(const EncoderInfo &encoder_info, int in_width, int in_height)
    : VideoEncoder(encoder_info, in_width, in_height) {

    if (in_width != out_width || in_height != out_height) {
      is_downscale = true;
    }
    // Zero-copy import is only feasible when we don't need RGA downscale.
    use_zero_copy = !is_downscale;
    if (const char *zero_copy_env = getenv("ENCODER_ZERO_COPY")) {
      use_zero_copy = atoi(zero_copy_env) != 0 && !is_downscale;
    }

    alw = is_downscale ? MPP_ALIGN(out_width, 16) : MPP_ALIGN(in_width, 16);
    alh = is_downscale ? MPP_ALIGN(out_height, 16) : in_height;

    if (is_downscale) {
      downscale_buf = malloc(alw * alh * 3 / 2);
      if (downscale_buf == nullptr) {
        LOGE("failed to allocate downscale buffer (%d bytes)", alw * alh * 3 / 2);
      }
    }
}

MppEncoder::~MppEncoder() {
  encoder_close();

  if (is_downscale) {
    free(downscale_buf);
    downscale_buf = NULL;
  }
}

void MppEncoder::encoder_open() {
  encoder_open(encoder_info.filename);
}

void MppEncoder::encoder_open(const char* path) {
    encoder_close();

    EncoderSettings settings = encoder_info.get_settings(in_width);
    if (mpp_create(&mpp_ctx, &mpp_mpi) != MPP_OK) {
      LOGE("mpp_create failed for %s", path);
      mpp_ctx = nullptr;
      mpp_mpi = nullptr;
      return;
    }
    LOGD("opened [%d %d %d %d] fps %d %s bitrate %d", in_width, in_height,
        out_width, out_height, encoder_info.fps,
        encoder_info.filename, settings.bitrate);

    if (settings.encode_type == cereal::EncodeIndex::Type::QCAMERA_H264) {
      if (mpp_init(mpp_ctx, MPP_CTX_ENC, MPP_VIDEO_CodingAVC) != MPP_OK) {
        LOGE("mpp_init AVC failed for %s", path);
        encoder_close();
        return;
      }
      if (mpp_enc_cfg_init(&cfg) != MPP_OK) {
        LOGE("mpp_enc_cfg_init AVC failed for %s", path);
        encoder_close();
        return;
      }
      if (mpp_mpi->control(mpp_ctx, MPP_ENC_GET_CFG, cfg) != MPP_OK) {
        LOGE("MPP_ENC_GET_CFG AVC failed for %s", path);
        encoder_close();
        return;
      }
      mpp_enc_cfg_set_u32(cfg, "codec:type", MPP_VIDEO_CodingAVC);
      mpp_enc_cfg_set_s32(cfg, "split:mode", MPP_ENC_SPLIT_NONE);

      //**Profile & Level Settings (Low Quality)**
      mpp_enc_cfg_set_u32(cfg, "h264:profile", 100);
      mpp_enc_cfg_set_u32(cfg, "h264:level", 40);

      // **Entropy Mode (CABAC for better compression)**
      mpp_enc_cfg_set_u32(cfg, "h264:cabac_en", 1);  // Enable CABAC
      mpp_enc_cfg_set_s32(cfg, "h264:cabac_idc", 0);
      mpp_enc_cfg_set_s32(cfg, "h264:trans8x8", 1);
      mpp_enc_cfg_set_s32(cfg, "h264:constraint_set", 0);

      // QP settings
      mpp_enc_cfg_set_s32(cfg, "rc:qp_init", 35);
      mpp_enc_cfg_set_s32(cfg, "rc:qp_max", 45);
      mpp_enc_cfg_set_s32(cfg, "rc:qp_min", 30);
      mpp_enc_cfg_set_s32(cfg, "rc:qp_max_i", 45);
      mpp_enc_cfg_set_s32(cfg, "rc:qp_min_i", 30);
      mpp_enc_cfg_set_s32(cfg, "rc:qp_ip", 6);
    }
    else if (settings.encode_type == cereal::EncodeIndex::Type::FULL_H_E_V_C) {
      if (mpp_init(mpp_ctx, MPP_CTX_ENC, MPP_VIDEO_CodingHEVC) != MPP_OK) {
        LOGE("mpp_init HEVC failed for %s", path);
        encoder_close();
        return;
      }
      if (mpp_enc_cfg_init(&cfg) != MPP_OK) {
        LOGE("mpp_enc_cfg_init HEVC failed for %s", path);
        encoder_close();
        return;
      }
      if (mpp_mpi->control(mpp_ctx, MPP_ENC_GET_CFG, cfg) != MPP_OK) {
        LOGE("MPP_ENC_GET_CFG HEVC failed for %s", path);
        encoder_close();
        return;
      }
      mpp_enc_cfg_set_u32(cfg, "codec:type", MPP_VIDEO_CodingHEVC);
    }
    else {
      LOGE("unsupported encode type %d for %s", (int)settings.encode_type, path);
      encoder_close();
      return;
    }

    mpp_enc_cfg_set_s32(cfg, "prep:width", out_width);
    mpp_enc_cfg_set_s32(cfg, "prep:height", out_height);
    mpp_enc_cfg_set_s32(cfg, "prep:hor_stride", alw);
    mpp_enc_cfg_set_s32(cfg, "prep:ver_stride", alh);
    mpp_enc_cfg_set_s32(cfg, "prep:format", MPP_FMT_YUV420SP);
    mpp_enc_cfg_set_u32(cfg, "rc:fps_in_num", MAIN_FPS);  // input FPS
    mpp_enc_cfg_set_u32(cfg, "rc:fps_out_num", encoder_info.fps); // output FPS
    mpp_enc_cfg_set_u32(cfg, "rc:mode", MPP_ENC_RC_MODE_CBR);
    mpp_enc_cfg_set_s32(cfg, "rc:bps_target", settings.bitrate);
    mpp_enc_cfg_set_s32(cfg, "rc:bps_max", settings.bitrate + 100000);
    mpp_enc_cfg_set_s32(cfg, "rc:bps_min", settings.bitrate - 100000);
    mpp_enc_cfg_set_u32(cfg, "rc:gop", 90); // keyframe interval 2-second GOP for 30 FPS
    if (mpp_mpi->control(mpp_ctx, MPP_ENC_SET_CFG, cfg) != MPP_OK) {
      LOGE("MPP_ENC_SET_CFG failed for %s", path);
      encoder_close();
      return;
    }
    if (mpp_frame_init(&frame) != MPP_OK) {
      LOGE("mpp_frame_init failed for %s", path);
      encoder_close();
      return;
    }

    if (!use_zero_copy) {
      if (mpp_buffer_group_get_internal(&frame_buf_group, MPP_BUFFER_TYPE_DRM) != MPP_OK) {
        LOGE("mpp_buffer_group_get_internal failed for %s", path);
        encoder_close();
        return;
      }
      for (size_t i = 0; i < frame_buffers.size(); ++i) {
        if (mpp_buffer_get(frame_buf_group, &frame_buffers[i], alw * alh * 3 / 2) != MPP_OK) {
          LOGE("mpp_buffer_get prealloc failed for %s idx %zu", path, i);
          encoder_close();
          return;
        }
      }
      frame_buffer_idx = 0;
    }

    is_open = true;
    segment_num++;
    counter = 0;
    LOGD("mpp encoder mode: %s", use_zero_copy ? "zero-copy" : "copy");
}

void MppEncoder::encoder_close() {
    for (auto &[fd, buf] : imported_buffers) {
      if (buf != nullptr) {
        mpp_buffer_put(buf);
      }
    }
    imported_buffers.clear();
    for (auto &buf : frame_buffers) {
      if (buf != nullptr) {
        mpp_buffer_put(buf);
        buf = nullptr;
      }
    }
    if (frame_buf_group != nullptr) {
      mpp_buffer_group_put(frame_buf_group);
      frame_buf_group = nullptr;
    }
    if (cfg != nullptr) {
      mpp_enc_cfg_deinit(cfg);
      cfg = nullptr;
    }
    if (frame != nullptr) {
      mpp_frame_deinit(&frame);
      frame = nullptr;
    }
    if (mpp_ctx != nullptr) {
      mpp_destroy(mpp_ctx);
      mpp_ctx = nullptr;
      mpp_mpi = nullptr;
    }
    if (mpp_buf != nullptr) {
      mpp_buf = nullptr;
    }
    is_open = false;
}

MppBuffer MppEncoder::acquire_frame_buffer() {
    if (frame_buffers.empty()) return nullptr;
    MppBuffer buf = frame_buffers[frame_buffer_idx];
    frame_buffer_idx = (frame_buffer_idx + 1) % frame_buffers.size();
    return buf;
}

int MppEncoder::encode_frame(VisionBuf* buf, VisionIpcBufExtra *extra) {
    if (!is_open || mpp_ctx == nullptr || mpp_mpi == nullptr) {
      return -1;
    }
    if (buf->width != this->in_width || buf->height != this->in_height) {
      LOGE("input size mismatch: got %zux%zu expected %dx%d",
           buf->width, buf->height, this->in_width, this->in_height);
      return -1;
    }

    if (use_zero_copy) {
      auto it = imported_buffers.find(buf->fd);
      if (it == imported_buffers.end()) {
        MppBuffer imported = nullptr;
        MppBufferInfo info = {};
        info.type = MPP_BUFFER_TYPE_EXT_DMA;
        info.fd = buf->fd;
        info.size = alw * alh * 3 / 2;
        info.ptr = buf->addr;
        if (mpp_buffer_import(&imported, &info) != MPP_OK) {
          LOGE("mpp_buffer_import failed, falling back to copy path");
          use_zero_copy = false;
          if (frame_buf_group == nullptr) {
            if (mpp_buffer_group_get_internal(&frame_buf_group, MPP_BUFFER_TYPE_DRM) != MPP_OK) {
              LOGE("fallback mpp_buffer_group_get_internal failed");
              return -1;
            }
            for (size_t i = 0; i < frame_buffers.size(); ++i) {
              if (mpp_buffer_get(frame_buf_group, &frame_buffers[i], alw * alh * 3 / 2) != MPP_OK) {
                LOGE("fallback mpp_buffer_get prealloc failed idx %zu", i);
                return -1;
              }
            }
            frame_buffer_idx = 0;
          }
        } else {
          imported_buffers.emplace(buf->fd, imported);
          mpp_buf = imported;
        }
      } else {
        mpp_buf = it->second;
      }
    }

    if (mpp_buf == nullptr) {
      // Reuse preallocated frame buffers to avoid per-frame allocator overhead.
      mpp_buf = acquire_frame_buffer();
      if (mpp_buf == nullptr) {
        LOGE("no preallocated mpp frame buffer available");
        return -1;
      }
    }
    mpp_frame_set_width(frame, buf->width);
    mpp_frame_set_height(frame, buf->height);
    mpp_frame_set_hor_stride(frame, alw);
    mpp_frame_set_ver_stride(frame, alh);
    mpp_frame_set_fmt(frame, MPP_FMT_YUV420SP);

    if (is_downscale) {
      if (downscale_buf == nullptr) {
        LOGE("downscale buffer is null");
        mpp_buf = nullptr;
        return -1;
      }
      src = wrapbuffer_virtualaddr(buf->addr, buf->width, buf->height, RK_FORMAT_YCbCr_420_SP);
      dst = wrapbuffer_virtualaddr(downscale_buf, alw, alh, RK_FORMAT_YCbCr_420_SP);
      if (imresize(src, dst, (double)out_width / buf->width, (double)out_height / buf->height, IM_SYNC) < 0) {
        LOGE("imresize failed");
        mpp_buf = nullptr;
        return -1;
      }
      memcpy(mpp_buffer_get_ptr(mpp_buf), downscale_buf, alw * alh * 3 / 2);
    }
    else if (!use_zero_copy) {
      memcpy(mpp_buffer_get_ptr(mpp_buf), buf->addr, alw * alh * 3 / 2);
    }

    mpp_frame_set_buffer(frame, mpp_buf);
    if (mpp_mpi->encode_put_frame(mpp_ctx, frame) != MPP_OK) {
      mpp_buf = nullptr;
      return -1;
    }
    if (mpp_mpi->encode_get_packet(mpp_ctx, &packet) != MPP_OK) {
      mpp_buf = nullptr;
      return -1;
    }

    uint8_t *pkt = (uint8_t*)mpp_packet_get_pos(packet);
    size_t pkt_size = mpp_packet_get_length(packet);

    if (env_debug_encoder) {
      printf("%20s got %8zu bytes idx %4d id %8d\n", encoder_info.publish_name, pkt_size, counter, extra->frame_id);
    }

    publisher_publish(segment_num, counter, *extra,
      V4L2_BUF_FLAG_KEYFRAME,
      kj::arrayPtr<capnp::byte>(pkt, (size_t)0), // TODO: get header
      kj::arrayPtr<capnp::byte>(pkt, pkt_size));

    counter++;
    mpp_packet_deinit(&packet);
    packet = nullptr;
    mpp_buf = nullptr;
    return 1;
}

