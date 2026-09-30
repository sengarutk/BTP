# Simulator validation: ns-3, OMNeT++, a real network stack

The system results of the paper come from the Python simulator in `simulation/`. This folder checks
that simulator against two independent packet-level simulators, **ns-3.48** and **OMNeT++ 6.3**
(INET 4.5.4, Simu5G 1.6.0), against the real Linux network stack, and checks the channel generator
against theory. It also re-runs the system study with link and sharing models calibrated to what
those checks found. `docs/assumptions_and_validation.md` lists every model input and its status.

| Check | Tool / scenario | What is compared | Script |
|---|---|---|---|
| C1 | (statistics) | Rician K-factor, Clarke/Jakes autocorrelation, Gudmundson shadowing of `trace_generator.py` against theory | `run_channel_statistics.py`, `tests/test_channel_statistics.py` |
| V1 | ns-3 `ns3/a2a_wifi.cc` | Air-to-air 802.11ax goodput vs. distance (full PHY/MAC, every fixed MCS and IdealWifiManager; 802.11 minimum-sensitivity and SNR-limited receivers) against `a2a_rate_mbps` | `run_link_validation.py --which a2a` |
| V2 | ns-3 `ns3/lte_uplink.cc` | Cellular uplink goodput vs. SINR (LTE, 20 MHz, MI error model, HARQ) against the TR 36.942 mapping of `trace_generator.py` | `run_link_validation.py --which lte` |
| V3/V4 | ns-3 `ns3/stream.cc` | On-time frames/s per UAV for the same traces, frames, onboard times and frame logic, over real TCP and a fair-queued shared cell, against `stream_sim.py` | `run_stream_validation.py` |
| V5 | Linux TCP over loopback + `tc netem` | Real frames, real codecs, real server-side models, real TCP; on-time frames/s against `stream_sim.py` on the same constant link | `run_emulation.py` (needs sudo for netem) |
| O1 | Simu5G `omnetpp/simu5g` RateVsSinr | 5G NR uplink goodput vs. SINR against TR 36.942 and ns-3 LTE | `run_omnetpp_validation.py --which o1` |
| O2 | Simu5G CellSharing | N saturated UAVs on one gNB (PF scheduler): per-UAV share and Jain fairness against water-filling | `run_omnetpp_validation.py --which o2` |
| O2b | Simu5G CellSharingMixed | 5 light + 5 saturated UAVs against water-filling | `run_omnetpp_validation.py --which o2b` |
| O3 | Simu5G FrameStream (`omnetpp/uavapp`) | Frame streaming over the full 5G stack | not usable: Simu5G loses or delays large bursts (see below) |
| O4 | INET `omnetpp/inet_a2a` | 802.11ac A2A range of every MCS: INET, ns-3 (`a2a_wifi.cc --standard=ac --aggregation=false`) and the Python PHY model | `run_omnetpp_a2a.py` |
| O5 | ns-3 `ns3/relay.cc` | Two-hop relay: A2A frame transfer time and whole relay-path latency against the Python relay model | `run_relay_validation.py` |
| Calibrated | (V1/V2 output) | Every system-level conclusion, re-computed with ns-3-calibrated link models | `run_calibrated_system.py` |
| Sharing | (O2 output) | Swarm conclusions under the unfair sharing Simu5G showed (`capped`, `weighted`) | `run_sharing_sensitivity.py` |
| Forwarding | (O5 output) | Swarm relay results with packet forwarding and ns-3 A2A rates | `run_relay_forwarding.py` |

Results are written to `experiments/results/validation/`. The raw ns-3 output is kept there, so the
comparisons can be recomputed without ns-3.

## Building ns-3

```bash
cd /path/to/workdir
curl -LO https://www.nsnam.org/releases/ns-allinone-3.48.tar.bz2 && tar xjf ns-allinone-3.48.tar.bz2
cd ns-allinone-3.48/ns-3.48
for f in /path/to/uav-split-perception/validation/ns3/*.cc; do ln -sf "$f" scratch/; done
./ns3 configure --build-profile=optimized --disable-examples --disable-tests --disable-python-bindings \
  --enable-modules "wifi;lte;point-to-point;applications;internet;mobility;propagation;traffic-control"
./ns3 build -j 8
```

Then, from the repository root, with `NS3_DIR` pointing at the `ns-3.48` folder:

```bash
NS3_DIR=/path/to/ns-3.48 python -m validation.run_link_validation
NS3_DIR=/path/to/ns-3.48 python -m validation.run_stream_validation
NS3_DIR=/path/to/ns-3.48 python -m validation.run_relay_validation
python -m validation.run_calibrated_system
python -m validation.run_relay_forwarding
python -m validation.run_channel_statistics
```

## Building OMNeT++, INET and Simu5G

Headless (no Qtenv, no OSG), clang:

```bash
cd /path/to/omnet
curl -LO https://github.com/omnetpp/omnetpp/archive/refs/tags/omnetpp-6.3.0.tar.gz   # source tarball
tar xzf omnetpp-6.3.0.tar.gz && cd omnetpp-omnetpp-6.3.0
cp configure.user.dist configure.user   # set PREFER_CLANG=yes, WITH_QTENV=no, WITH_OSG=no, WITH_OSGEARTH=no
source setenv -f && ./configure && make -j 8 MODE=release
cd .. && curl -LO https://github.com/inet-framework/inet/releases/download/v4.5.4/inet-4.5.4-src.tgz
tar xzf inet-4.5.4-src.tgz && cd inet4.5 && source setenv -f && make makefiles && make -j 8 MODE=release
cd .. && curl -LO https://github.com/Unipisa/Simu5G/archive/refs/tags/v1.6.0.tar.gz
tar xzf v1.6.0.tar.gz && cd Simu5G-1.6.0 && source setenv -f && make makefiles && make -j 8 MODE=release
```

A shell file that sources the three `setenv` scripts (default `/home/sengar/BTP/omnet/env.sh`,
override with `OMNET_ENV`) is used by the runners. The frame-streaming app of O3 is built with

```bash
cd validation/omnetpp/uavapp
opp_makemake -f --make-so -o uavapp -O out -I$INET_ROOT/src -L$INET_ROOT/src -lINET\$\(D\) -DINET_IMPORT && make MODE=release
```

Then `python -m validation.run_omnetpp_validation` (O1, O2, O2b) and `python -m validation.run_omnetpp_a2a` (O4).
Simu5G 1.6.0 needs several GB per run when saturated UAVs offer far more than their share at
N >= 10, so the runner caps each run at 4 GB and uses 2 workers.

## Emulation over the real network stack (V5)

`run_emulation.py` streams real COCO frames through the real codecs (INT8+zstd split packets with
the authenticated wire format, or JPEG Q90) over TCP on 127.0.0.1, shaped by `tc netem` (rate,
delay), to a server running the real server-side models on the GPU. The UAV side follows the frame
logic of the simulator, with the onboard time padded to the modelled value. `tc` needs root: the
script reads the sudo password from the `SUDO_PASS` environment variable (never store it in a
file) and always removes the qdisc afterwards. The UAV releases the uplink when all bytes are
acknowledged and the server has returned the result, which costs about two one-way delays per
frame; the simulator is run with the same rule (`release_extra_ms`) and without it.

## Modelling choices in the ns-3 scenarios

- **Same inputs.** V3/V4 feed ns-3 the exact channel traces the Python simulator generates for the
  same seeds, and the measured frame size, onboard time and server time of each configuration.
- **Same frame logic.** Camera ticks, sequential onboard processing, newest-frame-wins buffering,
  one frame on the uplink at a time (released when its last byte is transmitted on the UAV's link,
  or when it is delivered or abandoned at its deadline), and the deadline test.
- **Different network.** Real TCP (Cubic, 1400-byte segments) on a link whose rate and loss follow
  the trace every 10 ms, and a shared bottleneck with FQ-CoDel for swarms, instead of the fluid
  water-filling model.
- **Delay.** Packets travel with the trace's mean delay; changing the delay every slot would
  reorder a flow's packets, which cellular links do not do. Each frame's latency adds the slot's
  deviation from the mean, as the Python simulator does.
- **Measurement windows.** Link goodput counts only bytes received inside the measurement window.
- **O4 aggregation.** INET's 802.11 DCF sends one MPDU per channel access, so ns-3 is run with
  A-MPDU/A-MSDU off for O4. Both simulators then differ in MAC overhead (INET delivers 0.73-0.92x
  ns-3's goodput at 10 m), so O4 compares the *range* of each MCS: goodput at each distance
  normalised by the same MCS's goodput at 10 m, against 1 - PER of the Python model. In INET, set
  the band and channel on the radio (`**.wlan[*].radio.bandName = "5 GHz"`, `channelNumber = 157`),
  and set the mobility type only on the hosts: `**.mobility.typename` also creates a randomly placed
  mobility module inside every antenna.
- **O3 (not usable).** Simu5G's NR uplink does not carry bursts of many datagrams after idle periods
  reliably: with RLC UM, bursts of more than about 50 datagrams lose segments at reassembly, so
  every 93 KB frame arrives incomplete; with RLC AM (1.5.2 crashes; 1.6.0 runs), frames take
  400-530 ms. Pacing the datagrams, renaming packets and a larger reordering window did not help.
  Steady traffic (O1, O2) is unaffected. Frame streaming is therefore validated in ns-3 (V3/V4) and
  over the real stack (V5) only.
