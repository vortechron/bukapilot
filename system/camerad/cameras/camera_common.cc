#include "system/camerad/cameras/camera_common.h"

#include <cassert>
#include <cstring>
#include <string>
#include <vector>
#include <iostream>

#include <jpeglib.h>

#include "cereal/messaging/messaging.h"
#include "common/clutil.h"
#include "common/swaglog.h"
#include "system/camerad/cameras/camera_rk.h"
#ifdef QCOM2
#include "CL/cl_ext_qcom.h"
#endif

ExitHandler do_exit;

static void publish_thumbnail(PubMaster *pm, CameraBuf *buf);

void CameraBuf::init(cl_device_id device_id, cl_context context, CameraState *s, VisionIpcServer * v, int frame_cnt, VisionStreamType type) {
  vipc_server = v;
  stream_type = type;
  frame_buf_count = frame_cnt;

  rgb_width = 1920;
  rgb_height = 1200;
  out_img_width = (uint32_t)rgb_width;
  out_img_height = (uint32_t)rgb_height;

  // NV12 frame
  nv12_frame_size = (rgb_width * rgb_height * 3)/2;
  camera_bufs = std::make_unique<VisionBuf[]>(frame_buf_count);
  camera_bufs_metadata = std::make_unique<FrameMetadata[]>(frame_buf_count);

  int nv12_width = rgb_width;
  int nv12_height = rgb_height;
  size_t nv12_size = nv12_frame_size;
  size_t nv12_uv_offset = nv12_width * nv12_height;

  for (int i = 0; i < frame_buf_count; i++) {
    camera_bufs[i].allocate(nv12_frame_size);
  }
  LOGD("allocated %d buffers", frame_buf_count);

  vipc_server->create_buffers_with_sizes(stream_type, YUV_BUFFER_COUNT, rgb_width, rgb_height, nv12_size, nv12_width, nv12_uv_offset);
  LOGD("created %d YUV vipc buffers with size %dx%d", YUV_BUFFER_COUNT, nv12_width, nv12_height);
}

CameraBuf::~CameraBuf() {
  // RK path: buffers are mmap'd and freed by camera_close
}

bool CameraBuf::acquire() {
  int idx;
  if (!safe_queue.try_pop(idx, 100)) return false;
  cur_buf_idx = idx;
  cur_frame_data = camera_bufs_metadata[idx];
  sendFrameToVipc();
  return true;
}

void CameraBuf::sendFrameToVipc() {
  assert(cur_buf_idx >=0 && cur_buf_idx < frame_buf_count);

  cur_yuv_buf = vipc_server->get_buffer(stream_type);
  cur_camera_buf = &camera_bufs[cur_buf_idx];

  memcpy(cur_yuv_buf->addr, cur_camera_buf->addr, nv12_frame_size);

  VisionIpcBufExtra extra = {
    cur_frame_data.frame_id,
    cur_frame_data.timestamp_sof,
    cur_frame_data.timestamp_eof,
  };

  cur_yuv_buf->set_frame_id(cur_frame_data.frame_id);
  vipc_server->send(cur_yuv_buf, &extra, false);
}

void CameraBuf::queue(size_t buf_idx) {
  safe_queue.push(buf_idx);
}

// common functions

void fill_frame_data(cereal::FrameData::Builder &framed, const FrameMetadata &frame_data, CameraState *c) {
  framed.setFrameId(frame_data.frame_id);
  framed.setRequestId(frame_data.request_id);
  framed.setTimestampEof(frame_data.timestamp_eof);
  framed.setTimestampSof(frame_data.timestamp_sof);
  framed.setIntegLines(frame_data.integ_lines);
  framed.setGain(frame_data.gain);
  framed.setHighConversionGain(frame_data.high_conversion_gain);
  framed.setMeasuredGreyFraction(frame_data.measured_grey_fraction);
  framed.setTargetGreyFraction(frame_data.target_grey_fraction);
  framed.setProcessingTime(frame_data.processing_time);
  framed.setSensor(cereal::FrameData::ImageSensor::OX03C10);

  std::vector<float> temps = {frame_data.sensor_temp_c};
  kj::ArrayPtr<const float> temp_array(temps.data(), temps.size());
  framed.setTemperaturesC(temp_array);
}

kj::Array<uint8_t> get_raw_frame_image(const CameraBuf *b) {
  const uint8_t *dat = (const uint8_t *)b->cur_camera_buf->addr;

  kj::Array<uint8_t> frame_image = kj::heapArray<uint8_t>(b->cur_camera_buf->len);
  uint8_t *resized_dat = frame_image.begin();

  memcpy(resized_dat, dat, b->cur_camera_buf->len);

  return kj::mv(frame_image);
}

float calculate_exposure_value(const CameraBuf *b, Rect ae_xywh, int x_skip, int y_skip) {
  int lum_med;
  uint32_t lum_binning[256] = {0};
  const uint8_t *pix_ptr = b->cur_yuv_buf->y;

  unsigned int lum_total = 0;
  for (int y = ae_xywh.y; y < ae_xywh.y + ae_xywh.h; y += y_skip) {
    for (int x = ae_xywh.x; x < ae_xywh.x + ae_xywh.w; x += x_skip) {
      uint8_t lum = pix_ptr[(y * b->out_img_width) + x];
      lum_binning[lum]++;
      lum_total += 1;
    }
  }

  // Find mean lumimance value
  unsigned int lum_cur = 0;
  for (lum_med = 255; lum_med >= 0; lum_med--) {
    lum_cur += lum_binning[lum_med];

    if (lum_cur >= lum_total / 2) {
      break;
    }
  }

  return lum_med / 256.0;
}

void *processing_thread(MultiCameraState *cameras, CameraState *cs, process_thread_cb callback) {
  const char *thread_name = nullptr;
  if (cs == &cameras->road_cam) {
    thread_name = "RoadCamera";
  } else if (cs == &cameras->driver_cam) {
    thread_name = "DriverCamera";
  } else {
    thread_name = "WideRoadCamera";
  }
  util::set_thread_name(thread_name);

  uint32_t cnt = 0;
  while (!do_exit) {
    if (!cs->buf.acquire()) continue;

    callback(cameras, cs, cnt);

    if (cs == &(cameras->road_cam) && cameras->pm && cnt % 100 == 3) {
      // this takes 10ms???
      publish_thumbnail(cameras->pm, &(cs->buf));
    }
    ++cnt;
  }
  return NULL;
}

std::thread start_process_thread(MultiCameraState *cameras, CameraState *cs, process_thread_cb callback) {
  return std::thread(processing_thread, cameras, cs, callback);
}

// Publish road camera thumbnail for app preview (same format as loggerd's JpegEncoder)
static void publish_thumbnail(PubMaster *pm, CameraBuf *buf) {
  VisionBuf *vb = buf->cur_yuv_buf;
  if (!vb || !vb->y || !vb->uv) return;

  const int tw = 480, th = 240;  // thumbnail size (width/4, height/4 for 1920x1200)
  const int w = (int)vb->width, h = (int)vb->height, stride = (int)vb->stride;
  if (w < tw || h < th) return;

  int downscale = w / tw;
  if (downscale * th != h) return;

  // NV12 -> YUV420 planes for JPEG (16-line aligned for jpeg_write_raw_data)
  const size_t y_size = (size_t)tw * ((th + 15) & ~15);
  const size_t uv_size = y_size / 4;
  std::vector<uint8_t> y_plane(y_size), u_plane(uv_size), v_plane(uv_size);
  uint8_t *y_addr = vb->y, *uv_addr = vb->uv;

  for (int hy = 0; hy < th / 2; hy++) {
    for (int hx = 0; hx < tw / 2; hx++) {
      int ix = hx * downscale + (downscale - 1) / 2;
      int iy = hy * downscale + (downscale - 1) / 2;
      int oy = (hy * 2 + 0) * tw, oy1 = (hy * 2 + 1) * tw;
      y_plane[oy + (hx * 2 + 0)] = y_addr[(iy * 2 + 0) * stride + ix * 2 + 0];
      y_plane[oy + (hx * 2 + 1)] = y_addr[(iy * 2 + 0) * stride + ix * 2 + 1];
      y_plane[oy1 + (hx * 2 + 0)] = y_addr[(iy * 2 + 1) * stride + ix * 2 + 0];
      y_plane[oy1 + (hx * 2 + 1)] = y_addr[(iy * 2 + 1) * stride + ix * 2 + 1];
      u_plane[hy * (tw / 2) + hx] = uv_addr[iy * stride + ix * 2 + 0];
      v_plane[hy * (tw / 2) + hx] = uv_addr[iy * stride + ix * 2 + 1];
    }
  }

  unsigned char *out_buffer = nullptr;
  unsigned long out_size = 0;
  {
    struct jpeg_compress_struct cinfo;
    struct jpeg_error_mgr jerr;
    cinfo.err = jpeg_std_error(&jerr);
    jpeg_create_compress(&cinfo);
    jpeg_mem_dest(&cinfo, &out_buffer, &out_size);

    cinfo.image_width = tw;
    cinfo.image_height = th;
    cinfo.input_components = 3;
    jpeg_set_defaults(&cinfo);
    jpeg_set_colorspace(&cinfo, JCS_YCbCr);
    cinfo.comp_info[0].h_samp_factor = 2;
    cinfo.comp_info[0].v_samp_factor = 2;
    cinfo.comp_info[1].h_samp_factor = 1;
    cinfo.comp_info[1].v_samp_factor = 1;
    cinfo.comp_info[2].h_samp_factor = 1;
    cinfo.comp_info[2].v_samp_factor = 1;
    cinfo.raw_data_in = TRUE;
    jpeg_set_quality(&cinfo, 50, TRUE);
    jpeg_start_compress(&cinfo, TRUE);

    JSAMPROW y_rows[16], u_rows[8], v_rows[8];
    JSAMPARRAY planes[3] = {y_rows, u_rows, v_rows};
    for (int line = 0; line < th; line += 16) {
      for (int i = 0; i < 16; i++) {
        y_rows[i] = y_plane.data() + (line + i) * tw;
        if (i % 2 == 0) {
          int off = (tw / 2) * ((line + i) / 2);
          u_rows[i / 2] = u_plane.data() + off;
          v_rows[i / 2] = v_plane.data() + off;
        }
      }
      jpeg_write_raw_data(&cinfo, planes, 16);
    }
    jpeg_finish_compress(&cinfo);
    jpeg_destroy_compress(&cinfo);
  }

  MessageBuilder msg;
  auto ev = msg.initEvent().initThumbnail();
  ev.setFrameId(buf->cur_frame_data.frame_id);
  ev.setTimestampEof(buf->cur_frame_data.timestamp_eof);
  ev.setThumbnail(kj::arrayPtr(reinterpret_cast<const uint8_t *>(out_buffer), out_size));
  pm->send("thumbnail", msg);

  free(out_buffer);
}

void camerad_thread() {
  cl_device_id device_id = nullptr;
  cl_context context = nullptr;

  cl_device_id cl_device = cl_get_device_id_optional(CL_DEVICE_TYPE_DEFAULT);
  if (cl_device) {
    cl_platform_id device_platform;
    if (clGetDeviceInfo(cl_device, CL_DEVICE_PLATFORM, sizeof(cl_platform_id), &device_platform, NULL) == CL_SUCCESS) {
      const cl_context_properties props[] = {CL_CONTEXT_PLATFORM, (cl_context_properties)device_platform, 0};
      cl_int cl_err = CL_INVALID_VALUE;
      context = clCreateContext(props, 1, &cl_device, NULL, NULL, &cl_err);
      if (context && cl_err == CL_SUCCESS) {
        device_id = cl_device;
      } else {
        if (context) {
          clReleaseContext(context);
          context = nullptr;
        }
        LOGW("OpenCL context creation failed (err=%d), running without OpenCL", cl_err);
      }
    }
  } else {
    LOGW("No OpenCL device found, running without OpenCL");
  }

  {
    MultiCameraState cameras = {};
    VisionIpcServer vipc_server("camerad", device_id, context);

    cameras_open(&cameras);
    cameras_init(&vipc_server, &cameras, device_id, context);

    vipc_server.start_listener();

    cameras_run(&cameras);
  }
  if (context) {
    CL_CHECK(clReleaseContext(context));
  }
}

int open_v4l_by_name_and_index(const char name[], int index, int flags) {
  for (int v4l_index = 0; /**/; ++v4l_index) {
    std::string v4l_name = util::read_file(util::string_format("/sys/class/video4linux/video%d/name", v4l_index));
    if (v4l_name.empty()) return -1;
    if (v4l_name.find(name) == 0) {
      if (index == 0) {
        return HANDLE_EINTR(open(util::string_format("/dev/video%d", v4l_index).c_str(), flags));
      }
      index--;
    }
  }
}
