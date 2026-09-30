// PyTorch bindings for per-tensor symmetric INT8 (de)quantization.
// CPU and CUDA paths implement the same arithmetic as quantization/quantizer.py.
#include <torch/extension.h>

#include <cfenv>
#include <cmath>
#include <cstdint>
#include <utility>

#ifdef WITH_CUDA
#include <ATen/cuda/CUDAContext.h>
#include <c10/cuda/CUDAGuard.h>
#include "kernel.h"
#endif

namespace {

constexpr double kEps = 1e-6;

float scale_from_max(float max_abs) {
    return max_abs < kEps ? 1.0f : static_cast<float>(static_cast<double>(max_abs) / 127.0);
}

std::pair<torch::Tensor, double> quantize_cpu(const torch::Tensor& input) {
    auto x = input.contiguous();
    const float* p = x.data_ptr<float>();
    const int64_t n = x.numel();
    float max_abs = 0.0f;
    for (int64_t i = 0; i < n; ++i) max_abs = std::fmax(max_abs, std::fabs(p[i]));
    const float scale = scale_from_max(max_abs);
    auto q = torch::empty_like(x, x.options().dtype(torch::kInt8));
    int8_t* out = q.data_ptr<int8_t>();
    const int old_mode = std::fegetround();
    std::fesetround(FE_TONEAREST);
    for (int64_t i = 0; i < n; ++i) {
        const float v = std::nearbyint(p[i] / scale);  // ties to even
        out[i] = static_cast<int8_t>(std::fmin(127.0f, std::fmax(-128.0f, v)));
    }
    std::fesetround(old_mode);
    return {q, static_cast<double>(scale)};
}

torch::Tensor dequantize_cpu(const torch::Tensor& q_in, double scale) {
    auto q = q_in.contiguous();
    auto y = torch::empty_like(q, q.options().dtype(torch::kFloat32));
    const int8_t* p = q.data_ptr<int8_t>();
    float* out = y.data_ptr<float>();
    const float s = static_cast<float>(scale);
    for (int64_t i = 0, n = q.numel(); i < n; ++i) out[i] = static_cast<float>(p[i]) * s;
    return y;
}

}  // namespace

std::pair<torch::Tensor, double> quantize_int8(const torch::Tensor& input) {
    TORCH_CHECK(input.scalar_type() == torch::kFloat32, "quantize_int8 expects a float32 tensor");
#ifdef WITH_CUDA
    if (input.is_cuda()) {
        const c10::cuda::CUDAGuard guard(input.device());
        auto x = input.contiguous();
        auto stream = at::cuda::getCurrentCUDAStream();
        auto max_buf = torch::empty({1}, x.options());
        TORCH_CHECK(launch_max_abs(x.data_ptr<float>(), max_buf.data_ptr<float>(), x.numel(), stream) == cudaSuccess,
                    "max_abs kernel launch failed");
        const float scale = scale_from_max(max_buf.item<float>());  // item() synchronises the stream
        auto q = torch::empty_like(x, x.options().dtype(torch::kInt8));
        TORCH_CHECK(launch_quantize_int8(x.data_ptr<float>(), q.data_ptr<int8_t>(), scale, x.numel(), stream) == cudaSuccess,
                    "quantize kernel launch failed");
        return {q, static_cast<double>(scale)};
    }
#endif
    return quantize_cpu(input);
}

torch::Tensor dequantize_int8(const torch::Tensor& q, double scale) {
    TORCH_CHECK(q.scalar_type() == torch::kInt8, "dequantize_int8 expects an int8 tensor");
#ifdef WITH_CUDA
    if (q.is_cuda()) {
        const c10::cuda::CUDAGuard guard(q.device());
        auto qc = q.contiguous();
        auto y = torch::empty_like(qc, qc.options().dtype(torch::kFloat32));
        TORCH_CHECK(launch_dequantize_int8(qc.data_ptr<int8_t>(), y.data_ptr<float>(), static_cast<float>(scale),
                                           qc.numel(), at::cuda::getCurrentCUDAStream()) == cudaSuccess,
                    "dequantize kernel launch failed");
        return y;
    }
#endif
    return dequantize_cpu(q, scale);
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("quantize_int8", &quantize_int8, "Per-tensor symmetric INT8 quantization (returns tensor, scale)");
    m.def("dequantize_int8", &dequantize_int8, "INT8 -> float32 dequantization");
}
