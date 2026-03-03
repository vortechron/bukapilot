#pragma clang diagnostic ignored "-Wexceptions"

#include "selfdrive/modeld/runners/dmonitoring_rknnmodel.h"

#include <assert.h>
#include <cstring>
#include <memory>
#include <vector>

#include "common/util.h"
#include "common/rkutil.h"
#include "common/swaglog.h"

#define RKNN_CHECK(_expr) do { assert((_expr) == RKNN_SUCC); } while (0)

struct DMonitoringRKNNModel::ModelCtx {
  rknn_context ctx = 0;
  rknn_input_output_num io_num = {};
  std::vector<rknn_tensor_attr> input_attrs;
  std::vector<rknn_tensor_attr> output_attrs;
  std::vector<rknn_input> rknn_inputs;
  std::vector<rknn_output> rknn_outputs;
  std::vector<std::vector<half>> input_bufs;
  rknn_perf_run perf_run = {};
};

void DMonitoringRKNNModel::load_model(const std::string& path, DMonitoringRKNNModel::ModelCtx* out) {
  std::string model_data = util::read_file(path);
  std::vector<unsigned char> buffer(model_data.begin(), model_data.end());
  unsigned char* modelptr = buffer.data();
  size_t model_len = buffer.size();
  assert(model_len > 0);

  RKNN_CHECK(rknn_init(&out->ctx, (void*)modelptr, model_len, RKNN_FLAG_EXECUTE_FALLBACK_PRIOR_DEVICE_GPU, NULL));
  rknn_set_core_mask(out->ctx, RKNN_NPU_CORE_0_1);
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

DMonitoringRKNNModel::DMonitoringRKNNModel(const std::string& model_path, float* output)
    : ctx_(new ModelCtx()),
      output_(output),
      run_us_(0) {
  load_model(model_path, ctx_);
  assert(ctx_->io_num.n_input >= 2 && ctx_->io_num.n_output == 1);
  ctx_->rknn_outputs[0].buf = output_;
  ctx_->rknn_outputs[0].size = ctx_->output_attrs[0].n_elems * sizeof(float);
  ctx_->rknn_outputs[0].is_prealloc = 1;
  LOGD("DMonitoringRKNNModel: %u in / %u out, NPU cores 0+1\n",
       ctx_->io_num.n_input, ctx_->io_num.n_output);
}

DMonitoringRKNNModel::~DMonitoringRKNNModel() {
  if (ctx_ && ctx_->ctx) {
    rknn_destroy(ctx_->ctx);
  }
  delete ctx_;
}

void DMonitoringRKNNModel::run(const unsigned char* input_img, const float* calib) {
  ModelCtx* m = ctx_;
  assert(m->io_num.n_input >= 2);
  const uint32_t n_img = m->input_attrs[0].n_elems;
  const uint32_t n_calib = m->input_attrs[1].n_elems;
  half* buf0 = m->input_bufs[0].data();
  half* buf1 = m->input_bufs[1].data();
  for (uint32_t i = 0; i < n_img; i++) {
    float v = input_img[i] / 255.0f;
    buf0[i] = float_to_half(v);
  }
  float_to_half_array(const_cast<float*>(calib), buf1, n_calib);
  RKNN_CHECK(rknn_inputs_set(m->ctx, m->io_num.n_input, m->rknn_inputs.data()));
  RKNN_CHECK(rknn_run(m->ctx, NULL));
  RKNN_CHECK(rknn_outputs_get(m->ctx, m->io_num.n_output, m->rknn_outputs.data(), NULL));
  RKNN_CHECK(rknn_query(m->ctx, RKNN_QUERY_PERF_RUN, &m->perf_run, sizeof(m->perf_run)));
  run_us_ = m->perf_run.run_duration;
}
