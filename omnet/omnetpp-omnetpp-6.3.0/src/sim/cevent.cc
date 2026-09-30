//========================================================================
//  CEVENT.CC - part of
//
//                 OMNeT++/OMNEST
//              Discrete System Simulation in C++
//
//========================================================================

/*--------------------------------------------------------------*
  Copyright (C) 1992-2017 Andras Varga
  Copyright (C) 2006-2017 OpenSim Ltd.

  This file is distributed WITHOUT ANY WARRANTY. See the file
  `license' for details on this and other legal matters.
*--------------------------------------------------------------*/

#include <cstdio>  // sprintf
#include <sstream>
#include "omnetpp/globals.h"
#include "omnetpp/cevent.h"
#include "omnetpp/csimulation.h"
#include "omnetpp/cexception.h"
#include "omnetpp/cenvir.h"
#include "omnetpp/ccommbuffer.h"

using namespace omnetpp;

using std::ostream;

std::string cEvent::str() const
{
    if (!isScheduled())
        return "";
    else {
        std::stringstream out;
        simtime_t dt = arrivalTime - getSimulation()->getSimTime();
        out << "for t=" << arrivalTime.ustr() << " (now+" << dt.ustr() << ")";
        if (getTargetObject())
            out << ", target=" << getTargetObject()->getFullPath();
        return out.str();
    }
}

void cEvent::forEachChild(cVisitor *v)
{
}

void cEvent::parsimPack(cCommBuffer *buffer) const
{
    cOwnedObject::parsimPack(buffer);

    switch (buffer->getMode()) {
        case cCommBuffer::FINGERPRINT:
            // nothing to pack
            break;
        case cCommBuffer::FINGERPRINT_LEGACY:
            buffer->pack(priority);
            buffer->pack(arrivalTime);
            buffer->pack(heapIndex);
            buffer->pack(insertOrder);
            break;
        default: // case cCommBuffer::PARSIMPACK, etc.
            // heanIndex and insertOrder are only used by cEvent, no need to pack them
            buffer->pack(priority);
            buffer->pack(arrivalTime);
            break;
    }
}

void cEvent::parsimUnpack(cCommBuffer *buffer)
{
    cOwnedObject::parsimUnpack(buffer);

    switch (buffer->getMode()) {
        case cCommBuffer::FINGERPRINT:
            break;
        case cCommBuffer::FINGERPRINT_LEGACY:
            buffer->unpack(priority);
            buffer->unpack(arrivalTime);
            buffer->unpack(heapIndex);
            buffer->unpack(insertOrder);
            break;
        default: // case cCommBuffer::PARSIMPACK, etc.
            heapIndex = -1;
            buffer->unpack(priority);
            buffer->unpack(arrivalTime);
            break;
    }
}

cEvent& cEvent::operator=(const cEvent& event)
{
    if (this == &event)
        return *this;

    if (isScheduled())
        throw cRuntimeError(this, "operator=() may not be called while the event or message is scheduled"); // as it could affect the ordering of scheduled messages, violating the invariants of the FES data structure

    cOwnedObject::operator=(event);

    priority = event.priority;
    arrivalTime = event.arrivalTime;

    return *this;
}

void cEvent::setSchedulingPriority(short p)
{
    if (isScheduled())
        throw cRuntimeError(this, "setSchedulingPriority() may not be called while the event or message is scheduled"); // as it could affect the ordering of scheduled messages, violating the invariants of the FES data structure
    priority = p;
}

bool cEvent::shouldPrecede(const cEvent *other) const
{
    return getArrivalTime() < other->getArrivalTime() ? true :
           getArrivalTime() > other->getArrivalTime() ? false :
           getSchedulingPriority() == other->getSchedulingPriority() ? getInsertOrder() < other->getInsertOrder() :
           getSchedulingPriority() < other->getSchedulingPriority() ? true :
           getSchedulingPriority() > other->getSchedulingPriority() ? false :
           getInsertOrder() < other->getInsertOrder();
}

int cEvent::compareBySchedulingOrder(const cEvent *a, const cEvent *b)
{
    if (a->getArrivalTime() < b->getArrivalTime())
        return -1;
    if (a->getArrivalTime() > b->getArrivalTime())
        return 1;

    int priorityDiff = a->getSchedulingPriority() - b->getSchedulingPriority();
    if (priorityDiff)
        return priorityDiff;

    return a->getInsertOrder() < b->getInsertOrder() ? -1 : 1; // they cannot be equal
}
