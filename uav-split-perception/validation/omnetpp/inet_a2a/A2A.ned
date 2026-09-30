// O4: air-to-air 802.11ac link between two UAVs (INET), for comparison with ns-3 (V1 in ac mode).
package inetvalidation;

import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.node.inet.AdhocHost;
import inet.physicallayer.wireless.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;

network A2A
{
    submodules:
        radioMedium: Ieee80211ScalarRadioMedium;
        configurator: Ipv4NetworkConfigurator;
        uav[2]: AdhocHost;
}
