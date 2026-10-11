pragma ComponentBehavior: Bound
import QtQuick
import "../components"
import "../theme"

Item {
    id: root
    required property var modules
    property var screenInfo: null
    property var windowInfo: null
    property real budget: 500
    property bool compact: false
    property bool island: true
    implicitWidth: Math.min(budget, row.implicitWidth > 0 ? row.implicitWidth + 20 : 0)
    implicitHeight: Theme.barHeight
    visible: implicitWidth > 0
    GlassPanel { role: "barFill"; anchors.fill: parent; radius: height / 2; visible: root.island }
    Flickable {
        id: scroller
        objectName: "barModuleViewport"
        anchors.fill: parent; anchors.margins: Math.max(1, (root.height - 34) / 2); anchors.leftMargin: 10; anchors.rightMargin: 10
        contentWidth: row.implicitWidth; contentHeight: height
        clip: true; boundsBehavior: Flickable.StopAtBounds; flickableDirection: Flickable.HorizontalFlick
        Row {
            id: row
            height: parent.height; spacing: 4
            Repeater {
                model: root.modules
                delegate: BarModule {
                    id: barModule
                    required property string modelData
                    moduleId: modelData; screenInfo: root.screenInfo; windowInfo: root.windowInfo
                    compact: root.compact; titleBudget: Math.max(0, root.budget - 20)
                    Connections {
                        target: barModule.item
                        function onActiveFocusChanged() {
                            const item = barModule.item as Item;
                            if (item && item.activeFocus) {
                                if (barModule.x < scroller.contentX) scroller.contentX = barModule.x;
                                else if (barModule.x + barModule.width > scroller.contentX + scroller.width)
                                    scroller.contentX = Math.max(0, barModule.x + barModule.width - scroller.width);
                            }
                        }
                    }
                }
            }
        }
    }
}
