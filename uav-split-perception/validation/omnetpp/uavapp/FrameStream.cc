//
// O3 frame-streaming application for OMNeT++/INET/Simu5G. See FrameStream.ned.
//
// Every datagram starts with an INET ApplicationPacket header whose sequence number encodes
// (frame id, datagrams in frame); packet names are not preserved through the 5G stack. Each UAV
// streams to its own sink port, so the sink knows which UAV a datagram came from. When the last
// datagram of a frame has arrived, the sink The sink then notifies the sender
// directly (both live in the same simulation), which releases the uplink for the next frame, as in
// the Python simulator and the ns-3 replay. A frame that has not been delivered by its deadline is
// abandoned: its remaining datagrams are not sent, and datagrams already handed to the UE stack
// are still transmitted.
//

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <map>
#include <vector>

#include "inet/common/ModuleAccess.h"
#include "inet/common/packet/Packet.h"
#include "inet/applications/base/ApplicationPacket_m.h"
#include "inet/common/packet/chunk/ByteCountChunk.h"
#include "inet/networklayer/common/L3AddressResolver.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"

using namespace omnetpp;
using namespace inet;

namespace uavvalidation {

class FrameSink;

struct Frame
{
    int id;
    double captureMs;
    int datagrams;
    int sent = 0;
    bool aborted = false, delivered = false;
};

class FrameSender : public cSimpleModule, public UdpSocket::ICallback
{
  public:
    void frameArrived(int id, double nowMs);

  protected:
    UdpSocket socket;
    L3Address dest;
    int destPort = 0, payload = 0, dgBytes = 1400;
    double onboardMs = 0, cloudMs = 0, deadlineMs = 300, periodMs = 1000.0 / 30;
    double paceUs = 0, nextSendMs = 0; // microseconds per full datagram at sendRateMbps
    cMessage *captureMsg = nullptr, *sendMsg = nullptr;
    std::map<long, cMessage *> readyMsgs;
    double busyUntilMs = -1;
    int nextId = 0;
    Frame *pending = nullptr, *current = nullptr;
    std::vector<Frame *> frames;
    long captured = 0, skipped = 0, stale = 0, superseded = 0;
    std::vector<double> latencies, lateLatencies;
    simsignal_t latencySignal;

    int numInitStages() const override { return NUM_INIT_STAGES; }
    void initialize(int stage) override;
    void handleMessage(cMessage *msg) override;
    void finish() override;
    void trySend();
    double nowMs() const { return simTime().dbl() * 1000.0; }
    void socketDataArrived(UdpSocket *, Packet *p) override { delete p; }
    void socketErrorArrived(UdpSocket *, Indication *i) override { delete i; }
    void socketClosed(UdpSocket *) override {}
};

Define_Module(FrameSender);

class FrameSink : public cSimpleModule, public UdpSocket::ICallback
{
  protected:
    UdpSocket socket;
    std::map<int, int> received;     // frame id -> datagrams received
    FrameSender *sender = nullptr;   // the UAV whose frames this sink receives (ue[k].app[0] for app[k])

    int numInitStages() const override { return NUM_INIT_STAGES; }
    void initialize(int stage) override
    {
        if (stage == INITSTAGE_APPLICATION_LAYER) {
            socket.setOutputGate(gate("socketOut"));
            socket.setCallback(this);
            socket.bind(par("localPort").intValue());
        }
    }
    void handleMessage(cMessage *msg) override { socket.processMessage(msg); }
    void socketDataArrived(UdpSocket *, Packet *p) override
    {
        const auto& hdr = p->peekAtFront<ApplicationPacket>();
        long code = hdr->getSequenceNumber();
        lastCode = code;
        seen++;
        int frameId = int(code / 4096), total = int(code % 4096);
        if (++received[frameId] == total) {
            if (!sender) {
                int k = getIndex();
                sender = check_and_cast<FrameSender *>(getModuleByPath(("^.^.ue[" + std::to_string(k) + "].app[0]").c_str()));
            }
            sender->frameArrived(frameId, simTime().dbl() * 1000.0);
            received.erase(frameId);
        }
        delete p;
    }
    void socketErrorArrived(UdpSocket *, Indication *i) override { delete i; }
    void socketClosed(UdpSocket *) override {}
    void finish() override
    {
        recordScalar("framesIncompleteAtEnd", (double)received.size());
        int mx = 0;
        for (auto& [id, n] : received)
            mx = std::max(mx, n);
        recordScalar("maxDatagramsOfIncompleteFrame", mx);
        int mn = 1 << 30;
        for (auto& [id, n] : received)
            mn = std::min(mn, n);
        recordScalar("minDatagramsOfIncompleteFrame", received.empty() ? 0 : mn);
        recordScalar("lastCodeSeen", (double)lastCode);
        recordScalar("datagramsSeen", (double)seen);
    }
    long lastCode = -1, seen = 0;
};

Define_Module(FrameSink);

void FrameSender::initialize(int stage)
{
    if (stage == INITSTAGE_LOCAL) {
        payload = par("payloadBytes");
        dgBytes = par("datagramBytes");
        onboardMs = par("onboardMs");
        cloudMs = par("cloudMs");
        deadlineMs = par("deadlineMs");
        periodMs = 1000.0 / par("fps").doubleValue();
        double rate = par("sendRateMbps");
        paceUs = rate > 0 ? dgBytes * 8.0 / rate : 0.0;
        destPort = par("destPort");
        latencySignal = registerSignal("frameLatency");
        captureMsg = new cMessage("capture");
        sendMsg = new cMessage("send");
    }
    else if (stage == INITSTAGE_APPLICATION_LAYER) {
        socket.setOutputGate(gate("socketOut"));
        socket.setCallback(this);
        socket.bind(par("localPort").intValue());
        scheduleAt(par("startTime"), captureMsg);
    }
}

void FrameSender::handleMessage(cMessage *msg)
{
    if (msg == captureMsg) {
        double now = nowMs();
        captured++;
        if (now < busyUntilMs)
            skipped++;
        else {
            busyUntilMs = now + onboardMs;
            auto *ready = new cMessage("ready");
            ready->setContextPointer(new double(now));
            scheduleAfter(SimTime(onboardMs / 1000.0), ready);
        }
        scheduleAfter(SimTime(periodMs / 1000.0), captureMsg);
    }
    else if (msg == sendMsg) {
        trySend();
    }
    else if (!strcmp(msg->getName(), "ready")) {
        double *cap = static_cast<double *>(msg->getContextPointer());
        if (pending) {
            superseded++;
            delete pending;
        }
        pending = new Frame{nextId++, *cap, (payload + dgBytes - 1) / dgBytes};
        delete cap;
        delete msg;
        trySend();
    }
    else if (!strcmp(msg->getName(), "deadline")) {
        Frame *f = static_cast<Frame *>(msg->getContextPointer());
        delete msg;
        if (f == current && !f->delivered && !f->aborted) {
            f->aborted = true;
            trySend();
        }
    }
    else
        socket.processMessage(msg);
}

void FrameSender::trySend()
{
    if (dest.isUnspecified())
        dest = L3AddressResolver().resolve(par("destAddress"));
    double now = nowMs();
    bool currentDone = !current || current->aborted || current->delivered;
    if (currentDone && pending) {
        Frame *f = pending;
        pending = nullptr;
        if (now - f->captureMs > deadlineMs) {
            stale++;
            delete f;
            return;
        }
        current = f;
        frames.push_back(f);
        auto *dl = new cMessage("deadline");
        dl->setContextPointer(f);
        scheduleAfter(SimTime(std::max(0.0, f->captureMs + deadlineMs - now) / 1000.0), dl);
    }
    // Hand the frame to the UE stack datagram by datagram, paced at sendRateMbps (0: all at once).
    if (current && !current->aborted && !current->delivered) {
        while (current->sent < current->datagrams) {
            if (paceUs > 0 && nextSendMs > now + 1e-9) {
                if (!sendMsg->isScheduled())
                    scheduleAt(SimTime(nextSendMs / 1000.0), sendMsg);
                break;
            }
            int bytes = (current->sent == current->datagrams - 1) ? payload - dgBytes * (current->datagrams - 1) : dgBytes;
            auto *p = new Packet(par("packetName").stringValue());
            auto hdr = makeShared<ApplicationPacket>();
            hdr->setSequenceNumber(long(current->id) * 4096 + current->datagrams); // datagrams < 4096
            hdr->setChunkLength(B(8));
            p->insertAtBack(hdr);
            p->insertAtBack(makeShared<ByteCountChunk>(B(std::max(1, bytes - 8))));
            socket.sendTo(p, dest, destPort);
            current->sent++;
            if (paceUs > 0)
                nextSendMs = std::max(nextSendMs, now) + paceUs / 1000.0 * bytes / dgBytes;
        }
    }
}

void FrameSender::frameArrived(int id, double arrivalMs)
{
    Enter_Method("frameArrived"); // called from the sink module: switch context first
    for (Frame *f : frames) {
        if (f->id == id && f->aborted && !f->delivered)
            lateLatencies.push_back(arrivalMs + cloudMs - f->captureMs); // completed after being abandoned
        if (f->id == id && !f->aborted && !f->delivered) {
            f->delivered = true;
            double lat = arrivalMs + cloudMs - f->captureMs;
            latencies.push_back(lat);
            emit(latencySignal, lat / 1000.0);
            break;
        }
    }
    if (!sendMsg->isScheduled())
        scheduleAfter(SIMTIME_ZERO, sendMsg);
}

void FrameSender::finish()
{
    long onTime = std::count_if(latencies.begin(), latencies.end(), [&](double l) { return l <= deadlineMs; });
    long aborted = std::count_if(frames.begin(), frames.end(), [](Frame *f) { return f->aborted; });
    double measured = simTime().dbl() - par("startTime").doubleValue();
    recordScalar("captured", captured);
    recordScalar("skipped", skipped);
    recordScalar("sent", (double)frames.size());
    recordScalar("delivered", (double)latencies.size());
    recordScalar("onTime", onTime);
    recordScalar("aborted", aborted);
    recordScalar("stale", stale);
    recordScalar("superseded", superseded);
    recordScalar("onTimeFps", onTime / measured);
    recordScalar("lateCompleted", (double)lateLatencies.size());
    double lateMean = 0;
    for (double l : lateLatencies)
        lateMean += l / std::max<size_t>(1, lateLatencies.size());
    recordScalar("lateLatencyMeanMs", lateMean);
    for (Frame *f : frames)
        delete f;
    frames.clear();
    delete pending;
    pending = nullptr;
    cancelAndDelete(captureMsg);
    cancelAndDelete(sendMsg);
}

} // namespace uavvalidation
