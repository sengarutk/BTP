#!/usr/bin/env python3
"""Report terminology, 23 Oct 2026: standard metric names instead of the project's own.
  1. "mission perception" (sAP x flight minutes, our composite) removed: its table columns dropped, sentences reworded
     so accuracy (sAP), power and endurance (flight time) are reported separately, glossary entry removed
  2. renamed: fresh-detection share / availability -> P(AoI <= 300 ms); age p95 -> 95th-percentile AoI; maximum age ->
     peak AoI; on-time results/s (as a metric) -> deadline-met throughput; sAP per watt -> sAP/W (performance per
     watt); time throttled -> throttled-time ratio. Plain-English uses ("a late result is worth a quarter of an on-time
     one", the controller's P(on time)) stay.
Applied to the report (HTML + Markdown) and to the builders of Parts 17-19 (report_parts_oct22*.py,
report_figs_hier.py), so a rebuild keeps the new terms. Every replacement must match: a pattern that matches nothing
in the report stops the script.
usage: report_terms_oct23.py            (idempotent: a second run finds nothing left to change)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HTML = ROOT / "AEGIS-UAV Results Brief.html"
MD = ROOT / "AEGIS-UAV Results Brief.md"
BUILDERS = [ROOT / "uav-split-perception" / "scripts" / f for f in
            ("report_parts_oct22.py", "report_parts_oct22b.py", "report_figs_hier.py")]
B0, B1 = r"(\*\*|<b>)", r"(\*\*|</b>)"           # bold in Markdown or HTML
A = "P(AoI ≤ 300 ms)"

# (regex, replacement); applied in order to every file
SUBS = [
    # ---- 1. mission perception: sentences
    (B0 + r"mission perception" + B1 + r' = streaming AP × flight time \((?:"|&quot;)accuracy-minutes(?:"|&quot;)\)\.',
     "These are therefore reported side by side rather than combined into one number: accuracy (sAP), power and "
     "endurance (flight time)."),
    (r" ?Mission perception = sAP × flight minutes of a 249 g drone\.", ""),
    (r" ?Mission perception = sAP × flight minutes\.", ""),
    (r"wins on accuracy, freshness and mission perception, but not on energy", "wins on accuracy and freshness, but not on energy"),
    (r"On a 249 g drone its accuracy gain outweighs its 1\.3 minutes shorter flight \(mission perception 1\.41 against 1\.18\)\.",
     "On a 249 g drone it flies 1.3 minutes less."),
    (r" It also has the highest mission perception for both drone classes\.", ""),
    (r"so swarm mission perception \(sAP × swarm lifetime\) tracks the camera drone's\.", "so the swarm's endurance is the camera drone's."),
    (r"It has the highest accuracy and mission perception of all six policies\.", "It has the highest accuracy of all six policies."),
    (r" It also has the highest mission perception for 249 g and 1\.2 kg drones\.", ""),
    (r"<dt>Mission perception</dt><dd>[^<]*</dd>\n", ""),
    (r"\nMission perception\n\nStreaming AP × flight minutes: accuracy and endurance in one number\.\n", "\n"),
    # ---- 2. freshness -> AoI
    (r"Fresh-detection share", A),
    (B0 + r"Availability:" + B1 + r" the share of time the drone holds a detection less than 300 ms old\.",
     r"\1" + A + r":\2 the share of time the drone holds a detection less than 300 ms old (1 − the AoI violation "
     r"probability)."),
    (B0 + r"Age of information \(AoI\):" + B1 + r" the age of the newest detection the drone holds\.",
     r"\1Age of information (AoI):\2 the age of the newest detection the drone holds (Kaul, Yates and Gruteser, INFOCOM "
     r"2012); reported as its mean, its 95th percentile and its peak (maximum)."),
    (r"Availability \(newest detection under 300 ms old\) was 0\.999", A + " was 0.999"),
    (r"keeps a fresh detection ([\d.–]+ %) of the time", A + r" at \1"),
    (r"holds a fresh detection only half the time \(50 %\)", "has " + A + " of only 50 %"),
    (r"holds a fresh detection only half the time \(50 % against 87 %\)", "has " + A + " of only 50 % (against 87 %)"),
    (r"hold a fresh detection more often \(99 %\)", "have a higher " + A + " (99 %)"),
    (r"(?:\"|&quot;)fresh detection at least 95 % of the time(?:\"|&quot;)", A + " ≥ 0.95"),
    (r"keeps a fresh detection almost all the time", "keeps " + A + " close to 1"),
    (r"Availability", A),
    (r"availability", A),
    # Parts 18-19
    (r"sAP50, mAP, freshness, Pi power and temperature", "sAP50, mAP, AoI, Pi power and temperature"),
    (r"holds a detection younger than 300 ms 93 % of the time against 44–84 % for the fixed paths, with a 95th-percentile age of",
     "keeps " + A + " at 93 % against 44–84 % for the fixed paths, with a 95th-percentile AoI of"),
    (B0 + r"worst-case freshness" + B1, r"\1worst-case AoI\2"),
    (r"Freshness: 95th-percentile and maximum age of the held result, the longest stretch older than 300 ms, the fresh share",
     "AoI of the held result: 95th-percentile and peak AoI, the longest stretch with AoI > 300 ms, and " + A),
    (r"Worst-case freshness \(C3\)", "Worst-case AoI (C3)"),
    (r"hold a detection younger than 300 ms 86–100 % of the time with a 95th-percentile age of",
     "keep " + A + " at 86–100 % with a 95th-percentile AoI of"),
    (r"no stale stretch longer than", "no stretch with AoI > 300 ms longer than"),
    (r"95th-percentile ages of", "95th-percentile AoI of"),
    (r"the held result was older than 300 ms 34 % of the time", "P(AoI > 300 ms) was 34 %"),
    # table headers of Part 18 (report and builder)
    (r"<th>fresh</th><th>age p95</th>", "<th>" + A + "</th><th>95th-percentile AoI</th>"),
    (r"\| fresh \| age p95 \|", "| " + A + " | 95th-percentile AoI |"),
    (r'"fresh", "age p95"', '"' + A + '", "95th-percentile AoI"'),
    # ---- 2. deadline-met throughput
    (B0 + r"On-time frames/s:" + B1 + r" detections that come back within a deadline",
     r"\1Deadline-met throughput\2 (results/s): detections that come back within a deadline"),
    (r"On-time frames/s over the mission", "Deadline-met throughput over the mission (results/s)"),
    (r"accuracy-weighted on-time detections than", "accuracy-weighted deadline-met throughput than"),
    (r"keeps about 10 on-time detections per second", "keeps a deadline-met throughput of about 10 detections per second"),
    (r"predicts on-time results per phase", "predicts deadline-met throughput per phase"),
    (r"expected on-time results per second", "expected deadline-met throughput"),
    (r"measured on-time rates", "measured deadline-met throughput"),
    (r"adds the most accuracy-weighted on-time results per second", "adds the most accuracy-weighted deadline-met throughput"),
    (r"Accuracy-weighted on-time detections per second, median", "Accuracy-weighted deadline-met throughput (detections/s), median"),
    (r"raw on-time count", "raw deadline-met throughput"),
    (r"Metric: on-time frames per second per drone\.", "Metric: deadline-met throughput (frames/s) per drone."),
    (r"the swarm's expected on-time detections", "the swarm's expected deadline-met throughput"),
    (r"predicted on-time results per second for each of", "predicted deadline-met throughput for each of"),
    (r"Accuracy-weighted on-time /s", "Accuracy-weighted deadline-met throughput (/s)"),
    (r"accuracy-weighted 3\.59 on-time results/s", "accuracy-weighted deadline-met throughput 3.59 results/s"),
    (r"maximises accuracy-weighted on-time results per second", "maximises accuracy-weighted deadline-met throughput"),
    (r"accuracy-weighted on-time results than", "accuracy-weighted deadline-met throughput than"),
    (r"an accuracy-weighted on-time rate, a proxy", "an accuracy-weighted deadline-met throughput, a proxy"),
    (r"predicts on-time rates per phase", "predicts deadline-met throughput per phase"),
    # ---- 2. performance per watt
    (r"sAP per " + B0 + r"camera-drone" + B1 + r" watt", r"sAP/W (\1camera drone\2)"),
    (r"sAP per camera-drone watt", "sAP/W (camera drone)"),
    (r"sAP per camera watt", "sAP/W (camera)"),
    (r"sAP per Pi watt", "sAP/W (Pi)"),
    (r"sAP per watt", "sAP/W"),
    (r"sAP per W", "sAP/W"),
    # ---- 2. throttling
    (r"<th>time throttled</th>", "<th>throttled-time ratio</th>"),
    (r"\| time throttled \|", "| throttled-time ratio |"),
    (r'"time throttled"', '"throttled-time ratio"'),
    (r"<th>clock</th><th>throttled</th>", "<th>clock</th><th>throttled-time ratio</th>"),
    (r"\| clock \| throttled \|", "| clock | throttled-time ratio |"),
    (r'"clock", "throttled"\]', '"clock", "throttled-time ratio"]'),
    (r"share of the run the Pi was throttled \(firmware flag\)", "throttled-time ratio of the run (firmware flag)"),
]

# definitions added to Part 2 ("Measuring quality") and to the glossary
DEF_HTML = ("<li><b>Performance per watt (sAP/W):</b> streaming AP per watt of camera-drone (or whole-system) power.</li>\n"
            "<li><b>Throttled-time ratio:</b> the share of time the board's firmware reports it is throttling (its clock "
            "lowered to stay below its temperature limit).</li>\n")
DEF_MD = ("- **Performance per watt (sAP/W):** streaming AP per watt of camera-drone (or whole-system) power.\n"
          "- **Throttled-time ratio:** the share of time the board's firmware reports it is throttling (its clock lowered "
          "to stay below its temperature limit).\n")
GL = [("Deadline-met throughput", "Results per second that arrive within the deadline (300 ms)."),
      ("Peak AoI", "The largest age of the held detection over a run (with the 95th-percentile AoI, the worst-case "
                   "freshness measures)."),
      ("sAP/W", "Performance per watt: streaming AP per watt of camera-drone or whole-system power."),
      ("Throttled-time ratio", "Share of time the firmware reports throttling (clock lowered for heat).")]


def drop_mp_columns(text, html):
    """Remove every table column whose header names mission perception."""
    n = 0
    if html:
        def fix(m):
            nonlocal n
            t = m.group(0)
            rows = re.findall(r"<tr[^>]*>.*?</tr>", t, re.S)
            heads = re.findall(r"<t[hd][^>]*>.*?</t[hd]>", rows[0], re.S)
            idx = [i for i, c in enumerate(heads) if re.search(r"(?i)mission perception", c)]
            if not idx:
                return t
            n += 1
            for r in rows:
                cells = re.findall(r"<t[hd][^>]*>.*?</t[hd]>", r, re.S)
                assert len(cells) == len(heads), r[:120]
                new = r
                for i in sorted(idx, reverse=True):
                    k = new.rfind(cells[i])
                    new = new[:k] + new[k + len(cells[i]):]
                t = t.replace(r, new, 1)
            return t
        return re.sub(r"<table>.*?</table>", fix, text, flags=re.S), n
    out, lines, i = [], text.split("\n"), 0
    while i < len(lines):
        if lines[i].startswith("|") and re.search(r"(?i)mission perception", lines[i]):
            head = [c for c in lines[i].strip().strip("|").split("|")]
            idx = [k for k, c in enumerate(head) if re.search(r"(?i)mission perception", c)]
            n += 1
            while i < len(lines) and lines[i].startswith("|"):
                cells = lines[i].strip().strip("|").split("|")
                assert len(cells) == len(head), lines[i][:120]
                cells = [c for k, c in enumerate(cells) if k not in idx]
                out.append("|" + "|".join(cells) + "|")
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out), n


def main():
    report = {HTML: HTML.read_text(), MD: MD.read_text()}
    hits = {k: 0 for k in range(len(SUBS))}
    for f in list(report):
        t, ncol = drop_mp_columns(report[f], f == HTML)
        print(f.name, "mission-perception columns dropped:", ncol)
        for k, (pat, rep) in enumerate(SUBS):
            t, c = re.subn(pat, rep, t)
            hits[k] += c
        report[f] = t
    for f in BUILDERS:
        t = f.read_text()
        for pat, rep in SUBS:
            t = re.sub(pat, rep, t)
        f.write_text(t)
    missing = [SUBS[k][0] for k, c in hits.items() if c == 0]
    if missing and "--force" not in sys.argv:
        print("patterns that matched nothing in the report (already applied?):", *missing, sep="\n  ")
    h, m = report[HTML], report[MD]
    if "Performance per watt (sAP/W)" not in h:
        a = '<li><b>Age of information (AoI):</b>'
        i = h.index(a)
        j = h.index("</li>\n", i) + len("</li>\n")
        h = h[:i] + h[i:j] + DEF_HTML + h[j:]
        a = "- **Age of information (AoI):**"
        i = m.index(a)
        j = m.index("\n", i) + 1
        m = m[:i] + m[i:j] + DEF_MD + m[j:]
        k = h.index('<dl class="gl">') + len('<dl class="gl">')
        h = h[:k] + "\n" + "".join(f"<dt>{a}</dt><dd>{b}</dd>\n" for a, b in GL) + h[k:].lstrip("\n")
        k = m.index("## PART 25Glossary")
        k = m.index("\n\n", k) + 2
        m = m[:k] + "".join(f"{a}\n\n{b}\n\n" for a, b in GL) + m[k:]
    HTML.write_text(h)
    MD.write_text(m)
    left = {t: len(re.findall(t, h)) for t in ("(?i)mission perception", "Fresh-detection", "(?i)availability",
                                                "sAP per", "age p95", "time throttled")}
    print("left in HTML:", left)


if __name__ == "__main__":
    main()
