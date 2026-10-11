# Publication plan: value-of-refresh scheduling for aerial streaming perception

Written 11 Oct 2026. Built on the three Consensus literature reports the user shared, checked against what
AEGIS-UAV has actually built and measured (docs/novelty_and_related_work.md, the results brief, Phase G).

## 1. What the reports say, checked against our record

| Report claim | Our record | Verdict |
| --- | --- | --- |
| Adaptive / multi-server offloading, forecasting to hide latency, optical-flow camera-motion compensation and shared-link coordination are not novel | Already in our "claims we must not make" list (Odessa, Elf, Glimpse, Liu 2019, PVT++, BoT-SORT, JCAB) | Agree; nothing changes |
| Best opening: a scheduler driven by **measured forecast-decay** of stale detections | This is already the core of controller v3: its objective is (A/A_ref)·H(L,T)·p_late, where H is the measured decay ρ(age) averaged over how long the result will be held, and it is rebuilt on forecaster v2's decay curve | **We already have the core.** What is missing is the rigour the reports ask for: context-conditioned decay, the right ablations and stronger baselines |
| JPEG beats split computing is a bounded empirical finding, not a general one | Our split baselines are uniform int8 + zstd, not learned bottlenecks (Matsubara 2021 supervised compression, FrankenSplit) | Agree; keep it as one section, scoped to our split implementations, or add one learned-bottleneck baseline |
| Thermal-aware long runs are publishable only if they **change the optimal policy** | v4 already changed it: with energy priced, accuracy went up (+0.0074 sAP vs v3+fc2), Pi power fell by about 1 W and time at ≥ 80 °C fell from 76 % to 17 % (100 runs) | Strong. Still missing: 20–30-minute *controller* runs. The 24-minute *heat runs* on both boards are done; the reports read an older record that listed them as pending |
| Swarm admission is weak (2/10) | Simulation gains only; with two real cameras the coordinator rarely acts | Agree; it needs 3–5 real cameras or should stay a secondary result |
| Mesh after v4.2, keep Wi-Fi as the baseline | Matches our plan | Agree |

Two cautions the reports underplay:

1. **The closest prior work for the main idea is not in their "key papers"**:
   - AccuMO (MobiCom 2023) predicts how each task's accuracy drops since its last offload and offloads the task with the largest predicted gain.
   - Qiu et al. (SEC 2024) offload the frames with the highest estimated benefit under a rate budget.
   - Chanakya (NeurIPS 2023) and Sela et al. (2022) learn or contextualise runtime decisions for streaming perception.

   Our claim must be stated against these four precisely. What they lack is a *measured, forecaster-specific* decay of the task metric (streaming AP) used as the scheduling objective across heterogeneous tiers, priced for energy and heat, on aerial video. If a full-text read shows AccuMO already does most of this, the claim narrows to the aerial, multi-tier, energy and thermal setting.
2. **The reports' citations must be verified** before any reach the paper. Consensus output can contain wrong authors, years or DOIs: some entries are dated 2026 with arXiv IDs, and one has a blank author. Run every reference through CrossRef (bibtex-sanitizer) and read the full text of every paper we position against.

## 2. The paper

**Working title:** *When is a fresh detection worth paying for? Value-of-refresh scheduling for aerial
streaming perception across drone, edge-drone and ground tiers.*

**Thesis.** A stale detection keeps a known, measurable share of its value: how much depends on the forecaster, the camera motion and the objects. A scheduler that prices each refresh (Pi, Jetson edge drone or ground GPU) by the value it restores, against its latency risk, energy and heat, outperforms schedulers driven by confidence, queue or freshness alone. It also changes which tier should be used over a long mission.

**Contributions** (each tied to evidence we have or will produce):

| # | Contribution | Status |
| --- | --- | --- |
| C1 | **Measured decay of stale aerial detections.** Streaming-AP retention vs age with no correction, velocity forecasting and camera-motion-aligned forecasting (41 / 77 / 85 % kept at 100 ms). Stratified by object size, object speed, camera ego-motion and crowding, with cross-dataset transfer | Global curves done; stratification and transfer to do |
| C2 | **Value-of-refresh controller** (update 11 Oct: context-conditioned decay tested and dropped — camera-motion alignment makes one curve sufficient; see novelty_check_phase0.md; AccuMO already has content-dependent drop rates, so the headline is the joint energy + heat pricing). Objective = expected decayed accuracy over the hold window × on-time probability − μ_cam·E_cam − μ_edge·E_edge − thermal price, with dual ascent on measured power. New piece: the decay curve is **conditioned on live context** (ego-motion speed and object mix, already computed by forecaster v2) | v3 / v4 / v4.1 / v4.2 done; context-conditioned decay and thermal-headroom price to do |
| C3 | **Real three-tier evaluation.** Pi 5 + Jetson Orin Nano + ground GPU, task-level sAP on labelled aerial video, controlled impairments, paired tests, ablations against strong baselines, 20–30-minute thermal runs, and system-level energy (three accounting views, including the honest negative: an airborne edge drone costs far more energy than it saves, so its case is robustness) | Most done; ablation campaign, long runs and mesh to do |
| C4 | **Perception-value admission on a shared link.** Give the scarce link to the drone whose refresh is worth most per unit of airtime | Simulation done; 3–5-camera hardware test to do |
| C5 | **Scoped negative result.** No split of YOLOv8s (uniform quantisation + entropy coding) beats JPEG on our links; the serial sense → edge → cloud chain is the worst design; dominance proposition | Done; optionally add one learned-bottleneck baseline |

**The single most important experiment** (it decides whether C2 is a contribution): keep the same controller and change only its value curve:

- (a) the measured decay with forecasting (ours);
- (b) the measured decay without forecasting;
- (c) a generic decay (linear age of information, or exponential with a fitted rate);
- (d) a flat curve (the throughput / rate objective);
- (e) context-conditioned decay (ours, new).

If (a) and (e) do not beat (c) and (d) significantly in paired runs, the "measured decay" claim fails, and the paper falls back to a measurement-plus-systems paper (C1, C3, C5).

## 3. Phases

Times are working estimates; hardware campaigns run unattended overnight.

### Phase 0: groundwork (1–2 days, no hardware)
1. Commit and push the corrected Phase G work. Bring `docs/results_brief.html` and the published report up to date.
2. **Novelty go/no-go.** Read AccuMO, Qiu (SEC 2024), Chanakya, Sela (2022), OffloaD (TECS 2024), Glimpse, PVT++ and Jeon et al.'s Phoenix (2026) in full. Write a one-page difference table: what each optimises, its metric, whether it uses a *measured decay* and whether it has energy or heat.
3. Verify every citation in the three reports (CrossRef; the crossref MCP server failed to connect this session, so it must be reconnected or the bibtex-sanitizer skill used).

### Phase 1: offline decay science (C1, about 1 week, laptop only)
1. **Stratify the decay** on VisDrone-VID train: object size (small / medium / large), object speed, ego-motion speed (from egomotion.npz), crowding. For each stratum, measure ρ(age) for no forecaster, v1 and v2.
2. **Context-conditioned model**: ρ(age | ego-speed bin, small-object share), fitted on train and checked on val.
3. **Transfer**: score the same curves on a second aerial video dataset (UAVDT or another VisDrone split) without refitting. This answers the reports' "biggest open question": is the value model stable across scenes?
4. **Trace-driven replay evaluator**: replay the recorded link traces and per-frame detections, so that all ablations (a)–(e) and the baselines can be scored offline in minutes. Hardware then confirms only the finalists. (The simulator already matches the hardware with r = 0.91.)

### Phase 2: controller v5 and baselines (3–5 days, code + smoke tests)
1. **v5** = v4.2 + context-conditioned decay + a thermal-headroom price. It uses the measured 12.7 °C/W thermal model to predict the steady temperature of a candidate action, replacing the hard 78 °C guard with a smooth price.
2. **Baselines**, under the same harness:
   - confidence-triggered offloading (OffloaD-style);
   - tracking-drift-triggered refresh (Glimpse-style);
   - freshness / AoI threshold;
   - queue-only (join the shortest queue);
   - estimated-benefit offloading (Qiu-style);
   - the existing local-only, fixed JPEG, rule-fallback and rate (v2) baselines.
3. The ablations (a)–(e) as command-line options of one controller, so that only the value curve differs between them.

### Phase 3: Wi-Fi hardware campaigns (3–4 nights)
1. v4.2 campaign as planned (`campaign_energy.sh`, 120 runs, live power on both boards), after `push_code.sh` and one smoke run.
2. **Ablation and baseline campaign**: about 10 policies × 4 scenarios × 5 repetitions, shuffled and paired. This is the paper's main table.
3. **Long runs**: 24-minute controller runs (PHASE_S=240) for v5, v4, v3+fc2 and fixed JPEG, 2–3 repetitions each, live power and temperature. Shows whether the best policy changes as the Pi heats up: cold start vs stabilised.

### Phase 4: mesh (needs the AegisSwarm details: channel, band, IP range, batman-adv; plus the Ethernet cable)
1. Measure each mesh link (throughput, RTT, loss) and record traces for the replay evaluator.
2. Run the final policy set on the mesh (about 120–220 runs). Wi-Fi stays the baseline and is not replaced.

### Phase 5: swarm (needs the 2 extra Pis and the extra Jetson)
1. 3–5 real cameras on one shared link. Compare value-based admission against round-robin, equal share, proportional fair and no coordination. Report shared-link sAP, worst-camera sAP and fairness.

### Phase 6: field evidence (strongly recommended for a top venue)
1. At least one real outdoor capture: the Pi on a flying (or tethered / handheld-moving) platform, over the mesh, logging video, link traces and power. Best is a live run of the controller; at minimum, record traces to replay. Without this the paper must say "lab links with injected impairments", which reviewers at MobiSys and SenSys penalise.

### Phase 7: writing (2–3 weeks)
1. Paper structure:
   - motivation: the decay measurement;
   - design: the value-of-refresh objective, its energy and thermal prices, and admission;
   - implementation: the three-tier testbed;
   - evaluation: the ablations (a)–(e), baselines, long runs, mesh, swarm, energy views and the split negative result;
   - limitations.
2. Artifact: code, campaign scripts, raw logs and summaries, so results can be reproduced from the logs.

## 4. Venues (check each CFP for current deadlines)

| Tier | Venue | What it needs from us |
| --- | --- | --- |
| Top | ACM MobiSys, ACM SenSys, ACM MobiCom | C2 ablations clearly positive, Phase 6 field evidence, 3–5-camera swarm |
| Strong | IEEE/ACM SEC (Symposium on Edge Computing), IEEE INFOCOM, ACM/IEEE IPSN, IEEE TMC (journal) | C1 + C2 + C3 on Wi-Fi and mesh; field data helps but is not mandatory for SEC or TMC |
| Robotics angle | ICRA / IROS | Emphasise the decay-and-forecasting side and the UAV deployment |
| Early checkpoint | ACM DroNet (MobiSys workshop) or HotMobile | C1 + v3/v4 results as they are now: quick feedback, then the full paper |

Recommended: aim the full paper at **MobiSys or SenSys** if Phases 4–6 finish and the ablation is positive. Otherwise go to **SEC or TMC** with the same material. A workshop paper on C1 plus v4 can go out early without blocking the main paper (check the venue's dual-submission rules).

## 5. Decision points

| When | Question | If no |
| --- | --- | --- |
| After Phase 0 | Does a prior paper already use a measured forecast-decay of the task metric as an offloading objective? | Narrow the claim to multi-tier + energy/thermal + aerial; weight C3 and C1 more |
| After Phase 1 | Does decay differ enough across contexts (ego-motion, object size) to matter? | Drop context conditioning; keep the global curve |
| After the replay evaluator | Do (a)/(e) beat (c)/(d) offline? | Fix or drop before spending hardware nights |
| After Phase 3 | Is the paired hardware gain significant against the strongest baseline? | Measurement-plus-systems paper (C1, C3, C5) at SEC / TMC |
| Before Phase 6 | Can a drone carry the Pi on the mesh? | Replay of recorded field traces; state the limitation |

## 6. What we must still not claim
Unchanged from docs/novelty_and_related_work.md: parallel or adaptive offloading, latency-hiding
forecasting, optical-flow compensation and shared-link coordination as such are not ours; Wi-Fi with
injected impairments is not a flight test; "JPEG beats split" holds only for the split methods we tested.
