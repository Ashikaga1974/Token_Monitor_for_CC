import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import "../I18nHelper.js" as I18n

KCM.SimpleKCM {
    id: appearancePage

    property alias cfg_colorSchemeMode: modeCombo.currentIndex
    property alias cfg_refreshInterval: intervalCombo.currentValue
    property alias cfg_languageMode: languageCombo.currentIndex
    property alias cfg_panelDisplayStyle: panelStyleCombo.currentIndex

    function tr(text) {
        return I18n.tr(text, languageCombo.currentIndex);
    }

    Kirigami.FormLayout {
        QQC2.ComboBox {
            id: languageCombo
            Kirigami.FormData.label: appearancePage.tr("Language:")
            model: [
                appearancePage.tr("System Default"),
                "English",
                "Deutsch"
            ]
        }

        QQC2.ComboBox {
            id: modeCombo
            Kirigami.FormData.label: appearancePage.tr("Color Scheme / Style:")
            model: [
                appearancePage.tr("Plasma Theme (Default)"),
                appearancePage.tr("Light (Breeze Light)"),
                appearancePage.tr("Dark (Breeze Dark)"),
                appearancePage.tr("Transparent (No Card)"),
                appearancePage.tr("Modern Glass (Frosted)")
            ]
        }

        QQC2.ComboBox {
            id: panelStyleCombo
            Kirigami.FormData.label: appearancePage.tr("Taskbar / Panel Style:")
            model: [
                appearancePage.tr("Text (Default)"),
                appearancePage.tr("Progress Ring (Compact)"),
                appearancePage.tr("Combined (Ring + Text)")
            ]
        }

        QQC2.ComboBox {
            id: intervalCombo
            Kirigami.FormData.label: appearancePage.tr("Refresh Interval:")
            textRole: "text"
            valueRole: "value"
            model: [
                { text: appearancePage.tr("15 seconds"), value: 15 },
                { text: appearancePage.tr("30 seconds"), value: 30 },
                { text: appearancePage.tr("1 minute (Default)"), value: 60 },
                { text: appearancePage.tr("2 minutes"), value: 120 },
                { text: appearancePage.tr("5 minutes"), value: 300 }
            ]
        }

        Item {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: appearancePage.tr("Support & Donations")
        }

        RowLayout {
            Kirigami.FormData.label: appearancePage.tr("Buy me a coffee:")
            spacing: Kirigami.Units.smallSpacing

            QQC2.Button {
                icon.name: "help-donate"
                text: appearancePage.tr("☕ Buy Me a Coffee")
                onClicked: {
                    Qt.openUrlExternally("https://buymeacoffee.com/buellsunited");
                }
            }

            QQC2.Label {
                text: "kde.buells-united.com"
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                color: Kirigami.Theme.disabledTextColor
            }
        }

        Item {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: appearancePage.tr("Credits & Acknowledgments")
        }

        RowLayout {
            Kirigami.FormData.label: appearancePage.tr("Inspiration:")
            spacing: Kirigami.Units.smallSpacing

            QQC2.Button {
                icon.name: "help-about"
                text: "ccburn (GitHub)"
                onClicked: {
                    Qt.openUrlExternally("https://github.com/JuanjoFuchs/ccburn");
                }
            }

            QQC2.Label {
                text: appearancePage.tr("CLI tool by JuanjoFuchs")
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                color: Kirigami.Theme.disabledTextColor
            }
        }
    }
}
