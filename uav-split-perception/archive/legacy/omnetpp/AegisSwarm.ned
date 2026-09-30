package aegis_uav.simulations;

import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.node.inet.StandardHost;
import inet.physicallayer.wireless.common.contract.packetlevel.IRadioMedium;
import inet.visualizer.contract.IIntegratedVisualizer;

//
// AegisSwarm: Multi-UAV Scalable Split Perception Network Topology.
// Connects N UAV nodes to a 5G gNodeB base station and Ground Cloud Host,
// supporting A2A 802.11ax mesh relaying and shared cellular uplink contention.
//
network AegisSwarm
{
    parameters:
        @display("bgb=1500,1500;bgg=100,1,grey95");
        
        // Swarm sizing & physical configuration
        int numUavs = default(10);
        double cellCapacityMbps = default(200.0);
        double a2aFrequencyGhz = default(5.8);
        double cellularFrequencyGhz = default(3.5);
        double playgroundWidth @unit(m) = default(1000m);
        double playgroundHeight @unit(m) = default(1000m);

    submodules:
        configurator: Ipv4NetworkConfigurator {
            parameters:
                @display("p=100,100;is=s");
        }
        
        visualizer: <default("IntegratedMultiVisualizer")> like IIntegratedVisualizer if typename != "" {
            parameters:
                @display("p=100,200;is=s");
        }
        
        // 5G NR Cellular Physical Radio Medium (3.5 GHz)
        cellularRadioMedium: <default("Ieee80211ScalarRadioMedium")> like IRadioMedium {
            parameters:
                @display("p=100,300;is=s");
        }
        
        // 802.11ax Wi-Fi 6 A2A Mesh Radio Medium (5.8 GHz)
        a2aRadioMedium: <default("Ieee80211ScalarRadioMedium")> like IRadioMedium {
            parameters:
                @display("p=100,400;is=s");
        }
        
        // Cellular 5G NR gNodeB Base Station
        gNodeB: StandardHost {
            parameters:
                @display("p=750,750;i=device/antennatower;is=vl");
                numWlanInterfaces = 0;
        }
        
        // Centralized Ground Station (Edge-Cloud GPU Inference Server)
        groundStation: StandardHost {
            parameters:
                @display("p=1300,750;i=device/server;is=l");
                numWlanInterfaces = 0;
        }
        
        // Autonomous UAV Swarm Nodes
        uav[numUavs]: UAVNode {
            parameters:
                @display("p=250,250");
                uavId = index;
        }

    connections allowunconnected:
        // High-speed 10Gbps fiber link between gNodeB and Ground Server
        gNodeB.ethg++ <--> { datarate = 10Gbps; delay = 1ms; } <--> groundStation.ethg++;
}
