import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

Item {
    id: compactRoot

    readonly property bool inVerticalPanel: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property bool hasData: !!root.statsData
    readonly property int displayStyle: (root.panelDisplayStyle !== undefined) ? root.panelDisplayStyle : 0

    // Color selection depending on status with high-contrast panel colors
    function getStatusColor(util, pace, hits100) {
        if (!compactRoot.hasData && root.errorMessage !== "") {
            return Kirigami.Theme.neutralTextColor;
        }
        if (hits100 || util >= 90) {
            return "#ff5555"; // Leuchtendes Rot
        }
        if (util > pace + 10 || util >= 75) {
            return "#ffb86c"; // Helles Amber / Orange
        }
        return "#4cd964"; // Helles, gut lesbares Grün
    }

    readonly property bool isPanel: Plasmoid.formFactor !== PlasmaCore.Types.Planar
    readonly property int compactFontSize: Math.max(11, Math.round(Kirigami.Theme.smallFont.pixelSize * 1.15))
    readonly property color labelColor: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.78)

    implicitWidth: {
        if (inVerticalPanel) {
            return Kirigami.Units.gridUnit * 2.2;
        }
        if (displayStyle === 1) { // Progress Ring only
            return 36;
        }
        return rowLayout.implicitWidth + Kirigami.Units.smallSpacing * 2;
    }
    implicitHeight: inVerticalPanel ? (colLayout.implicitHeight + Kirigami.Units.smallSpacing * 2) : Kirigami.Units.gridUnit * 2

    Layout.preferredWidth: inVerticalPanel ? -1 : implicitWidth
    Layout.preferredHeight: inVerticalPanel ? implicitHeight : -1
    Layout.minimumWidth: inVerticalPanel ? -1 : implicitWidth
    Layout.minimumHeight: inVerticalPanel ? implicitHeight : -1

    // Horizontal layout (standard panel bottom or top)
    RowLayout {
        id: rowLayout
        visible: !inVerticalPanel
        anchors.centerIn: parent
        spacing: Kirigami.Units.smallSpacing + 2

        // Mode 0: Icon for pure text mode
        Kirigami.Icon {
            visible: compactRoot.displayStyle === 0
            source: Plasmoid.icon ? Plasmoid.icon : "utilities-system-monitor"
            implicitWidth: 22
            implicitHeight: 22
            Layout.alignment: Qt.AlignVCenter
        }

        // Modes 1 & 2: Radial Gauge Progress Ring
        Item {
            id: ringGaugeItem
            visible: compactRoot.displayStyle === 1 || compactRoot.displayStyle === 2
            implicitWidth: 32
            implicitHeight: 32
            Layout.alignment: Qt.AlignVCenter

            readonly property real sUtil: Math.max(0, Math.min(100, root.sessionUtil))
            readonly property real wUtil: Math.max(0, Math.min(100, root.weeklyUtil))
            readonly property color sColor: compactRoot.getStatusColor(root.sessionUtil, root.sessionPace, root.sessionHits100)
            readonly property color wColor: compactRoot.getStatusColor(root.weeklyUtil, root.weeklyPace, root.weeklyHits100)

            Shape {
                id: outerRingShape
                anchors.fill: parent
                layer.enabled: true
                layer.samples: 4

                // Outer Background Track (5h Session)
                ShapePath {
                    strokeColor: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.18)
                    strokeWidth: 2.5
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap

                    PathAngleArc {
                        centerX: 16
                        centerY: 16
                        radiusX: 13.5
                        radiusY: 13.5
                        startAngle: -90
                        sweepAngle: 360
                    }
                }

                // Outer Progress Track (5h Session)
                ShapePath {
                    strokeColor: ringGaugeItem.sColor
                    strokeWidth: 2.5
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap

                    PathAngleArc {
                        centerX: 16
                        centerY: 16
                        radiusX: 13.5
                        radiusY: 13.5
                        startAngle: -90
                        sweepAngle: (ringGaugeItem.sUtil > 0) ? (360 * (ringGaugeItem.sUtil / 100.0)) : 0.001
                    }
                }

                // Inner Background Track (7d Weekly)
                ShapePath {
                    strokeColor: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.12)
                    strokeWidth: 2.0
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap

                    PathAngleArc {
                        centerX: 16
                        centerY: 16
                        radiusX: 9.5
                        radiusY: 9.5
                        startAngle: -90
                        sweepAngle: 360
                    }
                }

                // Inner Progress Track (7d Weekly)
                ShapePath {
                    strokeColor: ringGaugeItem.wColor
                    strokeWidth: 2.0
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap

                    PathAngleArc {
                        centerX: 16
                        centerY: 16
                        radiusX: 9.5
                        radiusY: 9.5
                        startAngle: -90
                        sweepAngle: (ringGaugeItem.wUtil > 0) ? (360 * (ringGaugeItem.wUtil / 100.0)) : 0.001
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                text: (!compactRoot.hasData && root.errorMessage !== "") ? "--" : "%1".arg(Math.round(root.sessionUtil))
                font.pixelSize: 9
                font.bold: true
                color: ringGaugeItem.sColor
            }
        }

        // Modes 0 & 2: Numeric text columns
        ColumnLayout {
            id: textColumn
            visible: compactRoot.displayStyle === 0 || compactRoot.displayStyle === 2
            spacing: 1
            Layout.alignment: Qt.AlignVCenter

            // 5h Session limit
            RowLayout {
                spacing: 4
                Text {
                    text: "5h:"
                    font.pixelSize: compactRoot.compactFontSize
                    font.weight: Font.DemiBold
                    color: compactRoot.labelColor
                }
                Text {
                    text: (!compactRoot.hasData && root.errorMessage !== "") ? "--%" : "%1%".arg(Math.round(root.sessionUtil))
                    font.pixelSize: compactRoot.compactFontSize
                    font.weight: Font.Bold
                    color: compactRoot.getStatusColor(root.sessionUtil, root.sessionPace, root.sessionHits100)
                }
            }

            // 7d Weekly limit
            RowLayout {
                spacing: 4
                Text {
                    text: "7d:"
                    font.pixelSize: compactRoot.compactFontSize
                    font.weight: Font.DemiBold
                    color: compactRoot.labelColor
                }
                Text {
                    text: (!compactRoot.hasData && root.errorMessage !== "") ? "--%" : "%1%".arg(Math.round(root.weeklyUtil))
                    font.pixelSize: compactRoot.compactFontSize
                    font.weight: Font.Bold
                    color: compactRoot.getStatusColor(root.weeklyUtil, root.weeklyPace, root.weeklyHits100)
                }
            }
        }
    }

    // Vertical layout (side panel)
    ColumnLayout {
        id: colLayout
        visible: inVerticalPanel
        anchors.centerIn: parent
        spacing: 2

        Kirigami.Icon {
            visible: compactRoot.displayStyle === 0
            source: Plasmoid.icon ? Plasmoid.icon : "utilities-system-monitor"
            implicitWidth: Kirigami.Units.iconSizes.small
            implicitHeight: Kirigami.Units.iconSizes.small
            Layout.alignment: Qt.AlignHCenter
        }

        Item {
            id: vertRingGaugeItem
            visible: compactRoot.displayStyle === 1 || compactRoot.displayStyle === 2
            implicitWidth: 32
            implicitHeight: 32
            Layout.alignment: Qt.AlignHCenter

            readonly property real sUtil: Math.max(0, Math.min(100, root.sessionUtil))
            readonly property real wUtil: Math.max(0, Math.min(100, root.weeklyUtil))
            readonly property color sColor: compactRoot.getStatusColor(root.sessionUtil, root.sessionPace, root.sessionHits100)
            readonly property color wColor: compactRoot.getStatusColor(root.weeklyUtil, root.weeklyPace, root.weeklyHits100)

            Shape {
                id: vertOuterRingShape
                anchors.fill: parent
                layer.enabled: true
                layer.samples: 4

                ShapePath {
                    strokeColor: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.18)
                    strokeWidth: 2.5
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap

                    PathAngleArc {
                        centerX: 16
                        centerY: 16
                        radiusX: 13.5
                        radiusY: 13.5
                        startAngle: -90
                        sweepAngle: 360
                    }
                }

                ShapePath {
                    strokeColor: vertRingGaugeItem.sColor
                    strokeWidth: 2.5
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap

                    PathAngleArc {
                        centerX: 16
                        centerY: 16
                        radiusX: 13.5
                        radiusY: 13.5
                        startAngle: -90
                        sweepAngle: (vertRingGaugeItem.sUtil > 0) ? (360 * (vertRingGaugeItem.sUtil / 100.0)) : 0.001
                    }
                }

                ShapePath {
                    strokeColor: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.12)
                    strokeWidth: 2.0
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap

                    PathAngleArc {
                        centerX: 16
                        centerY: 16
                        radiusX: 9.5
                        radiusY: 9.5
                        startAngle: -90
                        sweepAngle: 360
                    }
                }

                ShapePath {
                    strokeColor: vertRingGaugeItem.wColor
                    strokeWidth: 2.0
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap

                    PathAngleArc {
                        centerX: 16
                        centerY: 16
                        radiusX: 9.5
                        radiusY: 9.5
                        startAngle: -90
                        sweepAngle: (vertRingGaugeItem.wUtil > 0) ? (360 * (vertRingGaugeItem.wUtil / 100.0)) : 0.001
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                text: (!compactRoot.hasData && root.errorMessage !== "") ? "--" : "%1".arg(Math.round(root.sessionUtil))
                font.pixelSize: 9
                font.bold: true
                color: vertRingGaugeItem.sColor
            }
        }

        Text {
            visible: compactRoot.displayStyle === 0 || compactRoot.displayStyle === 2
            text: (!compactRoot.hasData && root.errorMessage !== "") ? "--%" : "%1%".arg(Math.round(root.sessionUtil))
            font.pixelSize: compactRoot.compactFontSize
            font.weight: Font.Bold
            color: compactRoot.getStatusColor(root.sessionUtil, root.sessionPace, root.sessionHits100)
            Layout.alignment: Qt.AlignHCenter
        }

        Text {
            visible: compactRoot.displayStyle === 0 || compactRoot.displayStyle === 2
            text: (!compactRoot.hasData && root.errorMessage !== "") ? "--%" : "%1%".arg(Math.round(root.weeklyUtil))
            font.pixelSize: compactRoot.compactFontSize
            font.weight: Font.Bold
            color: compactRoot.getStatusColor(root.weeklyUtil, root.weeklyPace, root.weeklyHits100)
            Layout.alignment: Qt.AlignHCenter
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            root.expanded = !root.expanded;
        }
    }
}
