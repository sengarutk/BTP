simple Txc
{
    parameters:
        @display("i=block/routing;t=sent: 0");
        @signal[roundtripDelay](type="simtime_t");
        @statistic[roundtripDelay](record=vector,histogram,mean);
    gates:
        input in;
        output out;
}

network Tictoc
{
    submodules:
        tic: Txc;
        toc: Txc;
    connections:
        tic.out --> {  delay = truncnormal(1ms,10us); datarate=1Mbps; } --> toc.in;
        tic.in <-- {  delay = truncnormal(1ms,10us); datarate=1Mbps;  } <-- toc.out;
}
