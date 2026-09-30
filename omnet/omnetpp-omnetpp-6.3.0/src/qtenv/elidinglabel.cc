//==========================================================================
//  ELIDINGLABEL.CC - part of
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

#include "elidinglabel.h"
#include <QtGui/QPainter>
#include <QtGui/QFontMetrics>

namespace omnetpp {
namespace qtenv {

ElidingLabel::ElidingLabel(QWidget *parent)
    : QLabel(parent)
{
}

QSize ElidingLabel::sizeHint() const
{
    // Return size hint for the full text
    QSize textSize = fontMetrics().size(Qt::TextSingleLine, text());

    // Add margins
    int margin = this->margin();
    return textSize + QSize(2 * margin, 2 * margin);
}

QSize ElidingLabel::minimumSizeHint() const
{
    // Return a reasonable minimum size
    QSize textSize = fontMetrics().size(Qt::TextSingleLine, "...");

    // Add margins
    int margin = this->margin();
    return textSize + QSize(2 * margin, 2 * margin);
}

void ElidingLabel::paintEvent(QPaintEvent *event)
{
    // Skipping the QLabel base implementation
    QFrame::paintEvent(event);

    QPainter painter(this);
    QRect cr = contentsRect();

    // Get elided text that fits in the available width
    QString elidedText = fontMetrics().elidedText(text(), Qt::ElideRight, cr.width());

    // Use the same style as QLabel
    painter.setPen(palette().color(foregroundRole()));
    painter.setFont(font());

    // Draw the text
    QTextOption option;
    option.setAlignment(alignment());
    option.setWrapMode(QTextOption::NoWrap);

    painter.drawText(cr, elidedText, option);
}

}  // namespace qtenv
}  // namespace omnetpp
