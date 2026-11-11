# Novelty and strengthening roadmap for paper 1 and paper 2 (11 Nov 2026)

Based on everything committed up to 9126c5c5 and a literature survey of the closest work (sources at the end).
Status labels: **have** = done and in the drafts; **N** = adds novelty; **S** = strengthens what we claim;
effort in working days; **L** = laptop only, **B** = needs the boards (or a purchase).

## 0. Bottom line

- Neither paper has a new *algorithm*. The novelty lies in results that are proven, measured and stress-tested, and in
  design rules. That is the normal currency of MobiSys/MobiCom measurement-and-systems papers, but there the bar is
  realism (real deployment, flight) and one clear insight with a mechanism that exploits it.
- Paper 1 already has one crisp, defensible insight: no coder can raise the break-even goodput. Its gaps are breadth
  (one detector, one dataset), the strength of the image baseline (we compare against per-frame JPEG, while a drone
  streams video), and the lack of any hardware check of the rule.
- Paper 2 has a new measured thesis (heat as a streaming-accuracy cost), but its theory is a standard application, it
  overclaims in the abstract, and it is table-top. The most dangerous reviewer question, from the survey: on a flying
  drone, prop wash is the board's main cooling, so does the heat cost survive in flight?
- Strategic fact: **MobiSys 2027 abstract 27 Nov, paper 4 Dec 2026** (12 pages ACM). INFOCOM 2027 (July) and
  MobiCom 2027 summer (Sept) have passed. SenSys 2027 round 2 (5 Nov) has passed. The MobiCom 2027 winter cycle is
  TBD (typically Feb–Mar). IEEE TMC is rolling.

## 1. Novelty we already have (verified)

| # | Paper | Contribution | Closest prior work | Why ours differs |
|---|---|---|---|---|
| H1 | 1 | Closed-form break-even goodput B_be of any split against a whole image-codec family, in which the code's payload does not enter | Neurosurgeon (per-layer latency choice), Matsubara & Levorato 2020 (crossover ~8 Mbit/s for one setup), Bayes-Split-Edge, ENACHI (per-setup optimisation) | A proved bound for all codes of a given accuracy and onboard time, not a per-setup optimum |
| H2 | 1 | The bound stress-tested against ever-stronger splits: 18-quality JPEG, jointly trained codes, a JPEG-tuned detector, entropy-coded codes 52–73 % smaller (same B_be), a fading simulator (constant rule fails on fast devices; fading version 0 exceptions) | SC2 benchmark, Entropic Student, FrankenSplit, BottleFit, Yuan et al. 2022 (rate–accuracy only) | Prior work wins on rate–accuracy; we show the system-level win stays bounded however good the rate is |
| H3 | 1 | Post-hoc splits dominated (proof plus 19 detectors) | Matsubara & Levorato 2020 (naive splits do not cut latency) | Proof and breadth |
| H4 | 2 | Heat measured as a streaming-AP cost (37–59 % of onboard sAP) inside a real three-tier offloading system | Pi 4 throttling study (throughput), Heat & Memory 2024 (FPS halves above 80 °C), Tan & Cao TMC 2024, Phoenix | Accuracy in a distributed scheduler, not FPS on one device |
| H5 | 2 | Priced controller with a sample-path bound checked on every logged update (376 hardware runs, 215 replay runs) | Lyapunov / drift-plus-penalty ("the de facto standard"), ENACHI, JCAB | The verification on real logs and the explicit hold and cap terms are uncommon; the theory itself is standard |
| H6 | 2 | The objective's decay curve must match the forecaster; the hold drives the heat; a hold capped at 78 °C (replay) | AccuMO (accuracy decay), LEAF | New, but small; the capped hold has only been tested in the replay |
| H7 | both | Predictions committed before runs; open benchmark with a bit-exact check | — | Rare in systems papers: a methodological selling point |

## 2. Paper 1: every addition worth considering

### 2a. What top reviewers will ask (from the literature)

1. "A drone sends **video**, not JPEG frames. Compare against H.264/H.265." (FCM/VCM, VVC baselines are standard in
   coding-for-machines work.)
2. "Compare against **learned image codecs** (ELIC, Cheng2020, JPEG AI): image coding for machines beats JPEG by a
   wide margin."
3. "What about the **MPEG FCM** standard (feature coding for machines)? It reports 75–85 % bitrate savings over
   remote inference."
4. "Only YOLOv8s on VisDrone": generality.
5. "The rule is checked in your own model and simulator; does it predict a **real** crossover?"
6. "Information theory says the split point does not change the optimal rate–distortion (indirect R-D,
   arXiv 2602.12866); what does your bound add?"
7. "Energy, not only accuracy rate."

### 2b. Additions, ranked

| ID | Addition | Type | Effort | Where | Why it matters |
|---|---|---|---|---|---|
| P1-1 | **Video-codec image family.** x264/x265 low-delay (zerolatency, ultrafast–medium), per-frame bytes and mAP on VisDrone-VID; the Pi 5 has **no hardware H.264 encoder** (libx264 on the CPU, 1080p30 real time per the Raspberry Pi white paper), while the Jetson has NVENC | N+S | 2 | L (bytes, accuracy, laptop CPU times); B (Pi encode time) | The proposition holds for any family with (e_q, b_q). Inter-frame coding cuts the image payload several-fold, so B_be likely falls further, while e_q (software encode on the Pi) binds through the onboard term. This answers question 1 and exercises both terms of the bound |
| P1-2 | **Corollary: the bound is coder-independent, up to the information-theoretic limit.** As b_k → 0 (any future coder, including the indirect R-D optimum), B_be is unchanged; only A_k and e_k move it | N (theory) | 0.5 | L | Answers question 6 directly. It positions the paper against the task-oriented-communication literature (Shao et al. JSAC 2022; indirect R-D 2026): their limits are about rate, ours says rate is not the system bottleneck |
| P1-3 | **Learned image codecs as the image family** (pretrained ELIC/Cheng2020 in an isolated venv; JPEG AI reference software if feasible): rate, mAP, and onboard encode time | N+S | 1.5 | L (+ Pi timing, B) | Better b_q but far larger e_q. A clean demonstration that the onboard condition e_q ≤ m_k decides, not rate. Answers question 2 |
| P1-4 | **Second detector and dataset**: YOLO11s or RT-DETR-R18 (transformer: different activation profile), and UAVDT or VisDrone-VID; learned, entropy and joint codes plus the bound | S | 2 | L | Answers question 4, the most common generality objection |
| P1-5 | **Predict-then-measure on the real link**: the Pi with the smallest code and JPEG; shape the Pi's link rate on the boards (tc on the boards only, removed afterwards); predict the crossover from B_be before measuring | S (big) | 0.5 board + 0.5 analysis | B | Turns the rule from model-checked into hardware-confirmed. Answers question 5 |
| P1-6 | **Energy break-even**: J per on-time accurate result using the measured Pi power (compute, encode, radio); an energy version of B_be | N | 1 | L | A second axis of the design rule (question 7). Cheap, because the energy constants are measured |
| P1-7 | **Pi 5 + Hailo-8 (AI HAT+, ~80 fps YOLOv8s INT8 by secondary benchmarks)**: a measured fast drone-class device where the camera rate binds, exactly where the constant rule failed in simulation | N+S | 1 + purchase | B | A real device in the regime the fading rule was built for |
| P1-8 | MPEG FCM / FCTM baseline on our cut | S | 2–3 (VTM is slow) | L | Answers question 3; can otherwise be handled by discussion and citation |
| P1-9 | ROI / accuracy-gradient image encoding (AccMPEG-style per-macroblock quality, or DDS) as the image family | S | 2 | L | Strengthens the image side further; useful but optional |
| P1-10 | Inter-frame feature coding for the split (residuals between frames, as in IFMDC) | S (fairness) | 1.5 | L | The fair counterpart of P1-1, so the comparison is video against video |
| P1-11 | Confidence intervals on B_be (bootstrap of the accuracies → interval on q* and B_be) | S | 0.5 | L | Statistical rigour on the headline number |
| P1-12 | Channel-adaptive split selection (dynamic split, Bakhtiarnia 2023) obeys the bound slot by slot | S | 0.5 | L | Pre-empts "a dynamic split would do better" |

## 3. Paper 2: every addition worth considering

### 3a. What top reviewers will ask

1. "Drift-plus-penalty is standard; what is new in the theory?" (Lyapunov thermal virtual queues exist: data-centre
   average temperature (Fu et al. 2017), building HVAC, mmWave thermal exposure.)
2. "**In flight, prop wash cools the board**; a table-top heat result may not transfer." (Vendor forums say
   propeller airflow is the main cooling of drone compute boards.)
3. "The abstract says pricing removes the cost, but your own 24-min Wi-Fi runs are hot 19–27 % of the time."
   (Found in today's check; must be fixed.)
4. "Why not DVFS? Commercial governors and joint DVFS + offloading (Heat & Memory 2024) exist."
5. "Compare against a learned (constrained DRL) scheduler." (Safe-DQN / CMDP work on UAV offloading is common at
   INFOCOM and in IoT-J.)
6. "One camera drone on the mesh, few repetitions, replay bias larger than the effects."
7. "Why would ~1 W matter on a drone whose motors draw hundreds of watts?" (Answer: the thesis is heat, not energy;
   MAVBench shows compute affects mission time and energy.)

### 3b. Additions, ranked

| ID | Addition | Type | Effort | Where | Why it matters |
|---|---|---|---|---|---|
| P2-1 | **Thermal guarantee theorem.** With the first-order plant (a, b, τ) and the guard and capped hold, bound the peak temperature and the *time above* the throttle temperature (not just the mean, as Prop. 1 does), including the one-update overshoot; then check it on every logged run, as Theorem 1 is checked | N (theory) | 2 | L | Answers question 1. The distinctive part against thermal virtual-queue work is time above a threshold under a plant with memory and an exemption rule, verified on real logs |
| P2-2 | **Airflow test.** A bench fan at several speeds (or measured prop-wash speed) over the Pi: fit b(airflow) and rerun the throttling-cost measurement at the airflow a flying drone gives; or a tethered hover if a drone is available | S (critical) | 0.5–1 | B | Answers question 2, the most dangerous attack. Either outcome is publishable: "the cost persists at X m/s", or "it appears only below X m/s (hover, enclosures, hot days)", with the rule for which case applies |
| P2-3 | **Capped hold on the board, plus ≥ 5 more 24-min Wi-Fi runs each for v4.1 and the capped hold** | S (critical) | 1 | B | Converts the replay finding into a hardware result and removes the n = 2 weakness |
| P2-4 | **Fix the overclaim**: scope "removes the cost" to the mesh and short runs, and state the hold result | S | 0.5 | L | Mandatory before any submission |
| P2-5 | **Joint DVFS (clock cap) + offloading + price**: frequency as a third knob, with power and latency measured per frequency on the Pi (plan item 19.14); controller and replay extension | N | 2 L + 0.5 B | L+B | A new controller dimension. Prior joint DVFS/offloading work (Heat & Memory 2024) is threshold-based, without accuracy pricing or guarantees |
| P2-6 | **Self-calibrating thermal model**: recursive least squares on (a, b) from the logged temperature, so the budget and hold threshold adapt to the room; test it in the replay with ambient shifts, plus the price-cap sweep at +10 °C | N | 1 | L | Addresses the hot-room failure found today; it is also what a deployable system needs |
| P2-7 | **Constrained DRL baseline** (PPO-Lagrangian or Safe-DQN in the replay, same objective and budget) | S | 2 | L | Answers question 5; the oracle already bounds the gain, so the expected result is "no better, far costlier" |
| P2-8 | **Energy relevance**: compute power against flight power on the target airframe (MAVBench), and why heat is the binding constraint | S | 0.5 | L | Answers question 7 in one paragraph and one number |
| P2-9 | **More hardware breadth**: second camera drone on the mesh, more repetitions (≥ 5 per cell) | S | 1–2 | B | Answers question 6 |
| P2-10 | **Outdoor or flight test** (even one 10-min flight) | S (biggest credibility) | 2–5 | B + drone | What MobiSys/MobiCom reviewers value most; outside laptop scope |
| P2-11 | Position against AoI-energy work (Safe-DQN AoI, IoT-J 2024): our freshness price is an AoI-style constraint with a measured accuracy objective | S | 0.25 | L | Related-work completeness |

## 4. Venues and timing

| Venue | Deadline | Fit | What it needs |
|---|---|---|---|
| ACM MobiSys 2027 | abstract 27 Nov, paper 4 Dec 2026 (12 pp. ACM) | Paper 2 | P2-1, P2-2, P2-3, P2-4 and a 12-page rewrite within ~3 weeks: feasible only if a board day is possible within ~10 days. Without P2-2 the flight objection is likely fatal |
| ACM MobiCom 2027, winter cycle | TBD (typically Feb–Mar 2027) | Paper 2 (or a merged system paper) | Everything above plus ideally P2-10. The realistic top-venue target |
| IEEE INFOCOM 2028 | ~July 2027 | Paper 2 | P2-1, P2-5, P2-7 (theory and baselines matter more than flight there) |
| ACM SenSys 2028 | ~May–June 2027; has a *Benchmarks / Experiences* category | Paper 1 | P1-1…P1-5; the open benchmark fits the category |
| IEEE TMC / JSAC (task-oriented communication issues) | rolling / per call | Paper 1 | P1-1…P1-5 |

## 5. Recommended order

1. Laptop now (about 6 days): P2-4 (0.5), P2-1 (2), P1-2 (0.5), P1-1 laptop part (1.5), P1-4 (2) — in parallel with
   GPU jobs; P2-6 (1) if time allows.
2. One board session (1.5–2 days): P2-2 airflow, P2-3 capped hold + long runs, P1-5 predict-then-measure, Pi timings
   for P1-1/P1-3, plus the planned energy and noisy-relay runs.
3. Rewrite + fresh-context audit (2 days); then decide MobiSys (if all of step 2 lands before ~25 Nov) or the MobiCom
   winter cycle.
4. Later (for MobiCom/INFOCOM): P2-5, P2-7, P2-9, P2-10; for paper 1: P1-3, P1-6, P1-7, P1-10.

## Sources

Split computing and coding for machines: SC2 benchmark (arXiv 2203.08875); FrankenSplit (arXiv 2302.10681);
BottleFit (arXiv 2201.02693); Matsubara & Levorato, neural compression for edge detection (arXiv 2007.15818) and
split computing for complex detectors (arXiv 2007.13312); Yuan et al. (arXiv 2204.07314); MPEG FCM (arXiv 2512.10209,
2512.09232, 2512.10230); learned image coding for machines CI-ICM (arXiv 2604.05347); Shao, Mao & Zhang, JSAC 40(1)
2022; indirect rate–distortion for task-oriented coding (arXiv 2602.12866); dynamic split computing (arXiv
2205.11269); Bayes-Split-Edge (arXiv 2510.23503); ENACHI (arXiv 2601.08135); AccMPEG (arXiv 2204.12534); DDS
(kuntaidu.github.io); IFMDC (GCCE 2022); Raspberry Pi H.264 white paper RP-010033; Raspberry Pi AI HAT+
documentation; UAV detection pipeline under JPEG (arXiv 2203.00306).
Thermal, energy and offloading: Pi 4 thermal throttling (arXiv 2010.06291); Heat & Memory constraints (ACM,
doi 10.1145/3662004.3663555); Tan & Cao, thermal-aware scheduling with NPU (TMC 2024); Phoenix (doi 10.1145/3793860);
Lotus (arXiv 2410.10847); REACT (IoTDI 2023); HybridInfer (arXiv 2609.30270); thermal virtual queues (arXiv
2601.19587, 1709.00715, 2412.20032); constrained RL zero duality gap (arXiv 1910.13393); OCO with long-term
constraints (arXiv 2106.05135); JCAB (TNET, Temple); AccuMO (MobiCom 2023); Safe-DQN AoI offloading (IoT-J 2024);
MAVBench (arXiv 1905.06388) and its TOCS extension (arXiv 1906.10513); A2-UAV (arXiv 2301.06363); TESTUDO and
DroneCOCoNet (NSF PAR); ModalAI and NVIDIA forum notes on drone board cooling (informal).
Venues: MobiSys 2027, MobiCom 2027 and SenSys 2027 calls for papers (official sites).
