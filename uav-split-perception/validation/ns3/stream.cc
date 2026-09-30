/*
 * V3/V4: packet-level replay of the frame-streaming model of simulation/stream_sim.py.
 *
 * Each UAV runs the same application logic as the Python simulator:
 *   camera frames every 1/fps; a sequential onboard processor (frames arriving while it is busy
 *   are skipped); a newest-frame-wins uplink buffer; a frame is sent only if it can still meet
 *   the deadline, and sending stops (the rest of the frame is not written) once the deadline has
 *   passed; a frame is on time if its last byte reaches the server, plus the server time, within
 *   the deadline of its capture.
 * What differs is the network, which here is packet level:
 *   real TCP (Cubic) per UAV, a per-UAV access link whose rate and loss follow the given channel
 *   trace slot by slot (10 ms) and whose delay is the trace's mean (per-slot delay changes would
 *   reorder a flow's packets, which cellular links do not do; the slot's deviation from the mean
 *   is added to each frame's latency instead), and, for swarms, a shared bottleneck of the cell capacity
 *   with per-flow fair queueing (FQ-CoDel), standing in for the base station's fair scheduler.
 * The Python simulator instead uses a fluid model (bits per slot, water-filling).
 *
 * Output (stdout, CSV): one row per UAV
 *   uav,captured,skipped,sent,delivered,on_time,aborted,stale,superseded,lat_p50_ms,lat_p95_ms
 */

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/traffic-control-module.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>

using namespace ns3;

// ns-3's MilliSeconds() takes an integer; fractional milliseconds (e.g. a 33.33 ms camera period)
// must not be truncated, so all timing uses this nanosecond-resolution helper.
static Time
Ms(double ms)
{
    return NanoSeconds(int64_t(std::llround(ms * 1e6)));
}

struct Slot
{
    double bwMbps, delayMs, lossPct;
};

static std::vector<Slot>
ReadTrace(const std::string& path)
{
    std::vector<Slot> slots;
    std::ifstream in(path);
    NS_ABORT_MSG_IF(!in, "cannot open trace " << path);
    std::string line;
    std::getline(in, line); // header: timestamp_ms,sinr_db,bandwidth_mbps,delay_ms,packet_loss_pct
    while (std::getline(in, line))
    {
        std::stringstream ss(line);
        std::string t, sinr, bw, d, l;
        std::getline(ss, t, ',');
        std::getline(ss, sinr, ',');
        std::getline(ss, bw, ',');
        std::getline(ss, d, ',');
        std::getline(ss, l, ',');
        slots.push_back({std::stod(bw), std::stod(d), std::stod(l)});
    }
    return slots;
}

struct FrameRec
{
    double captureMs;
    uint64_t start = 0, end = 0; // byte offsets in the UAV's TCP stream
    bool fullyWritten = false, aborted = false, delivered = false;
    double deliverMs = 0;
};

struct Params
{
    uint32_t payloadBytes;
    double onboardMs, cloudMs, deadlineMs, fps, durationS;
};

class UavApp
{
  public:
    UavApp(uint32_t id, Ptr<Node> node, Address server, const Params& p, const std::vector<Slot>* trace,
           double meanDelayMs)
        : m_id(id), m_node(node), m_server(server), m_p(p), m_trace(trace), m_meanDelayMs(meanDelayMs)
    {
    }

    void Start()
    {
        m_sock = Socket::CreateSocket(m_node, TcpSocketFactory::GetTypeId());
        m_sock->Bind();
        m_sock->Connect(m_server);
        m_sock->SetSendCallback(MakeCallback(&UavApp::OnSendSpace, this));
        Simulator::Schedule(MilliSeconds(0), &UavApp::Capture, this);
    }

    // server side: cumulative bytes received from this UAV
    void OnServerBytes(uint64_t total)
    {
        m_rx = total;
        for (auto& f : m_frames)
        {
            if (!f->delivered && f->fullyWritten && !f->aborted && f->end <= m_rx)
            {
                f->delivered = true;
                f->deliverMs = Simulator::Now().GetSeconds() * 1000.0;
            }
        }
        TrySend(); // the uplink is free once the current frame has been delivered
    }

    void Report(std::ostream& os) const
    {
        uint32_t delivered = 0, onTime = 0, aborted = 0, sent = 0;
        std::vector<double> lat;
        for (const auto& f : m_frames)
        {
            sent++;
            aborted += f->aborted;
            if (f->delivered)
            {
                delivered++;
                // Packets travel with the trace's mean delay (so a flow is never reordered); the slot's
                // deviation from it is added here, as the Python simulator applies the slot delay.
                size_t k = size_t(f->deliverMs / 10.0) % m_trace->size();
                double l = f->deliverMs + ((*m_trace)[k].delayMs - m_meanDelayMs) + m_p.cloudMs - f->captureMs;
                lat.push_back(l);
                onTime += (l <= m_p.deadlineMs);
            }
        }
        std::sort(lat.begin(), lat.end());
        auto pct = [&](double q) { return lat.empty() ? NAN : lat[std::min(lat.size() - 1, size_t(q * lat.size()))]; };
        os << m_id << "," << m_captured << "," << m_skipped << "," << sent << "," << delivered << "," << onTime << ","
           << aborted << "," << m_stale << "," << m_superseded << "," << pct(0.5) << "," << pct(0.95) << "\n";
    }

  private:
    void Capture()
    {
        double now = Simulator::Now().GetSeconds() * 1000.0;
        if (now >= m_p.durationS * 1000.0)
        {
            return;
        }
        m_captured++;
        if (now < m_busyUntil)
        {
            m_skipped++;
        }
        else
        {
            m_busyUntil = now + m_p.onboardMs;
            Simulator::Schedule(Ms(m_p.onboardMs), &UavApp::Ready, this, now);
        }
        Simulator::Schedule(Ms(1000.0 / m_p.fps), &UavApp::Capture, this);
    }

    void Ready(double captureMs)
    {
        if (m_pending)
        {
            m_superseded++; // newest frame wins
        }
        m_pending = std::make_shared<FrameRec>();
        m_pending->captureMs = captureMs;
        TrySend();
    }

    void TrySend()
    {
        double now = Simulator::Now().GetSeconds() * 1000.0;
        if (m_current && !m_current->aborted && !m_current->fullyWritten &&
            now - m_current->captureMs > m_p.deadlineMs)
        {
            m_current->aborted = true; // stop writing the rest of a frame that can no longer be on time
            m_current->end = m_written;
        }
        // As in the Python simulator, one frame occupies the uplink at a time: the next frame starts
        // when the current one's last byte has been transmitted on the UAV's radio link (or it has been
        // delivered, or abandoned at its deadline).
        bool currentDone = !m_current || m_current->aborted || m_current->delivered ||
                           (m_current->fullyWritten && m_wireHigh >= m_current->end);
        if (currentDone && m_pending)
        {
            auto f = m_pending;
            m_pending = nullptr;
            if (now - f->captureMs > m_p.deadlineMs)
            {
                m_stale++;
                return;
            }
            f->start = m_written;
            f->end = m_written + m_p.payloadBytes;
            m_current = f;
            m_frames.push_back(f);
            double left = f->captureMs + m_p.deadlineMs - now;
            Simulator::Schedule(Ms(std::max(0.0, left) + 0.001), &UavApp::Deadline, this, f);
        }
        if (m_current && !m_current->aborted && !m_current->fullyWritten)
        {
            while (m_written < m_current->end)
            {
                uint32_t room = m_sock->GetTxAvailable();
                if (room == 0)
                {
                    break;
                }
                uint32_t chunk = std::min<uint64_t>({room, m_current->end - m_written, 65536});
                int sent = m_sock->Send(Create<Packet>(chunk));
                if (sent <= 0)
                {
                    break;
                }
                m_written += sent;
            }
            if (m_written >= m_current->end)
            {
                m_current->fullyWritten = true;
            }
        }
    }

  public:
    // Highest TCP payload byte transmitted on the UAV's access link (from the device's PhyTxEnd trace).
    void OnWireTx(Ptr<const Packet> pkt)
    {
        Ptr<Packet> c = pkt->Copy();
        PppHeader ppp;
        Ipv4Header ip;
        TcpHeader tcp;
        c->RemoveHeader(ppp);
        c->RemoveHeader(ip);
        if (ip.GetProtocol() != 6)
        {
            return;
        }
        c->RemoveHeader(tcp);
        if (c->GetSize() == 0)
        {
            return;
        }
        // Data bytes start at sequence number 1 (the SYN consumes 0).
        uint64_t last = uint64_t(tcp.GetSequenceNumber().GetValue()) - 1 + c->GetSize();
        if (last > m_wireHigh)
        {
            m_wireHigh = last;
            TrySend();
        }
    }

  private:
    void OnSendSpace(Ptr<Socket>, uint32_t)
    {
        TrySend();
    }

    // A frame not delivered by its deadline is abandoned: no further bytes of it are written, and the
    // uplink is released to the next frame (bytes already handed to TCP are still transmitted).
    void Deadline(std::shared_ptr<FrameRec> f)
    {
        if (f == m_current && !f->delivered && !f->aborted)
        {
            f->aborted = true;
            if (!f->fullyWritten)
            {
                f->end = m_written;
            }
            TrySend();
        }
    }

    uint32_t m_id;
    Ptr<Node> m_node;
    Address m_server;
    Params m_p;
    const std::vector<Slot>* m_trace;
    double m_meanDelayMs;
    Ptr<Socket> m_sock;
    double m_busyUntil = -1;
    uint64_t m_written = 0, m_rx = 0, m_wireHigh = 0;
    std::shared_ptr<FrameRec> m_pending, m_current;
    std::vector<std::shared_ptr<FrameRec>> m_frames;
    uint32_t m_captured = 0, m_skipped = 0, m_stale = 0, m_superseded = 0;
};

static std::vector<std::unique_ptr<UavApp>> g_apps;
static std::map<uint32_t, uint64_t> g_rxBytes;

static void
ServerRx(uint32_t uav, Ptr<const Packet> p, const Address&)
{
    g_rxBytes[uav] += p->GetSize();
    g_apps[uav]->OnServerBytes(g_rxBytes[uav]);
}

static void
ApplySlot(Ptr<PointToPointNetDevice> uavDev, Ptr<RateErrorModel> em, const std::vector<Slot>* tr, uint32_t k,
          double slotMs)
{
    const Slot& s = (*tr)[k % tr->size()];
    uavDev->SetDataRate(DataRate(std::max(s.bwMbps, 0.01) * 1e6));
    em->SetRate(std::min(1.0, s.lossPct / 100.0));
    Simulator::Schedule(Ms(slotMs), &ApplySlot, uavDev, em, tr, k + 1, slotMs);
}

int
main(int argc, char* argv[])
{
    uint32_t nUav = 1;
    std::string traceDir;
    double cellMbps = 0; // 0 = no shared bottleneck
    Params p{317849, 77.3, 11.0, 300.0, 30.0, 60.0};
    uint32_t seed = 1;
    CommandLine cmd(__FILE__);
    cmd.AddValue("nUav", "Number of UAVs", nUav);
    cmd.AddValue("traceDir", "Directory with uav<i>.csv channel traces", traceDir);
    cmd.AddValue("cellMbps", "Shared cell capacity (Mbit/s), 0 for none", cellMbps);
    cmd.AddValue("payloadBytes", "Bytes per frame", p.payloadBytes);
    cmd.AddValue("onboardMs", "Onboard time per frame (ms)", p.onboardMs);
    cmd.AddValue("cloudMs", "Server time per frame (ms)", p.cloudMs);
    cmd.AddValue("deadlineMs", "Deadline (ms)", p.deadlineMs);
    cmd.AddValue("fps", "Camera rate", p.fps);
    cmd.AddValue("duration", "Duration (s)", p.durationS);
    cmd.AddValue("seed", "RNG run number", seed);
    cmd.Parse(argc, argv);
    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(seed);

    Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue(1400));
    Config::SetDefault("ns3::TcpSocket::SndBufSize", UintegerValue(131072));
    Config::SetDefault("ns3::TcpSocket::RcvBufSize", UintegerValue(4 << 20));
    Config::SetDefault("ns3::TcpSocket::DelAckCount", UintegerValue(1));

    NodeContainer uavs, core;
    uavs.Create(nUav);
    core.Create(2); // 0 = cell router (base station), 1 = server
    InternetStackHelper internet;
    internet.Install(uavs);
    internet.Install(core);

    // Shared bottleneck: router -> server at the cell capacity, fair-queued per flow.
    PointToPointHelper bott;
    bott.SetDeviceAttribute("DataRate", DataRateValue(DataRate(cellMbps > 0 ? cellMbps * 1e6 : 1e10)));
    bott.SetChannelAttribute("Delay", TimeValue(MicroSeconds(1)));
    bott.SetQueue("ns3::DropTailQueue", "MaxSize", StringValue("100p"));
    NetDeviceContainer bdev = bott.Install(core.Get(0), core.Get(1));
    TrafficControlHelper tch;
    tch.SetRootQueueDisc("ns3::FqCoDelQueueDisc", "MaxSize", StringValue("10000p"));
    tch.Install(bdev.Get(0));
    Ipv4AddressHelper addr;
    addr.SetBase("10.0.0.0", "255.255.255.0");
    Ipv4InterfaceContainer bif = addr.Assign(bdev);

    std::vector<std::vector<Slot>> traces(nUav);
    std::vector<double> meanDelays;
    std::vector<Ptr<NetDevice>> uavDevs;
    for (uint32_t u = 0; u < nUav; ++u)
    {
        traces[u] = ReadTrace(traceDir + "/uav" + std::to_string(u) + ".csv");
        PointToPointHelper acc;
        acc.SetQueue("ns3::DropTailQueue", "MaxSize", StringValue("2000p"));
        // Downlink (ACKs) is not the object of study: fast. The uplink rate is set per slot below.
        acc.SetDeviceAttribute("DataRate", DataRateValue(DataRate("1Gbps")));
        NetDeviceContainer d = acc.Install(uavs.Get(u), core.Get(0));
        std::ostringstream base;
        base << "10.1." << u + 1 << ".0";
        addr.SetBase(base.str().c_str(), "255.255.255.0");
        addr.Assign(d);
        Ptr<RateErrorModel> em = CreateObject<RateErrorModel>();
        em->SetUnit(RateErrorModel::ERROR_UNIT_PACKET);
        d.Get(1)->SetAttribute("ReceiveErrorModel", PointerValue(em));
        double meanDelay = 0;
        for (const auto& sl : traces[u])
        {
            meanDelay += sl.delayMs / traces[u].size();
        }
        meanDelays.push_back(meanDelay);
        Ptr<PointToPointChannel> ch = DynamicCast<PointToPointChannel>(d.Get(0)->GetChannel());
        ch->SetAttribute("Delay", TimeValue(MicroSeconds(int64_t(meanDelay * 1000.0))));
        ApplySlot(DynamicCast<PointToPointNetDevice>(d.Get(0)), em, &traces[u], 0, 10.0);
        uavDevs.push_back(d.Get(0));
    }
    Ipv4GlobalRoutingHelper::PopulateRoutingTables();

    for (uint32_t u = 0; u < nUav; ++u)
    {
        uint16_t port = 10000 + u;
        PacketSinkHelper sink("ns3::TcpSocketFactory", InetSocketAddress(Ipv4Address::GetAny(), port));
        ApplicationContainer app = sink.Install(core.Get(1));
        app.Start(Seconds(0));
        app.Get(0)->TraceConnectWithoutContext("Rx", MakeBoundCallback(&ServerRx, u));
        g_apps.emplace_back(std::make_unique<UavApp>(u, uavs.Get(u), InetSocketAddress(bif.GetAddress(1), port), p,
                                                     &traces[u], meanDelays[u]));
        Simulator::Schedule(MilliSeconds(1), &UavApp::Start, g_apps.back().get());
        uavDevs[u]->TraceConnectWithoutContext("PhyTxEnd", MakeCallback(&UavApp::OnWireTx, g_apps.back().get()));
    }

    Simulator::Stop(Seconds(p.durationS + 1.0));
    Simulator::Run();
    std::cout << "uav,captured,skipped,sent,delivered,on_time,aborted,stale,superseded,lat_p50_ms,lat_p95_ms\n";
    for (auto& a : g_apps)
    {
        a->Report(std::cout);
    }
    Simulator::Destroy();
    return 0;
}
