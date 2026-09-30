//==========================================================================
//  ELIDINGLABEL.H - part of
//
//                     OMNeT++/OMNEST
//            Discrete System Simulation in C++
//
//==========================================================================

/*--------------------------------------------------------------*
  Copyright (C) 1992-2017 Andras Varga
  Copyright (C) 2006-2017 OpenSim Ltd.

  This file is distributed WITHOUT ANY WARRANTY. See the file
  `license' for details on this and other legal matters.
*--------------------------------------------------------------*/

#ifndef __OMNETPP_QTENV_ELIDINGLABEL_H
#define __OMNETPP_QTENV_ELIDINGLABEL_H

#include <QtWidgets/QLabel>
#include "qtenvdefs.h"

namespace omnetpp {
namespace qtenv {

/**
 * A simple QLabel subclass that elides text from the right when it doesn't fit.
 * Uses Qt's built-in elidedText() function with Qt::ElideRight mode.
 */
class QTENV_API ElidingLabel : public QLabel
{
    Q_OBJECT

public:
    explicit ElidingLabel(QWidget *parent = nullptr);

    // Override size hints to provide proper sizing behavior
    QSize sizeHint() const override;
    QSize minimumSizeHint() const override;

protected:
    // Override paintEvent to perform text elision
    void paintEvent(QPaintEvent *event) override;
};

}  // namespace qtenv
}  // namespace omnetpp

#endif // __OMNETPP_QTENV_ELIDINGLABEL_H
