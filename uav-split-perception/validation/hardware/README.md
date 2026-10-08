# Hardware placement study (Raspberry Pi 5, Jetson Orin Nano, laptop GPU)

Results and conclusions: `docs/hardware_results.md`. Outputs: `experiments/results/hardware/`.

| Script | Runs on | Measures |
|---|---|---|
| `hwbench.py` | each device | Per-layer and per-segment (all 276) YOLOv8s times, pre/NMS, INT8+zstd and FP16 encode/decode and bytes at every cut, JPEG Q90, board power idle/active |
| `netbench.py` | two devices | RTT, bulk goodput, and per-frame transfer time at the payload sizes (sender-side timing) |
| `pipeline_node.py` | each device of a chain | Live distributed pipeline: camera at 30 fps, segments per device, one frame per link (newest wins), detections returned to the camera |
| `placement.py` | laptop | Composes the measurements into every placement (P, P>J, P>C, P>J>C, J, J>C; all cuts and encodings) |
| `cascade_accuracy.py` | laptop GPU | mAP with two encoded boundaries (JPEG or INT8 first, INT8 or FP16 second) on all 5,000 COCO val2017 images |
| `summarize_live.py` | laptop | Median and range over the repeated live runs |

## Protocol used

```bash
# Pi 5 (4 threads; sustained thermal state after 60 s of inference)
python hwbench.py --device cpu --threads 4 --images frames --n 20 --preheat 60 --all-segments --seg-frames 5 --power pi --label pi5_cpu_4t_sustained --out results/pi5_cpu_4t_sustained.json
# Jetson (15 W mode) and laptop
python hwbench.py --device cuda --half --images frames --n 50 --warmup 10 --preheat 30 --all-segments --seg-frames 10 --power jetson --label jetson_gpu_fp16 --out results/jetson_gpu_fp16.json
# links: the upstream device listens and sends; the downstream device connects (the laptop is behind NAT)
python netbench.py serve --port 47700 --role send --label pi_laptop --out results/link_pi_laptop.json   # on the Pi
python netbench.py connect --host <pi-ip> --port 47700 --role recv                                      # on the laptop
# a live chain, e.g. Pi k4 -> laptop
python pipeline_node.py --role source --seg=-1:4 --enc int8_zstd --listen 47811 --images frames --duration 60   # Pi
python pipeline_node.py --role sink --seg 4:22 --device cuda --half --up <pi-ip>:47811                           # laptop
```

Notes:
- Ultralytics sets torch to one CPU thread on import; `hwbench.py` and `pipeline_node.py` reset the
  thread count.
- On the Jetson, PyTorch's CUDA 13 aarch64 wheels run, but without native sm_87 code. The detections
  were checked against the CPU.
- For the live runs, lock the Jetson's clocks with `sudo jetson_clocks`. At low frame rates its GPU
  otherwise down-clocks, and a segment took 47 ms instead of 17 ms.
