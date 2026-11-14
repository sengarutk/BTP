# Mesh session log (14 Nov 2026, IST)

Plan: `docs/mesh_work_plan_nov14.md`. Rules: no change to the mesh configuration (SSID, BSSID, channel, addresses,
batman-adv settings); temporary nft/tc rules removed after use; results never deleted; passwords only in environment
variables.

## Setup

| Time | Item | What was done | Check |
|---|---|---|---|
| 19:08 | Map | Read hostname, bat0 address and radio MAC on all five boards; batman-adv originator tables | Full mesh: every board hears the other four directly |
| 19:12 | A1 scripts | `tools/mesh_hosts.sh` (new): the board map. `mesh_ssh.sh`, `mesh_scp.sh`: targets sender, camera, camera2, jetson, jetson2. `mesh_askpass.sh`: Nano2 (N2_PW). `mesh_tunnel.sh`: new addresses. `arun_mesh.sh`: camera address for the Jetson worker and edge node; multihop blocks the camera's links to pi-receiver and Nano2 too, so the relay stays Nano1 | `bash -n`; live tests below |
| 19:16 | A2 pi-receiver | Copied pi-relayyy's `~/btp_env` and `~/hwbench` (code, weights, VisDrone clip; not results or its mesh scripts) board to board over the mesh | 29,641 files, byte totals equal; torch 2.14.1+cpu, ultralytics 8.4.183; YOLOv8s 320 px inference 114 ms |
| 19:21 | A3 Nano2 | Copied Nano1's `~/hwbench_env` (torch 2.14.1+cu130 with its own CUDA 13 runtime) and `~/hwbench`; venv paths rewritten from /home/nano to /home/nano2 in `bin/` only | 31,107 files, byte totals equal; CUDA on Orin; YOLOv8s 640 px FP16 median 32 ms (with pre/post-processing) |
| 19:28 | A4 push | Board copies of every pushed file saved to `~/hwbench/_prev_20261114/`; `TARGETS="camera camera2 jetson jetson2" push_code_mesh.sh` (now ends with an md5 check) | MD5_OK on all four; planner imports on both Pis; `adaptive`, `edge_node`, `adaptive2` import on both Nanos |
| 19:29 | energy constants | Boards had the 8 Oct `energy_constants.json` (thermal fit 34.43 + 12.73 P, used by every earlier heat-priced run); repository has the 28 Oct fit 37.26 + 11.31 P; only `pi/thermal_steady` differs. Repository version pushed | old copy in `_prev_20261114/` |
| 19:30 | Power modes | Nano1 15 W (GPU ≤ 625 MHz, as in every campaign); Nano2 25 W (GPU ≤ 918 MHz, its default). Not changed | — |
| 19:31 | Power save | "on" on both camera Pis; earlier mesh campaigns never changed it. Off on pi-receiver: ping RTT unchanged (5.6 vs 5.6 ms mean), so no effect in IBSS mode; restored to on | — |
| 19:33 | A6 health | `tools/mesh_health.sh` (new, read-only) | HEALTH_OK: 4 neighbours each, no leftover rule or process, no throttling; clock offsets pi-sender −1496 s, Nano1 +36 s (logged, not corrected) |
| 19:34 | Multihop | arun_mesh.sh's rules applied and removed | Route camera → pi-sender via Nano1 after 5 s; 20/20 pings, 10.6 ms mean; direct route back at once; HEALTH_OK after |
| 19:36 | Laptop | `mesh_tunnel.sh` (48101 → 10.1.0.11, 48104 → 10.1.0.14), keep-awake ping, 1-s ping log | both ports listening |

Open decisions (plan A7-A9): pi-sender's cable address and Nano2's mesh setup stay runtime-only (lost on reboot).
