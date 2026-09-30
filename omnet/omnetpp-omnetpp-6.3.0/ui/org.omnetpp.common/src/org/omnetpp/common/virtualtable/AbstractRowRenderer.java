package org.omnetpp.common.virtualtable;

import org.eclipse.jface.resource.JFaceResources;
import org.eclipse.jface.viewers.StyledString;
import org.eclipse.swt.custom.StyleRange;
import org.eclipse.swt.graphics.Font;
import org.eclipse.swt.graphics.GC;
import org.eclipse.swt.graphics.TextLayout;

/**
 * Base class for VirtualTable row renderers.
 *
 * @author andras
 */
public abstract class AbstractRowRenderer<T> implements IVirtualTableRowRenderer<T> {
    protected Font font = JFaceResources.getDefaultFont();
    protected int fontHeight = 0;

    public AbstractRowRenderer() {
        super();
    }

    public Font getFont() {
        return font;
    }

    public void setFont(Font font) {
        this.font = font;
    }

    public int getRowHeight(GC gc) {
        if (fontHeight == 0) {
            Font oldFont = gc.getFont();
            gc.setFont(font);
            fontHeight = gc.getFontMetrics().getHeight();
            gc.setFont(oldFont);
        }

        return fontHeight + 3;
    }

    @Override
    public void drawCell(GC gc, T element, int index, boolean isSelected) {
        StyledString styledString = getStyledText(element, index, isSelected);
        int indent = getIndentation(element, index);
        drawStyledString(gc, styledString, indent, 0);
    }

    protected void drawStyledString(GC gc, StyledString styledString, int x, int y) {
        TextLayout textLayout = new TextLayout(gc.getDevice());
        textLayout.setText(styledString.getString());
        for (StyleRange styleRange : styledString.getStyleRanges())
            textLayout.setStyle(styleRange, styleRange.start, styleRange.start + styleRange.length);
        textLayout.draw(gc, x, y);
        textLayout.dispose();
    }

}