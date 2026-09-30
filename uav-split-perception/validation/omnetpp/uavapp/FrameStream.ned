//
// O3: perception-frame streaming over a full 5G stack (Simu5G), with the frame logic of
// simulation/stream_sim.py: camera ticks, a sequential onboard processor (frames arriving while
// it is busy are skipped), newest-frame-wins buffering, one frame on the uplink at a time,
// deadline test and abandonment.
//
package uavvalidation;

import inet.applications.contract.IApp;

simple FrameSender like IApp
{
    parameters:
        string destAddress;
        int destPort;
        int localPort = default(5000);
        int payloadBytes;                     // bytes per frame on the wire
        double onboardMs;                     // onboard time per frame
        double cloudMs;                       // server time per frame
        double deadlineMs = default(300);
        double fps = default(30);
        int datagramBytes = default(1400);
        string packetName = default("UdpBasicAppData"); // some Simu5G releases classify traffic by packet name
        double sendRateMbps = default(0);     // pacing of a frame's datagrams (0: whole frame at once)
        double startTime @unit(s) = default(0.1s);
        @signal[frameLatency](type=double);
        @statistic[frameLatency](source=frameLatency; unit=s; record=vector,histogram,mean);
    gates:
        input socketIn @labels(UdpControlInfo/up);
        output socketOut @labels(UdpControlInfo/down);
}

simple FrameSink like IApp
{
    parameters:
        int localPort;
    gates:
        input socketIn @labels(UdpControlInfo/up);
        output socketOut @labels(UdpControlInfo/down);
}
