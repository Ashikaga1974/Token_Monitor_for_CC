import QtQuick
import org.kde.plasma.configuration

ConfigModel {
    id: configModel

    readonly property int activeLanguageMode: {
        if (plasmoid.configuration.Appearance && plasmoid.configuration.Appearance.languageMode !== undefined) {
            return plasmoid.configuration.Appearance.languageMode;
        }
        if (plasmoid.configuration.languageMode !== undefined) {
            return plasmoid.configuration.languageMode;
        }
        return 0;
    }
    readonly property bool isDe: (activeLanguageMode === 2) || (activeLanguageMode === 0 && (Qt.locale().name.indexOf("de") === 0))

    ConfigCategory {
        name: configModel.isDe ? "Erscheinungsbild" : "Appearance"
        icon: "preferences-desktop-color"
        source: "config/configAppearance.qml"
    }

    ConfigCategory {
        name: "API"
        icon: "network-server"
        source: "config/configApi.qml"
    }

    ConfigCategory {
        name: configModel.isDe ? "Benachrichtigungen" : "Notifications"
        icon: "preferences-desktop-notification"
        source: "config/configNotifications.qml"
    }
}
