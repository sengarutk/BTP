"""Text corrections of the 28 Oct 2026 audit (docs/audit_2026-10-28.md), registered with report_audit_oct28.py.
E(old, new[, count][, which][, html_old, html_new]): the markdown form; the HTML form is derived (**b** -> <b>, `c` ->
<code>) unless given. Interval values are the Student-t ones of the regenerated summaries (28 Oct)."""


def register(E, info):
    u, sv, sc, g = info["unique"], info["sig_vd"], info["sig_coco"], info["gained"]
    r0, r1 = info["ratio"]
    q0, q1 = info["rho"]

    def cell(label, old, new, bold=False):
        """A table cell right after a row label (md and html)."""
        b0, b1 = ("**", "**") if bold else ("", "")
        h0, h1 = ("<b>", "</b>") if bold else ("", "")
        E(f"| {label} | {b0}{old}{b1}", f"| {label} | {b0}{new}{b1}", 1, "md")
        E(f"<td>{label}</td><td class=\"n\">{h0}{old}{h1}", f"<td>{label}</td><td class=\"n\">{h0}{new}{h1}", 1, "html")

    # ---------------- Part 1 ----------------
    E("- **Ten-round check (26 Oct):**",
      f"- **Full audit (28 Oct):** every table of Parts 17–19 checked field by field against the data and every Part 19 "
      f"statistic recomputed independently (no mismatch); the analysis code read line by line (`docs/audit_2026-10-28.md`, "
      f"re-runnable checks in `scripts/audit_2026-10-28/`). Corrected: the Pi's thermal fit had included a throttling level "
      f"(now T = 37.3 °C + 11.3 °C/W × P); Holm is now applied over the unique comparisons of a campaign ({u} in 19.5, not 52; "
      f"{sv} significant with VisDrone detections, {g} newly significant); the holding rule changes 1 verdict, not none; the "
      f"remaining 1.96-based intervals of Parts 12–16 are now Student-t, so v3 + forecasting v2 beats v2 significantly only "
      f"in the original scoring; the onboard emulation's fresh AP; overstated statements about splitting, JPEG q90, energy "
      f"efficiency and the mothership placement.\n- **Ten-round check (26 Oct):**",
      html_old="<li><b>Ten-round check (26 Oct):</b>",
      html_new=f"<li><b>Full audit (28 Oct):</b> every table of Parts 17–19 checked field by field against the data and every "
               f"Part 19 statistic recomputed independently (no mismatch); the analysis code read line by line "
               f"(<code>docs/audit_2026-10-28.md</code>, re-runnable checks in <code>scripts/audit_2026-10-28/</code>). "
               f"Corrected: the Pi's thermal fit had included a throttling level (now T = 37.3 °C + 11.3 °C/W × P); Holm is "
               f"now applied over the unique comparisons of a campaign ({u} in 19.5, not 52; {sv} significant with VisDrone "
               f"detections, {g} newly significant); the holding rule changes 1 verdict, not none; the remaining 1.96-based "
               f"intervals of Parts 12–16 are now Student-t, so v3 + forecasting v2 beats v2 significantly only in the "
               f"original scoring; the onboard emulation's fresh AP; overstated statements about splitting, JPEG q90, energy "
               f"efficiency and the mothership placement.</li>\n<li><b>Ten-round check (26 Oct):</b>")
    E("equal to or above YOLOv8)", "equal to YOLOv8 for n (0.001 below), above it for s and m)")
    E("**Waiting for the go-ahead:** the VisDrone replay of the 776 earlier runs, then the AegisSwarm mesh work. Both since done (19.5; 18.8–18.10).",
      "**Done since the 6 October plan:** the VisDrone replay of the 776 earlier runs (19.5) and the AegisSwarm mesh work (18.8–18.10).")
    E("Splitting the network never beats sending a JPEG", "Splitting the network does not beat sending a JPEG")
    E("across 1,150 placements over the Pi, the Jetson and the laptop, and in live runs.",
      "across 1,150 placements over the Pi, the Jetson and the laptop, and in live runs. In random simulated systems a split "
      "wins by at most 0.47 % (Part 3).")
    E("59–62 %", "55–62 %", 3)
    E("and 75–201 % over rule-based fallback, the Jetson and onboard.", "and 68–201 % over the Jetson, rule-based fallback and onboard.")
    E("Energy-aware control is both more efficient and more accurate", "Energy-aware control is more accurate and uses less camera-drone power")
    E("than every other controller: +0.0074 ± 0.0030 sAP over v3 + forecasting v2, 17 of 20 pairs. The cost is freshness (87 % against 99 %).",
      "than v2 and v3 + forecasting v2: +0.0074 ± 0.0030 sAP over v3 + forecasting v2, 17 of 20 pairs. The cost is freshness "
      "(87 % against 99 %). Counting the edge drone it keeps in the air, fixed offloading to the ground is 2.5–2.7× more "
      "energy-efficient for the whole system (G10, G11).")
    E("A controller built for the forecaster it runs with wins, significantly", "A controller built for the forecaster it runs with wins (significant in the original scoring)")
    E("beats v2 by +0.0045 ± 0.0038 sAP over 20 paired runs (median +8.9 %). It is best in 3 of 4 scenarios, including the clean link where fixed laptop YOLOv8m had won before, and P(AoI ≤ 300 ms) at 99.5–99.8 %.",
      "beats v2 by +0.0045 ± 0.0038 sAP over 20 paired runs (median +8.9 %, p = 0.021); with the standard holding rule +0.0038 "
      "± 0.0039 (Holm p = 0.22, not significant), with VisDrone detections +0.015 (Holm p = 0.007). It is best in 3 of 4 "
      "scenarios, including the clean link where fixed laptop YOLOv8m had won before, and keeps P(AoI ≤ 300 ms) at 99.5–99.8 %.")
    E("raises Jetson-class swarms on Wi-Fi by up to 27 %", "raises Jetson-class swarms on Wi-Fi by 13–22 %")
    E("its worst loss shrinks from −7.4 % to −1.9 %", "its worst loss shrinks from −7.6 % to −1.9 %")
    E("v3 rebuilt with forecasting P(AoI ≤ 300 ms) at 99–100 %", "v3 rebuilt with forecasting keeps P(AoI ≤ 300 ms) at 99–100 %")

    # ---------------- Part 2 ----------------
    E("JPEG quality 90 (q90) is near-lossless for detection; q50 is smaller but costs some accuracy.",
      "JPEG quality 90 (q90) is near-lossless on COCO photographs (−0.7 %) but loses 4 % on aerial images (19.6); q50 is "
      "smaller but costs more.")
    E("4-core ARM CPU, no GPU |", "4-core ARM CPU (its GPU is not usable for detection) |", 1, "md")
    E("4-core ARM CPU, no GPU</td>", "4-core ARM CPU (its GPU is not usable for detection)</td>", 1, "html")
    E("### The three controller versions", "### The controller versions", 1, "md")
    E("<h3>The three controller versions</h3>", "<h3>The controller versions</h3>", 1, "html")
    E("accuracy × probability on time × the average staleness factor over the time it is shown. The staleness factor comes from the decay curve measured on training videos.",
      "accuracy × probability of arriving within 1 s × the average staleness factor over the time it is shown. The staleness "
      "factor comes from the decay curve measured on training videos.\n- **v4 to v5.1** (Parts 15–16) are v3 + forecasting "
      "with prices: v4 prices the camera drone's energy, v4.1 adds a freshness price (the best overall), v4.2 prices the edge "
      "drone's energy, v5 adds a predictive heat price, v5.1 uses all of them.",
      html_new="accuracy × probability of arriving within 1 s × the average staleness factor over the time it is shown. The "
               "staleness factor comes from the decay curve measured on training videos.</li>\n<li><b>v4 to v5.1</b> "
               "(Parts 15–16) are v3 + forecasting with prices: v4 prices the camera drone's energy, v4.1 adds a freshness "
               "price (the best overall), v4.2 prices the edge drone's energy, v5 adds a predictive heat price, v5.1 uses all "
               "of them.")
    E("tell whether one is reliably better: the interval must not cross zero.",
      "tell whether one is reliably better: the interval must not cross zero. From Part 18 on, and in the rescoring of Part "
      "19, significance is decided by an exact permutation p-value with the Holm correction; where the two rules disagree, "
      "the text says so.")

    # ---------------- Parts 5-11 ----------------
    E("The Pi has no cooler and throttles from 2.4 to 1.5 GHz at 85–89 °C.",
      "The Pi has no cooler: its firmware starts lowering the clock from 2.4 GHz at about 80 °C and holds about 85 °C (down to "
      "1.5 GHz).")
    E("Adaptive controllers v1, v2 and v3, and the workers", "Adaptive controllers v1 (`adaptive.py`) and v2–v5.1 (`adaptive2.py`), and the workers")
    E("The model predicts two-device placements within about 30 %.",
      "The model is optimistic: for two-device placements it predicts 0.8–2.0× the live rate (Jetson alone 15.0 against 18.5/s, "
      "Pi → Jetson 17.0 against 10.9, Pi → laptop 30.0 against 15.2; G4).")
    E("### Encoding twice costs nothing", "### A second encoding adds nothing (the first row's loss is the JPEG q90 hop itself)", 1, "md")
    E("<h3>Encoding twice costs nothing</h3>", "<h3>A second encoding adds nothing (the first row's loss is the JPEG q90 hop itself)</h3>", 1, "html")
    E("**Pi power:** 0.7–3.1 W, against 2.4–3.1 W without adaptation.",
      "**Pi power (the controller's early in-run estimate, far too low):** 0.7–3.1 W, against 2.4–3.1 W without adaptation; "
      "the measured model gives 2.2–5.1 W (G5).")
    E("**Limits:** only 2 repetitions, and the scoring uses COCO accuracy weights, a proxy.",
      "**Limits:** only 2 repetitions, the scoring uses COCO accuracy weights, a proxy, and the camera input was looped COCO "
      "photographs, not video (19.4).")
    E("v2 reaches 0.77–0.98 at 0.9–2.7 W.", "v2 reaches 0.77–0.98 at 0.9–2.7 W (the early in-run estimate; measured model 4.7–5.3 W, G6).")
    E("PVT / PVT++ (ICCV 2023)", "PVT++ (ICCV 2023) and its predecessor PVT")
    E("The rebuilt controller then significantly beats v2 (+8.9 % median over 20 paired runs) and P(AoI ≤ 300 ms) at 99.5–99.8 %.",
      "The rebuilt controller then beats v2 (+8.9 % median over 20 paired runs; significant in the original scoring, not after "
      "Holm with the standard holding rule, Part 19) and keeps P(AoI ≤ 300 ms) at 99.5–99.8 %.")
    E("Most novel (verify against more recent offloading work)",
      "Strong (narrowed after AccuMO, Part 15, which also adapts offloading to forecast accuracy: ours is the measured, "
      "forecaster-matched decay objective on a distributed system)",
      html_old="<span class=\"tag v\">Most novel</span> (verify against more recent offloading work)",
      html_new="<span class=\"tag v\">Strong</span> (narrowed after AccuMO, Part 15, which also adapts offloading to forecast "
               "accuracy: ours is the measured, forecaster-matched decay objective on a distributed system)")
    E("matches the hardware in all 528 phases (r = 0.947)",
      "predicts the hardware's deadline-met throughput over all 528 phases with correlation 0.947 (average error 1.6 results/s)")
    E("(needs a literature check before submission)", "(literature checked 26 Oct 2026, Part 15)")

    # ---------------- Part 12 paired table (Student-t) ----------------
    for lab, o, n, b in (("Fixed onboard YOLOv8n 320", "+0.0160 ± 0.0048", "+0.0160 ± 0.0054", False),
                         ("Rule-based fallback", "+0.0071 ± 0.0039", "+0.0071 ± 0.0044", False),
                         ("Fixed Jetson YOLOv8s q90", "+0.0098 ± 0.0034", "+0.0098 ± 0.0038", False),
                         ("Fixed laptop YOLOv8m q90", "+0.0039 ± 0.0047", "+0.0039 ± 0.0053", False),
                         ("v3 staleness-aware", "+0.0042 ± 0.0049", "+0.0042 ± 0.0055", False),
                         ("v2 with aerial accuracy", "+0.0028 ± 0.0045", "+0.0028 ± 0.0050", False),
                         ("Single-path rate adaptation", "+0.0025 ± 0.0038", "+0.0025 ± 0.0043", False),
                         ("All servers, no adaptation", "+0.0003 ± 0.0030", "+0.0003 ± 0.0034", False)):
        cell(lab, o, n, b)

    # ---------------- Part 13 ----------------
    E("| 20 Jetson-class drones, cell, capped router | 19.2 | 17.8 | −7.4 % |", "| 20 Jetson-class drones, cell, capped router | 19.2 | 17.8 | −7.6 % |", 1, "md")
    E("<td>20 Jetson-class drones, cell, capped router</td><td class=\"n\">19.2</td><td class=\"n\">17.8</td><td class=\"n\">−7.4 %",
      "<td>20 Jetson-class drones, cell, capped router</td><td class=\"n\">19.2</td><td class=\"n\">17.8</td><td class=\"n\">−7.6 %", 1, "html")
    E("| Study 0–4 | Plain | 16 / 74 / 6 | −7.4 % |", "| Study 0–4 | Plain | 16 / 74 / 6 | −7.6 % |", 1, "md")
    E("<td>Study 0–4</td><td>Plain</td><td class=\"n\">16 / 74 / 6</td><td class=\"n\">−7.4 %",
      "<td>Study 0–4</td><td>Plain</td><td class=\"n\">16 / 74 / 6</td><td class=\"n\">−7.6 %", 1, "html")
    E("| Held-out 5–9 | Plain | 16 / 74 / 6 | −7.3 % |", "| Held-out 5–9 | Plain | 16 / 74 / 6 | −7.5 % |", 1, "md")
    E("<td>Held-out 5–9</td><td>Plain</td><td class=\"n\">16 / 74 / 6</td><td class=\"n\">−7.3 %",
      "<td>Held-out 5–9</td><td>Plain</td><td class=\"n\">16 / 74 / 6</td><td class=\"n\">−7.5 %", 1, "html")
    E("The one real loss disappears (−7.4 % → +0.5 %)", "The one real loss disappears (−7.6 % → +0.5 %)")
    E("The two-camera Wi-Fi test below is the hardware check so far", "The two-camera Wi-Fi test above is the hardware check so far")

    # ---------------- Part 14 ----------------
    E("and camera alignment alone barely helps (AP 0.039 against 0.029 at 167 ms).",
      "and camera alignment alone helps less than alignment plus object velocity (AP 0.039 against 0.029 without, +34 %, at 167 ms).")
    E("on the mean by 0.0003 ± 0.0062 sAP", "on the mean by 0.0003 ± 0.0070 sAP")
    E("v3 + forecasting v2 beats v2, and the difference is significant", "v3 + forecasting v2 beats v2, significantly in the original scoring")
    E("With the newest-result rule: +0.0038 ± 0.0037, ahead in 14 of 20.",
      "With the standard newest-result rule: +0.0038 ± 0.0039, ahead in 14 of 20; this interval crosses zero (Holm p = 0.22, "
      "Part 19).")
    E("It P(AoI ≤ 300 ms) at 99.5–99.8 %", "It keeps P(AoI ≤ 300 ms) at 99.5–99.8 %")

    # ---------------- Part 15 ----------------
    E("The Pi PMIC rails exclude 5 V conversion losses, so Pi numbers are a lower bound.",
      "The Pi PMIC rails exclude 5 V conversion losses, so Pi numbers are a lower bound. Pi idle power depends on how and when "
      "it is measured: 1.89 W in this 20-s profile, 1.66 W over 6 minutes (G2), 1.81 W in the 24-minute run with an SSH poll; "
      "Part 6's 2.6 / 2.0 W are the cruder 3 October readings. YOLOv8n's 6.0 W is a 20-s burst at full clock; sustained, it "
      "settles at 4.15 W once the Pi throttles (G2).")
    E("(linear fit of the Pi's measured points)", "(linear fit of the Pi's measured points; within 10–13 % at 2–10 Mbit/s)")
    E("**+12.7 °C per extra watt; throttling from about 3.6 W sustained**A linear fit of the steady levels below the throttle limit gives T = 34.4 °C + 12.7 °C/W × P (the fitted constants are stored in `energy_constants.json`). The firmware starts lowering the clock at about 80 °C (about 3.6 W)",
      "**+11.3 °C per extra watt; throttling from about 3.5–3.7 W sustained**A linear fit of the five steady levels below the "
      "80 °C throttle limit gives T = 37.3 °C + 11.3 °C/W × P (the fitted constants are stored in `energy_constants.json`; "
      "corrected 28 Oct: the earlier fit, 34.4 + 12.7 × P, also included the throttling 50 % level). The firmware starts "
      "lowering the clock at about 80 °C (between 3.49 and 3.69 W measured)")
    E("That is why YOLOv8s slowed from 576 to 718–758 ms in earlier tests.",
      "That, and the controller's 3 inference threads against 4 in Part 6, is why YOLOv8s slowed from 576 to 718–758 ms in "
      "earlier tests.")
    E("and the 6-minute fit above predicts the 50 %-duty row to within half a degree (82.3 predicted, 81.8 measured).",
      "and the 6-minute fit above predicts 66.9 / 75.5 / 79.9 °C for the 15 / 30 / 50 % rows against 62.3 / 71.5 / 81.8 °C "
      "measured: about 4–5 °C high for the unthrottled rows of this run and 2 °C low at the throttling onset.")
    E("The metric that combines everything is These are therefore reported side by side rather than combined into one number:",
      "No single number combines them, so they are reported side by side:")
    E("Splitting is worst on every axis: speed, accuracy and energy.",
      "The split loses to sending a JPEG on speed and energy; it is still faster and cheaper for the drone than running "
      "everything on the Pi (2,046 mJ), and its INT8 features are lossless where JPEG q90 loses 4 % on aerial images (19.6).")
    E("| ≈ 86 °C → throttles |", "| ≈ 83 °C → throttles |", 1, "md")
    E(">≈ 86 °C → throttles<", ">≈ 83 °C → throttles<", 1, "html")
    E("| **6.9** | 68 °C |", "| **6.9** | 67 °C |", 1, "md")
    E("<b>6.9</b></td><td class=\"n\">68 °C", "<b>6.9</b></td><td class=\"n\">67 °C", 1, "html")
    E("| ≈ 87 °C, throttles |", "| ≈ 84 °C, throttles |", 1, "md")
    E(">≈ 87 °C, throttles<", ">≈ 84 °C, throttles<", 1, "html")
    E("| 4.28 W | ≈ 89 °C |", "| 4.28 W | above 85 °C (throttles) |", 1, "md")
    E(">4.28 W</td><td class=\"n\">≈ 89 °C<", ">4.28 W</td><td class=\"n\">above 85 °C (throttles)<", 1, "html")
    E("| 4.38 W | ≈ 90 °C |", "| 4.38 W | above 85 °C (throttles) |", 1, "md")
    E(">4.38 W</td><td class=\"n\">≈ 90 °C<", ">4.38 W</td><td class=\"n\">above 85 °C (throttles)<", 1, "html")
    E("about 89–98 °C steady, so it would throttle", "a steady temperature above the 85 °C limit, so it would throttle")
    E("3.5 W (thermal-safe, below the throttling region from G2) and 2.8 W (energy-saving, about 70 °C).",
      "3.5 W (thermal-safe: about 77 °C steady by the G2 fit, below the 78 °C guard) and 2.8 W (energy-saving, about 69 °C).")
    # G9 pooled and paired (Student-t; recomputed from energy_campaign_measured.json)
    for o, n in (("0.0543 ± 0.0069", "0.0543 ± 0.0074"), ("3.33 ± 0.11 W", "3.33 ± 0.12 W"),
                 ("0.0525 ± 0.0072", "0.0525 ± 0.0077"), ("0.0470 ± 0.0080", "0.0470 ± 0.0085"),
                 ("4.47 ± 0.17 W", "4.47 ± 0.19 W"), ("0.0465 ± 0.0067", "0.0465 ± 0.0071"),
                 ("4.24 ± 0.14 W", "4.24 ± 0.15 W"), ("0.0463 ± 0.0105", "0.0463 ± 0.0113"), ("2.65 ± 0.07 W", "2.65 ± 0.08 W"),
                 ("−1.14 ± 0.19 W", "−1.14 ± 0.21 W"), ("−0.91 ± 0.13 W", "−0.91 ± 0.14 W"),
                 ("+0.0080 ± 0.0052", "+0.0080 ± 0.0056"), ("+0.68 ± 0.15 W", "+0.68 ± 0.16 W"),
                 ("+0.0055 ± 0.0043", "+0.0055 ± 0.0046"), ("−0.87 ± 0.18 W", "−0.87 ± 0.19 W"),
                 ("+0.0018 ± 0.0031", "+0.0018 ± 0.0033")):
        E(o, n)
    E("+0.0078 ± 0.0034", "+0.0078 ± 0.0037", 2)
    E("Model-predicted Pi power is within 0.1–0.4 W (about 5–10 %) of the live-measured power in all five policies.",
      "Model-predicted Pi power is 0.1–0.4 W (2–11 %) below the live-measured power in all five policies: a consistent "
      "underestimate.")
    E("2.65 W measured, 0.0175 sAP/W", "2.65 W measured, 0.0175 sAP/W (ratio of the means; G9's 0.0171 is the mean of the per-run ratios)")
    # G11 paired
    E("+0.0025 ± 0.0038 (13/20)", "+0.0025 ± 0.0041 (13/20)")
    E("+0.0009 ± 0.0040", "+0.0009 ± 0.0042", 2)
    E("| −0.12 ± 0.11 |", "| −0.12 ± 0.12 |", 1, "md")
    E(">−0.12 ± 0.11<", ">−0.12 ± 0.12<", 1, "html")
    E("−0.0005 ± 0.0050", "−0.0005 ± 0.0053")
    E("+0.36 ± 0.09 (20/20)", "+0.36 ± 0.10 (20/20)")
    E("+1.25 ± 0.16 (20/20)", "+1.25 ± 0.17 (20/20)")
    E("−0.0091 ± 0.0057", "−0.0091 ± 0.0061")
    E("| −0.69 ± 0.16 |", "| −0.69 ± 0.18 |", 1, "md")
    E(">−0.69 ± 0.16<", ">−0.69 ± 0.18<", 1, "html")
    E("85 % / 58 % kept at 100 / 267 ms on training, 82 % / 52 % held out.",
      "85 % / 58 % kept at 100 / 267 ms on training, 82 % / 52 % held out (CPU detections; the controllers' curve, from GPU "
      "detections, keeps 85 % / 60 %).")
    # G12 paired
    E("0.0018 ± 0.0022", "0.0018 ± 0.0024", 4)
    E("+0.0005 ± 0.0014", "+0.0005 ± 0.0015")
    E("−0.0002 ± 0.0025", "−0.0002 ± 0.0026")
    E("−0.0059 ± 0.0039", "−0.0059 ± 0.0042", 2)
    E("| +0.08 ± 0.09 |", "| +0.08 ± 0.10 |", 1, "md")
    E(">+0.08 ± 0.09<", ">+0.08 ± 0.10<", 1, "html")
    E("−0.0054 ± 0.0032", "−0.0054 ± 0.0034", 2)
    E("**+0.41 ± 0.15**", "**+0.41 ± 0.16**")
    E("−0.0004 ± 0.0015", "−0.0004 ± 0.0016", 2)
    E("| −0.02 ± 0.16 |", "| −0.02 ± 0.17 |", 1, "md")
    E(">−0.02 ± 0.16<", ">−0.02 ± 0.17<", 1, "html")
    E("−0.0076 ± 0.0053", "−0.0076 ± 0.0057")
    E("+0.0076 ± 0.0053", "+0.0076 ± 0.0057")
    E("| −0.74 ± 0.13 |", "| −0.74 ± 0.14 |", 1, "md")
    E(">−0.74 ± 0.13<", ">−0.74 ± 0.14<", 1, "html")
    E("−0.0112 ± 0.0030", "−0.0112 ± 0.0032")
    E("| −0.55 ± 0.10 |", "| −0.55 ± 0.11 |", 1, "md")
    E(">−0.55 ± 0.10<", ">−0.55 ± 0.11<", 1, "html")
    E("−0.0146 ± 0.0024", "−0.0146 ± 0.0025")
    E("| +1.68 ± 0.14 |", "| +1.68 ± 0.15 |", 1, "md")
    E(">+1.68 ± 0.14<", ">+1.68 ± 0.15<", 1, "html")
    E("−0.0214 ± 0.0025", "−0.0214 ± 0.0027")
    E("−0.0278 ± 0.0033", "−0.0278 ± 0.0035")
    E("| +1.54 ± 0.15 |", "| +1.54 ± 0.16 |", 1, "md")
    E(">+1.54 ± 0.15<", ">+1.54 ± 0.16<", 1, "html")
    E("The LEAF-style weight was set to 2.0, the median price v4's dual ascent itself settled at in the 100-run campaign",
      "The LEAF-style weight was set to 2.0, about the median price v4's dual ascent reached in the 100-run campaign (1.93; "
      "the price moves with conditions and does not settle to one value)")
    # G13 same-day paired
    E("0.0003 ± 0.0017", "0.0003 ± 0.0018", 3)
    E("| −0.10 ± 0.08 |", "| −0.10 ± 0.09 |", 1, "md")
    E(">−0.10 ± 0.08<", ">−0.10 ± 0.09<", 1, "html")
    E("| −0.03 ± 0.07 |", "| −0.03 ± 0.08 |", 1, "md")
    E(">−0.03 ± 0.07<", ">−0.03 ± 0.08<", 1, "html")
    E("−0.0428 ± 0.0079", "−0.0428 ± 0.0085", 2)
    E("found four problems that change", "found five problems that change")
    E("3. The simulator matches the hardware in every phase.", "3. The simulator tracks the hardware over every phase.")

    # ---------------- Part 16 ----------------
    E("max(t_tx + rtt, one frame) for a path, the onboard time rounded up to whole frames",
      "max(t_tx + rtt, one frame) for a path (an approximation: the path is held until its result returns, so the server time "
      "t_rem, 13.6 ms on the laptop and 29–57 ms on the Jetson, is left out), the onboard time rounded up to whole frames")
    E("p_on = P(300 ms),   p_late = P(1000 ms)", "p_on = P(300 ms),   p_late = P(1000 ms)        (v1: P(1500 ms))")
    E("only because we set it to 2.0, the value v4's own price settles at; nobody could have chosen it without running v4 first.",
      "only because we set it to 2.0, about the median of v4's own price in G9 (1.93; the price does not settle to one value); "
      "without running v4 first we would not have known that value.")
    E("without this, μ grew to 41 in a 90-s blackout", "without this, μ grew to 41 over about 4.5 minutes from a 90-s blackout on (one long test run)")
    E("The bonus is paid only to a result that would arrive before the held detection goes stale (the indicator)",
      "The bonus is paid only when the held detection will be stale by the time this result arrives (the indicator, "
      "AoI + L ≥ 300 ms)")
    E("E_edge = 0.040–0.371 J per Jetson inference (measured)", "E_edge = 0.067–0.163 J per Jetson inference (YOLOv8s at 320–640 px, measured)")
    E("T_steady = 34.43 °C + 12.73 °C/W × P̄_10s          (measured fit)",
      "T_steady = 34.43 °C + 12.73 °C/W × P̄_10s          (the fit used in the v5 runs; corrected fit 37.26 + 11.31 × P, G2)")
    E("the steady temperature is a straight line in power (12.7 °C per watt). A separate heat price therefore **counts the same cost twice**. It also lags: after the onboard-only blackout the predicted temperature stays high for minutes (time constant 149 s)",
      "the steady temperature is a straight line in power (11.3 °C per watt). With the 2.8 W budget the energy price already "
      "holds the Pi near 69 °C, below the heat price's 75 °C target, so a separate heat price is **mostly redundant**; it binds "
      "only after blackouts. It also lags: after the onboard-only blackout the predicted temperature stays high for minutes "
      "(149 s is the cooling time constant; under load the Pi heats far faster, 72 → 85 °C in 17 s)")
    E("+0.0025 ± 0.0038 (n.s.)", "+0.0025 ± 0.0041 (n.s.)")
    E("(2) It P(AoI ≤ 300 ms) at 97–98 %", "(2) It keeps P(AoI ≤ 300 ms) at 97–98 %")

    # ---------------- Part 17 ----------------
    E("8 output classes", "6 output classes (in the 8 COCO id slots 0–7; airplane and train are never labelled)")
    E("YOLOv8l 50 epochs (batch 4, 5.1 h); best epoch by DET-val mAP.",
      "YOLOv8l 50 epochs (batch 4, 5.1 h); best epoch by DET-val mAP. YOLOv8n (80 epochs, `experiments/finetune/yolov8n_e80/`) "
      "was trained later for 17.7.")
    E("pi2 `sengar@192.168.0.129` (\"pi-relayyy\") and pi3 `dubey@192.168.0.247` (\"pi-sender\")",
      "pi2 (hostname \"pi-relayyy\") and pi3 (hostname \"pi-sender\"; the names do not describe their roles)")
    E("3 CPU threads, conf 0.01)", "3 CPU threads as in every campaign since Part 9, against 4 in Part 6; conf 0.01)")
    E("(measured time × mean clock / 2,400 MHz)", "(measured time × mean clock / 2,400 MHz, which assumes inference time scales inversely with the clock)")
    E("| fresh AP (no delay) | 0.199 | 0.199 | 0.203 | 0.215 | 0.171 |",
      "| fresh AP (no delay, all 2,846 frames) | 0.229 | 0.229 | 0.242 | 0.249 | 0.202 |", 1, "md")
    E("<td>fresh AP (no delay)</td><td class=\"n\">0.199</td><td class=\"n\">0.199</td><td class=\"n\">0.203</td><td class=\"n\">0.215</td><td class=\"n\">0.171</td>",
      "<td>fresh AP (no delay, all 2,846 frames)</td><td class=\"n\">0.229</td><td class=\"n\">0.229</td><td class=\"n\">0.242</td><td class=\"n\">0.249</td><td class=\"n\">0.202</td>", 1, "html")
    E("| time per frame: measured → at 2.4 GHz | sAP + forecaster: measured → at 2.4 GHz |",
      "| time per frame: measured → at 2.4 GHz | sAP + forecaster (emulated): at the measured time → at 2.4 GHz |", 1, "md")
    E("<th>sAP + forecaster: measured → at 2.4 GHz</th>", "<th>sAP + forecaster (emulated): at the measured time → at 2.4 GHz</th>", 1, "html")

    # ---------------- Part 18 ----------------
    E("and an offloading Pi stays at about 50 °C)", "and an offloading Pi stays far below its throttling point, 54–69 °C here)")
    E("(5 per scenario would allow p = 0.03 per scenario)", "(6 per scenario would allow p = 0.031 per scenario; 5 give at best 0.0625)")
    E("| Mission (mean of the six phases) | **0.121–0.122** |", "| Mission (mean of the six phases) | **0.117–0.122** |", 1, "md")
    E("<td>Mission (mean of the six phases)</td><td class=\"n\"><b>0.121–0.122</b>", "<td>Mission (mean of the six phases)</td><td class=\"n\"><b>0.117–0.122</b>", 1, "html")
    E("| ground congested | **0.090** |", "| ground congested | **0.079–0.090** |", 1, "md")
    E("<td>ground congested</td><td class=\"n\"><b>0.090</b>", "<td>ground congested</td><td class=\"n\"><b>0.079–0.090</b>", 1, "html")
    E("| both degraded | 0.032 |", "| both degraded | 0.031–0.032 |", 1, "md")
    E("<td>both degraded</td><td class=\"n\">0.032<", "<td>both degraded</td><td class=\"n\">0.031–0.032<", 1, "html")
    E("| recovered | 0.189 |", "| recovered | 0.170–0.189 |", 1, "md")
    E("<td>recovered</td><td class=\"n\">0.189<", "<td>recovered</td><td class=\"n\">0.170–0.189<", 1, "html")
    E("slightly better on a normal link and out of range (+0.012 to +0.018), about equal in the mission",
      "slightly better on a normal link (+0.001 to +0.016) and out of range (+0.012 to +0.018), slightly behind in the mission "
      "(0.117–0.122 against 0.126)")
    E("against 31 dBm on the Pis)", "against 31 dBm reported by the Pis' driver, its cap; their real output is likely lower)")
    E("at the measured 4 Mbit/s an 87 KB frame takes about 210 ms.", "at the measured 4 Mbit/s an 87 KB frame takes about 175 ms to transfer.")
    E("v4.1's Jetson power was not logged.", "v4.1's Jetson power was not logged (it was logged live for every strategy in G11 on Wi-Fi; on the mesh only the strategies that price it log it).")
    E("Without prices the controller is as accurate as v4.1 (-0.002 sAP", "Without prices the controller is almost as accurate as v4.1 (-0.002 sAP")
    E("filled = throttled in most of the window", "filled = throttled in at least half of the window", 1, "md")
    E("filled = throttled in most of the window", "filled = throttled in at least half of the window", 2, "html")

    # ---------------- Part 19 ----------------
    E("(22–25 Oct 2026; C1–C7 done)", "(22–26 Oct 2026; C1–C7 done; corrected 28 Oct)")
    E("with exact permutation p-values corrected by Holm within each campaign.",
      "with exact permutation p-values corrected by Holm over all unique comparisons of a campaign (a pair compared from both "
      "reference controllers is one comparison, listed once; until 28 Oct each reference was corrected separately and such "
      "pairs were listed twice).")
    E("**The holding rule changes no verdict.** The standard and the 'quality' sAP differ by at most a few percent in every campaign, and every comparison that was significant under one rule is significant under the other (C1).",
      "**The holding rule changes 1 verdict of 49.** The standard and the 'quality' sAP differ by at most a few percent in "
      "every campaign; the one comparison whose significance differs is A_full against A_stream in the forecaster-v1 "
      "campaign (Holm p 0.005 standard, 0.097 quality) (C1; corrected 28 Oct, it said no verdict changes).")
    E("(G13, 20 pairs each, p = 0.69)", "(G13, 20 pairs each, Holm p = 1.0)")
    E("the adaptive controllers keep P(AoI ≤ 300 ms) at 86–100 % with a 95th-percentile AoI of 0.2–0.4 s and no stretch with AoI > 300 ms longer than 0.2 s on the Part 12 campaign",
      "the adaptive controllers keep P(AoI ≤ 300 ms) at 86–100 % on average over the Part 12 campaign (80–100 % per scenario) "
      "with a 95th-percentile AoI of 0.2–0.4 s and stale stretches (AoI > 300 ms) of about 0.2 s on average, 0.5 s at worst")
    E("52 paired comparisons, Holm-corrected within each campaign as in 19.3.",
      f"{u} paired comparisons (a pair reached from both reference controllers counts once), Holm-corrected within each "
      f"campaign as in 19.3.")
    E("every campaign's sAP rises by a median factor of 2.3–2.6, and the ranking of the strategy × scenario cells is almost the same (rank correlation 0.90–1.00).",
      f"every campaign's sAP rises by a median factor of {r0:.1f}–{r1:.1f}, and the ranking of the strategy × scenario cells "
      f"is almost the same (rank correlation {q0:.2f}–{q1:.2f}; the pooled row is no longer counted as a cell).")
    E("Of the 52 paired comparisons, none changes from a significant win to a significant loss or back. 19 are significant with the VisDrone weights against 15 with the COCO weights: 4 comparisons",
      f"Of the {u} paired comparisons, none changes from a significant win to a significant loss or back. {sv} are "
      f"significant with the VisDrone weights against {sc} with the COCO weights: {g} comparisons")
    E("Comparisons whose verdict or sign changed:", "Comparisons whose verdict or sign changed (each pair once):", 1, "md")
    E("<p>Comparisons whose verdict or sign changed:</p>", "<p>Comparisons whose verdict or sign changed (each pair once):</p>", 1, "html")
    E("All 52 paired comparisons, COCO and VisDrone weights", f"All {u} paired comparisons, COCO and VisDrone weights", 1, "html")

    # ---------------- 19.7 ----------------
    E("| v4, v3, v3 + forecaster, no energy price |", "| v4, v2, v3 + forecaster (no energy price) |", 1, "md")
    E("<td class=\"n\">v4, v3, v3 + forecaster, no energy price</td>", "<td class=\"n\">v4, v2, v3 + forecaster (no energy price)</td>", 1, "html")
    E("v4.2 (decayed), v3 + forecaster, no energy price", "v4.2 (decayed), v3 + forecaster (no energy price)")
    E("stream objective, no prices, v5.1, v5", "v3 + forecaster (stream objective, no prices), v5.1, v5")
    E("No baseline is both more accurate and cheaper.",
      "No baseline is both more accurate and cheaper in camera-drone power; counting the Jetson that the adaptive controllers "
      "keep in the air (4–5 W), fixed offloading is the cheapest system (G10).")
    E("without the energy price (v3, v3 + forecaster,", "without the energy price (v2, v3 + forecaster,")
    E("set to the price v4's dual ascent itself settles at (Part 16)", "set to about the median price v4's dual ascent reached in G9 (Part 16)")

    # ---------------- Part 20 ----------------
    E("Both costs push latency up, and they buy no accuracy, because JPEG q90 is near-lossless for detection.",
      "Both costs push latency up, and they buy little accuracy: JPEG q90 loses 0.7 % on COCO and 4 % on aerial images, "
      "where an INT8 split is lossless (19.6).")
    E("**Evidence.** A closed-form bound, simulation, all 1,150 placements",
      "**Evidence.** A closed-form bound, simulation (a split wins by at most 0.47 % in 1,300 random systems), all 1,150 placements")
    E("beats v2 significantly over 20 paired runs (+0.0045 ± 0.0038 sAP, original scoring; standard sAP +0.0038, Holm p = 0.11; VisDrone detections +0.015, Holm p = 0.004)",
      "beats v2 over 20 paired runs (+0.0045 ± 0.0038 sAP, p = 0.021 in the original scoring; standard sAP +0.0038 ± 0.0039, "
      "Holm p = 0.22, not significant; VisDrone detections +0.015, Holm p = 0.007)")
    E("predicts deadline-met throughput per phase with correlation 0.947, in every phase.",
      "predicts deadline-met throughput per phase with correlation 0.947 over all 528 phases.")
    E("while being significantly more accurate than every other controller (+0.0074 ± 0.0030 sAP over v3 + forecasting v2)",
      "while being significantly more accurate than v2 and v3 + forecasting v2 (+0.0074 ± 0.0030 sAP over v3 + forecasting v2)")
    E("a priced controller is the most accurate strategy in every campaign and on the accuracy-versus-power front (19.7).",
      "a priced controller is the most accurate strategy in every campaign and on the accuracy-versus-camera-power front "
      "(19.7). Counting the edge drone, fixed offloading to the ground stays 2.5–2.7× more energy-efficient for the whole "
      "system (G10, G11).")
    E("The Jetson's power was modelled until 25 October and logged live since (profile within 0.1 W of live).",
      "The Jetson's power was modelled up to G9, logged live for every strategy in G11, and on the mesh for the strategies "
      "that price it (profile within 0.11 W of live).")
    E("The PDF's mothership split design was the worst placement measured (Part 8).",
      "The PDF's mothership split design was never on time: 2.7 frames/s against 15.2 for a JPEG to the laptop (only the Pi "
      "alone and the two-split chain were slower; Parts 7–8).")

    # ---------------- Parts 22-25 ----------------
    E("the work since (mesh campaigns, VisDrone replay, YOLO11, analyses, reports) is not yet committed.",
      "the work since (mesh campaigns, VisDrone replay, YOLO11, analyses, reports) is not yet committed. 28 Oct: full audit "
      "(`docs/audit_2026-10-28.md`), re-runnable checks in `scripts/audit_2026-10-28/`.")
    E("including the simulator tests. This matters because `simulation/stream_sim.py` gained the coordinator.",
      "including the simulator tests. This matters because `simulation/stream_sim.py` gained the coordinator. The hardware "
      "pipeline of Parts 12–19 has no unit tests; its results are cross-checked by `scripts/audit_2026-10-28/`.")
    E("`simulation/stream_sim.py` is the only modified tracked file (+124 lines). `validation/hardware/`, the new docs and `experiments/results/hardware/` are untracked. Ready to commit on `publication-overhaul` when you say so.",
      "the work since `08bc5a28` (branch `main`) is not yet committed; it is committed on your go-ahead.")
    E("**Still needs**: the campaign night itself (v4.2/v4.1/v4/v3+fc2/fixed, live logging on both boards) + the 24-min heat runs | Code done; one campaign night | 1–2 days |",
      "**Done**: the campaign (G11, 11 Oct) and the 24-min runs (G13) | — | — |", 1, "md")
    E("<td><s>Code + one campaign night</s> Code done; still needs the campaign night itself (v4.2/v4.1/v4/v3+fc2/fixed, live logging on both boards) + the 24-min heat runs</td><td>1–2 days</td>",
      "<td><b>Done</b>: the campaign (G11, 11 Oct) and the 24-min runs (G13)</td><td>—</td>", 1, "html")
    E("| Learned-split test: can a trained compressed split beat JPEG? | The laptop GPU free | 1–2 weeks, overnight |\n", "", 1, "md")
    E("<tr><td>Learned-split test: can a trained compressed split beat JPEG?</td><td>The laptop GPU free</td><td>1–2 weeks, overnight</td></tr>\n", "", 1, "html")
    E("— to be filled by `validation/hardware/tools/campaign_energy.sh` |",
      "(G11, 120 runs) |\n| `vid_campaign_mesh*/`, `vid_campaign_b/` | The mesh campaigns (18.8–18.10) and the relay campaign (18.3) |\n"
      "| `onboard_sap/`, `vd_variant_dets/` | Onboard emulation and the VisDrone detections of every setting (Parts 17, 19.5) |\n"
      "| `pareto_analysis.json/.md` | 19.7 |\n| `validation/hardware/edge_node.py` | The Jetson's decision program of the hierarchical chain |\n"
      "| `docs/controller_formulas.md` | The controllers' objective functions (Part 16) |\n"
      "| `docs/audit_2026-10-28.md`, `scripts/audit_2026-10-28/` | The 28 Oct audit and its re-runnable checks |", 1, "md")
    E("— to be filled by <code>validation/hardware/tools/campaign_energy.sh</code></td></tr>",
      "(G11, 120 runs)</td></tr>\n<tr><td><code>vid_campaign_mesh*/</code>, <code>vid_campaign_b/</code></td><td>The mesh campaigns "
      "(18.8–18.10) and the relay campaign (18.3)</td></tr>\n<tr><td><code>onboard_sap/</code>, <code>vd_variant_dets/</code></td>"
      "<td>Onboard emulation and the VisDrone detections of every setting (Parts 17, 19.5)</td></tr>\n<tr><td><code>"
      "pareto_analysis.json/.md</code></td><td>19.7</td></tr>\n<tr><td><code>validation/hardware/edge_node.py</code></td><td>The "
      "Jetson's decision program of the hierarchical chain</td></tr>\n<tr><td><code>docs/controller_formulas.md</code></td><td>The "
      "controllers' objective functions (Part 16)</td></tr>\n<tr><td><code>docs/audit_2026-10-28.md</code>, <code>"
      "scripts/audit_2026-10-28/</code></td><td>The 28 Oct audit and its re-runnable checks</td></tr>", 1, "html")
    gl = [("v4.1", "v4 plus a freshness price that keeps P(AoI ≤ 300 ms) near a 95 % target; the best controller overall."),
          ("v4.2, v5, v5.1", "v4.2 also prices the edge drone's energy; v5 adds a predictive heat price; v5.1 uses every price."),
          ("Holm correction", "Raises p-values when several comparisons are tested together, so that the chance of any false "
                              "\"significant\" result stays at 5 %."),
          ("Pareto front", "The strategies that no other strategy beats on both accuracy and power."),
          ("sAP50", "Streaming AP at an IoU threshold of 0.5 only (sAP averages 0.5–0.95)."),
          ("Holding rule", "Which arrived result the drone shows: the newest-captured one (standard) or the one with the "
                           "highest expected accuracy (quality)."),
          ("Ignored regions", "Image areas VisDrone marks as unlabelled; detections and objects inside them are not scored "
                              "in the masked metric."),
          ("Hierarchical chain", "Camera → Jetson, and the Jetson decides to detect or forward to the ground (18.6)."),
          ("Multihop", "The camera reaches the ground only through the Jetson (18.9).")]
    E("The best fixed strategy per phase, chosen with hindsight.",
      "The best fixed strategy per phase, chosen with hindsight (\"hindsight fixed\" in the tables)." +
      "".join(f"\n\n{t}\n\n{d}" for t, d in gl), 1, "md")
    E("<dd>The best fixed strategy per phase, chosen with hindsight.</dd>",
      "<dd>The best fixed strategy per phase, chosen with hindsight (\"hindsight fixed\" in the tables).</dd>" +
      "".join(f"\n<dt>{t}</dt><dd>{d}</dd>" for t, d in gl), 1, "html")
