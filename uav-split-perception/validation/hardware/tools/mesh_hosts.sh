#!/bin/bash
# mesh_hosts.sh - the AegisSwarm mesh map, sourced by mesh_ssh.sh, mesh_scp.sh, mesh_tunnel.sh and arun_mesh.sh.
# Verified 14 Nov 2026 (hostname, bat0 address and radio MAC read on each board). The laptop reaches the mesh only
# through pi-sender (ground radio; cable 10.230.3.10); every drone is reached with ssh -J dubey@10.230.3.10.
#   target   board         login    mesh address  radio MAC          role
#   sender   pi-sender     dubey    10.1.0.12     88:a2:9e:4c:87:54  ground radio (cable to the laptop)
#   camera   pi-relayyy    sengar   10.1.0.11     88:a2:9e:4c:95:78  sense drone S1 (the camera of every campaign so far)
#   camera2  pi-receiver   sengar   10.1.0.13     88:a2:9e:4c:94:40  sense drone S2 (new 14 Nov)
#   jetson   nano          nano     10.1.0.14     58:02:05:de:50:ff  edge drone E1, Jetson Orin Nano (radio wlP1p1s0)
#   jetson2  nano2         nano2    10.1.0.15     f8:3d:c6:57:2d:5d  edge drone E2, Jetson Orin Nano Super (radio wlP1p1s0)
# Until 13 Nov the scripts used the 23 Oct addresses (pi-sender .11, pi-relayyy .12, Jetson .13); the boards' radios
# (MACs) are unchanged, so the MAC-based route checks of earlier campaigns still name the same boards.
# Passwords (env only, never stored): PI3_PW dubey, PI2_PW sengar (both camera Pis), NANO_PW nano, N2_PW nano2.
SENDER_CABLE=10.230.3.10
SENDER_IP=10.1.0.12;  SENDER_MAC=88:a2:9e:4c:87:54
CAM_IP=10.1.0.11;     CAM_MAC=88:a2:9e:4c:95:78
CAM2_IP=10.1.0.13;    CAM2_MAC=88:a2:9e:4c:94:40
JET_IP=10.1.0.14;     JET_MAC=58:02:05:de:50:ff
JET2_IP=10.1.0.15;    JET2_MAC=f8:3d:c6:57:2d:5d
JUMP="-J dubey@$SENDER_CABLE"
mesh_target() {   # sets H (user@address) and J (jump option) for a target name; returns 2 for an unknown target
  case $1 in
    sender)  H=dubey@$SENDER_CABLE; J=;;
    camera)  H=sengar@$CAM_IP;  J=$JUMP;;
    camera2) H=sengar@$CAM2_IP; J=$JUMP;;
    jetson)  H=nano@$JET_IP;    J=$JUMP;;
    jetson2) H=nano2@$JET2_IP;  J=$JUMP;;
    *) echo "unknown target '$1' (sender|camera|camera2|jetson|jetson2)" >&2; return 2;;
  esac
}
