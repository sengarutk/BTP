import re
L = open("/home/sengar/BTP/AEGIS-UAV Results Brief.md").read().split("\n")
def sec(a, b): return "\n".join(L[a - 1:b])
p1 = sec(37, 82); p20 = sec(2031, 2103); p11 = sec(318, 357); p16 = sec(1054, 1251)
body = "\n".join(L[82:2030])
num = re.compile(r"(?<![\w.])[+−-]?\d+(?:[.,]\d+)?\s?(?:%|×|W|°C|ms|s|fps)?")
for name, txt, ex in (("Part 1", p1, sec(83, 2400)), ("Part 20", p20, sec(83, 2030)), ("Part 11", p11, sec(358, 2400)), ("Part 16", p16, sec(83, 1053) + sec(1252, 2400))):
    exn = ex.replace("−", "-")
    miss = []
    for m in re.finditer(r"(?<![\w.])(\d+\.\d+|\d{2,}(?:,\d{3})*)(\s?%|×| W| °C| ms)?", txt.replace("−", "-")):
        tok = m.group(1)
        if tok in ("2026", "2025", "2024", "2023", "2022", "2020", "2019", "2015", "2009"): continue
        if tok not in exn: miss.append(m.group(0))
    print(name, "numbers not found anywhere in the body:", sorted(set(miss)))
