/*
 * V2: cellular uplink throughput versus SINR with ns-3's LTE model (LENA).
 *
 * simulation/trace_generator.py converts SINR to rate with the 3GPP TR 36.942 (Annex A.2)
 * attenuated and truncated Shannon bound: SE = 0.4 log2(1 + SINR), capped at 2 bit/s/Hz, zero
 * below -10 dB, times the bandwidth. Here one UAV (UE) streams saturated UDP uplink to a remote
 * host through an eNB with 20 MHz (100 resource blocks) of uplink, at a sweep of distances; ns-3
 * simulates SRS/PUSCH SINR, adaptive modulation and coding, HARQ and the error model. The eNB's
 * reported uplink SINR and the goodput at the remote host are recorded for each distance.
 *
 * Output (stdout, CSV): distance_m,sinr_db,goodput_mbps
 */

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/lte-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"

#include <cmath>
#include <iostream>

using namespace ns3;

static double g_sinrSum = 0.0;
static uint64_t g_sinrCount = 0;
static bool g_measuring = false;

static void
UeSinr(uint16_t cellId, uint16_t rnti, double sinrLinear, uint8_t ccId)
{
    if (g_measuring && sinrLinear > 0)
    {
        g_sinrSum += 10.0 * std::log10(sinrLinear);
        g_sinrCount++;
    }
}

static void
StartMeasuring()
{
    g_measuring = true;
}

int
main(int argc, char* argv[])
{
    double distance = 1000.0;
    double simTime = 2.0;
    double ueTxDbm = 23.0;
    uint32_t seed = 1;
    CommandLine cmd(__FILE__);
    cmd.AddValue("distance", "UE-eNB distance (m)", distance);
    cmd.AddValue("simTime", "Measurement time (s)", simTime);
    cmd.AddValue("ueTxDbm", "UE transmit power (dBm)", ueTxDbm);
    cmd.AddValue("seed", "RNG run number", seed);
    cmd.Parse(argc, argv);
    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(seed);

    Config::SetDefault("ns3::LteUePhy::TxPower", DoubleValue(ueTxDbm));
    Config::SetDefault("ns3::LteEnbPhy::TxPower", DoubleValue(46.0));
    Config::SetDefault("ns3::LteAmc::AmcModel", EnumValue(LteAmc::MiErrorModel));
    Config::SetDefault("ns3::LteHelper::UseIdealRrc", BooleanValue(true));
    Config::SetDefault("ns3::LteUePowerControl::ClosedLoop", BooleanValue(false));
    Config::SetDefault("ns3::LteUePowerControl::PoNominalPusch", IntegerValue(-40));

    Ptr<LteHelper> lte = CreateObject<LteHelper>();
    Ptr<PointToPointEpcHelper> epc = CreateObject<PointToPointEpcHelper>();
    lte->SetEpcHelper(epc);
    lte->SetAttribute("PathlossModel", StringValue("ns3::FriisPropagationLossModel"));
    lte->SetEnbDeviceAttribute("UlBandwidth", UintegerValue(100));
    lte->SetEnbDeviceAttribute("DlBandwidth", UintegerValue(100));

    Ptr<Node> pgw = epc->GetPgwNode();
    NodeContainer remote;
    remote.Create(1);
    InternetStackHelper internet;
    internet.Install(remote);
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", DataRateValue(DataRate("10Gb/s")));
    p2p.SetChannelAttribute("Delay", TimeValue(MilliSeconds(1)));
    NetDeviceContainer inetDevs = p2p.Install(pgw, remote.Get(0));
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("1.0.0.0", "255.0.0.0");
    Ipv4InterfaceContainer inetIf = ipv4.Assign(inetDevs);
    Ipv4StaticRoutingHelper routing;
    routing.GetStaticRouting(remote.Get(0)->GetObject<Ipv4>())
        ->AddNetworkRouteTo(Ipv4Address("7.0.0.0"), Ipv4Mask("255.0.0.0"), 1);

    NodeContainer enb, ue;
    enb.Create(1);
    ue.Create(1);
    MobilityHelper mob;
    Ptr<ListPositionAllocator> pos = CreateObject<ListPositionAllocator>();
    pos->Add(Vector(0.0, 0.0, 30.0));
    pos->Add(Vector(distance, 0.0, 80.0));
    mob.SetPositionAllocator(pos);
    mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mob.Install(enb);
    mob.Install(ue);

    NetDeviceContainer enbDev = lte->InstallEnbDevice(enb);
    NetDeviceContainer ueDev = lte->InstallUeDevice(ue);
    internet.Install(ue);
    Ipv4InterfaceContainer ueIf = epc->AssignUeIpv4Address(ueDev);
    routing.GetStaticRouting(ue.Get(0)->GetObject<Ipv4>())
        ->SetDefaultRoute(epc->GetUeDefaultGatewayAddress(), 1);
    lte->Attach(ueDev.Get(0), enbDev.Get(0));

    const uint16_t port = 5000;
    PacketSinkHelper sink("ns3::UdpSocketFactory", InetSocketAddress(Ipv4Address::GetAny(), port));
    ApplicationContainer sinkApp = sink.Install(remote.Get(0));
    sinkApp.Start(Seconds(0.0));
    OnOffHelper src("ns3::UdpSocketFactory", InetSocketAddress(inetIf.GetAddress(1), port));
    src.SetConstantRate(DataRate("120Mbps"), 1400);
    ApplicationContainer srcApp = src.Install(ue.Get(0));
    const double warmup = 0.5;
    srcApp.Start(Seconds(warmup));
    srcApp.Stop(Seconds(warmup + simTime));

    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/*/ComponentCarrierMap/*/LteEnbPhy/ReportUeSinr", MakeCallback(&UeSinr));
    Simulator::Schedule(Seconds(warmup), &StartMeasuring);
    // Bytes received inside the measurement window only (queued data after the source stops is excluded).
    Ptr<PacketSink> sinkPtr = DynamicCast<PacketSink>(sinkApp.Get(0));
    uint64_t rxStart = 0, rxEnd = 0;
    Simulator::Schedule(Seconds(warmup), [&]() { rxStart = sinkPtr->GetTotalRx(); });
    Simulator::Schedule(Seconds(warmup + simTime), [&]() { rxEnd = sinkPtr->GetTotalRx(); g_measuring = false; });
    Simulator::Stop(Seconds(warmup + simTime + 0.01));
    Simulator::Run();
    uint64_t rx = rxEnd - rxStart;
    Simulator::Destroy();

    double sinrDb = g_sinrCount ? g_sinrSum / g_sinrCount : NAN;
    std::cout << distance << "," << sinrDb << "," << rx * 8.0 / simTime / 1e6 << std::endl;
    return 0;
}
