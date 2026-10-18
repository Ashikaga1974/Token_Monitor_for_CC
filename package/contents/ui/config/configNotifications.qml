import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import "../I18nHelper.js" as I18n

KCM.SimpleKCM {
    id: notificationsPage

    property alias cfg_notificationsEnabled: enabledCheck.checked
    property alias cfg_notifyBurnRate: burnRateCheck.checked
    property alias cfg_notifyThreshold1: t1Check.checked
    property alias cfg_threshold1Percent: t1Spin.value
    property alias cfg_notifyThreshold2: t2Check.checked
    property alias cfg_threshold2Percent: t2Spin.value

    property string testFeedback: ""

    readonly property int activeLanguageMode: {
        if (plasmoid.configuration.Appearance && plasmoid.configuration.Appearance.languageMode !== undefined) {
            return plasmoid.configuration.Appearance.languageMode;
        }
        if (plasmoid.configuration.languageMode !== undefined) {
            return plasmoid.configuration.languageMode;
        }
        return 0;
    }

    function tr(text) {
        return I18n.tr(text, activeLanguageMode);
    }

    Timer {
        id: feedbackTimer
        interval: 3500
        onTriggered: notificationsPage.testFeedback = ""
    }

    Kirigami.FormLayout {
        QQC2.CheckBox {
            id: enabledCheck
            Kirigami.FormData.label: notificationsPage.tr("Desktop Notifications:")
            text: notificationsPage.tr("Enable native KDE Plasma notifications on limit hazard")
        }

        Item {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: notificationsPage.tr("Thresholds & Warning Levels")
        }

        QQC2.CheckBox {
            id: burnRateCheck
            enabled: enabledCheck.checked
            Kirigami.FormData.label: notificationsPage.tr("Burn Rate Warning:")
            text: notificationsPage.tr("Alert when current pace exhausts limit before reset (100% projected)")
        }

        RowLayout {
            enabled: enabledCheck.checked
            Kirigami.FormData.label: notificationsPage.tr("Warning Threshold 1:")
            spacing: Kirigami.Units.smallSpacing

            QQC2.CheckBox {
                id: t1Check
                text: notificationsPage.tr("Alert at")
            }

            QQC2.SpinBox {
                id: t1Spin
                enabled: t1Check.checked
                from: 50
                to: 94
                stepSize: 1
                editable: true
            }

            QQC2.Label {
                text: "%"
                font.bold: true
            }

            QQC2.Label {
                text: notificationsPage.tr("(Default: 85%)")
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                color: Kirigami.Theme.disabledTextColor
            }
        }

        RowLayout {
            enabled: enabledCheck.checked
            Kirigami.FormData.label: notificationsPage.tr("Critical Threshold 2:")
            spacing: Kirigami.Units.smallSpacing

            QQC2.CheckBox {
                id: t2Check
                text: notificationsPage.tr("Alert at")
            }

            QQC2.SpinBox {
                id: t2Spin
                enabled: t2Check.checked
                from: 70
                to: 99
                stepSize: 1
                editable: true
            }

            QQC2.Label {
                text: "%"
                font.bold: true
            }

            QQC2.Label {
                text: notificationsPage.tr("(Default: 95%)")
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                color: Kirigami.Theme.disabledTextColor
            }
        }

        Item {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: notificationsPage.tr("Diagnostics & Test")
        }

        RowLayout {
            Kirigami.FormData.label: notificationsPage.tr("Test Notification:")
            spacing: Kirigami.Units.smallSpacing

            QQC2.Button {
                icon.name: "dialog-information"
                text: notificationsPage.tr("🔔 Send Test Notification")
                onClicked: {
                    var xhr = new XMLHttpRequest();
                    xhr.open("GET", "http://127.0.0.1:48291/notify-test");
                    xhr.onreadystatechange = function() {
                        if (xhr.readyState === XMLHttpRequest.DONE) {
                            if (xhr.status === 200) {
                                notificationsPage.testFeedback = notificationsPage.tr("Test notification sent ✓");
                            } else {
                                notificationsPage.testFeedback = notificationsPage.tr("Error sending notification");
                            }
                            feedbackTimer.restart();
                        }
                    };
                    xhr.send();
                }
            }

            QQC2.Label {
                text: notificationsPage.testFeedback
                font.bold: true
                color: Kirigami.Theme.positiveTextColor
                visible: notificationsPage.testFeedback !== ""
            }
        }
    }
}
