#-------------------------------------------------
#
# Project created by QtCreator 2015-03-13T00:38:46
#
#-------------------------------------------------
#
# THIS FILE IS NO LONGER USED FOR BUILDING QTENV.
#
# It is merely a "project file" for Qt Creator.
# The following still applies though:
#
# To properly set up the project/build process for Qt Creator you need to invoke only
# the 'make' command in this directory (by default Qt Creator also invokes qmake)
#
# - make sure PATH contains the omnetpp/bin directory
#   (for example by starting Qt Creator from the command line after sourcing the setenv script)
# - open this file as a project
# - select the "Projects" pane on the left
# - press "Configure Project" button
# - select the "Projects" pane again
# - turn off "Shadow build"
# - on the build steps, delete the "qmake" build step
# - optional (if you want to create release builds from QtCreator):
#   for the release configuration add the MODE=release argument to the make line
# - optional (for faster build times):
#   add -j8 (or whatever number suits your system best) to the Make arguments line

TARGET = qtenv
TEMPLATE = lib

MAKEFILE_GENERATOR = UNIX
QMAKE_MACOSX_DEPLOYMENT_TARGET = 10.7

# makes the QMAKE_MOC variable available, so we can add OPP_CFLAGS to it
load(moc)

# IMPORTANT: on turn off the option to generate both debug and release version
# we need only one of them not both and this is the default setting on Windows
# but sadly it generates broken makefiles
CONFIG *= static c++14 qt
CONFIG -= debug_and_release
CONFIG -= warn_on warn_off
DEFINES += "QT_NO_KEYWORDS"
WARNING_FLAGS *= -Wall -Wextra -Wno-unused-parameter -Wno-microsoft-enum-value
QMAKE_CXXFLAGS += $$(OPP_CFLAGS) $$WARNING_FLAGS
QMAKE_CFLAGS += $$(OPP_CFLAGS) $$WARNING_FLAGS
# we have to add all defines to the MOC compiler command line to correctly parse the code
QMAKE_MOC += $$(OPP_DEFINES)

# add QT modules
QT *= core gui opengl openglwidgets widgets printsupport

SOURCES += animationcontrollerdialog.cc \
    areaselectordialog.cc \
    arrow.cc \
    canvasinspector.cc \
    canvasrenderer.cc \
    canvasviewer.cc \
    chartgriditem.cc \
    charttickdecimal.cc \
    comboselectiondialog.cc \
    componenthistory.cc \
    compoundmoduleitem.cc \
    connectionitem.cc \
    displaystringaccess.cc \
    displayupdatecontroller.cc \
    elidinglabel.cc \
    exponentialspinbox.cc \
    figurerenderers.cc \
    fileeditor.cc \
    findobjectsdialog.cc \
    genericobjectinspector.cc \
    genericobjecttreemodel.cc \
    genericobjecttreenodes.cc \
    graphicsitems.cc \
    highlighteritemdelegate.cc \
    histograminspector.cc \
    histograminspectorconfigdialog.cc \
    histogramview.cc \
    imagecache.cc \
    inspector.cc \
    inspectorfactory.cc \
    inspectorutil.cc \
    iosgviewer.cc \
    layersdialog.cc \
    layouterenv.cc \
    logbuffer.cc \
    logfilterdialog.cc \
    logfinddialog.cc \
    loginspector.cc \
    mainwindow.cc \
    messageanimations.cc \
    messageanimator.cc \
    messageitem.cc \
    messageprintertagsdialog.cc \
    modulecanvasviewer.cc \
    moduleinspector.cc \
    modulelayouter.cc \
    objectlistmodel.cc \
    objectlistview.cc \
    objecttreeinspector.cc \
    osgcanvasinspector.cc \
    outputvectorinspector.cc \
    outputvectorinspectorconfigdialog.cc \
    outputvectorview.cc \
    preferencesdialog.cc \
    qtenv.cc \
    qtutil.cc \
    randomicongen.cc \
    runselectiondialog.cc \
    rununtildialog.cc \
    stopdialog.cc \
    submoduleitem.cc \
    textviewerproviders.cc \
    textviewerwidget.cc \
    timelinegraphicsview.cc \
    timelineinspector.cc \
    vectorplotitem.cc \
    videorecordingdialog.cc \
    watchinspector.cc


HEADERS += animationcontrollerdialog.h \
    areaselectordialog.h \
    arrow.h \
    canvasinspector.h \
    canvasrenderer.h \
    canvasviewer.h \
    chartgriditem.h \
    charttickdecimal.h \
    circularbuffer.h \
    comboselectiondialog.h \
    componenthistory.h \
    compoundmoduleitem.h \
    connectionitem.h \
    displaystringaccess.h \
    displayupdatecontroller.h \
    elidinglabel.h \
    exponentialspinbox.h \
    figurerenderers.h \
    fileeditor.h \
    findobjectsdialog.h \
    genericobjectinspector.h \
    genericobjecttreemodel.h \
    genericobjecttreenodes.h \
    graphicsitems.h \
    highlighteritemdelegate.h \
    histograminspectorconfigdialog.h \
    histograminspector.h \
    histogramview.h \
    imagecache.h \
    inspectorfactory.h \
    inspector.h \
    inspectorutil.h \
    inspectorutiltypes.h \
    iosgviewer.h \
    layersdialog.h \
    layouterenv.h \
    logbuffer.h \
    logfilterdialog.h \
    logfinddialog.h \
    loginspector.h \
    mainwindow.h \
    messageanimations.h \
    messageanimator.h \
    messageitem.h \
    messageprintertagsdialog.h \
    modulecanvasviewer.h \
    moduleinspector.h \
    modulelayouter.h \
    objectlistmodel.h \
    objectlistview.h \
    objecttreeinspector.h \
    osgcanvasinspector.h \
    outputvectorinspectorconfigdialog.h \
    outputvectorinspector.h \
    outputvectorview.h \
    preferencesdialog.h \
    qtenvdefs.h \
    qtenv.h \
    qtutil.h \
    randomicongen.h \
    runselectiondialog.h \
    rununtildialog.h \
    stopdialog.h \
    submoduleitem.h \
    textviewerproviders.h \
    textviewerwidget.h \
    timelinegraphicsview.h \
    timelineinspector.h \
    vectorplotitem.h \
    videorecordingdialog.h \
    watchinspector.h


# include path is relative to the current build directory (e.g. out/src/gcc-debug/qtenv)
INCLUDEPATH += ../../../../src ../../../../include

# next line is for the QtCreator only to be able to show the OMNeT++ sources (not needed for the actual build process)
INCLUDEPATH += .. ../../include

FORMS += animationcontrollerdialog.ui \
    areaselectordialog.ui \
    comboselectiondialog.ui \
    fileeditor.ui \
    findobjectsdialog.ui \
    histograminspectorconfigdialog.ui \
    layersdialog.ui \
    logfilterdialog.ui \
    logfinddialog.ui \
    mainwindow.ui \
    messageprintertagsdialog.ui \
    outputvectorinspectorconfigdialog.ui \
    preferencesdialog.ui \
    runselectiondialog.ui \
    rununtildialog.ui \
    stopdialog.ui \
    videorecordingdialog.ui

RESOURCES += \
    fonts.qrc \
    icons.qrc
