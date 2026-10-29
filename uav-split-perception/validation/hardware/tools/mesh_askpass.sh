#!/bin/sh
# SSH_ASKPASS for the mesh: picks the password by the user in the prompt; passwords only from environment variables
case "$1" in *dubey@*) printf "%s\n" "$PI3_PW";; *sengar@*) printf "%s\n" "$PI2_PW";; *nano@*) printf "%s\n" "$NANO_PW";; esac
