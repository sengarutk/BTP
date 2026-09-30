#ifndef AEGIS_CUDA_QUANT_KERNEL_H
#define AEGIS_CUDA_QUANT_KERNEL_H

#include <cstdint>
#include <cuda_runtime.h>

// All launchers are asynchronous on `stream` and return the launch status.
cudaError_t launch_max_abs(const float* x, float* out_max, int64_t n, cudaStream_t stream);
cudaError_t launch_quantize_int8(const float* x, int8_t* q, float scale, int64_t n, cudaStream_t stream);
cudaError_t launch_dequantize_int8(const int8_t* q, float* y, float scale, int64_t n, cudaStream_t stream);

#endif  // AEGIS_CUDA_QUANT_KERNEL_H
