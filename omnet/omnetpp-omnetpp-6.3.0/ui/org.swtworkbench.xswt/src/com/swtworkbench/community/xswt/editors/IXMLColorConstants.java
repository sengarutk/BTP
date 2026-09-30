package com.swtworkbench.community.xswt.editors;

import org.eclipse.swt.graphics.RGB;
import org.omnetpp.common.util.DisplayUtils;

public abstract interface IXMLColorConstants {
    // Light theme colors (original)
    public static final RGB XML_COMMENT_LIGHT = new RGB(128, 0, 0);
    public static final RGB PROC_INSTR_LIGHT = new RGB(128, 128, 128);
    public static final RGB STRING_LIGHT = new RGB(0, 128, 0);
    public static final RGB DEFAULT_LIGHT = new RGB(0, 0, 0);
    public static final RGB TAG_LIGHT = new RGB(0, 0, 128);

    // Dark theme colors (bright colors for dark background)
    public static final RGB XML_COMMENT_DARK = new RGB(255, 128, 128);  // light red/salmon
    public static final RGB PROC_INSTR_DARK = new RGB(192, 192, 192);   // light gray
    public static final RGB STRING_DARK = new RGB(128, 255, 128);       // light green
    public static final RGB DEFAULT_DARK = new RGB(220, 220, 220);      // light gray for default text
    public static final RGB TAG_DARK = new RGB(128, 192, 255);          // light blue

    // Dynamic methods to get theme-appropriate colors
    public static RGB getXmlCommentColor() {
        return isDarkTheme() ? XML_COMMENT_DARK : XML_COMMENT_LIGHT;
    }

    public static RGB getProcInstrColor() {
        return isDarkTheme() ? PROC_INSTR_DARK : PROC_INSTR_LIGHT;
    }

    public static RGB getStringColor() {
        return isDarkTheme() ? STRING_DARK : STRING_LIGHT;
    }

    public static RGB getDefaultColor() {
        return isDarkTheme() ? DEFAULT_DARK : DEFAULT_LIGHT;
    }

    public static RGB getTagColor() {
        return isDarkTheme() ? TAG_DARK : TAG_LIGHT;
    }

    // Helper method to detect dark theme
    private static boolean isDarkTheme() {
        return DisplayUtils.isDarkTheme();
    }
}
