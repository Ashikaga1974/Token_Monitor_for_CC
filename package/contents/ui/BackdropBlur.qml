pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Effects

Item {
    id: backdropRoot

    property Item sourceItem: null
    property real radius: 16
    property real strength: 0.85

    readonly property bool available: !!sourceItem && !!backdropRoot.Window && !!sourceItem.Window && sourceItem.Window.window === backdropRoot.Window.window && GraphicsInfo.api !== GraphicsInfo.Software

    // Track geometry of parents to automatically update sample coordinates when dragging or resizing
    readonly property var geometrySignature: {
        var geometry = [];
        for (var start of [backdropRoot, sourceItem]) {
            for (var item = start; item; item = item.parent) {
                geometry.push(item.x, item.y, item.width, item.height, item.scale, item.rotation);
            }
        }
        return geometry;
    }

    readonly property rect sampleRect: {
        var _ = geometrySignature;
        return (sourceItem && available && backdropRoot.width > 0 && backdropRoot.height > 0)
            ? backdropRoot.mapToItem(sourceItem, 0, 0, width, height)
            : Qt.rect(0, 0, 0, 0);
    }

    Loader {
        anchors.fill: parent
        active: backdropRoot.available && backdropRoot.visible && backdropRoot.width > 0 && backdropRoot.height > 0
        sourceComponent: Item {
            anchors.fill: parent

            ShaderEffectSource {
                id: wallpaperTexture
                width: backdropRoot.width
                height: backdropRoot.height
                sourceItem: backdropRoot.sourceItem
                sourceRect: backdropRoot.sampleRect
                textureSize: Qt.size(Math.max(1, Math.ceil(backdropRoot.width / 8) * 8), Math.max(1, Math.ceil(backdropRoot.height / 8) * 8))
                live: true
                hideSource: false
                visible: false
            }

            Rectangle {
                id: frostMask
                anchors.fill: parent
                radius: backdropRoot.radius
                color: "black"
                visible: false
                layer.enabled: true
            }

            MultiEffect {
                anchors.fill: parent
                source: wallpaperTexture
                blurEnabled: true
                blurMax: 48
                blur: backdropRoot.strength
                autoPaddingEnabled: false
                maskEnabled: true
                maskSource: frostMask
            }
        }
    }
}
