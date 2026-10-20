import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Item {
    id: fullRoot

    property string weeklyTimeframe: "7d" // "7h", "24h", "7d"

    implicitWidth: Kirigami.Units.gridUnit * 18
    implicitHeight: mainColumn.implicitHeight + Kirigami.Units.gridUnit


    function formatMinutes(min) {
        if (!min || min <= 0) return "0m";
        var d = Math.floor(min / 1440);
        var h = Math.floor((min % 1440) / 60);
        var m = min % 60;
        if (d > 0) {
            return "%1d %2h".arg(d).arg(h);
        } else if (h > 0) {
            return "%1h %2m".arg(h).arg(m);
        }
        return "%1m".arg(m);
    }

    function formatResetTime(isoStr, isWeekly) {
        if (!isoStr || isoStr === "") return "";
        var dt = new Date(isoStr);
        if (isNaN(dt.getTime())) return "";
        var timeStr = Qt.formatTime(dt, "hh:mm");
        if (isWeekly) {
            var isDe = (root.languageMode === 2) || (root.languageMode === 0 && (Qt.locale().name.indexOf("de") === 0));
            var daysDe = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
            var daysEn = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
            var dayName = isDe ? daysDe[dt.getDay()] : daysEn[dt.getDay()];
            return isDe ? "%1 %2 Uhr".arg(dayName).arg(timeStr) : "%1 %2".arg(dayName).arg(timeStr);
        }
        return timeStr;
    }

    function formatEta(min) {
        if (!min || min === null) return root.tr("No exhaustion");
        return formatMinutes(min);
    }

    function formatTrend(trend) {
        if (!trend) return "";
        return root.tr(trend);
    }

    // Leitet die Alarm-Warnstufe ab (Parität zu ChartSeverityResolver der Windows-App):
    // "critical" wenn das Limit vor dem Reset erreicht wird, "warning" bei Verbrauch über dem
    // Soll-Tempo, sonst "none". Bei inaktiver Sitzung immer "none" (keine sinnvolle Prognose).
    function alarmSeverity(hits100, paceStatus, active) {
        if (!active) return "none";
        if (hits100) return "critical";
        if (paceStatus === "ahead_of_pace") return "warning";
        return "none";
    }

    // Baut den Alarmtext: kritisch mit Restzeit bis Limit und bis Reset, Warnung als Tempo-Hinweis.
    function alarmText(severity, etaMin, resetsIn) {
        if (severity === "critical") {
            return (etaMin && etaMin > 0)
                ? root.tr("Limit in %1 · reset in %2", formatMinutes(etaMin), formatMinutes(resetsIn))
                : root.tr("Limit reached before reset");
        }
        return (etaMin && etaMin > 0)
            ? root.tr("Over budget · limit in %1", formatMinutes(etaMin))
            : root.tr("Over budget");
    }

    // Alarm-Banner über einem Chart (Parität zur Windows-App): rot bei kritischem Alarm,
    // amber bei Verbrauch über dem Soll-Tempo. Bei severity "none" unsichtbar und ohne Platzbedarf.
    component AlarmBanner: Rectangle {
        id: banner
        property string severity: "none"
        property string message: ""
        readonly property color accent: severity === "critical"
            ? Kirigami.Theme.negativeTextColor
            : Kirigami.Theme.neutralTextColor

        visible: severity !== "none" && message !== ""
        implicitHeight: bannerRow.implicitHeight + Kirigami.Units.smallSpacing * 2
        radius: root.isGlass ? 8 : 6
        // Signalfarbe nur als dezenter Hintergrund + Rand; der Text bleibt in der gut lesbaren
        // UI-Farbe, da akzentfarbener Text (v. a. amber) auf getöntem Grund schwer zu lesen ist.
        color: Qt.rgba(accent.r, accent.g, accent.b, 0.22)
        border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.55)
        border.width: 1

        RowLayout {
            id: bannerRow
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            spacing: Kirigami.Units.smallSpacing

            Text {
                Layout.fillWidth: true
                text: banner.message
                color: root.uiTextColor
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                font.bold: true
                wrapMode: Text.WordWrap
                verticalAlignment: Text.AlignVCenter
            }
        }
    }

    ColumnLayout {
        id: mainColumn
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.mediumSpacing

        // Header
        RowLayout {
            Layout.fillWidth: true

            Kirigami.Heading {
                level: 3
                text: root.tr("Token Monitor for Claude Code")
                color: root.uiTextColor
                Layout.fillWidth: true
            }

            QQC2.Button {
                icon.name: "view-refresh"
                text: ""
                enabled: !root.isFetching
                onClicked: {
                    root.fetchStats(true);
                }
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: root.tr("Refresh now")
            }
        }

        // Rate limit warning banner if active
        Rectangle {
            visible: root.isRateLimited
            Layout.fillWidth: true
            implicitHeight: rateLimitLayout.implicitHeight + Kirigami.Units.smallSpacing * 2
            color: Qt.rgba(Kirigami.Theme.neutralTextColor.r, Kirigami.Theme.neutralTextColor.g, Kirigami.Theme.neutralTextColor.b, 0.2)
            border.color: Kirigami.Theme.neutralTextColor
            border.width: 1
            radius: 4

            RowLayout {
                id: rateLimitLayout
                anchors.centerIn: parent
                width: parent.width - 16
                spacing: 8

                Kirigami.Icon {
                    source: "data-warning"
                    implicitWidth: Kirigami.Units.iconSizes.small
                    implicitHeight: Kirigami.Units.iconSizes.small
                    color: Kirigami.Theme.neutralTextColor
                }

                Text {
                    text: root.tr("API rate limit active (HTTP 429) — Next retry in %1s (Click 🔄 to retry now)", root.rateLimitRemaining)
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    color: root.uiTextColor
                    font.bold: true
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                }
            }
        }

        // Error message banner if present
        Rectangle {
            visible: root.errorMessage !== ""
            Layout.fillWidth: true
            implicitHeight: errorLayout.implicitHeight + Kirigami.Units.smallSpacing * 2
            color: Qt.rgba(Kirigami.Theme.negativeTextColor.r, Kirigami.Theme.negativeTextColor.g, Kirigami.Theme.negativeTextColor.b, 0.2)
            radius: 4

            ColumnLayout {
                id: errorLayout
                anchors.centerIn: parent
                width: parent.width - 16
                spacing: 4

                Text {
                    text: root.errorMessage
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    color: root.uiNegativeColor
                    font.bold: true
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                }

                QQC2.Button {
                    visible: root.errorMessage.indexOf("Daemon") !== -1 || root.errorMessage.indexOf("48291") !== -1
                    Layout.alignment: Qt.AlignLeft
                    icon.name: root.isStartingDaemon ? "view-refresh" : "media-playback-start"
                    text: root.isStartingDaemon ? root.tr("Starting service…") : root.tr("Start Background Service")
                    enabled: !root.isStartingDaemon
                    onClicked: {
                        root.startDaemon(true);
                    }
                }

                Text {
                    visible: root.errorMessage.indexOf("Daemon") !== -1 || root.errorMessage.indexOf("48291") !== -1
                    text: root.tr("Auto-starts and enables systemd user service 'token-monitor.service'")
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    color: root.uiSubTextColor
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize * 0.85
                }

                Text {
                    visible: root.errorMessage.indexOf("Daemon") === -1 && root.errorMessage.indexOf("48291") === -1
                    text: root.tr("Tip: Run './install.sh' or 'systemctl --user start token-monitor'")
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    color: root.uiTextColor
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize * 0.9
                }
            }
        }

        // Stale-Daten-Banner: letzter erfolgreicher Abruf liegt deutlich zurück.
        // Nur zeigen, wenn kein harter Fehler-Banner aktiv ist (sonst doppelte Meldung).
        Rectangle {
            visible: root.dataStale && root.errorMessage === ""
            Layout.fillWidth: true
            implicitHeight: staleLayout.implicitHeight + Kirigami.Units.smallSpacing * 2
            color: Qt.rgba(Kirigami.Theme.neutralTextColor.r, Kirigami.Theme.neutralTextColor.g, Kirigami.Theme.neutralTextColor.b, 0.18)
            border.color: Qt.rgba(Kirigami.Theme.neutralTextColor.r, Kirigami.Theme.neutralTextColor.g, Kirigami.Theme.neutralTextColor.b, 0.4)
            radius: 4

            RowLayout {
                id: staleLayout
                anchors.centerIn: parent
                width: parent.width - 16
                spacing: 8

                Kirigami.Icon {
                    source: "view-refresh"
                    implicitWidth: Kirigami.Units.iconSizes.small
                    implicitHeight: Kirigami.Units.iconSizes.small
                    color: Kirigami.Theme.neutralTextColor
                }

                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: root.uiTextColor
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                    text: {
                        var clock = "";
                        if (root.lastSuccessIso !== "") {
                            var dt = new Date(root.lastSuccessIso);
                            if (!isNaN(dt.getTime())) clock = Qt.formatTime(dt, "hh:mm");
                        }
                        var msg = (clock !== "")
                            ? root.tr("Values out of date — last update %1", clock)
                            : root.tr("Values out of date");
                        if (root.fetchError !== "") msg += " · " + root.fetchError;
                        return msg;
                    }
                }
            }
        }

        // --- SESSION (5 hours) BLOCK ---
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: sessionCol.implicitHeight + Kirigami.Units.smallSpacing * 2
            color: root.uiCardBg
            border.color: root.uiCardBorder
            radius: root.isGlass ? 10 : 6
            clip: true

            ColumnLayout {
                id: sessionCol
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    Text {
                        text: root.tr("5-Hour Session")
                        font.bold: true
                        color: root.uiTextColor
                    }

                    Rectangle {
                        visible: root.activeModelName !== ""
                        radius: 3
                        color: Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.15)
                        border.color: Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.35)
                        border.width: 1
                        implicitWidth: modelBadgeText.implicitWidth + 8
                        implicitHeight: modelBadgeText.implicitHeight + 4

                        Text {
                            id: modelBadgeText
                            anchors.centerIn: parent
                            text: root.activeModelName
                            font.pixelSize: Kirigami.Theme.smallFont.pixelSize * 0.85
                            font.bold: true
                            color: Kirigami.Theme.highlightColor
                        }
                    }

                    Item {
                        Layout.fillWidth: true
                    }

                    Text {
                        text: "%1%".arg(root.sessionUtil)
                        font.bold: true
                        color: root.sessionHits100 ? root.uiNegativeColor : root.uiTextColor
                    }
                }

                // Progress Bar
                QQC2.ProgressBar {
                    Layout.fillWidth: true
                    from: 0
                    to: 100
                    value: root.sessionUtil
                }

                // Budget Pace & Reset
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: root.tr("Target Pace: %1%", root.sessionPace)
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        color: root.uiSubTextColor
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: {
                            var exact = fullRoot.formatResetTime(root.sessionResetsAt, false);
                            var inMin = fullRoot.formatMinutes(root.sessionResetsIn);
                            return exact !== "" ? root.tr("Reset: %1 (in %2)", exact, inMin) : root.tr("Reset in: %1", inMin);
                        }
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        color: root.uiSubTextColor
                    }
                }

                // „Erschöpft vor Reset"-Alarm der Session
                AlarmBanner {
                    Layout.fillWidth: true
                    severity: fullRoot.alarmSeverity(root.sessionHits100, root.sessionPaceStatus, root.isSessionActive)
                    message: fullRoot.alarmText(severity, root.sessionEtaMin, root.sessionResetsIn)
                }

                // Burn-up Chart (Canvas)
                BurnupChart {
                    Layout.fillWidth: true
                    implicitHeight: 90
                    usagePoints: (root.sessionChart && root.sessionChart.usage) ? root.sessionChart.usage : []
                    projectionPoints: (root.sessionChart && root.sessionChart.projection) ? root.sessionChart.projection : []
                    paceValue: root.sessionPace
                    elapsedRatio: (root.sessionChart && root.sessionChart.elapsed_ratio !== undefined) ? root.sessionChart.elapsed_ratio : 0
                    hits100: root.sessionHits100
                    separatorCount: 5 // 5-Stunden-Fenster -> Stundenraster
                }

                // Burn-Rate Info
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: root.tr("Burn: %1%/h (%2)", root.sessionBurnRate, fullRoot.formatTrend(root.sessionTrend))
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        color: root.uiTextColor
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: root.sessionEtaMin ? root.tr("100% in ~%1", fullRoot.formatEta(root.sessionEtaMin)) : root.tr("Safe before reset ✓")
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        font.bold: root.sessionHits100
                        color: root.sessionHits100 ? root.uiNegativeColor : Kirigami.Theme.positiveTextColor
                    }
                }
            }
        }

        // --- WEEKLY (7 days) BLOCK ---
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: weeklyCol.implicitHeight + Kirigami.Units.smallSpacing * 2
            color: root.uiCardBg
            border.color: root.uiCardBorder
            radius: root.isGlass ? 10 : 6
            clip: true

            ColumnLayout {
                id: weeklyCol
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: root.tr("Weekly Limit (7 Days)")
                        font.bold: true
                        color: root.uiTextColor
                        Layout.fillWidth: true
                    }
                    Text {
                        text: "%1%".arg(root.weeklyUtil)
                        font.bold: true
                        color: root.weeklyHits100 ? root.uiNegativeColor : root.uiTextColor
                    }
                }

                QQC2.ProgressBar {
                    Layout.fillWidth: true
                    from: 0
                    to: 100
                    value: root.weeklyUtil
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: root.tr("Target Pace: %1%", root.weeklyPace)
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        color: root.uiSubTextColor
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: {
                            var exact = fullRoot.formatResetTime(root.weeklyResetsAt, true);
                            var inMin = fullRoot.formatMinutes(root.weeklyResetsIn);
                            return exact !== "" ? root.tr("Reset: %1 (in %2)", exact, inMin) : root.tr("Reset in: %1", inMin);
                        }
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        color: root.uiSubTextColor
                    }
                }

                // Timeframe Selector: 7h | 24h | 7d | 30d
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    Item { Layout.fillWidth: true }

                    Repeater {
                        model: ["7h", "24h", "7d", "30d"]
                        delegate: Rectangle {
                            id: tfBtn
                            implicitWidth: tfText.implicitWidth + 12
                            implicitHeight: 20
                            radius: 4
                            readonly property bool isSelected: fullRoot.weeklyTimeframe === modelData

                            color: isSelected
                                ? (root.isGlass ? Qt.rgba(0, 229/255, 255/255, 0.3) : Kirigami.Theme.highlightColor)
                                : (tfMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : "transparent")
                            border.color: isSelected
                                ? (root.isGlass ? "#00e5ff" : Kirigami.Theme.highlightColor)
                                : root.uiCardBorder

                            Text {
                                id: tfText
                                anchors.centerIn: parent
                                text: modelData
                                font.pixelSize: Kirigami.Theme.smallFont.pixelSize * 0.9
                                font.bold: tfBtn.isSelected
                                color: tfBtn.isSelected
                                    ? (root.isGlass ? "#ffffff" : Kirigami.Theme.highlightedTextColor)
                                    : root.uiSubTextColor
                            }

                            MouseArea {
                                id: tfMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    fullRoot.weeklyTimeframe = modelData;
                                }
                            }
                        }
                    }
                }

                readonly property var activeWeeklyChart: {
                    if (root.weeklyCharts && root.weeklyCharts[fullRoot.weeklyTimeframe]) {
                        return root.weeklyCharts[fullRoot.weeklyTimeframe];
                    }
                    return root.weeklyChart;
                }

                // „Erschöpft vor Reset"-Alarm der Woche
                AlarmBanner {
                    Layout.fillWidth: true
                    severity: fullRoot.alarmSeverity(root.weeklyHits100, root.weeklyPaceStatus, root.isSessionActive)
                    message: fullRoot.alarmText(severity, root.weeklyEtaMin, root.weeklyResetsIn)
                }

                // Burn-up Chart (Weekly)
                BurnupChart {
                    Layout.fillWidth: true
                    implicitHeight: 90
                    usagePoints: (weeklyCol.activeWeeklyChart && weeklyCol.activeWeeklyChart.usage) ? weeklyCol.activeWeeklyChart.usage : []
                    projectionPoints: (weeklyCol.activeWeeklyChart && weeklyCol.activeWeeklyChart.projection) ? weeklyCol.activeWeeklyChart.projection : []
                    paceValue: root.weeklyPace
                    elapsedRatio: (weeklyCol.activeWeeklyChart && weeklyCol.activeWeeklyChart.elapsed_ratio !== undefined) ? weeklyCol.activeWeeklyChart.elapsed_ratio : 0
                    hits100: root.weeklyHits100
                    startLabel: (weeklyCol.activeWeeklyChart && weeklyCol.activeWeeklyChart.label_start) ? weeklyCol.activeWeeklyChart.label_start : (fullRoot.weeklyTimeframe === "7d" ? root.tr("Start") : "-" + fullRoot.weeklyTimeframe)
                    endLabel: (weeklyCol.activeWeeklyChart && weeklyCol.activeWeeklyChart.label_end) ? weeklyCol.activeWeeklyChart.label_end : (fullRoot.weeklyTimeframe === "7d" ? root.tr("Reset") : root.tr("Now"))
                    showPaceLine: fullRoot.weeklyTimeframe === "7d"
                    // Vertikales Raster je Zeitfenster: 7d -> Tage, 30d -> Wochen, 24h -> 6h-Schritte, 7h -> Stunden
                    separatorCount: {
                        switch (fullRoot.weeklyTimeframe) {
                            case "7d": return 7;
                            case "30d": return 4;
                            case "24h": return 4;
                            case "7h": return 7;
                            default: return 0;
                        }
                    }
                    autoScaleY: fullRoot.weeklyTimeframe !== "7d" // Lookback-Ansichten auf Wertebereich zoomen; 7d behält 0-100 für die Pace-Diagonale
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: root.tr("Burn: %1%/h", root.weeklyBurnRate)
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        color: root.uiTextColor
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: root.weeklyHits100 ? root.tr("Limit reached before reset!") : root.tr("Sufficient until reset ✓")
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        font.bold: root.weeklyHits100
                        color: root.weeklyHits100 ? root.uiNegativeColor : Kirigami.Theme.positiveTextColor
                    }
                }
            }
        }

        // Model Breakdown Card (visible only when model sub-limits are available)
        Rectangle {
            id: modelBreakdownCard
            visible: root.modelLimits && root.modelLimits.length > 0
            Layout.fillWidth: true
            implicitHeight: modelCol.implicitHeight + Kirigami.Units.smallSpacing * 2
            color: root.uiCardBg
            border.color: root.uiCardBorder
            radius: root.isGlass ? 10 : 6
            clip: true

            ColumnLayout {
                id: modelCol
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: root.tr("By Model (Weekly)")
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        font.bold: true
                        color: root.uiTextColor
                    }
                    Item { Layout.fillWidth: true }
                }

                Repeater {
                    model: root.modelLimits
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing

                        Text {
                            text: modelData.label || ""
                            font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                            color: root.uiTextColor
                            Layout.preferredWidth: Kirigami.Units.gridUnit * 4.5
                            elide: Text.ElideRight
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 6
                            radius: 3
                            color: Qt.rgba(root.uiTextColor.r, root.uiTextColor.g, root.uiTextColor.b, 0.15)

                            Rectangle {
                                width: parent.width * Math.max(0, Math.min((modelData.percent || 0) / 100, 1))
                                height: parent.height
                                radius: 3
                                color: (modelData.percent >= 90)
                                    ? root.uiNegativeColor
                                    : ((modelData.percent >= 70) ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.positiveTextColor)
                            }
                        }

                        Text {
                            text: Math.round(modelData.percent || 0) + "%"
                            font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                            font.bold: true
                            color: root.uiTextColor
                            Layout.preferredWidth: Kirigami.Units.gridUnit * 2.5
                            horizontalAlignment: Text.AlignRight
                        }
                    }
                }
            }
        }

        // Footer with last updated timestamp & Buy Me a Coffee button
        RowLayout {
            Layout.fillWidth: true
            Text {
                text: root.lastUpdated !== "" ? root.tr("Updated: %1", root.lastUpdated) : ""
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                color: root.uiSubTextColor
            }
            Text {
                visible: root.isRateLimited
                text: "• ⚠️ " + root.tr("API paused (%1s)", root.rateLimitRemaining)
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                font.bold: true
                color: Kirigami.Theme.neutralTextColor
            }
            Item { Layout.fillWidth: true }
            QQC2.ToolButton {
                icon.name: "help-donate"
                text: ""
                implicitWidth: Kirigami.Units.iconSizes.small + 8
                implicitHeight: Kirigami.Units.iconSizes.small + 8
                onClicked: Qt.openUrlExternally("https://buymeacoffee.com/buellsunited")
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: root.tr("☕ Buy Me a Coffee")
            }
            QQC2.BusyIndicator {
                running: root.isFetching
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: Kirigami.Units.iconSizes.small
            }
        }
    }
}
