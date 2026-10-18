import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import "../I18nHelper.js" as I18n

KCM.SimpleKCM {
    id: apiPage

    property alias cfg_apiBaseUrl: urlField.text

    // Standardwert zum Zuruecksetzen; muss mit dem Default in main.xml uebereinstimmen
    readonly property string defaultBaseUrl: "https://api.anthropic.com"

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

    // Prueft, ob die Eingabe mit http:// oder https:// beginnt (einfache Client-seitige Vorvalidierung)
    readonly property bool isValidUrl: /^https?:\/\/.+/.test(urlField.text.trim())

    Kirigami.FormLayout {
        QQC2.TextField {
            id: urlField
            Kirigami.FormData.label: apiPage.tr("API Base URL:")
            Layout.fillWidth: true
            Layout.minimumWidth: Kirigami.Units.gridUnit * 20
            placeholderText: apiPage.defaultBaseUrl
            inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoAutoUppercase
        }

        QQC2.Label {
            Kirigami.FormData.label: ""
            text: apiPage.tr("Only change this if you route the Anthropic API through a proxy or gateway. Leave empty to use the default.")
            wrapMode: Text.WordWrap
            Layout.maximumWidth: Kirigami.Units.gridUnit * 24
            opacity: 0.7
            font: Kirigami.Theme.smallFont
        }

        QQC2.Label {
            Kirigami.FormData.label: ""
            text: apiPage.tr("Invalid URL – must start with http:// or https://")
            color: Kirigami.Theme.negativeTextColor
            visible: urlField.text.trim() !== "" && !apiPage.isValidUrl
            font.bold: true
        }

        Item {
            Kirigami.FormData.isSection: true
        }

        QQC2.Button {
            Kirigami.FormData.label: apiPage.tr("Reset:")
            icon.name: "edit-undo"
            text: apiPage.tr("Reset to default")
            enabled: urlField.text.trim() !== apiPage.defaultBaseUrl
            onClicked: urlField.text = apiPage.defaultBaseUrl
        }
    }
}
