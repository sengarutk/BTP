"""Example policy for the open benchmark (benchmark/aegis_bench.py): a goodput-threshold rule with a heat guard.

Send the frame to the laptop at the highest JPEG setting when its goodput estimate is high, at a smaller one when it
is moderate, to the Jetson when only the Jetson link is usable, and run the smallest onboard model otherwise; never
start onboard work above 80 C. It prices nothing and forecasts nothing: a simple reference to beat.
"""


def decide(rp, t):
    lap, jet = rp.links["laptop"], rp.links["jetson"]
    g_lap, g_jet = lap.est(t)[0], jet.est(t)[0]
    if lap.idle(t) and g_lap >= 8.0:
        return ("laptop", "m640q90")
    if lap.idle(t) and g_lap >= 3.0:
        return ("laptop", "s320q50")
    if jet.idle(t) and g_jet >= 3.0:
        return ("jetson", "s320q50")
    if rp.onb_free <= t and rp.temp < 80.0:
        return ("onboard", "n320")
    return None
