"""Second pass of the 28 Oct 2026 corrections (statements found stale after the first pass)."""


def register(E, info):
    E("the standard holding rule and the masking of ignored regions change no verdict;",
      "masking the ignored regions changes no verdict and the holding rule changes 1 of 49 (Part 14);")
    E("× 4 strategies (onboard, split at layer 4 with INT8+zstd, JPEG q90, adaptive) = 384 cells,",
      "× 4 strategies (onboard, split at layer 4 with INT8+zstd, JPEG q90, adaptive) = 384 cells (the two coordinated "
      "variants added below make 6 strategies and 576 cells, the grid re-weighted in 19.6),")
    E("compare within one campaign only.",
      "compare within one campaign only.\n- Camera ticks the Pi's loop skipped under load (0 for fixed offloading, about 12 of "
      "3,600 for the adaptive controllers, up to 34 of 7,200 without prices on the mesh) are not scored; scoring them, holding "
      "the newest result, changes sAP by at most ±0.22 % (5 runs checked, 28 Oct).", 1, "md")
    E("compare within one campaign only.</li>",
      "compare within one campaign only.</li>\n<li>Camera ticks the Pi's loop skipped under load (0 for fixed offloading, "
      "about 12 of 3,600 for the adaptive controllers, up to 34 of 7,200 without prices on the mesh) are not scored; scoring "
      "them, holding the newest result, changes sAP by at most ±0.22 % (5 runs checked, 28 Oct).</li>", 1, "html")
    rows = [("The Pi's thermal fit admitted the 50 %-duty level (83.8 °C, clock already lowered) as \"below the throttle "
             "limit\" (`energy_model.py`)", "T = 34.4 + 12.7 × P instead of 37.3 + 11.3 × P: steady temperatures 2–5 °C too "
             "high at 4–5 W (G5–G7); v5 ran with this fit", "Fit only levels below 80 °C (28 Oct); constants and energy rescoring "
             "regenerated (only the steady temperatures change)"),
            ("Onboard emulation kept the fresh AP of its last latency (6 s: every 180th frame) (`onboard_sap.py`)",
             "17.7 \"fresh AP (no delay)\" 0.17–0.22 instead of 0.20–0.25", "Fresh AP over all frames (28 Oct); every sAP "
             "value regenerates identically"),
            ("Holm per reference controller; a pair reached from both references counted twice (`report_rescore.py`)",
             "19.5 said 52 comparisons, 19 significant, 4 newly significant (unique: 49, 18, 3); two families per campaign "
             "not corrected jointly", "Holm over the unique comparisons of a campaign (28 Oct); no verdict changes"),
            ("VisDrone rescoring copied the COCO 'quality'-rule values (`report_rescore.py --visdrone`)", "Not printed in the "
             "brief", "Left out with --visdrone (28 Oct)"),
            ("19.5 counted the pooled row as a strategy × scenario cell (`report_c7_oct25.py`)", "Cells 45/15/… instead of "
             "36/12/…; rank correlation 0.90 instead of 0.92 at the low end", "Pooled row excluded (28 Oct)"),
            ("Pareto labels: v2 named \"v3\", labels with commas (`report_pareto_oct26.py`)", "19.7 dominated lists read as "
             "extra or duplicate strategies", "Labels fixed (28 Oct)"),
            ("Campaign summaries not regenerated after the Student-t fix", "About 45 intervals of Parts 12–16 still 7–14 % "
             "too narrow; v3 + forecasting v2 over v2 appeared significant with the standard rule", "All summaries "
             "regenerated (28 Oct; only interval fields change); text updated")]
    anchor_md = ("| Exact t quantiles (26 Oct); Part 19 and every mesh, relay and Pareto output regenerate identically |")
    anchor_html = ("<td>Exact t quantiles (26 Oct); Part 19 and every mesh, relay and Pareto output regenerate identically</td></tr>")
    E(anchor_md, anchor_md + "".join(f"\n| {a} | {b} | {c} |" for a, b, c in rows), 1, "md")
    code = lambda t: __import__("re").sub(r"`([^`]+)`", r"<code>\1</code>", t)  # noqa: E731
    E(anchor_html, anchor_html + "".join(f"\n<tr><td>{code(a)}</td><td>{code(b)}</td><td>{code(c)}</td></tr>"
                                         for a, b, c in rows), 1, "html")
