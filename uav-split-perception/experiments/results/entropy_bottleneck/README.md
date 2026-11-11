# Entropy-coded bottlenecks (11 Nov 2026), paper 1 hardening: the strongest frozen-detector split

`evaluation/entropy_bottleneck.py`, chain `scripts/entropy_chain_nov11.sh` (under `scripts/guarded_run.py`).
The learned codes of `../learned_bottleneck/` quantise to uint8 with a per-image min-max scale and compress with zstd.
Here the same codec (k4, 32 channels, width 128, stride 2, 2 decoder layers, initialised from the trained k4_c32
code) gets a learned per-channel gain, integer rounding, a factorised entropy model (Ballé et al. 2018) and a range
coder (`constriction` 0.4), trained for distillation + λ × rate (KiB per image), 20 epochs, detector frozen.
The bitstream is real: per-channel int16 range header + range-coded symbols; every one of the 548 VisDrone-DET val
frames is decoded again and checked to equal the encoder's symbols, for every code (2740 decodes, 0 mismatches).

| λ (per KiB) | Payload | mAP50-95 | coder vs ideal | range encode (host CPU) |
| --- | --- | --- | --- | --- |
| 0.003 | 12.9 kB | 0.230 | −0.0 % | 0.6 ms |
| 0.01 | 8.7 kB | 0.226 | −0.5 % | 0.6 ms |
| 0.03 | 5.3 kB | 0.206 | −0.8 % | 1.2 ms |
| 0.1 | 2.8 kB | 0.171 | +0.0 % | 0.6 ms |
| 0.3 | 1.5 kB | 0.121 | +0.0 % | 0.5 ms |

(The coder can beat the model's ideal size slightly because each image's probabilities are renormalised on the
image's own symbol range.) At the same accuracy the payload is 52–73 % smaller than the zstd codes' and 72–88 %
smaller than JPEG's (interpolated on each measured curve; `be_metrics.tex` BeEcSave*).

Break-even rule (`evaluation/break_even_rule.py` → `../break_even/break_even.json` "entropy_codes", analysed
separately so the main cells are unchanged): 0 exceptions against untuned and tuned JPEG. A code of equal accuracy
with a 2.6× smaller payload has the same B_be and the same largest winning goodput (ec λ 0.03 vs zstd k4_c16, both
0.206 mAP: 7.78 Mbit/s and 7.17 Mbit/s on the Jetson); it wins only at more low goodputs (down to 0.25 instead of
0.42 Mbit/s). The proposition says so: B_be is set by the matching JPEG setting's size and the device's onboard
time, not by the split's payload. Simulator check: `../break_even/sim_check_entropy*.json`.

Timings: the onboard encoder is the k4_c32 code's (same MACs); the onboard non-DNN time is the measured range encode
(host CPU, conservative against the zstd rows' 0.26 ms); the server time adds the measured range decode.
Smoke run (64 images, 2 epochs, pipeline check only): `smoke/`. Weights (`weights/entropy_bottleneck/`) are not in git.
