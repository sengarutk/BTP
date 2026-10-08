#!/bin/sh
# SSH_ASKPASS helper: prints the password from the SSHPW environment variable (never stored in a file)
printf "%s\n" "$SSHPW"
