// Per-tensor symmetric INT8 quantization kernels.
// Semantics match quantization/quantizer.py exactly:
//   scale = float32(double(max|x|) / 127)   (1.0 if max|x| < 1e-6)
//   q     = clamp(rint(x / scale), -128, 127)   // round half to even, like torch.round
#include "kernel.h"

#include <cuda_runtime.h>
#include <math.h>

namespace {

constexpr int kBlock = 256;

__global__ void max_abs_kernel(const float* __restrict__ x, float* __restrict__ out, int64_t n) {
    __shared__ float smem[kBlock];
    float m = 0.0f;
    for (int64_t i = blockIdx.x * (int64_t)blockDim.x + threadIdx.x; i < n; i += (int64_t)blockDim.x * gridDim.x) {
        m = fmaxf(m, fabsf(x[i]));
    }
    smem[threadIdx.x] = m;
    __syncthreads();
    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (threadIdx.x < s) smem[threadIdx.x] = fmaxf(smem[threadIdx.x], smem[threadIdx.x + s]);
        __syncthreads();
    }
    // Non-negative floats order like their bit patterns, so an integer atomicMax is exact.
    if (threadIdx.x == 0) atomicMax(reinterpret_cast<int*>(out), __float_as_int(smem[0]));
}

__global__ void quantize_kernel(const float* __restrict__ x, int8_t* __restrict__ q, float scale, int64_t n) {
    for (int64_t i = blockIdx.x * (int64_t)blockDim.x + threadIdx.x; i < n; i += (int64_t)blockDim.x * gridDim.x) {
        float v = rintf(__fdiv_rn(x[i], scale));
        q[i] = static_cast<int8_t>(fminf(127.0f, fmaxf(-128.0f, v)));
    }
}

__global__ void dequantize_kernel(const int8_t* __restrict__ q, float* __restrict__ y, float scale, int64_t n) {
    for (int64_t i = blockIdx.x * (int64_t)blockDim.x + threadIdx.x; i < n; i += (int64_t)blockDim.x * gridDim.x) {
        y[i] = __fmul_rn(static_cast<float>(q[i]), scale);
    }
}

int grid_for(int64_t n) {
    int64_t blocks = (n + kBlock - 1) / kBlock;
    return static_cast<int>(blocks > 4096 ? 4096 : (blocks < 1 ? 1 : blocks));
}

}  // namespace

cudaError_t launch_max_abs(const float* x, float* out_max, int64_t n, cudaStream_t stream) {
    cudaError_t err = cudaMemsetAsync(out_max, 0, sizeof(float), stream);
    if (err != cudaSuccess) return err;
    max_abs_kernel<<<grid_for(n), kBlock, 0, stream>>>(x, out_max, n);
    return cudaGetLastError();
}

cudaError_t launch_quantize_int8(const float* x, int8_t* q, float scale, int64_t n, cudaStream_t stream) {
    quantize_kernel<<<grid_for(n), kBlock, 0, stream>>>(x, q, scale, n);
    return cudaGetLastError();
}

cudaError_t launch_dequantize_int8(const int8_t* q, float* y, float scale, int64_t n, cudaStream_t stream) {
    dequantize_kernel<<<grid_for(n), kBlock, 0, stream>>>(q, y, scale, n);
    return cudaGetLastError();
}
