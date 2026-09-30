/*
 * O5: two-hop relay, packet level. A UAV with a weak cellular link (A) hands its perception frames
 * over an 802.11ax air-to-air link to a neighbour (B), which forwards them over its own uplink to
 * the server (S). The Python simulator models this at frame level: the frame crosses the A2A link at
 * a2a_rate_mbps(distance) (goodput-maximising MCS, MAC efficiency 0.65), then waits for B's uplink,
 * where it shares B's rate with B's own frames (equal split between B's two flows), plus the
 * one-way delay.
 *
 * Here the same path is packet level: A -- Wi-Fi (802.11ax, 20 MHz, 1 stream, 800 ns GI, the V1 radio,
 * IdealWifiManager link adaptation, aggregation) -- B -- point-to-point uplink (rate, delay,
 * FQ-CoDel) -- S, with one persistent TCP (Cubic) connection A -> sink. Frames of payloadBytes are
 * sent one after another (the next when the previous has fully arrived); a frame's latency is
 * from its first write to its last byte at the sink. B may also send its own saturated TCP flow to S.
 *
 *   --sink=b   the sink is on B: the A2A hop alone
 *   --sink=s   the sink is on S: the whole relay path (B forwards packet by packet, i.e. the hops
 *              overlap; the Python model, which forwards whole frames, adds them)
 *
 * Output (stdout, CSV): distance_m,payload_bytes,sink,b_own,frames,lat_mean_ms,lat_p50_ms,lat_p95_ms
 */

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/traffic-control-module.h"
#include "ns3/wifi-module.h"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <vector>

using namespace ns3;

namespace
{

struct FrameSender
{
    Ptr<Socket> sock;
    uint32_t payload = 0;
    uint32_t nFrames = 0;
    uint32_t frame = 0;       // frame being sent
    uint64_t written = 0;     // bytes of the current frame handed to TCP
    uint64_t received = 0;    // bytes at the sink, all frames
    Time start;
    std::vector<double> lat;

    void StartFrame()
    {
        if (frame >= nFrames)
        {
            Simulator::Stop();
            return;
        }
        written = 0;
        start = Simulator::Now();
        Write();
    }

    void Write()
    {
        while (written < payload)
        {
            uint32_t n = std::min<uint64_t>(payload - written, sock->GetTxAvailable());
            n = std::min<uint32_t>(n, 1400 * 16);
            if (n == 0)
            {
                return; // resumed from the send callback
            }
            int sent = sock->Send(Create<Packet>(n));
            if (sent <= 0)
            {
                return;
            }
            written += sent;
        }
    }

    void OnSpace(Ptr<Socket>, uint32_t)
    {
        if (frame < nFrames && written < payload)
        {
            Write();
        }
    }

    void OnRx(Ptr<const Packet> p, const Address&)
    {
        received += p->GetSize();
        if (received >= uint64_t(frame + 1) * payload)
        {
            lat.push_back((Simulator::Now() - start).GetSeconds() * 1000.0);
            ++frame;
            Simulator::ScheduleNow(&FrameSender::StartFrame, this);
        }
    }
};

double
Quantile(std::vector<double> v, double q)
{
    if (v.empty())
    {
        return NAN;
    }
    std::sort(v.begin(), v.end());
    double pos = q * (v.size() - 1);
    size_t i = size_t(pos);
    double f = pos - i;
    return i + 1 < v.size() ? v[i] * (1 - f) + v[i + 1] * f : v[i];
}

} // namespace

int
main(int argc, char* argv[])
{
    double distance = 100.0, uplinkMbps = 20.0, delayMs = 20.0;
    uint32_t payload = 318122, frames = 30, seed = 1;
    std::string sinkAt = "s";
    bool bOwn = false;
    CommandLine cmd(__FILE__);
    cmd.AddValue("distance", "A-B distance (m)", distance);
    cmd.AddValue("payload", "Bytes per frame", payload);
    cmd.AddValue("frames", "Frames to send (the first is excluded as TCP warm-up)", frames);
    cmd.AddValue("uplinkMbps", "B's uplink rate (Mbit/s)", uplinkMbps);
    cmd.AddValue("delayMs", "B's uplink one-way delay (ms)", delayMs);
    cmd.AddValue("sink", "b: A2A hop only; s: through B to the server", sinkAt);
    cmd.AddValue("bOwn", "B also sends its own saturated TCP flow to the server", bOwn);
    cmd.AddValue("seed", "RNG run number", seed);
    cmd.Parse(argc, argv);
    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(seed);

    Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue(1400));
    Config::SetDefault("ns3::TcpSocket::SndBufSize", UintegerValue(1 << 20));
    Config::SetDefault("ns3::TcpSocket::RcvBufSize", UintegerValue(4 << 20));
    Config::SetDefault("ns3::TcpSocket::DelAckCount", UintegerValue(1));

    NodeContainer nodes;
    nodes.Create(3); // 0 = A (relayed UAV), 1 = B (relay UAV), 2 = S (server)

    // --- A2A link: the V1 radio (validation/ns3/a2a_wifi.cc) -------------------------------------
    const double freqHz = 5.785e9;
    const double refLoss = 20.0 * std::log10(4.0 * M_PI * freqHz / 299792458.0);
    YansWifiChannelHelper channel;
    channel.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    channel.AddPropagationLoss("ns3::LogDistancePropagationLossModel", "Exponent", DoubleValue(2.2),
                               "ReferenceDistance", DoubleValue(1.0), "ReferenceLoss", DoubleValue(refLoss));
    YansWifiPhyHelper phy;
    phy.SetChannel(channel.Create());
    phy.Set("ChannelSettings", StringValue("{157, 20, BAND_5GHZ, 0}"));
    phy.Set("TxPowerStart", DoubleValue(20.0));
    phy.Set("TxPowerEnd", DoubleValue(20.0));
    phy.Set("RxNoiseFigure", DoubleValue(6.0));
    phy.SetPreambleDetectionModel("ns3::ThresholdPreambleDetectionModel", "MinimumRssi", DoubleValue(-100.0),
                                  "Threshold", DoubleValue(4.0));
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211ax);
    wifi.SetRemoteStationManager("ns3::IdealWifiManager");
    WifiMacHelper mac;
    Ssid ssid("uav-a2a");
    mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid), "ActiveProbing", BooleanValue(false));
    NetDeviceContainer wA = wifi.Install(phy, mac, nodes.Get(0));
    mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(ssid));
    NetDeviceContainer wB = wifi.Install(phy, mac, nodes.Get(1));
    Config::Set("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/HeConfiguration/GuardInterval",
                TimeValue(NanoSeconds(800)));

    MobilityHelper mobility;
    Ptr<ListPositionAllocator> pos = CreateObject<ListPositionAllocator>();
    pos->Add(Vector(0.0, 0.0, 80.0));
    pos->Add(Vector(distance, 0.0, 80.0));
    pos->Add(Vector(distance, 0.0, 0.0));
    mobility.SetPositionAllocator(pos);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(nodes);

    // --- B's uplink: point-to-point at the cellular rate, fair-queued ------------------------------
    PointToPointHelper up;
    up.SetDeviceAttribute("DataRate", DataRateValue(DataRate(uplinkMbps * 1e6)));
    up.SetChannelAttribute("Delay", TimeValue(MicroSeconds(int64_t(delayMs * 1000))));
    up.SetQueue("ns3::DropTailQueue", "MaxSize", StringValue("100p"));
    NetDeviceContainer pB = up.Install(nodes.Get(1), nodes.Get(2));
    pB.Get(1)->SetAttribute("DataRate", DataRateValue(DataRate("1Gbps"))); // downlink (ACKs)

    InternetStackHelper stack;
    stack.Install(nodes);
    TrafficControlHelper tch;
    tch.SetRootQueueDisc("ns3::FqCoDelQueueDisc", "MaxSize", StringValue("10000p"));
    tch.Install(pB.Get(0));
    Ipv4AddressHelper addr;
    addr.SetBase("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer iw = addr.Assign(NetDeviceContainer(wA, wB));
    addr.SetBase("10.2.2.0", "255.255.255.0");
    Ipv4InterfaceContainer ip = addr.Assign(pB);
    Ipv4GlobalRoutingHelper::PopulateRoutingTables();

    const uint16_t port = 9000;
    Ptr<Node> sinkNode = nodes.Get(sinkAt == "b" ? 1 : 2);
    Ipv4Address sinkAddr = sinkAt == "b" ? iw.GetAddress(1) : ip.GetAddress(1);
    PacketSinkHelper sinkHelper("ns3::TcpSocketFactory", InetSocketAddress(Ipv4Address::GetAny(), port));
    ApplicationContainer sinkApp = sinkHelper.Install(sinkNode);
    sinkApp.Start(Seconds(0.0));

    if (bOwn) // B's own frames: a saturated flow on the same uplink
    {
        PacketSinkHelper ownSink("ns3::TcpSocketFactory", InetSocketAddress(Ipv4Address::GetAny(), port + 1));
        ownSink.Install(nodes.Get(2)).Start(Seconds(0.0));
        BulkSendHelper bulk("ns3::TcpSocketFactory", InetSocketAddress(ip.GetAddress(1), port + 1));
        bulk.SetAttribute("SendSize", UintegerValue(1400));
        bulk.Install(nodes.Get(1)).Start(Seconds(0.5));
    }

    FrameSender fs;
    fs.payload = payload;
    fs.nFrames = frames;
    fs.sock = Socket::CreateSocket(nodes.Get(0), TcpSocketFactory::GetTypeId());
    fs.sock->Bind();
    fs.sock->SetSendCallback(MakeCallback(&FrameSender::OnSpace, &fs));
    sinkApp.Get(0)->TraceConnectWithoutContext("Rx", MakeCallback(&FrameSender::OnRx, &fs));
    Simulator::Schedule(Seconds(1.0), [&]() { fs.sock->Connect(InetSocketAddress(sinkAddr, port)); });
    Simulator::Schedule(Seconds(1.5), &FrameSender::StartFrame, &fs);

    Simulator::Stop(Seconds(600.0));
    Simulator::Run();
    std::vector<double> lat(fs.lat.begin() + std::min<size_t>(1, fs.lat.size()), fs.lat.end());
    double mean = 0;
    for (double l : lat)
    {
        mean += l / lat.size();
    }
    std::cout << "distance_m,payload_bytes,sink,b_own,frames,lat_mean_ms,lat_p50_ms,lat_p95_ms\n"
              << distance << "," << payload << "," << sinkAt << "," << bOwn << "," << lat.size() << "," << mean
              << "," << Quantile(lat, 0.5) << "," << Quantile(lat, 0.95) << std::endl;
    Simulator::Destroy();
    return 0;
}
