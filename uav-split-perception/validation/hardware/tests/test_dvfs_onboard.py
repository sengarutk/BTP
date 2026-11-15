# test of adaptive2.py's DVFS clock twins on a Pi: the cap applies during a twin's inference, the default
# otherwise, and is restored on SIGTERM. Run as root from ~/hwbench.
import os, sys, threading, time, signal
sys.argv = ["x"]; sys.path.insert(0, os.path.expanduser("~/hwbench"))
import numpy as np
import adaptive2 as A
A.ONBOARD_VARIANTS = {"s320": ("yolov8s_visdrone", 320), "s320@1800": ("yolov8s_visdrone", 320)}
A.ONBOARD_CLOCK = {"s320@1800": 1800}
res, lock = {}, threading.Lock()
ob = A.Onboard(".", 3, res, lock, "cpu", "")
print("default clock", ob.clock_default, "start-up ms", {k: round(v) for k, v in ob.ms.items() if k.startswith("s320")})
print("same model object shared:", ob.models["s320"] is ob.models["s320@1800"])
seen = {"s320": set(), "s320@1800": set()}; cur = [None]
def watch():
    while True:
        if cur[0]:
            seen[cur[0]].add(int(open(A.CPUFREQ_MAX).read()) // 1000)
        time.sleep(0.01)
threading.Thread(target=watch, daemon=True).start()
img = np.zeros((360, 640, 3), np.uint8)
for var in ("s320", "s320@1800", "s320", "s320@1800"):
    cur[0] = var; t0 = time.perf_counter(); ob._infer(img, var); cur[0] = None
    print(var, "%.0f ms" % ((time.perf_counter() - t0) * 1e3))
print("caps seen during inference:", {k: sorted(v) for k, v in seen.items()})
print("after:", int(open(A.CPUFREQ_MAX).read()) // 1000)
# SIGTERM during a capped inference
def kill():
    time.sleep(0.05); os.kill(os.getpid(), signal.SIGTERM)
threading.Thread(target=kill, daemon=True).start()
try:
    while True:
        ob._infer(img, "s320@1800")
except SystemExit as e:
    print("SIGTERM -> exit", e.code, "; cap after:", int(open(A.CPUFREQ_MAX).read()) // 1000)
