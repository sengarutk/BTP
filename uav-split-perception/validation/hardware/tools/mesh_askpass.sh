#!/bin/sh
# SSH_ASKPASS for the mesh: picks the password by the user in the prompt; passwords only from environment variables
# (dubey = pi-sender PI3_PW; sengar = pi-relayyy and pi-receiver PI2_PW; nano = Nano1 NANO_PW; nano2 = Nano2 N2_PW)
case "$1" in *dubey@*) printf "%s\n" "$PI3_PW";; *sengar@*) printf "%s\n" "$PI2_PW";; *nano2@*) printf "%s\n" "$N2_PW";;
  *nano@*) printf "%s\n" "$NANO_PW";; esac
