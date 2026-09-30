#include <omnetpp.h>
#include "tictoc_m.h"

using namespace omnetpp;

class Txc : public cSimpleModule
{
  private:
    int sendCount;
    simtime_t lastSendTime;
    simsignal_t roundtripDelaySignal;
    cFigure *figure;

  protected:
    virtual void initialize() override;
    virtual void handleMessage(cMessage *msg) override;
    void updateDisplayString();
};

Define_Module(Txc);

void Txc::initialize()
{
    sendCount = 0;
    roundtripDelaySignal = registerSignal("roundtripDelay");
    updateDisplayString();

    // Create a filled rounded rectangle figure
    cCanvas *canvas = getParentModule()->getCanvas();
    figure = new cRectangleFigure("movingRect");
    cRectangleFigure *rectFig = static_cast<cRectangleFigure*>(figure);
    rectFig->setBounds(cFigure::Rectangle(10, 10, 30, 20));
    rectFig->setFilled(true);
    rectFig->setFillColor(cFigure::BLUE);
    rectFig->setCornerRadius(5);
    canvas->addFigure(figure);

    if (strcmp("tic", getName()) == 0) {
        TictocPacket *msg = new TictocPacket("packet");
        msg->setKind(8);
        msg->setGreeting("Ahoy");
        msg->setFoo(42);
        msg->setByteLength(1000);

        sendCount++;
        updateDisplayString();
        send(msg, "out");
    }
}

void Txc::handleMessage(cMessage *msg)
{
    // Emit signal on message arrival
    emit(roundtripDelaySignal, simTime() - lastSendTime);
    lastSendTime = simTime();

    // Move figure randomly on message arrival
    if (figure) {
        cRectangleFigure *rectFig = static_cast<cRectangleFigure*>(figure);
        double x = uniform(0, 200);
        double y = uniform(0, 150);
        rectFig->setBounds(cFigure::Rectangle(x, y, 30, 20));
    }

    // Update and display send count
    sendCount++;
    updateDisplayString();

    // Send back
    send(msg, "out");
}

void Txc::updateDisplayString()
{
    char buf[32];
    sprintf(buf, "sent: %d", sendCount);
    getDisplayString().setTagArg("t", 0, buf);
}
