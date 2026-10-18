import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as Plasma5Support
import "I18nHelper.js" as I18n

PlasmoidItem {
    id: root

    preferredRepresentation: (Plasmoid.formFactor === PlasmaCore.Types.Planar) ? fullRepresentation : compactRepresentation

    readonly property int colorSchemeMode: {
        if (plasmoid.configuration.Appearance && plasmoid.configuration.Appearance.colorSchemeMode !== undefined) {
            return plasmoid.configuration.Appearance.colorSchemeMode;
        }
        if (plasmoid.configuration.colorSchemeMode !== undefined) {
            return plasmoid.configuration.colorSchemeMode;
        }
        return 0;
    }
    // 0 = Plasma Theme, 1 = Light, 2 = Dark, 3 = Transparent

    readonly property int refreshIntervalSeconds: {
        var intervalVal = (plasmoid.configuration.Appearance && plasmoid.configuration.Appearance.refreshInterval !== undefined)
            ? plasmoid.configuration.Appearance.refreshInterval
            : (plasmoid.configuration.refreshInterval !== undefined ? plasmoid.configuration.refreshInterval : 60);
        return Math.max(10, intervalVal);
    }

    readonly property int languageMode: {
        if (plasmoid.configuration.Appearance && plasmoid.configuration.Appearance.languageMode !== undefined) {
            return plasmoid.configuration.Appearance.languageMode;
        }
        if (plasmoid.configuration.languageMode !== undefined) {
            return plasmoid.configuration.languageMode;
        }
        return 0; // 0 = Auto/System, 1 = English, 2 = German
    }

    readonly property int panelDisplayStyle: {
        if (plasmoid.configuration.Appearance && plasmoid.configuration.Appearance.panelDisplayStyle !== undefined) {
            return plasmoid.configuration.Appearance.panelDisplayStyle;
        }
        if (plasmoid.configuration.panelDisplayStyle !== undefined) {
            return plasmoid.configuration.panelDisplayStyle;
        }
        return 0; // 0 = Text (Default), 1 = Progress Ring, 2 = Combined
    }

    readonly property bool notificationsEnabled: {
        if (plasmoid.configuration.Notifications && plasmoid.configuration.Notifications.notificationsEnabled !== undefined) {
            return plasmoid.configuration.Notifications.notificationsEnabled;
        }
        if (plasmoid.configuration.notificationsEnabled !== undefined) {
            return plasmoid.configuration.notificationsEnabled;
        }
        return true;
    }

    readonly property bool notifyBurnRate: {
        if (plasmoid.configuration.Notifications && plasmoid.configuration.Notifications.notifyBurnRate !== undefined) {
            return plasmoid.configuration.Notifications.notifyBurnRate;
        }
        if (plasmoid.configuration.notifyBurnRate !== undefined) {
            return plasmoid.configuration.notifyBurnRate;
        }
        return true;
    }

    readonly property bool notifyThreshold1: {
        if (plasmoid.configuration.Notifications && plasmoid.configuration.Notifications.notifyThreshold1 !== undefined) {
            return plasmoid.configuration.Notifications.notifyThreshold1;
        }
        if (plasmoid.configuration.notifyThreshold1 !== undefined) {
            return plasmoid.configuration.notifyThreshold1;
        }
        return true;
    }

    readonly property int threshold1Percent: {
        if (plasmoid.configuration.Notifications && plasmoid.configuration.Notifications.threshold1Percent !== undefined) {
            return plasmoid.configuration.Notifications.threshold1Percent;
        }
        if (plasmoid.configuration.threshold1Percent !== undefined) {
            return plasmoid.configuration.threshold1Percent;
        }
        return 85;
    }

    readonly property bool notifyThreshold2: {
        if (plasmoid.configuration.Notifications && plasmoid.configuration.Notifications.notifyThreshold2 !== undefined) {
            return plasmoid.configuration.Notifications.notifyThreshold2;
        }
        if (plasmoid.configuration.notifyThreshold2 !== undefined) {
            return plasmoid.configuration.notifyThreshold2;
        }
        return true;
    }

    readonly property int threshold2Percent: {
        if (plasmoid.configuration.Notifications && plasmoid.configuration.Notifications.threshold2Percent !== undefined) {
            return plasmoid.configuration.Notifications.threshold2Percent;
        }
        if (plasmoid.configuration.threshold2Percent !== undefined) {
            return plasmoid.configuration.threshold2Percent;
        }
        return 95;
    }

    readonly property string apiBaseUrl: {
        if (plasmoid.configuration.Api && plasmoid.configuration.Api.apiBaseUrl !== undefined) {
            return plasmoid.configuration.Api.apiBaseUrl;
        }
        if (plasmoid.configuration.apiBaseUrl !== undefined) {
            return plasmoid.configuration.apiBaseUrl;
        }
        return "https://api.anthropic.com";
    }

    onApiBaseUrlChanged: root.syncApiConfig()
    onNotificationsEnabledChanged: root.syncNotificationConfig()
    onNotifyBurnRateChanged: root.syncNotificationConfig()
    onNotifyThreshold1Changed: root.syncNotificationConfig()
    onThreshold1PercentChanged: root.syncNotificationConfig()
    onNotifyThreshold2Changed: root.syncNotificationConfig()
    onThreshold2PercentChanged: root.syncNotificationConfig()

    function tr(text, arg1, arg2) {
        return I18n.tr(text, root.languageMode, arg1, arg2);
    }

    Plasmoid.backgroundHints: {
        if (Plasmoid.formFactor !== PlasmaCore.Types.Planar) {
            return PlasmaCore.Types.DefaultBackground;
        }
        return (colorSchemeMode === 4 || colorSchemeMode === 3 || colorSchemeMode === 1 || colorSchemeMode === 2)
            ? PlasmaCore.Types.NoBackground
            : (PlasmaCore.Types.DefaultBackground | PlasmaCore.Types.ConfigurableBackground);
    }

    // Resolve desktop wallpaper containment for real frosted glass blur
    readonly property Item desktopWallpaper: {
        if (Plasmoid.formFactor !== PlasmaCore.Types.Planar) {
            return null;
        }
        for (var p = root.parent; p; p = p.parent) {
            if (p && p.wallpaper !== undefined && p.wallpaper !== null) {
                return p.wallpaper;
            }
        }
        return null;
    }

    // Define color palette based on active theme mode
    readonly property bool isCustomLight: colorSchemeMode === 1
    readonly property bool isCustomDark: colorSchemeMode === 2
    readonly property bool isTransparent: colorSchemeMode === 3
    readonly property bool isGlass: colorSchemeMode === 4

    readonly property color uiTextColor: isCustomLight ? "#232629" : (isCustomDark ? "#fcfcfc" : (isGlass ? "#ffffff" : Kirigami.Theme.textColor))
    readonly property color uiSubTextColor: isCustomLight ? "#60656a" : (isCustomDark ? "#a0a0a0" : (isGlass ? Qt.rgba(1, 1, 1, 0.7) : Kirigami.Theme.disabledTextColor))
    // Gut lesbares Alarm-Rot: kräftiges Dunkelrot auf hellem Grund, helles Rot auf dunklen/Glass-Hintergründen,
    // da das Theme-Negativrot (negativeTextColor) dort zu kontrastarm wirkt.
    readonly property color uiNegativeColor: isCustomLight ? "#c0392b" : ((isCustomDark || isGlass || isTransparent) ? "#ff5555" : Kirigami.Theme.negativeTextColor)
    readonly property color uiCardBg: isCustomLight ? "#ffffff" : (isCustomDark ? Qt.rgba(35/255, 38/255, 41/255, 0.75) : (isGlass ? Qt.rgba(1, 1, 1, 0.04) : (isTransparent ? Qt.rgba(0, 0, 0, 0.25) : Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.4))))
    readonly property color uiCardBorder: isCustomLight ? "#d0d3d6" : (isCustomDark ? Qt.rgba(1, 1, 1, 0.15) : (isGlass ? Qt.rgba(1, 1, 1, 0.08) : (isTransparent ? Qt.rgba(1, 1, 1, 0.15) : Qt.rgba(Kirigami.Theme.disabledTextColor.r, Kirigami.Theme.disabledTextColor.g, Kirigami.Theme.disabledTextColor.b, 0.3))))
    readonly property color uiContainerBg: isCustomLight ? "#eff0f1" : (isCustomDark ? "#1e2124" : "transparent")

    property var statsData: null
    property bool isFetching: false
    property string lastUpdated: ""
    property string errorMessage: ""
    property bool isStartingDaemon: false
    property int daemonStartAttempts: 0

    // Computed property shortcuts for panel & popup representation
    readonly property real sessionUtil: (statsData && statsData.session && statsData.session.utilization !== undefined) ? statsData.session.utilization : 0
    readonly property real sessionPace: (statsData && statsData.session && statsData.session.budget_pace !== undefined) ? statsData.session.budget_pace : 0
    readonly property int sessionResetsIn: (statsData && statsData.session && statsData.session.resets_in_minutes !== undefined) ? statsData.session.resets_in_minutes : 0
    readonly property string sessionResetsAt: (statsData && statsData.session && statsData.session.resets_at_iso) ? statsData.session.resets_at_iso : ""
    readonly property real sessionBurnRate: (statsData && statsData.session && statsData.session.burn_rate_pct_per_hour !== undefined) ? statsData.session.burn_rate_pct_per_hour : 0
    readonly property string sessionTrend: (statsData && statsData.session && statsData.session.trend) ? statsData.session.trend : "low"
    readonly property var sessionEtaMin: (statsData && statsData.session) ? statsData.session.estimated_minutes_to_100 : null
    readonly property bool sessionHits100: (statsData && statsData.session && statsData.session.hits_100_before_reset) ? true : false
    readonly property string sessionPaceStatus: (statsData && statsData.session && statsData.session.pace_status) ? statsData.session.pace_status : "on_pace"

    readonly property real weeklyUtil: (statsData && statsData.weekly && statsData.weekly.utilization !== undefined) ? statsData.weekly.utilization : 0
    readonly property real weeklyPace: (statsData && statsData.weekly && statsData.weekly.budget_pace !== undefined) ? statsData.weekly.budget_pace : 0
    readonly property int weeklyResetsIn: (statsData && statsData.weekly && statsData.weekly.resets_in_minutes !== undefined) ? statsData.weekly.resets_in_minutes : 0
    readonly property string weeklyResetsAt: (statsData && statsData.weekly && statsData.weekly.resets_at_iso) ? statsData.weekly.resets_at_iso : ""
    readonly property real weeklyBurnRate: (statsData && statsData.weekly && statsData.weekly.burn_rate_pct_per_hour !== undefined) ? statsData.weekly.burn_rate_pct_per_hour : 0
    readonly property var weeklyEtaMin: (statsData && statsData.weekly) ? statsData.weekly.estimated_minutes_to_100 : null
    readonly property bool weeklyHits100: (statsData && statsData.weekly && statsData.weekly.hits_100_before_reset) ? true : false
    readonly property string weeklyPaceStatus: (statsData && statsData.weekly && statsData.weekly.pace_status) ? statsData.weekly.pace_status : "on_pace"

    readonly property var sessionChart: (statsData && statsData.session) ? statsData.session.chart : null
    readonly property var weeklyChart: (statsData && statsData.weekly) ? statsData.weekly.chart : null
    readonly property var weeklyCharts: (statsData && statsData.weekly) ? statsData.weekly.charts : null
    readonly property var modelLimits: (statsData && statsData.model_limits) ? statsData.model_limits : []

    readonly property bool isRateLimited: (statsData && statsData.is_rate_limited) ? true : false
    readonly property int rateLimitRemaining: (statsData && statsData.rate_limit_remaining_seconds !== undefined) ? statsData.rate_limit_remaining_seconds : 0
    readonly property bool isSessionActive: (statsData && statsData.is_active) ? true : false

    readonly property string activeModelName: {
        if (statsData && statsData.model && statsData.model.display_name) {
            return statsData.model.display_name;
        }
        if (statsData && statsData.session && statsData.session.model && statsData.session.model.display_name) {
            return statsData.session.model.display_name;
        }
        return "";
    }
    readonly property string activeModelId: {
        if (statsData && statsData.model && statsData.model.id) {
            return statsData.model.id;
        }
        if (statsData && statsData.session && statsData.session.model && statsData.session.model.id) {
            return statsData.session.model.id;
        }
        return "";
    }

    toolTipMainText: root.tr("Token Monitor for Claude Code")
    toolTipSubText: {
        if (errorMessage !== "") {
            return errorMessage;
        }
        if (!statsData) {
            return root.tr("Loading data…");
        }
        var base = root.tr("Session (5h): %1% | Weekly: %2%", sessionUtil, weeklyUtil);
        if (root.activeModelName !== "") {
            base += " (" + root.activeModelName + ")";
        }
        if (root.isRateLimited) {
            return base + "\n⚠️ " + root.tr("API paused (429: %1s left)", root.rateLimitRemaining);
        }
        return base;
    }

    Timer {
        id: refreshTimer
        interval: root.refreshIntervalSeconds * 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            root.fetchStats(false);
        }
    }

    function syncNotificationConfig() {
        var payload = JSON.stringify({
            enabled: root.notificationsEnabled,
            notify_burn_rate: root.notifyBurnRate,
            notify_threshold_1: root.notifyThreshold1,
            threshold_1_percent: root.threshold1Percent,
            notify_threshold_2: root.notifyThreshold2,
            threshold_2_percent: root.threshold2Percent
        });
        var xhr = new XMLHttpRequest();
        xhr.open("POST", "http://127.0.0.1:48291/notify-config");
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(payload);
    }

    function syncApiConfig() {
        var payload = JSON.stringify({ base_url: root.apiBaseUrl });
        var xhr = new XMLHttpRequest();
        xhr.open("POST", "http://127.0.0.1:48291/api-config");
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(payload);
    }

    Component.onCompleted: {
        root.syncApiConfig();
        root.syncNotificationConfig();
    }

    Plasma5Support.DataSource {
        id: daemonLauncher
        engine: "executable"
        connectedSources: []
        onNewData: function(source, data) {
            disconnectSource(source);
            root.isStartingDaemon = false;
            daemonCheckTimer.restart();
        }
    }

    Timer {
        id: daemonCheckTimer
        interval: 1200
        repeat: false
        onTriggered: {
            root.fetchStats(true);
        }
    }

    function startDaemon(isManual) {
        if (root.isStartingDaemon) return;
        root.isStartingDaemon = true;
        if (!isManual) {
            root.daemonStartAttempts += 1;
        }
        var scriptUrl = Qt.resolvedUrl("../scripts/start_daemon.sh").toString();
        var scriptPath = scriptUrl.replace("file://", "");
        daemonLauncher.connectSource("sh \"" + scriptPath + "\"");
    }

    function fetchStats(forceRefresh) {
        if (root.isFetching) return;
        root.isFetching = true;

        var endpoint = forceRefresh ? "http://127.0.0.1:48291/refresh" : "http://127.0.0.1:48291/stats";
        var xhr = new XMLHttpRequest();
        xhr.open("GET", endpoint);
        xhr.timeout = 5000;

        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                root.isFetching = false;
                if (xhr.status === 200) {
                    try {
                        var parsed = JSON.parse(xhr.responseText);
                        if (parsed.error) {
                            root.errorMessage = parsed.error;
                        } else {
                            root.statsData = parsed;
                            root.errorMessage = "";
                            root.daemonStartAttempts = 0;
                            var d = new Date();
                            root.lastUpdated = Qt.formatTime(d, "hh:mm:ss");
                        }
                    } catch (e) {
                        root.errorMessage = root.tr("JSON parse error");
                    }
                } else {
                    root.errorMessage = root.tr("Daemon unreachable (port 48291)");
                    if (!root.isStartingDaemon && root.daemonStartAttempts < 1) {
                        root.startDaemon(false);
                    }
                }
            }
        };

        xhr.ontimeout = function() {
            root.isFetching = false;
            root.errorMessage = root.tr("Daemon request timed out");
            if (!root.isStartingDaemon && root.daemonStartAttempts < 1) {
                root.startDaemon(false);
            }
        };

        xhr.onerror = function() {
            root.isFetching = false;
            root.errorMessage = root.tr("Daemon connection failed");
            if (!root.isStartingDaemon && root.daemonStartAttempts < 1) {
                root.startDaemon(false);
            }
        };

        xhr.send();
    }

    compactRepresentation: CompactRepresentation {}

    fullRepresentation: Item {
        id: fullRepItem
        implicitWidth: Kirigami.Units.gridUnit * 20
        implicitHeight: fullRepContent.implicitHeight + Kirigami.Units.smallSpacing * 2
        Layout.minimumWidth: Kirigami.Units.gridUnit * 18
        Layout.minimumHeight: Kirigami.Units.gridUnit * 24
        Layout.preferredWidth: implicitWidth
        Layout.preferredHeight: implicitHeight

        // Real frosted glass wallpaper blur when active on desktop
        BackdropBlur {
            anchors.fill: parent
            visible: root.isGlass && !!root.desktopWallpaper && (Plasmoid.formFactor === PlasmaCore.Types.Planar)
            sourceItem: root.desktopWallpaper
            radius: 16
            strength: 0.85
        }

        // Embed directly as content with optional container background
        Rectangle {
            anchors.fill: parent
            clip: true
            color: (Plasmoid.formFactor !== PlasmaCore.Types.Planar)
                ? (root.isGlass ? Qt.rgba(18/255, 24/255, 38/255, 0.85) : root.uiContainerBg)
                : (root.isGlass
                    ? (root.desktopWallpaper ? Qt.rgba(14/255, 18/255, 28/255, 0.48) : Qt.rgba(18/255, 24/255, 38/255, 0.75))
                    : root.uiContainerBg)
            radius: (root.isGlass || root.isCustomLight || root.isCustomDark) ? 16 : 0
            border.color: (root.isGlass ? Qt.rgba(1, 1, 1, 0.16) : ((root.isCustomLight || root.isCustomDark) ? root.uiCardBorder : "transparent"))
            border.width: (root.isGlass || root.isCustomLight || root.isCustomDark) ? 1 : 0

            // 1px subtle top sheen highlight for authentic glass finish
            Rectangle {
                visible: root.isGlass && (Plasmoid.formFactor === PlasmaCore.Types.Planar)
                anchors.top: parent.top
                anchors.topMargin: 1
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.right: parent.right
                anchors.rightMargin: 14
                height: 1
                color: Qt.rgba(1, 1, 1, 0.22)
            }

            FullRepresentation {
                id: fullRepContent
                anchors.fill: parent
            }
        }
    }
}
