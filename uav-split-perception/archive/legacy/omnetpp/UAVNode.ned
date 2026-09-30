package aegis_uav.simulations;

import inet.mobility.contract.IMobility;
import inet.node.inet.WirelessHost;
import inet.power.contract.IEnergyStorage;
import inet.linklayer.contract.IWirelessInterface;
import inet.queueing.contract.IPacketQueue;

//
// UAVNode: Autonomous Aerial Perception Node for AEGIS-UAV Swarms.
// Integrates Edge Split Perception App, FIFO Frame Queue, 802.11ax A2A Mesh,
// and 5G NR Cellular Uplink Interface with Calibrated Power Modeling.
//
module UAVNode extends WirelessHost
{
    parameters:
        @display("i=misc/drone;is=s");
        
        // UAV & Application Parameters
        int uavId = default(0);
        double frameRateFps @unit(fps) = default(30.0fps);
        double frameIntervalMs @unit(ms) = default(33.33ms);
        int maxQueueDepth = default(30);
        
        // Calibrated Jetson Hardware Parameters
        double aCoeffEdge = default(11.2330);
        double bCoeffTx = default(3.8000);
        double pIdleW @unit(W) = default(2.20W);
        double pMaxW @unit(W) = default(10.00W);
        double pTxRfW @unit(W) = default(3.80W);
        double pAvionicsW @unit(W) = default(15.00W);
        double batteryCapacityWh @unit(Wh) = default(55.5Wh);
        
        // Dynamic Policy Weights
        double alphaWeight = default(0.40);
        double betaWeight = default(0.40);
        double gammaWeight = default(0.20);
        double deadlineMs @unit(ms) = default(300.0ms);
        double hysteresisDelta = default(0.05);

        // Network Interfaces
        numWlanInterfaces = default(1);
        numRadios = default(2); // Radio 0: 802.11ax (5.8 GHz), Radio 1: 5G NR (3.5 GHz)
        
        mobility.typename = default("LinearMobility");
        mobility.speed = default(10mps);
        mobility.constraintAreaMinZ = default(50m);
        mobility.constraintAreaMaxZ = default(150m);
}
