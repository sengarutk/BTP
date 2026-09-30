package org.omnetpp.common.ui;

import org.eclipse.swt.custom.CTabFolder;
import org.eclipse.swt.custom.CTabFolderRenderer;
import org.eclipse.swt.graphics.Rectangle;

/**
 * A specialized CTabFolderRenderer which adds some configurable padding around the contents of each tab.
 */
public class CTabFolderRendererWithItemPadding extends CTabFolderRenderer {

    protected int horizontalPadding = 10;
    protected int verticalPadding = 6;

   public CTabFolderRendererWithItemPadding(CTabFolder parent) {
        super(parent);
    }

    public CTabFolderRendererWithItemPadding(CTabFolder parent, int horiz, int vert) {
        this(parent);
        horizontalPadding = horiz;
        verticalPadding = vert;
    }

    @Override
    protected Rectangle computeTrim(int part, int state, int x, int y, int width, int height) {
        Rectangle rect = super.computeTrim(part, state, x, y, width, height);

        if (part >= 0) {
            rect.x -= horizontalPadding;
            rect.width += horizontalPadding * 2;
            rect.y -= verticalPadding;
            rect.height += verticalPadding * 2;
        }

        return rect;
    }
}
