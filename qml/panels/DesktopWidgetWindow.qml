pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import "../services"
import "../theme"

PanelWindow {
    id: root
    required property string widgetId
    required property var screenInfo
    readonly property var record: DesktopState.widgets[widgetId] || {}
    readonly property string recordKey: JSON.stringify(record)
    property real draftX: NaN
    property real draftY: NaN
    property real draftWidth: NaN
    property real draftHeight: NaN
    readonly property real topInset: Theme.barBottom ? 8 : Theme.panelTopMargin
    readonly property real bottomInset: Theme.barBottom ? Theme.panelTopMargin : 8
    readonly property real usableHeight: Math.max(1, screenInfo.height-topInset-bottomInset)
    readonly property real left: Number.isFinite(draftX) ? draftX : (record.x || 0)*Math.max(0,screenInfo.width-width)
    readonly property real top: Number.isFinite(draftY) ? draftY : topInset+(record.y || 0)*Math.max(0,usableHeight-height)
    screen: screenInfo
    color: "transparent"
    anchors { top: true; left: true }
    margins.left: Math.round(Math.max(0,Math.min(screenInfo.width-width,left)))
    margins.top: Math.round(Math.max(topInset,Math.min(screenInfo.height-bottomInset-height,top)))
    implicitWidth: Math.min(screenInfo.width,Number.isFinite(draftWidth) ? draftWidth : record.width || 320)
    implicitHeight: Math.min(usableHeight,Number.isFinite(draftHeight) ? draftHeight : record.height || 240)
    exclusionMode: ExclusionMode.Ignore; exclusiveZone: 0
    WlrLayershell.namespace: "lme-desktop"
    WlrLayershell.layer: DesktopState.editing ? WlrLayer.Overlay : WlrLayer.Bottom
    WlrLayershell.keyboardFocus: record.interactive || DesktopState.editing ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
    mask: Region { item: root.record.interactive || DesktopState.editing ? card : null; radius: 24 }
    BackgroundEffect.blurRegion: ShellState.barBlurEnabled ? blur : null
    Region { id: blur; item: card; radius: 24 }
    onRecordKeyChanged: { draftX=NaN;draftY=NaN;draftWidth=NaN;draftHeight=NaN; }
    function commit() {
        DesktopState.patch(widgetId,{x:Math.max(0,Math.min(1,left/Math.max(1,screenInfo.width-implicitWidth))),
            y:Math.max(0,Math.min(1,(top-topInset)/Math.max(1,usableHeight-implicitHeight))),width:Math.round(implicitWidth),height:Math.round(implicitHeight)});
    }
    DesktopCard {
        id: card; anchors.fill: parent; widgetId: root.widgetId; record: root.record
        onMoveBy: (dx,dy) => { root.draftX=Math.max(0,Math.min(root.screenInfo.width-root.width,root.left+dx));root.draftY=Math.max(root.topInset,Math.min(root.screenInfo.height-root.bottomInset-root.height,root.top+dy)); }
        onResizeBy: (dx,dy) => { root.draftWidth=Math.max(180,Math.min(1200,root.screenInfo.width,root.implicitWidth+dx));root.draftHeight=Math.max(180,Math.min(1200,root.usableHeight,root.implicitHeight+dy)); }
        onCommitted: root.commit()
    }
}
