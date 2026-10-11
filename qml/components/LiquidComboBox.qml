pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import "../theme"

ComboBox {
    id: root
    implicitWidth: Math.max(132, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: 40
    leftPadding: 10
    rightPadding: 30
    topPadding: 8
    bottomPadding: 8
    hoverEnabled: true
    font.family: Theme.buttonFamily
    font.pixelSize: Theme.bodySize - 1
    palette.button: Theme.fieldFill
    palette.buttonText: Theme.fieldText
    palette.text: Theme.fieldText
    palette.base: Theme.panel
    palette.window: Theme.panel
    palette.windowText: Theme.text
    palette.highlight: Theme.accent
    palette.highlightedText: Theme.background

    background: Rectangle {
        radius: root.hovered && Theme.animations ? 12 : Theme.smallRadius
        color: root.down ? Qt.lighter(root.palette.button, 1.18) : root.hovered && root.enabled ? Qt.lighter(root.palette.button, 1.1) : root.palette.button
        border.width: root.visualFocus ? 2 : 1
        border.color: root.visualFocus ? Theme.accent : Theme.alpha(Theme.border, root.enabled ? 0.65 : 0.35)
        Behavior on color { ColorAnimation { duration: Theme.animationDuration } }
        Behavior on radius { MotionAnimation {} }
        LiquidFeedback { hovered: root.hovered; pressed: root.down; radius: parent.radius }
    }

    contentItem: Text {
        text: root.displayText
        textFormat: Text.PlainText
        color: root.enabled ? Theme.fieldText : Theme.muted
        font: root.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    indicator: Canvas {
        x: root.width - width - 11
        y: (root.height - height) / 2
        width: 10
        height: 6
        property color strokeColor: root.enabled ? Theme.text : Theme.muted
        onStrokeColorChanged: requestPaint()
        onPaint: {
            const context = getContext("2d");
            context.clearRect(0, 0, width, height);
            context.strokeStyle = strokeColor;
            context.lineWidth = 1.5;
            context.lineCap = "round";
            context.lineJoin = "round";
            context.beginPath();
            context.moveTo(1, 1);
            context.lineTo(width / 2, height - 1);
            context.lineTo(width - 1, 1);
            context.stroke();
        }
    }

    delegate: ItemDelegate {
        id: option
        required property int index
        width: menuList.width
        height: 36
        leftPadding: 12
        rightPadding: 25
        hoverEnabled: true
        highlighted: root.highlightedIndex === index
        text: root.textAt(index)
        font: root.font
        Accessible.name: text

        background: Rectangle {
            radius: 8
            color: option.highlighted || option.hovered ? Theme.alpha(Theme.accent, 0.24) : root.currentIndex === option.index ? Theme.alpha(Theme.accent, 0.12) : "transparent"
        }
        contentItem: Text {
            text: option.text
            textFormat: Text.PlainText
            color: !option.enabled ? Theme.muted : root.currentIndex === option.index ? Theme.accent : Theme.text
            font: option.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        Rectangle {
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            width: 6
            height: 6
            radius: 3
            color: Theme.accent
            visible: root.currentIndex === option.index
        }
    }

    popup: Popup {
        x: root.width - width
        y: root.height + 6
        width: Math.max(root.width, 176)
        implicitHeight: Math.min(menuList.contentHeight + topPadding + bottomPadding, 300)
        padding: 6
        // Keep the menu inside the shell's surface, independent of the system Qt style.
        popupType: Popup.Item

        background: Rectangle {
            color: Theme.panel
            radius: Theme.smallRadius
            border.width: 1
            border.color: Theme.border
        }
        contentItem: ListView {
            id: menuList
            clip: true
            implicitHeight: contentHeight
            model: root.popup.visible ? root.delegateModel : null
            currentIndex: root.highlightedIndex
            boundsBehavior: Flickable.StopAtBounds
            ScrollIndicator.vertical: ScrollIndicator {}
        }
    }
}
