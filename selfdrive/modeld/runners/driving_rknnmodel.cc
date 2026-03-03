#pragma clang diagnostic ignored "-Wexceptions"

#include "selfdrive/modeld/runners/driving_rknnmodel.h"

#include <assert.h>
#include <cstring>
#include <memory>
#include <vector>

#include "common/util.h"
#include "common/rkutil.h"
#include "common/swaglog.h"

#define RKNN_CHECK(_expr) do { assert((_expr) == RKNN_SUCC); } while (0)

struct DrivingRKNNModel::ModelCtx {
  rknn_context ctx = 0;
  rknn_input_output_num io_num = {};
  std::vector<rknn_tensor_attr> input_attrs;
  std::vector<rknn_tensor_attr> output_attrs;
  std::vector<rknn_input> rknn_inputs;
  std::vector<rknn_output> rknn_outputs;
  std::vector<std::vector<half>> input_bufs;  // float16 input buffers
  rknn_perf_run perf_run = {};
};

void DrivingRKNNModel::load_model(const std::string& path, DrivingRKNNModel::ModelCtx* out) {
  std::string model_data = util::read_file(path);
  std::vector<unsigned char> buffer(model_data.begin(), model_data.end());
  unsigned char* modelptr = buffer.data();
  size_t model_len = buffer.size();
  assert(model_len > 0);

  RKNN_CHECK(rknn_init(&out->ctx, (void*)modelptr, model_len, RKNN_FLAG_EXECUTE_FALLBACK_PRIOR_DEVICE_GPU, NULL));
  rknn_set_core_mask(out->ctx, RKNN_NPU_CORE_2);
  rknn_write_driver_version_to_shm(out->ctx);

  RKNN_CHECK(rknn_query(out->ctx, RKNN_QUERY_IN_OUT_NUM, &out->io_num, sizeof(out->io_num)));
  out->input_attrs.resize(out->io_num.n_input);
  out->output_attrs.resize(out->io_num.n_output);
  out->rknn_inputs.resize(out->io_num.n_input);
  out->rknn_outputs.resize(out->io_num.n_output);
  out->input_bufs.resize(out->io_num.n_input);

  for (uint32_t i = 0; i < out->io_num.n_input; i++) {
    out->input_attrs[i].index = i;
    RKNN_CHECK(rknn_query(out->ctx, RKNN_QUERY_INPUT_ATTR, &out->input_attrs[i], sizeof(rknn_tensor_attr)));
    size_t n_elems = out->input_attrs[i].n_elems;
    out->input_bufs[i].resize(n_elems);
  }
  for (uint32_t i = 0; i < out->io_num.n_output; i++) {
    out->output_attrs[i].index = i;
    RKNN_CHECK(rknn_query(out->ctx, RKNN_QUERY_NATIVE_OUTPUT_ATTR, &out->output_attrs[i], sizeof(rknn_tensor_attr)));
  }

  memset(out->rknn_inputs.data(), 0, out->rknn_inputs.size() * sizeof(rknn_input));
  for (uint32_t i = 0; i < out->io_num.n_input; i++) {
    out->rknn_inputs[i].index = i;
    out->rknn_inputs[i].fmt = out->input_attrs[i].fmt;
    out->rknn_inputs[i].pass_through = 1;
    out->rknn_inputs[i].type = RKNN_TENSOR_FLOAT16;
    out->rknn_inputs[i].size = out->input_attrs[i].size;
    out->rknn_inputs[i].buf = out->input_bufs[i].data();
  }
  memset(out->rknn_outputs.data(), 0, out->rknn_outputs.size() * sizeof(rknn_output));
  for (uint32_t i = 0; i < out->io_num.n_output; i++) {
    out->rknn_outputs[i].want_float = 1;
    out->rknn_outputs[i].index = i;
    out->rknn_outputs[i].is_prealloc = 0;
  }
}

DrivingRKNNModel::DrivingRKNNModel(const std::string& vision_path,
                                   const std::string& policy_path,
                                   float* vision_output,
                                   float* policy_output)
    : vision_ctx_(new ModelCtx()),
      policy_ctx_(new ModelCtx()),
      vision_output_(vision_output),
      policy_output_(policy_output),
      vision_run_us_(0),
      policy_run_us_(0) {
  load_model(vision_path, vision_ctx_);
  load_model(policy_path, policy_ctx_);
  // Prealloc output buffers so rknn_outputs_get writes directly (avoids extra memcpy).
  // With want_float=1, RKNN expects size = n_elems * sizeof(float), not native tensor size.
  assert(vision_ctx_->io_num.n_output == 1 && policy_ctx_->io_num.n_output == 1);
  vision_ctx_->rknn_outputs[0].buf = vision_output_;
  vision_ctx_->rknn_outputs[0].size = vision_ctx_->output_attrs[0].n_elems * sizeof(float);
  vision_ctx_->rknn_outputs[0].is_prealloc = 1;
  policy_ctx_->rknn_outputs[0].buf = policy_output_;
  policy_ctx_->rknn_outputs[0].size = policy_ctx_->output_attrs[0].n_elems * sizeof(float);
  policy_ctx_->rknn_outputs[0].is_prealloc = 1;
  LOGD("DrivingRKNNModel: vision %u in / %u out, policy %u in / %u out\n",
       vision_ctx_->io_num.n_input, vision_ctx_->io_num.n_output,
       policy_ctx_->io_num.n_input, policy_ctx_->io_num.n_output);
}

DrivingRKNNModel::~DrivingRKNNModel() {
  if (vision_ctx_ && vision_ctx_->ctx) {
    rknn_destroy(vision_ctx_->ctx);
  }
  if (policy_ctx_ && policy_ctx_->ctx) {
    rknn_destroy(policy_ctx_->ctx);
  }
  delete vision_ctx_;
  delete policy_ctx_;
}

void DrivingRKNNModel::run_vision(const unsigned char* img, const unsigned char* big_img) {
  ModelCtx* m = vision_ctx_;
  assert(m->io_num.n_input >= 2);
  const uint32_t n_img = m->input_attrs[0].n_elems;
  const uint32_t n_big = m->input_attrs[1].n_elems;
  half* buf0 = m->input_bufs[0].data();
  half* buf1 = m->input_bufs[1].data();
  for (uint32_t i = 0; i < n_img; i++) {
    float v = img[i] / 255.0f;
    buf0[i] = float_to_half(v);
  }
  for (uint32_t i = 0; i < n_big; i++) {
    float v = big_img[i] / 255.0f;
    buf1[i] = float_to_half(v);
  }
  RKNN_CHECK(rknn_inputs_set(m->ctx, m->io_num.n_input, m->rknn_inputs.data()));
  RKNN_CHECK(rknn_run(m->ctx, NULL));
  RKNN_CHECK(rknn_outputs_get(m->ctx, m->io_num.n_output, m->rknn_outputs.data(), NULL));
  RKNN_CHECK(rknn_query(m->ctx, RKNN_QUERY_PERF_RUN, &m->perf_run, sizeof(m->perf_run)));
  vision_run_us_ = m->perf_run.run_duration;
  // Output already in vision_output_ (is_prealloc=1)
}

void DrivingRKNNModel::run_policy(const float* desire_pulse,
                                 const float* traffic_convention,
                                 const float* features_buffer) {
  ModelCtx* m = policy_ctx_;
  assert(m->io_num.n_input >= 3);
  float_to_half_array(const_cast<float*>(desire_pulse), m->input_bufs[0].data(), m->input_attrs[0].n_elems);
  float_to_half_array(const_cast<float*>(traffic_convention), m->input_bufs[1].data(), m->input_attrs[1].n_elems);
  float_to_half_array(const_cast<float*>(features_buffer), m->input_bufs[2].data(), m->input_attrs[2].n_elems);
  RKNN_CHECK(rknn_inputs_set(m->ctx, m->io_num.n_input, m->rknn_inputs.data()));
  RKNN_CHECK(rknn_run(m->ctx, NULL));
  RKNN_CHECK(rknn_outputs_get(m->ctx, m->io_num.n_output, m->rknn_outputs.data(), NULL));
  RKNN_CHECK(rknn_query(m->ctx, RKNN_QUERY_PERF_RUN, &m->perf_run, sizeof(m->perf_run)));
  policy_run_us_ = m->perf_run.run_duration;
  // Output already in policy_output_ (is_prealloc=1)
}
