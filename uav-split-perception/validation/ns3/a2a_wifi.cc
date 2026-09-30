/*
 * V1: air-to-air 802.11ax link, goodput versus distance, with ns-3's own Wi-Fi model.
 *
 * Mirrors the assumptions of simulation/stream_sim.py (a2a_rate_mbps):
 *   5.8 GHz band (channel 157, 20 MHz), one spatial stream, 0.8 us guard interval,
 *   20 dBm transmit power, log-distance path loss with exponent 2.2 and free-space loss at 1 m,
 *   receiver noise figure chosen so the noise floor is -95 dBm over 20 MHz.
 * Unlike the Python model, ns-3 simulates the full PHY/MAC: preambles, contention, A-MPDU
 * aggregation, block ACKs, retransmissions, and its table-based error-rate model.
 *
 * For each distance the transmitter is saturated with UDP and the goodput at the receiver is
 * measured for every fixed MCS (HeMcs0..11); the best of them is the goodput an ideal link
 * adaptation achieves. The run also reports ns-3's IdealWifiManager (SNR-driven selection).
 *
 * Output (stdout, CSV): distance_m,manager,mcs,goodput_mbps
 */

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/propagation-module.h"
#include "ns3/wifi-module.h"

#include <cmath>
#include <iostream>

using namespace ns3;

static double
RunOnce(double distance, const std::string& manager, int mcs, double simTime, uint32_t seed, double minRssiDbm,
        const std::string& standard, bool aggregation)
{
    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(seed);

    NodeContainer nodes;
    nodes.Create(2); // 0 = sender UAV (station), 1 = neighbour UAV (access point)

    const double freqHz = 5.785e9; // channel 157
    const double refLoss = 20.0 * std::log10(4.0 * M_PI * freqHz / 299792458.0);

    YansWifiChannelHelper channel;
    channel.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    channel.AddPropagationLoss("ns3::LogDistancePropagationLossModel",
                               "Exponent", DoubleValue(2.2),
                               "ReferenceDistance", DoubleValue(1.0),
                               "ReferenceLoss", DoubleValue(refLoss));

    YansWifiPhyHelper phy;
    phy.SetChannel(channel.Create());
    phy.Set("ChannelSettings", StringValue("{157, 20, BAND_5GHZ, 0}"));
    phy.Set("TxPowerStart", DoubleValue(20.0));
    phy.Set("TxPowerEnd", DoubleValue(20.0));
    // Thermal noise over 20 MHz is -174 + 10 log10(20e6) = -101.0 dBm; NF 6 dB gives -95.0 dBm.
    phy.Set("RxNoiseFigure", DoubleValue(6.0));
    // Preamble detection: ns-3's default ignores frames below -82 dBm, the 802.11 minimum receiver
    // sensitivity for 20 MHz. Real receivers are usually more sensitive; the run is repeated with an
    // SNR-limited receiver (minRssi at the noise floor) to match the Python model's assumption.
    phy.SetPreambleDetectionModel("ns3::ThresholdPreambleDetectionModel",
                                  "MinimumRssi", DoubleValue(minRssiDbm),
                                  "Threshold", DoubleValue(4.0));

    WifiHelper wifi;
    // 802.11ax by default; 802.11ac for the cross-check with INET (OMNeT++), which has no 802.11ax.
    wifi.SetStandard(standard == "ac" ? WIFI_STANDARD_80211ac : WIFI_STANDARD_80211ax);
    if (manager == "constant")
    {
        std::string mode = (standard == "ac" ? "VhtMcs" : "HeMcs") + std::to_string(mcs);
        wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                     "DataMode", StringValue(mode),
                                     "ControlMode", StringValue("OfdmRate6Mbps"));
    }
    else
    {
        wifi.SetRemoteStationManager("ns3::IdealWifiManager");
    }

    WifiMacHelper mac;
    Ssid ssid("uav-a2a");
    mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid), "ActiveProbing", BooleanValue(false));
    NetDeviceContainer staDev = wifi.Install(phy, mac, nodes.Get(0));
    mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(ssid));
    NetDeviceContainer apDev = wifi.Install(phy, mac, nodes.Get(1));

    if (!aggregation) // one MPDU per channel access, as INET's DCF sends (cross-check O4)
    {
        Config::Set("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Mac/BE_MaxAmpduSize", UintegerValue(0));
        Config::Set("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/Mac/BE_MaxAmsduSize", UintegerValue(0));
    }

    if (standard != "ac") // 802.11ac uses the long (800 ns) guard interval by default
    {
        Config::Set("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/HeConfiguration/GuardInterval",
                    TimeValue(NanoSeconds(800)));
    }

    if (std::getenv("A2A_DEBUG"))
    {
        Ptr<WifiPhy> dbg = DynamicCast<WifiNetDevice>(staDev.Get(0))->GetPhy();
        std::cerr << "width_MHz=" << dbg->GetChannelWidth() << " freq_MHz=" << dbg->GetFrequency()
                  << " nss=" << int(dbg->GetMaxSupportedTxSpatialStreams()) << std::endl;
    }

    MobilityHelper mobility;
    Ptr<ListPositionAllocator> pos = CreateObject<ListPositionAllocator>();
    pos->Add(Vector(0.0, 0.0, 80.0));
    pos->Add(Vector(distance, 0.0, 80.0));
    mobility.SetPositionAllocator(pos);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(nodes);

    InternetStackHelper stack;
    stack.Install(nodes);
    Ipv4AddressHelper addr;
    addr.SetBase("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer staIf = addr.Assign(staDev);
    Ipv4InterfaceContainer apIf = addr.Assign(apDev);

    const uint16_t port = 9;
    PacketSinkHelper sinkHelper("ns3::UdpSocketFactory", InetSocketAddress(Ipv4Address::GetAny(), port));
    ApplicationContainer sinkApp = sinkHelper.Install(nodes.Get(1));
    sinkApp.Start(Seconds(0.0));

    // Saturating UDP source: offered load well above the highest PHY rate (143.4 Mbit/s).
    OnOffHelper src("ns3::UdpSocketFactory", InetSocketAddress(apIf.GetAddress(0), port));
    src.SetConstantRate(DataRate("300Mbps"), 1472);
    ApplicationContainer srcApp = src.Install(nodes.Get(0));
    const double warmup = 1.0;
    srcApp.Start(Seconds(warmup));
    srcApp.Stop(Seconds(warmup + simTime));

    // Count only bytes received inside the measurement window [warmup, warmup + simTime]; packets
    // still queued when the source stops must not inflate the goodput.
    Ptr<PacketSink> sink = DynamicCast<PacketSink>(sinkApp.Get(0));
    uint64_t rxStart = 0, rxEnd = 0;
    Simulator::Schedule(Seconds(warmup), [&]() { rxStart = sink->GetTotalRx(); });
    Simulator::Schedule(Seconds(warmup + simTime), [&]() { rxEnd = sink->GetTotalRx(); });
    Simulator::Stop(Seconds(warmup + simTime + 0.01));
    Simulator::Run();
    Simulator::Destroy();
    return (rxEnd - rxStart) * 8.0 / simTime / 1e6;
}

int
main(int argc, char* argv[])
{
    double simTime = 3.0;
    uint32_t seed = 1;
    std::string distances = "10,25,50,100,150,200,300,400,500,600,700,800,900,1000";
    double minRssi = -82.0;
    std::string standard = "ax";
    CommandLine cmd(__FILE__);
    cmd.AddValue("simTime", "Measurement time per run (s)", simTime);
    cmd.AddValue("seed", "RNG run number", seed);
    cmd.AddValue("distances", "Comma-separated distances (m)", distances);
    cmd.AddValue("standard", "ax (802.11ax) or ac (802.11ac)", standard);
    cmd.AddValue("minRssi", "Preamble detection minimum RSSI (dBm); -82 = 802.11 minimum sensitivity", minRssi);
    bool aggregation = true;
    cmd.AddValue("aggregation", "A-MPDU/A-MSDU aggregation (false: one MPDU per access, like INET's DCF)", aggregation);
    cmd.Parse(argc, argv);

    std::cout << "distance_m,manager,mcs,goodput_mbps" << std::endl;
    std::stringstream ss(distances);
    std::string tok;
    while (std::getline(ss, tok, ','))
    {
        double d = std::stod(tok);
        for (int mcs = 0; mcs <= (standard == "ac" ? 8 : 11); ++mcs) // VHT MCS 9 is not valid for 20 MHz, 1 stream
        {
            std::cout << d << ",constant," << mcs << "," << RunOnce(d, "constant", mcs, simTime, seed, minRssi, standard, aggregation) << std::endl;
        }
        std::cout << d << ",ideal,-1," << RunOnce(d, "ideal", -1, simTime, seed, minRssi, standard, aggregation) << std::endl;
    }
    return 0;
}
