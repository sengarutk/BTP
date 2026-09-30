"""Builds the INT8 quantization extension (CUDA if a matching toolkit is available, else CPU only).

    pip install --no-build-isolation ./deployment/jetson/cuda_quant
    USE_CUDA=0 pip install --no-build-isolation ./deployment/jetson/cuda_quant   # force CPU build
"""
import os

import torch
from setuptools import setup
from torch.utils.cpp_extension import BuildExtension, CppExtension, CUDAExtension

here = os.path.dirname(os.path.abspath(__file__))
use_cuda = torch.cuda.is_available() and os.environ.get("USE_CUDA", "1") == "1"

if use_cuda:
    ext = CUDAExtension("cuda_quant", [os.path.join(here, "bindings.cpp"), os.path.join(here, "kernel.cu")],
                        extra_compile_args={"cxx": ["-O3", "-DWITH_CUDA"], "nvcc": ["-O3", "-DWITH_CUDA"]})
else:
    ext = CppExtension("cuda_quant", [os.path.join(here, "bindings.cpp")], extra_compile_args={"cxx": ["-O3"]})

setup(name="cuda_quant", version="1.1.0", description="INT8 feature-map quantization for AEGIS-UAV",
      ext_modules=[ext], cmdclass={"build_ext": BuildExtension})
