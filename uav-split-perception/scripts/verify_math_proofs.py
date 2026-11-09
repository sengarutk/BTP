#!/usr/bin/env python3
"""Checks every equation and model constant of paper/main.tex, symbolically and against the code.

Status of each check:
  PROVED    derived or confirmed symbolically with SymPy;
  VERIFIED  the code evaluates the paper's formula exactly, an integer-rounding step holds on every
            one of many random exact-rational inputs, or a number in the paper is reproduced from the
            code, configs/split_config.yaml and the result files;
  FAIL      the paper, the code, or the data disagree.
SymPy's inequality solvers do not handle ceil() or max(). Where an argument needs them, that step is
checked exhaustively on exact rationals and the check says so.

Run from the repository root:  python scripts/verify_math_proofs.py   (exit status 1 on any FAIL)
"""

import ast
import csv
import inspect
import math
import random
import re
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np
import sympy as sp
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
PAPER = REPO / "paper"
RESULTS = REPO / "experiments" / "results"
TEX = (PAPER / "main.tex").read_text(encoding="utf-8")
GENERATED = "\n".join(p.read_text(encoding="utf-8") for p in sorted((PAPER / "generated_tables").glob("*.tex")))
RNG = random.Random(20260928)
INF = math.inf

CHECKS = []


def check(section):
    def register(fn):
        CHECKS.append((section, fn))
        return fn
    return register


def _load_macros():
    out = {}
    for path in sorted((PAPER / "generated_tables").glob("*metrics.tex")):
        out.update(re.findall(r"^\\newcommand\{\\([A-Za-z]+)\}\{(.*)\}\s*$", path.read_text(encoding="utf-8"), flags=re.M))
    return out


MACROS = _load_macros()


def macro(*names):
    for n in names:
        if n in MACROS:
            return MACROS[n]
    raise AssertionError(f"macro \\{names[0]} is not generated (run `make tables`)")


def macro_num(*names):
    text = macro(*names).replace("$-$", "-").replace(",", "")
    return float(re.search(r"[-+]?\d+(?:\.\d+)?", text).group())


def shown_as(value, *names):
    """True if ``value``, printed with the macro's number of decimals, reads as the macro."""
    text = macro(*names).replace("$-$", "-").replace(",", "")
    m = re.search(r"[-+]?\d+(?:\.(\d+))?", text)
    digits = len(m.group(1) or "")
    return f"{value:.{digits}f}" == f"{float(m.group()):.{digits}f}"


def nonneg(expr, symbols):
    """Sufficient test for expr >= 0 when every symbol is >= 0: after cancelling, numerator and
    denominator are polynomials in the symbols whose coefficients are all non-negative."""
    num, den = sp.fraction(sp.cancel(sp.together(sp.expand(expr))))
    return all(c >= 0 for part in (num, den) for c in sp.Poly(sp.expand(part), *symbols).coeffs())


def frac(lo, hi, den=1000):
    return Fraction(RNG.randint(round(lo * den), round(hi * den)), den)


def rows(name):
    with open(RESULTS / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tick_rate(F, x):
    """F / ceil(F x): frames per unit time when one frame needs x (F in frames per the same unit)."""
    return F / math.ceil(F * x)


# ============================================================================ Sec. 3: quantization
SEC_Q = "Sec. 3 -- quantization at the boundary (Proposition 1)"


@check(SEC_Q)
def q_clamp_inactive():
    """Prop. 1, step 1: with S rounded to float32 the clamp in q = clamp(round(X/S), -128, 127) is inactive."""
    u = sp.Rational(1, 2**23)  # max|X|/127 is formed in float64, then rounded to float32: relative error < 2^-23
    bound = 127 / (1 - u)
    assert bound < sp.Rational(255, 2)
    return "PROVED", (f"S >= (1 - 2^-23) max|X|/127, so |X_i/S| <= 127/(1 - 2^-23) = {sp.N(bound, 10)} < 127.5; "
                      "round(X_i/S) then lies in [-127, 127]")


@check(SEC_Q)
def q_error_bound():
    """Prop. 1, step 2: X_i - qS = S r with |r| <= 1/2, hence ||X - qS||_inf <= S/2."""
    S, w = sp.symbols("S w", nonnegative=True)
    n, r = sp.symbols("n r", real=True)
    assert sp.simplify(sp.expand(S * (n + r) - n * S) - S * r) == 0   # X_i/S = n + r, q = n
    assert nonneg(S / 2 - S * (sp.Rational(1, 2) - w), [S, w])          # |r| = 1/2 - w, w >= 0
    return "PROVED", "X_i - qS = S r and S/2 - S|r| = S w >= 0; identical per channel with S_c"


@check(SEC_Q)
def q_code_exact():
    """Prop. 1 holds for the code's own q and S in exact rational arithmetic (per tensor and per channel)."""
    import torch
    from quantization.quantizer import FeatureMapQuantizer as Q

    torch.manual_seed(1)
    g = torch.Generator().manual_seed(0)
    worst, count, degenerate = Fraction(0), 0, 0
    for i in range(48):
        shape = (1, 6, 10, 10)
        kind = i % 4
        if kind == 0:
            x = torch.randn(shape, generator=g) * float(10 ** RNG.uniform(-3, 2))
        elif kind == 1:
            x = torch.nn.functional.silu(torch.randn(shape, generator=g) * 4)
        elif kind == 2:
            x = torch.distributions.StudentT(2.0).sample(shape)
        else:
            x = torch.rand(shape, generator=g) * 1e-7   # below the 1e-6 guard: S = 1, q = 0
        for mode in ("int8", "int8_per_channel"):
            q, s = Q.quantize_tensor(x, mode)
            scales = [Fraction(v) for v in (s.tolist() if mode == "int8_per_channel" else [s] * 6)]
            degenerate += int(all(v == 1 for v in scales))
            for c, (xs, qs) in enumerate(zip(x.double().reshape(6, -1).tolist(), q.reshape(6, -1).tolist())):
                S = scales[c]
                for xv, qv in zip(xs, qs):
                    e = abs(Fraction(xv) - qv * S)
                    assert e <= S / 2, f"{mode}: |X - qS| = {float(e)} > S/2 = {float(S) / 2}"
                    worst = max(worst, e / (S / 2))
                    count += 1
    return "VERIFIED", (f"{count:,} values from 48 tensors (Gaussian, SiLU, Student-t, all below 1e-6: "
                        f"{degenerate} tensor/mode pairs used S = 1); max |X - qS|/(S/2) = {float(worst):.6f}")


@check(SEC_Q)
def q_per_channel_shapes():
    """Per-channel INT8: C scales, broadcast over (N, C, H, W) and (C, H, W) without shape mismatch."""
    import torch
    from quantization.quantizer import FeatureMapQuantizer as Q

    for shape in ((1, 7, 5, 3), (2, 7, 5, 3), (7, 5, 3)):
        x = torch.randn(shape)
        q, s = Q.quantize_tensor(x, "int8_per_channel")
        c = shape[1] if len(shape) == 4 else shape[0]
        assert q.shape == x.shape and tuple(s.shape) == (c,)
        assert Q.dequantize_tensor(q, s, "int8_per_channel").shape == x.shape
    return "VERIFIED", "scale vector has length C and dequantization returns the input shape for 4-D and 3-D tensors"


@check(SEC_Q)
def q_bound_in_results():
    """Table II / Sec. 3.2: the measured max |X - X_hat|/(S/2) on k4 activations is within float32 slack of 1."""
    qm = {r["mode"]: r for r in rows("quantization_modes_benchmark.csv")}
    ratios = [float(qm[m]["bound_ratio_max"]) for m in ("int8", "int8_per_channel")]
    assert all(r <= 1 + 1e-4 for r in ratios), ratios
    assert shown_as(max(ratios), "BoundRatioMax")
    return "VERIFIED", f"per tensor {ratios[0]}, per channel {ratios[1]}; \\BoundRatioMax = {macro('BoundRatioMax')}"


# ============================================================================ tensor dimensions and payloads
SEC_T = "Sec. 3.1, 3.3, 5.2 -- tensor dimensions (configs/split_config.yaml), wire sizes, Table I"
CUT_WORD = {2: "Two", 4: "Four", 5: "Five", 7: "Seven", 9: "Nine", 12: "Twelve", 15: "Fifteen", 18: "Eighteen"}


def _split_config():
    return yaml.safe_load((REPO / "configs" / "split_config.yaml").read_text(encoding="utf-8"))


@check(SEC_T)
def t_config_dimensions():
    """Every live tensor is (1, C, 640/s, 640/s) for a stride s in {4, 8, 16, 32}; element counts, sizes, and FLOPs add up."""
    cfg = _split_config()
    n_layers = len(cfg["full"]["edge_layers"])
    for tag, c in cfg.items():
        k = c["cut_layer"]
        assert c["edge_layers"] == list(range(k + 1)) and c["cloud_layers"] == list(range(k + 1, n_layers)), tag
        assert sorted(int(i) for i in c["tensors"]) == c["live_layers"], tag
        total = 0
        for layer, t in c["tensors"].items():
            b, ch, h, w = t["shape"]
            assert b == 1 and h == w and 640 % h == 0 and 640 // h in (4, 8, 16, 32), (tag, layer, t["shape"])
            assert t["num_elements"] == ch * h * w, (tag, layer)
            for dt, nb in (("fp32", 4), ("fp16", 2), ("int8", 1)):
                assert t[f"size_{dt}_kib"] == round(ch * h * w * nb / 1024, 1), (tag, layer, dt)
            total += ch * h * w
        assert c["total_elements"] == total, tag
        for dt, nb in (("fp32", 4), ("fp16", 2), ("int8", 1)):
            assert c[f"payload_{dt}_kib"] == round(total * nb / 1024, 1), (tag, dt)
        assert abs(c["edge_gflops"] - 2 * c["edge_gmacs"]) <= 0.002, tag   # FLOPs = 2 MACs
    assert n_layers == 23 and len(cfg) - 1 == 8
    return "VERIFIED", f"{len(cfg) - 1} cuts + full model, 23 modules; shapes, element counts, sizes and FLOPs = 2 MACs consistent"


@check(SEC_T)
def t_wire_sizes():
    """Measured wire bytes = elements x bytes/element + 16-byte header + 4-byte CRC32 + 16-byte descriptor per tensor."""
    from protocol.packet import DESCRIPTOR_SIZE, PRIMARY_HEADER_SIZE

    assert PRIMARY_HEADER_SIZE == 16 and DESCRIPTOR_SIZE == 16
    cfg = _split_config()
    n = 0
    for r in rows("split_pareto_analysis.csv"):
        if r["kind"] != "split" or r["dtype"] not in ("int8", "fp16"):
            continue
        c = cfg[f"k{r['cut']}"]
        expect = c["total_elements"] * (1 if r["dtype"] == "int8" else 2) + PRIMARY_HEADER_SIZE + 4 \
            + DESCRIPTOR_SIZE * len(c["live_layers"])
        assert float(r["payload_bytes_mean"]) == expect, (r["config"], r["payload_bytes_mean"], expect)
        n += 1
    return "VERIFIED", f"{n} INT8/FP16 split configurations match to the byte"


@check(SEC_T)
def t_table_numbers():
    """Table I and Sec. 5.2 numbers (FLOP %, payloads, zstd ratios, raw image, GFLOPs, payload ratios) follow from configs and CSVs."""
    cfg = _split_config()
    par = {r["config"]: r for r in rows("split_pareto_analysis.csv")}
    codec = {r["config"]: r for r in rows("codec_offload.csv")}
    ratios = []
    for k, word in CUT_WORD.items():
        assert shown_as(cfg[f"k{k}"]["edge_flop_pct"], f"FlopPctK{word}")
        assert float(par[f"k{k}_int8"]["edge_flop_pct"]) == cfg[f"k{k}"]["edge_flop_pct"]
        i8, z = float(par[f"k{k}_int8"]["payload_kib_mean"]), float(par[f"k{k}_int8_zstd"]["payload_kib_mean"])
        assert shown_as(i8, f"PayloadINTK{word}") and shown_as(z, f"PayloadZstdK{word}")
        ratios.append(i8 / z)
    assert shown_as(min(ratios), "ZstdRatioMin") and shown_as(max(ratios), "ZstdRatioMax")
    assert shown_as(3 * 640 * 640 / 1024, "RawImageKiB") and shown_as(cfg["full"]["edge_gflops"], "TotalGFLOPs")
    zmin = min(float(par[f"k{k}_int8_zstd"]["payload_kib_mean"]) for k in CUT_WORD)
    q90, q95 = (float(codec[q]["payload_kib_mean"]) for q in ("jpeg_q90", "jpeg_q95"))
    k4 = float(par["k4_int8"]["payload_kib_mean"])
    for value, name in ((zmin, "MinSplitKiB"), (zmin / q90, "RatioMinSplitOverJPEG"), (zmin / q95, "RatioMinSplitOverJPEGQNinetyFive"),
                        (k4 / q90, "RatioKFourOverJPEG"), (k4 / q95, "RatioKFourOverJPEGQNinetyFive")):
        assert shown_as(value, name), (name, value, macro(name))
    return "VERIFIED", (f"8 cuts x (FLOP %, INT8 KiB, INT8+zstd KiB); zstd ratio {min(ratios):.2f}-{max(ratios):.2f}; "
                        f"smallest split {zmin:.1f} KiB = {zmin / q95:.2f}x Q95 JPEG")


# ============================================================================ Sec. 4: model and policy
SEC_P = "Sec. 4 -- onboard time, energy, deadline condition and the adaptive policy"


@check(SEC_P)
def p_onboard_time():
    """e_c = t_full (phi_c + rho_c): the simulator's scaling of host times equals the paper's expression."""
    from simulation.analytic import Option, System, onboard_ms
    from simulation.system_model import load_offload_configs, make_hardware

    t, phi, h, host = sp.symbols("t_full phi h t_host", positive=True)
    assert sp.simplify((t * phi + h * (t / host)) - t * (phi + h / host)) == 0
    cfgs = load_offload_configs()
    n = 0
    for tf in (40.0, 90.0, 180.0, 360.0):
        hw = make_hardware(tf)
        for c in cfgs.values():
            assert math.isclose(hw.onboard_ms(c), onboard_ms(Option.from_config(c, hw.host_full_ms), System(tf)), rel_tol=1e-12)
            n += 1
    return "PROVED", f"t_full phi + t_proc t_full/t_host = t_full (phi + rho); simulator and closed form agree on {n} (config, t_full) pairs"


@check(SEC_P)
def p_deadline_condition():
    """L_c <= D  <=>  B >= B*_c = b_c/(D - e_c - d - s_c) when D > e_c + d + s_c; no B > 0 works otherwise."""
    B, b, g = sp.symbols("B b g", positive=True)          # g = D - e - d - s > 0
    h = sp.Symbol("h", nonnegative=True)                   # D - e - d - s = -h <= 0
    e, d, s, D = sp.symbols("e d s D", real=True)
    assert sp.expand((D - (e + b / B + d + s)) - ((D - e - d - s) - b / B)) == 0   # L <= D  <=>  b/B <= g
    assert sp.simplify((g - b / B) - (g / B) * (B - b / g)) == 0                    # g - b/B = (g/B)(B - b/g), g/B > 0
    assert (b / B + h).is_positive                                                  # b/B > 0 >= -h: never on time
    return "PROVED", ("L_c <= D <=> b/B <= g; g - b/B = (g/B)(B - b/g) with g/B > 0 gives B >= b/g; "
                      "for g = -h <= 0, b/B + h > 0 so no B works: B* = oo and p_c = 0")


@check(SEC_P)
def p_normal_tail():
    """p_c = Pr[B >= B*] = erfc((B* - mu)/(sqrt(2) sigma))/2 for B ~ N(mu, sigma^2); it is a valid, monotone probability."""
    from sympy.stats import Normal, P

    mu, b = sp.symbols("mu b", real=True)
    sigma = sp.Symbol("sigma", positive=True)
    closed = sp.erfc((b - mu) / (sp.sqrt(2) * sigma)) / 2
    assert sp.simplify((P(Normal("B", mu, sigma) >= b) - closed).rewrite(sp.erf)) == 0
    density = sp.exp(-(b - mu) ** 2 / (2 * sigma ** 2)) / (sp.sqrt(2 * sp.pi) * sigma)
    assert sp.simplify(sp.diff(closed, b) + density) == 0          # dp/dB* = -density < 0
    assert sp.limit(closed, b, -sp.oo) == 1 and sp.limit(closed, b, sp.oo) == 0
    return "PROVED", "SymPy's Pr[N(mu, sigma^2) >= b] equals the erfc form; decreasing in b from 1 to 0, so 0 <= p_c <= 1"


def _paper_policy(c, hw, mu, sd, D, d, F, lam, floor, a_ref):
    """Sec. 4.6 as printed, including its stated special cases (independent of the simulator code)."""
    rho = c.host_edge_proc_ms / hw.host_full_ms
    phi = 1.0 if c.kind == "onboard" else c.edge_flop_frac
    e = hw.t_full_ms * (phi + (0.0 if c.kind == "onboard" else rho))
    b_kbit, s = c.payload_bytes * 8 / 1e3, c.cloud_ms
    sigma = max(sd, floor * mu)
    if c.kind == "onboard":
        p, t_tx = (1.0 if hw.t_full_ms <= D else 0.0), 0.0
    elif mu <= 1e-3:
        p, t_tx = 0.0, INF
    else:
        t_tx, slack = b_kbit / mu, D - e - d - s
        p = 0.0 if slack <= 0 else 0.5 * math.erfc((b_kbit / slack - mu) / (math.sqrt(2) * sigma))
    bottleneck = max(e, 0.0 if math.isinf(t_tx) else t_tx)
    f = F / math.ceil(Fraction(F) * Fraction(bottleneck) / 1000)
    energy = ((hw.p_compute_w - hw.p_idle_w) * e + (hw.p_tx_w - hw.p_rx_idle_w) * (0.0 if math.isinf(t_tx) else t_tx)) / 1e3
    return p, f, energy, f * p * c.map50_95 / a_ref - lam * energy


@check(SEC_P)
def p_policy_matches_paper():
    """AdaptivePolicy computes p_c, f_c, E_c and the score exactly as printed; the printed special cases are needed."""
    from simulation.system_model import AdaptivePolicy, load_offload_configs, make_hardware

    cfgs = list(load_offload_configs().values())
    hws = {tf: make_hardware(tf) for tf in (40.0, 90.0, 180.0, 360.0)}
    n = 0
    for _ in range(4000):
        hw = hws[RNG.choice(list(hws))]
        pol = AdaptivePolicy(cfgs, hw)
        c = RNG.choice(cfgs)
        mu = RNG.choice([0.0, 5e-4, RNG.uniform(0.01, 200)])
        sd = RNG.choice([0.0, RNG.uniform(0, 50)])
        got = pol.predict(c, mu, sd)
        p, f, energy, score = _paper_policy(c, hw, mu, sd, pol.deadline_ms, pol.delay_ms, pol.camera_fps,
                                            pol.w.energy_per_frame, pol.w.min_rel_std, pol.base_map)
        assert math.isclose(got["p_on_time"], p, rel_tol=1e-12, abs_tol=1e-15), (c.name, mu, got["p_on_time"], p)
        assert got["fps"] == f and math.isclose(got["energy_j"], energy, rel_tol=1e-12), (c.name, mu)
        assert math.isclose(pol.score(c, mu, sd), score, rel_tol=1e-12, abs_tol=1e-12)
        n += 1
    # Why the paper states the special cases: the bare formula gives wrong probabilities there.
    hw = hws[360.0]
    pol = AdaptivePolicy(cfgs, hw)
    late = next(c for c in cfgs if c.kind == "split" and pol.deadline_ms - hw.onboard_ms(c) - pol.delay_ms - c.cloud_ms <= 0)
    slack = pol.deadline_ms - hw.onboard_ms(late) - pol.delay_ms - late.cloud_ms
    bare = 0.5 * math.erfc((late.payload_bytes * 8 / 1e3 / slack - 50.0) / (math.sqrt(2) * 5.0))
    assert pol.predict(late, 50.0, 5.0)["p_on_time"] == 0.0
    onboard_bare = 0.5 * math.erfc((0 - 1.0) / (math.sqrt(2) * 1.0))
    return "VERIFIED", (f"{n} random (config, t_full, mu, sigma) cases match; without the stated cases the formula gives "
                        f"p = {bare:.3f} for {late.name} at t_full = 360 ms (slack {slack:.1f} ms, code: 0) and "
                        f"p = Pr[B >= 0] = {onboard_bare:.3f} for onboard at mu = sigma = 1 (code: 1)")


@check(SEC_P)
def p_units():
    """Dimensional analysis of L_c, B*_c, f_c, p_c, beta_c, the score, the endurance and hover formulas, and the code's unit conversions."""
    s_, bit, J, kg, m_ = sp.symbols("second bit joule kilogram metre", positive=True)
    q = sp.symbols("e b B d s g F mu sigma P W_bat t T_th rho_air A", positive=True)
    e, b, B, d, s, g, F, mu, sig, P, Wb, t, Th, rho_air, A = q     # g = D - e - d - s (a time)
    units = {e: s_, d: s_, s: s_, g: s_, t: s_, b: bit, B: bit / s_, mu: bit / s_, sig: bit / s_, F: 1 / s_,
             P: J / s_, Wb: 3600 * J, Th: kg * m_ / s_ ** 2, rho_air: kg / m_ ** 3, A: m_ ** 2}

    def unit(monomial):
        """Unit of a product/quotient of quantities (numeric factors dropped)."""
        ratio = sp.powsimp(sp.simplify(monomial.subs({x: x * u for x, u in units.items()}, simultaneous=True) / monomial), force=True)
        return sp.Mul(*[f for f in sp.Mul.make_args(ratio) if f.free_symbols])

    assert {unit(x) for x in (e, b / B, d, s)} == {s_}                           # L_c = e + b/B + d + s
    assert {unit(x) for x in (d, s, e, g)} == {s_}                                # slack D - e - d - s is a time
    assert unit(b / g) == unit(B) == unit(mu) == bit / s_                         # B*_c is a rate, like B and mu
    assert unit(F * e) == 1 and unit(F * b / B) == 1 and unit(F) == 1 / s_        # f_c = F / ceil(F max(e, b/B))
    assert unit(mu / sig) == 1 and unit(B * t / b) == 1                           # p_c argument, beta_c
    lam_unit = sp.simplify(unit(F) / unit(P * e))                                 # score = f p A/A - lam E
    assert lam_unit == 1 / (s_ * J)
    assert unit(Wb / P) == s_ and sp.simplify(3600 * Wb / P / 60 - 60 * Wb / P) == 0   # 60 W_bat[Wh]/P[W] minutes
    assert unit(Th ** sp.Rational(3, 2) / sp.sqrt(2 * rho_air * A)) == kg * m_ ** 2 / s_ ** 3   # hover power: watts
    # code: t_tx[ms] = (bytes*8/1e3)/B[Mbit/s];  E[J] = P[W] * t[ms] / 1e3
    nbytes, rate = sp.symbols("n_bytes rate", positive=True)
    t_true = (8 * nbytes * bit) / (rate * 10 ** 6 * bit / s_)
    assert sp.simplify(t_true / (s_ / 1000) - (nbytes * 8 / sp.Integer(10) ** 3) / rate) == 0
    return "PROVED", ("every sum adds like terms; B*_c is a rate, F max(e, b/B) and beta_c are dimensionless; "
                      "the energy weight must carry s^-1 J^-1 (lambda_E in the paper); code conversions kbit/Mbps = ms and W ms/1e3 = J hold")


@check(SEC_P)
def p_ewma():
    """EWMA: alpha = 1 - exp(-slot/tau) lies in (0, 1) and the variance recursion (1-alpha)(v + alpha diff^2) stays >= 0."""
    x = sp.Symbol("x", positive=True)            # x = slot / tau
    alpha = 1 - sp.exp(-x)
    assert alpha.subs(x, 0) == 0 and sp.diff(alpha, x).is_positive and sp.limit(alpha, x, sp.oo) == 1
    a, c, var, d2 = sp.symbols("a c v d2", nonnegative=True)   # a = alpha, c = 1 - alpha
    assert nonneg(c * (var + a * d2), [a, c, var, d2])
    from simulation.stream_sim import SimParams
    tau = SimParams.__dataclass_fields__["est_tau_ms"].default
    return "PROVED", f"alpha(0) = 0, alpha' > 0, alpha -> 1; with tau = {tau:g} ms and 10 ms slots alpha = {1 - math.exp(-10 / tau):.4f}"


# ============================================================================ Sec. 4: channel and links
SEC_C = "Sec. 4.4-4.5 -- channel, delay, loss and air-to-air link models"


@check(SEC_C)
def c_shannon():
    """SE(gamma) = min(alpha log2(1+gamma), SE_max) above gamma_min: increasing, cap reached at 2^(SE_max/alpha) - 1; code identical."""
    from simulation.trace_generator import SE_MAX, SHANNON_ALPHA, SINR_MIN_DB, attenuated_shannon_se

    g = sp.Symbol("gamma", positive=True)
    al, cap = sp.nsimplify(SHANNON_ALPHA), sp.nsimplify(SE_MAX)
    se = al * sp.log(1 + g, 2)
    assert sp.diff(se, g).is_positive
    g_star = sp.solve(sp.Eq(se, cap), g)[0]
    assert g_star == 2 ** (cap / al) - 1
    sinr = np.concatenate([np.linspace(-30, 40, 7001), [SINR_MIN_DB, SINR_MIN_DB - 1e-9]])
    lin = 10 ** (sinr / 10)
    expect = np.where(sinr < SINR_MIN_DB, 0.0, np.minimum(SHANNON_ALPHA * np.log2(1 + lin), SE_MAX))
    assert np.array_equal(attenuated_shannon_se(sinr), expect)
    return "PROVED", (f"alpha = {SHANNON_ALPHA:g}, SE_max = {SE_MAX:g}: cap binds at gamma* = {g_star} "
                      f"({10 * math.log10(float(g_star)):.2f} dB); 0 below {SINR_MIN_DB:g} dB; code equal on 7,003 SINR values")


@check(SEC_C)
def c_gudmundson():
    """Shadowing AR(1) in dB: stationary variance sigma^2 and correlation exp(-distance/d_corr); code statistics agree."""
    from simulation.trace_generator import _shadowing_db

    r, sig, dx, dc, k = sp.symbols("rho sigma dx d_corr k", positive=True)
    assert sp.simplify(r ** 2 * sig ** 2 + sig ** 2 * (1 - r ** 2) - sig ** 2) == 0
    assert sp.simplify(sp.powsimp(sp.exp(-dx / dc) ** k, force=True) - sp.exp(-k * dx / dc)) == 0
    s = _shadowing_db(200_000, 4.0, 1.0, 10.0, np.random.default_rng(0))
    var = float(np.var(s))
    lag = 5
    corr = float(np.corrcoef(s[:-lag], s[lag:])[0, 1])
    assert abs(var / 16.0 - 1) < 0.05 and abs(corr - math.exp(-lag / 10.0)) < 0.03, (var, corr)
    return "PROVED", f"Var = rho^2 sigma^2 + sigma^2 (1 - rho^2) = sigma^2; code: var {var:.2f} (16), lag-5 corr {corr:.3f} ({math.exp(-0.5):.3f})"


@check(SEC_C)
def c_rician():
    """Rician block fading has unit mean power: K/(K+1) + E|scatter|^2/(K+1) = 1; code's per-slot gain averages to 1."""
    from simulation.trace_generator import _rician_slot_gain_db

    K = sp.Symbol("K", positive=True)
    p1, p2 = sp.symbols("phi1 phi2", real=True)
    cross = sp.integrate(sp.exp(sp.I * (p1 - p2)), (p1, 0, 2 * sp.pi), (p2, 0, 2 * sp.pi)) / (4 * sp.pi ** 2)
    assert cross == 0                                              # E[e^{j(phi_m - phi_n)}] = 0 for m != n
    assert sp.simplify(K / (K + 1) + 1 / (K + 1)) == 1             # E|scatter|^2 = M/M = 1
    means = []
    for k_db in (0.0, 9.0):
        for seed in range(3):
            gain = _rician_slot_gain_db(20_000, k_db, 12.0, 3.5e9, np.random.default_rng(seed))
            means.append(float(np.mean(10 ** (gain / 10))))
    assert all(abs(m - 1) < 0.06 for m in means), means
    return "PROVED", f"cross terms integrate to 0 and K/(K+1) + 1/(K+1) = 1; code mean linear gain {min(means):.3f}-{max(means):.3f}"


@check(SEC_C)
def c_doppler_sampling():
    """The 1 kHz fading simulation resolves the largest Doppler shift of every scenario (f_d = v f_c / c < f_s / 2)."""
    from simulation.trace_generator import PROFILES, _rician_slot_gain_db

    fs = sp.Integer(inspect.signature(_rician_slot_gain_db).parameters["sub_hz"].default)
    v_max = max(sp.nsimplify(p.speed_mps) for p in PROFILES.values())
    fd_profiles = v_max * sp.Rational(35, 10) * 10 ** 9 / (3 * 10 ** 8)
    fd_mc = 30 * sp.Rational(35, 10) * 10 ** 9 / (3 * 10 ** 8)       # Monte Carlo speeds reach 30 m/s
    assert fd_profiles < fs / 2 and fd_mc < fs / 2
    return "PROVED", f"f_d = {sp.N(fd_profiles, 4)} Hz (profiles), {sp.N(fd_mc, 4)} Hz (Monte Carlo) < f_s/2 = {fs / 2} Hz"


@check(SEC_C)
def c_delay_and_loss():
    """Trace delay = base + 10(1 - SE/SE_max) ms + Exp(mean 2 ms); residual loss 0.1 e^{-(gamma-gamma_min)/3} % (<= 0.1 %), 100 % in outage."""
    from simulation.trace_generator import SINR_MIN_DB, ChannelProfile, PROFILES, generate_trace

    x = sp.Symbol("x", nonnegative=True)                   # x = gamma - gamma_min in dB
    loss = sp.Rational(1, 10) * sp.exp(-x / 3)
    assert sp.diff(loss, x).is_negative and loss.subs(x, 0) == sp.Rational(1, 10)
    strong = ChannelProfile("strong", "", 40.0, 0.5, 30.0, 10.0, 20.0, 30.0, 12.0)
    dead = ChannelProfile("dead", "", -60.0, 0.5, 30.0, 10.0, 20.0, 30.0, 12.0)
    ds = np.array([r["delay_ms"] for r in generate_trace(strong, 120.0, seed=5)]) - 12.0
    dd = [(r["delay_ms"] - 12.0, r["packet_loss_pct"], r["bandwidth_mbps"]) for r in generate_trace(dead, 120.0, seed=6)]
    assert ds.min() >= -0.01 and abs(ds.mean() - 2.0) < 0.1, ds.mean()           # SE = SE_max: jitter only
    assert all(b == 0 and l == 100.0 for _, l, b in dd)
    assert abs(np.mean([d for d, _, _ in dd]) - 12.0) < 0.1                         # outage: +10 ms + jitter
    n_up = 0
    for r in generate_trace(PROFILES["moderate"], 60.0, seed=7):
        if r["bandwidth_mbps"] > 0:
            expect = 0.1 * math.exp(-(r["sinr_db"] - SINR_MIN_DB) / 3.0)
            assert r["packet_loss_pct"] <= 0.1 + 1e-9 and abs(r["packet_loss_pct"] - expect) < 3e-4
            n_up += 1
    return "PROVED", (f"loss decreasing from 0.1 % at the cut-off; jitter mean {ds.mean():.2f} ms at full SE, "
                      f"delay excess {np.mean([d for d, _, _ in dd]):.2f} ms in outage; loss formula matches {n_up:,} slots")


@check(SEC_C)
def c_a2a_link():
    """A2A: PER capped at 1 (reached 2 dB below each threshold); goodput at the spacing and the zero-goodput range reproduce Sec. 4.5."""
    from simulation.stream_sim import (A2A_MAC_EFFICIENCY, A2A_MCS, A2A_PER_AT_THRESHOLD, A2A_PER_DB_PER_DECADE, SimParams,
                                       a2a_per, a2a_rate_mbps, a2a_snr_db)

    snr, thr, dist = sp.symbols("snr thr d", positive=True)
    per0, slope = sp.nsimplify(A2A_PER_AT_THRESHOLD), sp.nsimplify(A2A_PER_DB_PER_DECADE)
    per = per0 * 10 ** (-(snr - thr) / slope)
    edge = sp.solve(sp.Eq(per, 1), snr)
    assert len(edge) == 1 and sp.simplify(edge[0] - (thr - slope * sp.log(1 / per0, 10))) == 0, edge
    assert all(0.0 <= a2a_per(s, t) <= 1.0 for s in np.linspace(-20, 60, 801) for t, _ in A2A_MCS)
    radio = {k: sp.nsimplify(v.default) for k, v in inspect.signature(a2a_snr_db).parameters.items()
             if k not in ("dist_m", "shadow_db")}
    pl1 = 20 * sp.log(4 * sp.pi * radio["f_ghz"] * 10 ** 9 / (3 * 10 ** 8), 10)
    snr_d = radio["tx_dbm"] - (pl1 + 10 * radio["n_exp"] * sp.log(dist, 10)) - radio["noise_dbm"]
    spacing = SimParams.__dataclass_fields__["spacing_m"].default
    rate = lambda dd: sp.N(sp.nsimplify(A2A_MAC_EFFICIENCY) * max(sp.nsimplify(r) * (1 - sp.Min(1, per.subs({snr: snr_d.subs(dist, dd), thr: sp.nsimplify(t)})))
                                                                  for t, r in A2A_MCS), 15)
    at_spacing = float(rate(spacing))
    assert math.isclose(at_spacing, a2a_rate_mbps(spacing), rel_tol=1e-9) and shown_as(at_spacing, "AtwoASpacingMbps")
    t0 = sp.nsimplify(min(t for t, _ in A2A_MCS))
    d_zero = float(sp.solve(sp.Eq(snr_d, t0 - slope * sp.log(1 / per0, 10)), dist)[0])
    assert a2a_rate_mbps(d_zero * 0.999) > 0 and a2a_rate_mbps(d_zero * 1.001) == 0
    assert 10 * round(d_zero / 10) == macro_num("AtwoARangeM")
    return "PROVED", (f"PER = 1 at SNR = threshold - {sp.N(slope * sp.log(1 / per0, 10), 3)} dB; {at_spacing:.2f} Mbit/s at "
                      f"{spacing:g} m (\\AtwoASpacingMbps = {macro('AtwoASpacingMbps')}); zero at {d_zero:.1f} m (\\AtwoARangeM = {macro('AtwoARangeM')})")


@check(SEC_C)
def c_a2a_reciprocal():
    """Static A2A shadowing is one draw per unordered UAV pair (symmetric, zero diagonal), as stated."""
    from simulation.stream_sim import SimParams, StreamSimulator
    from simulation.system_model import load_offload_configs, make_hardware

    sim = StreamSimulator(SimParams(make_hardware(180.0), load_offload_configs(), mode="k4_int8_zstd", n_uavs=6, duration_s=2.0))
    sh = sim.a2a_shadow_db
    assert np.array_equal(sh, sh.T) and np.all(np.diag(sh) == 0) and np.std(sh[np.triu_indices(6, 1)]) > 0
    return "VERIFIED", "6-UAV shadowing matrix is symmetric with zero diagonal"


# ============================================================================ Sec. 6: closed form and propositions
SEC_M = "Sec. 5.1 and 6 -- closed-form model, Propositions 2-5, crossover bandwidths, hover and endurance"


def _closed_form(e, b, s, B, d, D, F, onboard=False):
    """Sec. 6.1 as printed (exact when the inputs are Fractions). Times in ms, b in kbit, B in kbit/ms = Mbit/s, F in 1/ms."""
    if onboard:
        return e, (Fraction(0) if e <= D else INF), tick_rate(F, e)
    slack = D - e - d - s
    b_star = b / slack if slack > 0 else INF
    return e + b / B + d + s, b_star, tick_rate(F, max(e, b / B))


@check(SEC_M)
def m_closed_form_code():
    """simulation/analytic.py evaluates B*_c, f_c and U_c exactly as printed, including B*_c = oo and the onboard case."""
    from simulation.analytic import Option, System, frame_rate, required_mbps, utility

    n = 0
    for _ in range(6000):
        kind = RNG.choice(["onboard", "split", "codec"])
        o = Option("x", kind, 1.0 if kind == "onboard" else (0.0 if kind == "codec" else RNG.uniform(0.05, 0.9)),
                   RNG.uniform(0, 0.4), 0.0 if kind == "onboard" else RNG.uniform(1e4, 2e7), RNG.uniform(1, 40), RNG.uniform(0.3, 0.45))
        s = System(RNG.uniform(10, 1000), RNG.uniform(100, 1000), float(RNG.choice([10, 15, 24, 30, 60])),
                   RNG.uniform(5, 100), RNG.uniform(0.5, 4))
        B = RNG.uniform(0.05, 300)
        e = Fraction(s.t_full_ms) * (Fraction(o.phi) + (0 if kind == "onboard" else Fraction(o.rho)))
        _, b_star, f = _closed_form(e, Fraction(o.bits) / 1000, Fraction(o.server_ms) * Fraction(s.server_scale), Fraction(B),
                                    Fraction(s.delay_ms), Fraction(s.deadline_ms), Fraction(s.camera_fps) / 1000, kind == "onboard")
        got = required_mbps(o, s)
        assert (math.isinf(got) and b_star == INF) or math.isclose(got, float(b_star), rel_tol=1e-9, abs_tol=1e-12), (o, s)
        assert math.isclose(frame_rate(o, s, B), float(f) * 1000, rel_tol=1e-12), (o, s, B)
        u = float(f) * 1000 * o.acc / 0.44 if B >= float(b_star) else 0.0
        assert math.isclose(utility(o, s, B, 0.44), u, rel_tol=1e-9, abs_tol=1e-12)
        n += 1
    return "VERIFIED", f"{n} random (option, system, goodput) cases, reference evaluated in exact rationals"


@check(SEC_M)
def m_dominance_symbolic():
    """Prop. 2: under b_q <= b_k, e_q <= e_k, e_q + s_q <= e_k + s_k: L_q <= L_k, B*_q <= B*_k, E_q <= E_k (slack variables)."""
    B, bq, x1, x2, x3, gk, pc, pt = sp.symbols("B b_q x1 x2 x3 g_k Pc Pt", nonnegative=True)
    eq, sq, d, D = sp.symbols("e_q s_q d D", real=True)
    ek, bk = eq + x1, bq + x3                   # e_k = e_q + x1, b_k = b_q + x3
    sk = sq + x2 - x1                           # e_k + s_k = e_q + s_q + x2
    L = lambda e, b, s: e + b / B + d + s
    assert nonneg(L(ek, bk, sk) - L(eq, bq, sq), [B, x2, x3])
    # B*: g_k = D - e_k - d - s_k > 0, so g_q = g_k + x2
    assert nonneg(bk / gk - bq / (gk + x2), [bq, x3, gk, x2])
    assert nonneg((pc * ek + pt * bk / B) - (pc * eq + pt * bq / B), [pc, pt, x1, x3, B])
    return "PROVED", ("L_k - L_q = x2 + x3/B; B*_k - B*_q = (b_q x2 + x3 g_k + x2 x3)/(g_k (g_k + x2)); "
                      "E_k - E_q = (P_busy - P_idle) x1 + (P_tx - P_rx) x3/B -- all >= 0")


@check(SEC_M)
def m_dominance_exhaustive():
    """Prop. 2 (ceil and max steps): f_q >= f_k and U_k/U_q <= A_k/A_q on random exact-rational instances."""
    n = 0
    while n < 40_000:
        F = Fraction(RNG.choice([10, 15, 24, 30, 60]), 1000)
        D, d, B = frac(100, 1000), frac(1, 100), frac(0.1, 200)
        eq, sq, bq = frac(0.5, 400), frac(0, 50), frac(1, 3000)
        ek, sk, bk = eq + frac(0, 300), frac(0, 60), bq + frac(0, 10000)
        if ek + sk < eq + sq:
            continue
        aq, ak = frac(0.3, 0.5), frac(0.3, 0.5)
        Lq, Bq, fq = _closed_form(eq, bq, sq, B, d, D, F)
        Lk, Bk, fk = _closed_form(ek, bk, sk, B, d, D, F)
        assert Lq <= Lk and Bq <= Bk and fq >= fk
        uq, uk = (fq * aq if B >= Bq else 0), (fk * ak if B >= Bk else 0)
        if uq > 0:
            assert uk * aq <= uq * ak
        n += 1
    return "VERIFIED", f"{n:,} instances satisfying the conditions; no violation of any of the four conclusions"


@check(SEC_M)
def m_dominance_constants():
    """Prop. 2 constants: t_full >= (s_q - s_k)/(phi_k + rho_k - rho_q) and the numbers quoted after the proposition."""
    from simulation.analytic import Option
    from simulation.system_model import host_full_ms, load_offload_configs

    # e_q + s_q <= e_k + s_k  <=>  t (phi_k + rho_k - rho_q) >= s_q - s_k  <=>  t >= (s_q - s_k)/a  for a = phi_k + rho_k - rho_q > 0
    t, phk, rhk, rhq, sq, sk = sp.symbols("t phi_k rho_k rho_q s_q s_k", real=True)
    a = phk + rhk - rhq
    assert sp.expand((t * (phk + rhk) + sk) - (t * rhq + sq) - (t * a - (sq - sk))) == 0
    assert sp.simplify(t * a - (sq - sk) - a * (t - (sq - sk) / a)) == 0          # divide by a > 0: order kept
    cfg = load_offload_configs()
    h = host_full_ms(cfg)
    o = {n: Option.from_config(c, h) for n, c in cfg.items()}
    splits = [n for n in o if o[n].kind == "split"]
    jpegs = [n for n in o if n.startswith("jpeg")]
    q = o["jpeg_q90"]
    assert all(q.bits <= o[k].bits for k in splits) and all(o[k].phi + o[k].rho > max(o[j].rho for j in jpegs) for k in splits)
    t_min = max(max(0.0, q.server_ms - o[k].server_ms) / (o[k].phi + o[k].rho - q.rho) for k in splits)
    k4 = o["k4_int8_zstd"]
    assert shown_as(t_min, "GenDominanceTmin", "GenPropOneTmin")
    assert shown_as(k4.phi + k4.rho, "GenPhiRhoKFour") and shown_as(max(o[j].rho for j in jpegs), "GenRhoJpegMax")
    assert shown_as(100 * (k4.acc / o["jpeg_q90"].acc - 1), "GenAccBoundNinetyPct")
    assert shown_as(100 * (k4.acc / o["jpeg_q95"].acc - 1), "GenAccBoundNinetyFivePct")
    return "PROVED", (f"e_k + s_k - e_q - s_q = a (t - (s_q - s_k)/a) with a = phi_k + rho_k - rho_q > 0; measured: t_min = {t_min:.1f} ms, "
                      f"phi+rho(k4) = {k4.phi + k4.rho:.3f}, "
                      f"max rho_JPEG = {max(o[j].rho for j in jpegs):.3f}; every split payload > Q90 JPEG")


@check(SEC_M)
def m_breakeven_symbolic():
    """Prop. 3 rearrangements: b/B < t <=> B > b/t;  t(phi+rho) < t <=> phi+rho < 1;  beta = Bt/b > 1 <=> B > b/t;  exact threshold."""
    B, b, t, F, n = sp.symbols("B b t F n", positive=True)   # n = ceil(F t_full) - 1 >= 1
    y = sp.Symbol("y", real=True)
    # each rearrangement is  lhs - rhs = (positive factor) * (normalised form), so the order is kept
    assert sp.simplify((t - b / B) - (t / B) * (B - b / t)) == 0          # b/B < t     <=> B > b/t
    assert sp.simplify((B * t / b - 1) - (t / b) * (B - b / t)) == 0      # Bt/b > 1    <=> B > b/t   (beta)
    assert sp.expand((t - t * y) - t * (1 - y)) == 0                      # t y < t     <=> y < 1     (y = phi + rho)
    assert sp.simplify((n - F * b / B) - (n / B) * (B - F * b / n)) == 0  # F b/B <= n  <=> B >= F b/n
    return "PROVED", "four rearrangements, each a positive multiple of the stated form (n = ceil(F t_full) - 1)"


@check(SEC_M)
def m_breakeven_exhaustive():
    """Prop. 3 (ceil step): 'split beats onboard' <=> the exact tick condition; the tick-free B_be is necessary, not sufficient."""
    n, wins, example = 0, 0, None
    while n < 60_000:
        F = Fraction(RNG.choice([10, 15, 24, 30, 60]), 1000)
        t = frac(5, 400)
        D = t + frac(0, 500)                                   # onboard on time: t_full <= D
        e = t * frac(0, 1.3)
        b, B, d, s = frac(1, 3000), frac(0.1, 300), frac(1, 100), frac(0, 50)
        _, b_star, f_k = _closed_form(e, b, s, B, d, D, F)
        r_on, r_k = tick_rate(F, t), (f_k if B >= b_star else 0)
        beats = r_k > r_on
        ticks = math.ceil(F * t)
        exact = B >= b_star and ticks >= 2 and e <= (ticks - 1) / F and B >= F * b / (ticks - 1)
        necessary = B >= b_star and B > b / t and e < t
        assert beats == exact and (not beats or necessary), (F, t, D, e, b, B, d, s)
        if necessary and not beats and example is None and ticks >= 2 and e <= (ticks - 1) / F:
            example = (F * 1000, t, e, B, max(b / t, b_star), F * b / (ticks - 1))
        wins += beats
        n += 1
    assert example is not None
    F, t, e, B, be, exact_thr = example
    return "VERIFIED", (f"{n:,} instances ({wins:,} where the split wins): equivalence holds everywhere. Example of B > B_be without a win: "
                        f"F = {F} FPS, t_full = {float(t):.2f} ms, e_k = {float(e):.2f} ms, B = {float(B):.2f} > B_be = {float(be):.2f} "
                        f"but below the tick threshold {float(exact_thr):.2f} Mbit/s")


@check(SEC_M)
def m_breakeven_code():
    """analytic.break_even_mbps implements B_be = max(b_k/t_full, B*_k), and oo when phi_k + rho_k >= 1."""
    from simulation.analytic import Option, System, break_even_mbps, required_mbps
    from simulation.system_model import host_full_ms, load_offload_configs

    cfg = load_offload_configs()
    h = host_full_ms(cfg)
    n = 0
    for c in cfg.values():
        if c.kind == "onboard":
            continue
        o = Option.from_config(c, h)
        for tf in (10.0, 40.0, 180.0, 360.0, 900.0):
            s = System(tf)
            expect = INF if o.phi + o.rho >= 1 else max(o.bits / 1e3 / tf, required_mbps(o, s))
            got = break_even_mbps(o, s)
            assert got == expect or math.isclose(got, expect, rel_tol=1e-12)
            n += 1
    return "VERIFIED", f"{n} (configuration, t_full) pairs"


@check(SEC_M)
def m_swarm():
    """Prop. 4: water-filling gives each UAV >= min(B_i, C/N); N <= C/B* <=> C/N >= B*. 'At least C/N' alone is false."""
    from simulation.analytic import Option, System, required_mbps, swarm_capacity
    from simulation.stream_sim import _waterfill

    N, C, Bs = sp.symbols("N C B_star", positive=True)
    assert sp.simplify((C / N - Bs) - (Bs / N) * (C / Bs - N)) == 0     # C/N >= B* <=> N <= C/B*  (B*/N > 0)
    n = 0
    for _ in range(20_000):
        k = RNG.randint(1, 30)
        dem = {i: RNG.choice([0.0, RNG.uniform(0, 5), RNG.uniform(0, 200)]) for i in range(k)}
        cap = RNG.uniform(1, 400)
        alloc = _waterfill(dem, cap)
        assert all(alloc[i] >= min(dem[i], cap / k) - 1e-9 and alloc[i] <= dem[i] + 1e-9 for i in dem)
        assert math.isclose(sum(alloc.values()), min(cap, sum(dem.values())), rel_tol=1e-9, abs_tol=1e-9)
        n += 1
    counter = _waterfill({0: 1.0, 1: 50.0, 2: 50.0}, 60.0)
    assert counter[0] < 60.0 / 3
    o = Option("k", "split", 0.2, 0.1, 2.5e6, 10.0, 0.44)
    s = System(180.0)
    assert math.isclose(swarm_capacity(o, s, 100.0), 100.0 / required_mbps(o, s))
    return "PROVED", (f"C/N - B* = (B*/N)(C/B* - N); _waterfill on {n:,} random cells: min(B_i, C/N) <= share <= B_i and work-conserving; "
                      f"counterexample to 'at least C/N': demands (1, 50, 50), C = 60 -> first UAV gets {counter[0]:g} < 20")


@check(SEC_M)
def m_endurance_symbolic():
    """Prop. 5: idle floor <= P_perc <= floor + Delta, and the relative endurance difference <= Delta/H in either normalisation."""
    pb, pt, u, v, uu, vv = sp.symbols("Pb Pt u v uu vv", nonnegative=True)    # Pb = P_busy - P_idle, Pt = P_tx - P_rx
    inc = pb * u + pt * v                                                       # u, v in [0, 1] busy fractions
    assert nonneg(inc, [pb, pt, u, v])
    assert nonneg((pb + pt) - inc.subs({u: 1 - uu, v: 1 - vv}), [pb, pt, uu, vv])
    K, H = sp.symbols("K H", positive=True)
    x1, g, w = sp.symbols("x1 g w", nonnegative=True)                          # x2 = x1 + g, Delta = x2 + w
    e1, e2, delta = K / (H + x1), K / (H + x1 + g), x1 + g + w
    assert nonneg(delta / H - (e1 - e2) / e1, [K, H, x1, g, w])
    assert nonneg(delta / H - (e1 - e2) / e2, [K, H, x1, g, w])
    wh, p = sp.symbols("W_bat P", positive=True)
    assert sp.simplify((3600 * wh / p) / 60 - 60 * wh / p) == 0               # seconds -> minutes
    return "PROVED", "both bounds on P_perc and both normalisations of the spread (numerators are sums of non-negative terms)"


@check(SEC_M)
def m_endurance_data():
    """Prop. 5 in the results: perception power within the bound, endurance formula, \\PerceptionPower*/\\Endurance*, Monte Carlo spread."""
    from simulation.analytic import endurance_spread_bound
    from simulation.system_model import EdgeHardware, PlatformModel

    hw, plat = EdgeHardware("d", 180.0, 12.0), PlatformModel()
    lo, hi = hw.p_idle_w + hw.p_rx_idle_w, hw.p_idle_w + hw.p_rx_idle_w + (hw.p_compute_w - hw.p_idle_w) + (hw.p_tx_w - hw.p_rx_idle_w)
    single = rows("system_single_uav.csv")
    for r in single:
        pw = float(r["perception_power_w"])
        assert lo - 1e-9 <= pw <= hi + 1e-9, (r["profile"], r["strategy"], pw)
        assert math.isclose(float(r["endurance_min"]), plat.endurance_min(pw), rel_tol=1e-3)
    at180 = [r for r in single if float(r["t_full_ms"]) == 180.0]
    pw = [float(r["perception_power_w"]) for r in at180]
    en = [float(r["endurance_min"]) for r in at180]
    for value, name in ((min(pw), "PerceptionPowerMinW"), (max(pw), "PerceptionPowerMaxW"), (min(en), "EnduranceMin"), (max(en), "EnduranceMax")):
        assert shown_as(value, name), (name, value)
    for _ in range(2000):
        a = [RNG.uniform(0.5, 40) for _ in range(6)]
        assert math.isclose(endurance_spread_bound(*a), ((a[0] - a[1]) + (a[2] - a[3])) / (a[4] + a[5] + a[1] + a[3]))
    mc = rows("generalization/scenarios.csv")
    assert all(float(r["endurance_spread"]) <= float(r["endurance_bound"]) + 1e-9 for r in mc)
    return "VERIFIED", (f"{len(single)} single-UAV rows in [{lo:g}, {hi:g}] W; {len(mc):,} Monte Carlo scenarios within the bound; "
                        f"power {min(pw):.1f}-{max(pw):.1f} W, endurance {min(en):.1f}-{max(en):.1f} min")


@check(SEC_M)
def m_relay_energy():
    """Energy is the busy-time-weighted increment: the modem is never charged for longer than the run, even when relaying."""
    from simulation.stream_sim import SimParams, StreamSimulator
    from simulation.system_model import EdgeHardware, load_offload_configs, make_hardware

    hw = make_hardware(180.0)
    sim = StreamSimulator(SimParams(hw, load_offload_configs(), mode="k4_int8_zstd", profile="vehicular_fading", n_uavs=10,
                                    duration_s=30.0, seed=0, cell_capacity_mbps=100.0, relay=True))
    sim.run()
    busy = max(u.energy.tx_j / (hw.p_tx_w - hw.p_rx_idle_w) / 30.0 for u in sim.uavs)
    assert busy <= 1.0 + 1e-9, f"modem charged for {100 * busy:.1f} % of the run: own and relayed frames counted twice"
    d = EdgeHardware("d", 180.0, 12.0)
    ceiling = d.p_idle_w + d.p_rx_idle_w + (d.p_compute_w - d.p_idle_w) + (d.p_tx_w - d.p_rx_idle_w) + d.p_a2a_tx_w
    relay_rows = [r for r in rows("system_swarm.csv") if r["relay"] == "True"]
    worst = max(float(r["perception_power_w"]) for r in relay_rows)
    assert worst <= ceiling + 1e-9, (worst, ceiling)
    return "VERIFIED", (f"modem busy at most {100 * busy:.1f} % of a 10-UAV relay run; the {len(relay_rows)} relay rows of "
                        f"system_swarm.csv stay below Prop. 5's ceiling with relaying ({worst:.2f} <= {ceiling:.1f} W)")


@check(SEC_M)
def m_hover():
    """Hover power: T v_i with v_i = sqrt(T/(2 rho A)) equals T^(3/2)/sqrt(2 rho A); with the stated values it is \\HoverW W."""
    from simulation.system_model import hover_power_w

    T, rho, A, fom, eta = sp.symbols("T rho_air A FoM eta", positive=True)
    ideal = T * sp.sqrt(T / (2 * rho * A))
    assert sp.simplify(ideal - T ** sp.Rational(3, 2) / sp.sqrt(2 * rho * A)) == 0
    p = {k: v.default for k, v in inspect.signature(hover_power_w).parameters.items()}
    g = sp.Rational(981, 100)
    assert "9.81" in inspect.getsource(hover_power_w)
    value = sp.N((sp.nsimplify(p["mass_kg"]) * g) ** sp.Rational(3, 2) / sp.sqrt(2 * sp.nsimplify(p["rho"]) * sp.nsimplify(p["disk_area_m2"]))
                 / (sp.nsimplify(p["figure_of_merit"]) * sp.nsimplify(p["motor_esc_eff"])), 12)
    assert math.isclose(float(value), hover_power_w(), rel_tol=1e-12) and shown_as(float(value), "HoverW")
    return "PROVED", (f"m = {p['mass_kg']} kg, A = {p['disk_area_m2']} m^2, rho_air = {p['rho']} kg/m^3, FoM = {p['figure_of_merit']}, "
                      f"eta = {p['motor_esc_eff']}, g = 9.81 m/s^2 -> {float(value):.2f} W")


@check(SEC_M)
def m_crossover_bandwidths():
    """Sec. 5.1: the goodputs needed to meet the deadline (\\BwReq*) are B*_c of the policy's model at t_full = 40 and 180 ms."""
    from simulation.system_model import AdaptivePolicy, load_offload_configs, make_hardware

    cfgs = load_offload_configs()
    out = []
    for tf, tname in ((40.0, "TForty"), (180.0, "TOneEighty")):
        pol = AdaptivePolicy(list(cfgs.values()), make_hardware(tf))
        for name, mname in (("jpeg_q90", "JPEG"), ("k4_int8", "KFour"), ("k4_int8_zstd", "KFourZstd")):
            c = cfgs[name]
            b = Fraction(c.payload_bytes) * 8 / 1000
            slack = Fraction(pol.deadline_ms) - Fraction(pol.hw.onboard_ms(c)) - Fraction(pol.delay_ms) - Fraction(c.cloud_ms)
            assert slack > 0
            assert shown_as(float(b / slack), f"BwReq{mname}{tname}")
            out.append(f"{name}@{tf:g}: {float(b / slack):.1f}")
    return "VERIFIED", "; ".join(out) + " Mbit/s"


# ============================================================================ parameter map
SEC_H = "Code <-> paper: every parameter the paper states"


@check(SEC_H)
def h_parameters():
    """Constants stated in the text or generated tables equal the code defaults."""
    from protocol.packet import DESCRIPTOR_SIZE, PRIMARY_HEADER_SIZE
    from simulation.stream_sim import SimParams, a2a_snr_db
    from simulation.system_model import (CAMERA_FPS, DEADLINE_MS, HARDWARE_SCENARIOS_MS, AdaptivePolicy, PolicyWeights,
                                         hover_power_w)
    from simulation.trace_generator import PROFILES, SLOT_MS, _rician_slot_gain_db, generate_trace

    default = lambda cls, f: cls.__dataclass_fields__[f].default                                  # noqa: E731
    arg = lambda fn, p: inspect.signature(fn).parameters[p].default                              # noqa: E731
    doc = TEX + GENERATED
    literal = [  # (what, code value, expected, text that must appear in main.tex or a generated table)
        ("deadline D (ms)", DEADLINE_MS, 300.0, r"300~ms"), ("camera rate F (FPS)", CAMERA_FPS, 30.0, r"F=30\$~FPS"),
        ("profile base delays (ms)", (min(p.base_delay_ms for p in PROFILES.values()), max(p.base_delay_ms for p in PROFILES.values())),
         (10.0, 20.0), r"base of 10--20~ms"),
        ("slot (ms)", SLOT_MS, 10.0, r"10~ms"), ("carrier (Hz)", default(SimParams, "carrier_hz"), 3.5e9, r"3\.5~GHz"),
        ("trace carrier default (Hz)", arg(generate_trace, "fc_hz"), 3.5e9, r"3\.5~GHz"),
        ("fading simulation rate (Hz)", arg(_rician_slot_gain_db, "sub_hz"), 1000.0, r"1~kHz"),
        ("blackout lengths (s)", [e - b for b, e in PROFILES["blackout"].blackouts_s], [3.0, 3.0], r"two 3~s deep fades"),
        ("t_full sweep (ms)", HARDWARE_SCENARIOS_MS, [40.0, 90.0, 180.0, 360.0], r"\\\{40,90,180,360\\\}"),
        ("A2A carrier (GHz)", arg(a2a_snr_db, "f_ghz"), 5.8, r"5\.8~GHz"),
        ("A2A tx power (dBm)", arg(a2a_snr_db, "tx_dbm"), 20.0, r"20 dBm"),
        ("A2A noise floor (dBm)", arg(a2a_snr_db, "noise_dbm"), -95.0, r"\$-\$95 dBm"),
        ("A2A path-loss exponent", arg(a2a_snr_db, "n_exp"), 2.2, r"dBm, 2\.2"),
        ("hover mass (kg)", arg(hover_power_w, "mass_kg"), 1.2, r"m=1\.2\$~kg"),
        ("rotor disk area (m^2)", arg(hover_power_w, "disk_area_m2"), 0.2, r"A_\{\\mathrm\{disk\}\}=0\.2\$~m\$\^2\$"),
        ("air density (kg/m^3)", arg(hover_power_w, "rho"), 1.225, r"\\rho_\{\\mathrm\{air\}\}=1\.225\$~kg/m\$\^3\$"),
        ("gravity (m/s^2)", float(re.search(r"mass_kg \* ([\d.]+)", inspect.getsource(hover_power_w)).group(1)), 9.81, r"g=9\.81\$"),
        ("figure of merit", arg(hover_power_w, "figure_of_merit"), 0.7, r"\\mathrm\{FoM\}=0\.7\$"),
        ("motor/ESC efficiency", arg(hover_power_w, "motor_esc_eff"), 0.75, r"\\eta=0\.75\$"),
        ("header / descriptor (bytes)", (PRIMARY_HEADER_SIZE, DESCRIPTOR_SIZE), (16, 16), r"16-byte header.*16-byte descriptor"),
    ]
    for what, code, expect, pattern in literal:
        assert code == expect, f"{what}: code {code} != paper {expect}"
        assert re.search(pattern, doc, flags=re.S), f"{what}: paper does not state {pattern!r}"
    macros = [  # (what, code value, macro)
        ("policy delay d (ms)", default(SimParams, "policy_delay_ms"), "PolicyDelayMs"),
        ("EWMA time constant (ms)", default(SimParams, "est_tau_ms"), "PolicyTauMs"),
        ("sigma floor (x mu)", PolicyWeights().min_rel_std, "PolicySigmaFloor"),
        ("energy weight lambda_E", PolicyWeights().energy_per_frame, "PolicyEnergyWeight"),
        ("hysteresis (%)", 100 * default(SimParams, "hysteresis"), "PolicyHysteresisPct"),
        ("relay trigger (Mbit/s)", default(SimParams, "relay_threshold_mbps"), "RelayThresholdMbps"),
        ("relay neighbour minimum (Mbit/s)", default(SimParams, "relay_neighbor_min_mbps"), "RelayNeighbourMinMbps"),
        ("formation spacing (m)", default(SimParams, "spacing_m"), "AtwoASpacingM"),
    ]
    for what, code, name in macros:
        assert math.isclose(code, macro_num(name)), f"{what}: code {code} != \\{name} = {macro(name)}"
        assert f"\\{name}" in TEX, f"\\{name} is generated but not used in the paper"
    sig = inspect.signature(AdaptivePolicy.__init__).parameters     # the switchboard's defaults must equal the simulator's
    assert sig["hysteresis"].default == default(SimParams, "hysteresis")
    assert sig["one_way_delay_ms"].default == default(SimParams, "policy_delay_ms")
    return "VERIFIED", f"{len(literal)} stated constants and {len(macros)} generated macros equal the code; policy defaults consistent"


@check(SEC_H)
def h_monte_carlo():
    """Monte Carlo: sampled ranges equal Table V, swarm ranges, 60 s traces, seed 0, airframe scaling and assumed delay as stated."""
    import evaluation.gen_scenarios as gs
    from simulation.system_model import hover_power_w

    src = (REPO / "evaluation" / "make_generalization.py").read_text(encoding="utf-8")
    space = ast.literal_eval(re.search(r"^SPACE = (\[.*?^\])", src, flags=re.M | re.S).group(1))   # the rows of Table V
    rng = np.random.default_rng(3)
    draws = [gs.sample(rng, swarm=True) for _ in range(20_000)]
    for col, _, text in space:
        vals = np.array([d[col] for d in draws], dtype=float)
        text = text.replace("$-$", "-").replace("$\\times$", "")
        if "--" in text:
            lo, hi = (float(re.search(r"-?\d+(?:\.\d+)?", part).group()) for part in text.split("--")[:2])
            assert lo - 1e-9 <= vals.min() and vals.max() <= hi + 1e-9, (col, text, vals.min(), vals.max())
            assert vals.max() - vals.min() > 0.9 * (hi - lo), (col, "range not covered")
        else:
            allowed = {float(x) for x in re.findall(r"\d+", text)}
            assert set(vals.tolist()) == allowed, (col, text)
    n_uav = [d["n_uavs"] for d in draws]
    cell = [d["cell_capacity_mbps"] for d in draws]
    assert min(n_uav) == 2 and max(n_uav) == 30 and 20 <= min(cell) and max(cell) <= 400
    assert re.search(r"2--30 UAVs and a 20--400~Mbit/s cell", TEX)
    assert gs.DURATION_S == 60.0 and re.search(r"60~s traces", TEX)
    assert re.search(r'add_argument\("--seed", type=int, default=0\)', inspect.getsource(gs)) and "Monte Carlo draws use seed 0" in TEX
    plat = gs.platform_of({"mass_kg": 2.0, "avionics_w": 10.0})
    assert math.isclose(plat.battery_wh, 75.0) and math.isclose(plat.hover_w, hover_power_w(mass_kg=2.0, disk_area_m2=0.3))
    assert re.search(r"37\.5\\,m", TEX) and re.search(r"0\.15\\,m", TEX), "airframe scaling not stated"
    assert 'policy_delay_ms=p["base_delay_ms"] + 5.0' in inspect.getsource(gs.run_scenario) and "base delay plus 5~ms" in TEX
    return "VERIFIED", f"{len(space)} variables of Table V over 20,000 draws; N in [2, 30], C in [20, 400] Mbit/s; scaling and delay as stated"


@check(SEC_H)
def h_protocols():
    """Accuracy protocol (conf 0.001, IoU 0.7, 101-point AP, batch 1, seed 0), bootstrap seeds, and timing NMS settings."""
    import ultralytics.engine.validator as validator
    import ultralytics.utils.metrics as metrics
    from ultralytics.cfg import DEFAULT_CFG

    assert DEFAULT_CFG.iou == 0.7 and DEFAULT_CFG.conf is None
    assert re.search(r"self\.args\.conf = 0\.01 if .* else 0\.001", inspect.getsource(validator))
    assert "np.linspace(0, 1, 101)" in inspect.getsource(metrics.compute_ap)
    ev = (REPO / "evaluation" / "detection_eval.py").read_text(encoding="utf-8")
    assert "batch=1" in ev and "seed=0" in ev and "seed * 100003 + r" in ev
    timing = (REPO / "evaluation" / "benchmark_split_pareto.py").read_text(encoding="utf-8")
    assert "conf_thres=0.25, iou_thres=0.45" in timing
    for text in ("confidence 0.001, IoU 0.7, 101-point interpolation", "batch size 1", "validation uses seed 0",
                 "100003\\,s+r", "confidence 0.25, IoU 0.45"):
        assert text in TEX, f"paper does not state {text!r}"
    return "VERIFIED", "Ultralytics defaults (installed version), detection_eval.py and benchmark_split_pareto.py match the text"


# ============================================================================ notation
SEC_N = "Notation, stated conditions, and proposition numbering"
RETIRED = [  # (pattern, what replaced it)
    (r"T_d\b", "deadline is $D$"), (r"t\^\{edge\}", "onboard time is $e_c$"), (r"t\^\{srv\}", "server time is $s_c$"),
    (r"D_c\b", "payload is $b_c$ ($D$ is the deadline)"), (r"F_k\b", "FLOP fraction is $\\phi_k$ ($F$ is the camera rate)"),
    (r"T_\{cam\}", "camera period is $1/F$"), (r"\\mathrm\{mAP\}_\{FP32\}|\\mathrm\{mAP\}_c", "accuracy is $A_c/A_{ref}$"),
    (r"\$P_h\$", "hover power is $P_{hover}$"), (r"\$P_c\$|P_c-P_0|P_0\+P_\{rx\}|\$P_0\$", "compute power is $P_{busy}$/$P_{idle}$"),
    (r"\\rho\$\(|\|\\rho\||\(\$\\rho=\\Gen", "Spearman correlation is $r_s$ ($\\rho_c$ is onboard work)"),
    (r"latency \$T\$|b_k/T\b|BT/b_c|T\(\\phi|\(\$T\\le D|T\\le\\Gen", "onboard full-model latency is $t_{full}$"),
    (r"Shadowing \$\\sigma\$", "channel shadowing is $\\sigma_{sh}$"), (r"\(\$\\sigma=\\AtwoAShadowDb", "A2A shadowing is $\\sigma_{a2a}$"),
    (r"& \$\\sigma\$ &", "A2A shadowing is $\\sigma_{a2a}$"),
]
STATED = [  # (pattern, condition the code enforces and the paper must state)
    (r"\$S=1\$ if \$\\max\|X\|<10\^\{-6\}\$", "degenerate scale (no division by zero)"),
    (r"127/\(1-2\^\{-23\}\)<127\.5", "clamp inactive with the float32 scale"),
    (r"B\^\\ast_c=\\infty\$ if \$D\\le e_c\+d\+s_c", "B* = oo without positive slack"),
    (r"\$p_c=0\$", "p_c = 0 when the deadline cannot be met"),
    (r"p_c=\\mathbf\{1\}\[t_\{full\}\\le D\]", "onboard p_c"),
    (r"\\lambda_E=\\PolicyEnergyWeight~\\mathrm\{s\^\{-1\}J\^\{-1\}\}", "units of the energy weight"),
    (r"\$A_\{\\mathrm\{ref\}\}\$ that of the unsplit FP32 model", "definition of A_ref"),
    (r"\\min\(B_i,\s*C/N\)", "water-filling share in Prop. 4"),
    (r"\\lceil F t_\{full\}\\rceil-1", "exact camera-tick threshold in Prop. 3"),
    (r"inverse proportion to their payloads", "direction of the swarm-size ratio"),
    (r"capped at 1", "PER is a probability"),
    (r"older than the \d+~ms deadline", "when transfers are dropped"),
    (r"Under onboard inference the result is available onboard, after \$t_\{full\}\$", "on-time definition of onboard frames"),
    (r"\\PolicyTauMs.*\\PolicySigmaFloor", "EWMA time constant and sigma floor"),
    (r"d=\\PolicyDelayMs\$~ms the one-way delay the policy assumes", "the policy's d"),
    (r"10\(1-\\mathrm\{SE\}/\\mathrm\{SE\}_\{max\}\)\$~ms plus exponential jitter with mean 2~ms", "delay model"),
    (r"residual post-HARQ loss of \$0\.1\\,e\^\{-\(\\gamma-\\gamma_\{min\}\)/3\}\$", "loss model"),
    (r"P_\{\\mathrm\{perc\}\} = P_\{\\mathrm\{idle\}\}\+P_\{rx\}\s*&?\+", "busy-time power model used by Prop. 5"),
    (r"10\\log_\{10\}\(\\\|X\\\|_2\^2/\\\|X-\\hat X\\\|_2\^2\)", "SQNR definition"),
]


@check(SEC_N)
def n_retired_symbols():
    """No symbol is used for two quantities, and no quantity has two symbols (paper text, generated tables, figure labels)."""
    labels = "\n".join((REPO / "evaluation" / f).read_text(encoding="utf-8") for f in ("make_generalization.py", "make_figures.py", "make_tables.py"))
    hits = []
    for pattern, why in RETIRED:
        for where, text in (("main.tex", TEX), ("generated_tables", GENERATED), ("figure/table generators", labels)):
            found = re.findall(pattern, text)
            if found:
                hits.append(f"{found[0]!r} in {where} ({why})")
    assert not hits, "; ".join(hits)
    return "VERIFIED", f"none of {len(RETIRED)} retired notations remains"


@check(SEC_N)
def n_stated_conditions():
    """The paper states every guard and definition that the code enforces (division by zero, domains, probability caps)."""
    missing = [why for pattern, why in STATED if not re.search(pattern, TEX, flags=re.S)]
    assert not missing, "not stated: " + "; ".join(missing)
    return "VERIFIED", f"all {len(STATED)} conditions are stated"


@check(SEC_N)
def n_proposition_numbers():
    """Code comments cite the propositions by the numbers they have in the compiled paper."""
    aux = PAPER / "main.aux"
    if not aux.exists():
        raise AssertionError("paper/main.aux missing: build the paper first")
    labels = dict(re.findall(r"\\newlabel\{prop:(\w+)\}\{\{(\d+)\}", aux.read_text(encoding="utf-8")))
    expect = {"int8": "INT8 error bound", "dominance": "offload dominance", "breakeven": "split versus onboard",
              "swarm": "swarm capacity", "energy": "endurance"}
    assert set(labels) == set(expect), labels
    analytic = (REPO / "simulation" / "analytic.py").read_text(encoding="utf-8")
    for key in ("dominance", "breakeven", "swarm", "energy"):
        assert f"Proposition {labels[key]} ({expect[key]})" in analytic, f"analytic.py does not cite Proposition {labels[key]} ({expect[key]})"
    quant = (REPO / "evaluation" / "benchmark_quant_modes.py").read_text(encoding="utf-8")
    assert f"Proposition {labels['int8']}" in quant and "Theorem" not in quant
    stale = []
    for path in list((REPO / "evaluation").glob("*.py")) + list((REPO / "tests").glob("*.py")) + [REPO / "simulation" / "analytic.py"]:
        for m in re.finditer(r"Proposition (\d) \(([A-Za-z0-9 ]+)\)", path.read_text(encoding="utf-8")):
            num, name = m.groups()
            key = next((k for k, v in expect.items() if v.lower() == name.lower()), None)
            if key is None or labels[key] != num:
                stale.append(f"{path.name}: {m.group(0)}")
    assert not stale, "; ".join(stale)
    return "VERIFIED", ", ".join(f"{expect[k]} = {labels[k]}" for k in expect)


# ============================================================================ main
def main() -> int:
    counts = {}
    current = None
    t_start = time.perf_counter()
    for section, fn in CHECKS:
        t0 = time.perf_counter()
        try:
            status, detail = fn()
        except Exception as e:  # noqa: BLE001 -- report every failure and keep going
            status, detail = "FAIL", f"{type(e).__name__}: {e}"
        counts[status] = counts.get(status, 0) + 1
        if section != current:
            print(f"\n{section}")
            current = section
        title = (inspect.getdoc(fn) or fn.__name__).splitlines()[0]
        print(f"  [{status:<8}] {title}  ({time.perf_counter() - t0:.1f} s)")
        print(f"             {detail}")
    summary = ", ".join(f"{counts[k]} {k}" for k in ("PROVED", "VERIFIED", "FAIL") if k in counts)
    print(f"\n{len(CHECKS)} checks in {time.perf_counter() - t_start:.0f} s: {summary}")
    return 1 if counts.get("FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
