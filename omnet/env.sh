# Source this to use OMNeT++ 6.3 + INET 4.5.4 + Simu5G 1.6.0 built in /home/sengar/BTP/omnet
__oldpwd="$PWD"
cd /home/sengar/BTP/omnet/omnetpp-omnetpp-6.3.0 && source setenv -f >/dev/null 2>&1
cd /home/sengar/BTP/omnet/inet4.5 && source setenv -f >/dev/null 2>&1
cd /home/sengar/BTP/omnet/Simu5G-1.6.0 && source setenv -f >/dev/null 2>&1
cd "$__oldpwd"
