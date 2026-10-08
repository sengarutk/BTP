# Staleness-aware multi-tier scheduling: formal model

Implemented in `validation/hardware/adaptive2.py` (`--objective stream`).

## System

- **Camera.** It produces frames at rate f (30 fps), at times t_k = k / f.
- **Servers.** The set is S = {onboard, edge, ground}. A server s holds at most one frame at a time.
  Processing a frame with variant v on s keeps s busy for B_s(v) and delivers the result after latency
  L_s(v):
  - **Onboard:** B = L = the measured inference time, rounded up to whole frame periods.
  - **A path:** L = encoding time + transfer time b_v / R_s + remote inference time + RTT. The path
    takes the next frame once the bytes have left the radio, so B = max(transfer time + RTT, 1/f).
- **Variants.** Each variant v (model, input size, JPEG quality) has payload b_v and accuracy a_v,
  measured as AP on VisDrone-DET val, which is disjoint from the test videos.
- **Path goodput.** R_s is unknown. It is modelled as R_s ~ N(μ_s, σ_s²) with online estimates
  (EWMA of per-frame goodput net of RTT, stall detection, probing of idle paths).

## What the UAV holds and how it is scored

At every instant t the UAV holds one delivered result h(t). Its value is a_{v(h)} · ρ(t − c(h)), where
c(h) is the capture time of the frame and ρ is the staleness decay.
- **Decay.** ρ(Δ) = AP(detections from frame t − Δ scored on frame t) / AP(Δ = 0), measured on
  VisDrone-VID train: ρ(33 ms) = 0.82, ρ(100 ms) = 0.42, ρ(267 ms) = 0.07.
- **Holding rule.** On the UAV, h(t) = argmax over delivered results of a_v · ρ(t − c).
- **Task metric.** Streaming AP is the AP of h(t) against the ground truth at t, pooled over all t. The
  time average of a_{v(h)} · ρ(age) is a first-order surrogate of it.

## Dispatch rule

At each frame time, for every idle server s and variant v, the controller computes

    V_s(v) = a_v / a_ref · P(L_s(v) ≤ L_max) · (1/T) ∫_0^T ρ(L_s(v) + τ) dτ,   T = B_s(v) / n_active

- **Holding window T.** A result from s is replaced roughly when the next result arrives. With
  n_active servers interleaving, that happens about every B_s(v) / n_active. The integral is the
  average decayed value of the result over the time it is held.
- **Variant choice.** Each idle server proposes v*_s = argmax_v V_s(v), and the frame goes to the idle
  server with the largest V_s(v*_s) > 0.
- **Uncertainty.** P(L ≤ L_max) is computed from the Gaussian goodput model (L_max = 1 s). A larger
  σ_s lowers the value of large payloads on uncertain links.

## Why this is the right greedy rule

Under the surrogate objective, the long-run value is the time average of a_{v(h(t))} · ρ(age(t)).

- **The renewal-reward view.** Between two consecutive deliveries, the value accrued is the decayed
  accuracy of the held result over the inter-delivery interval. With a single server, each cycle
  lasts B_s(v) and the held result's age runs from L_s(v) to L_s(v) + B_s(v). So the long-run average
  is a_v · (1/B) ∫_0^B ρ(L + τ) dτ, which is V_s(v) with n_active = 1. Choosing v*_s maximises the
  long-run average for that server: the per-server rule is optimal in that case.
- **Several servers.** Deliveries interleave and the holding window shrinks to about B/n_active. The
  rule then evaluates each frame's contribution to the interleaved stream; it is a greedy index policy
  and not provably optimal.
- **Testing the approximation.** The live campaign compares it with the ablations: v2's rate
  objective with COCO accuracy, the same with aerial accuracy, and single-path adaptation.

## Inputs and leakage

| Input | Source | Disjoint from the test videos? |
|---|---|---|
| a_v | VisDrone-DET val, 548 still images | Yes |
| ρ(Δ) | VisDrone-VID train, 8 sequences picked by a fixed rule (every 7th sequence) | Yes |
| Device times and payload priors | COCO frames on the devices, then learned online | Yes |

Test data: VisDrone-VID val (7 sequences), used only for evaluation.
