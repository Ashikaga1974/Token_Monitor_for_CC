import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: chartRoot

    // Data series:
    // usagePoints: [{x: 0..1, y: 0..100}, ...]
    // projectionPoints: [{x: 0..1, y: 0..100}, ...]
    // paceValue: 0..100 (Target pace at 'now')
    // elapsedRatio: 0..1 (Position of 'now' within the window)
    property var usagePoints: []
    property var projectionPoints: []
    property real paceValue: 0
    property real elapsedRatio: 0
    property bool hits100: false
    property string startLabel: "Start"
    property string endLabel: "Reset"
    property bool showPaceLine: true
    // Anzahl gleich langer Segmente, in die das Fenster geteilt wird (Stunden im Session-Fenster,
    // Tage in der 7d-Ansicht). Ab 2 werden (separatorCount - 1) vertikale Trennlinien gezeichnet.
    property int separatorCount: 0
    // Dynamische Y-Achse: zoomt auf den tatsächlichen Wertebereich statt fest 0-100%.
    // Für Lookback-Ansichten (7h/24h/30d) sinnvoll, da dort kleine Trends sichtbar werden sollen.
    // Für Fenster mit Pace-Diagonale (7d, Session) bleibt die feste 0-100-Skala.
    property bool autoScaleY: false


    implicitWidth: parent ? parent.width : 280
    implicitHeight: 120

    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);

            var paddingLeft = 30;
            var paddingRight = 10;
            var paddingTop = 10;
            var paddingBottom = 20;

            var plotW = width - paddingLeft - paddingRight;
            var plotH = height - paddingTop - paddingBottom;

            if (plotW <= 0 || plotH <= 0) return;

            function toX(normX) {
                return paddingLeft + (normX * plotW);
            }

            // Y-Achsen-Bereich: fest 0-100 oder dynamisch auf den Wertebereich gezoomt
            var yMin = 0;
            var yMax = 100;
            if (chartRoot.autoScaleY && chartRoot.usagePoints && chartRoot.usagePoints.length > 0) {
                var dMin = chartRoot.usagePoints[0].y;
                var dMax = chartRoot.usagePoints[0].y;
                for (var m = 1; m < chartRoot.usagePoints.length; m++) {
                    var vy = chartRoot.usagePoints[m].y;
                    if (vy < dMin) dMin = vy;
                    if (vy > dMax) dMax = vy;
                }
                var range = dMax - dMin;
                var pad = Math.max(2, range * 0.15);
                yMin = Math.max(0, Math.floor(dMin - pad));
                yMax = Math.min(100, Math.ceil(dMax + pad));
                // Mindestspanne, damit fast konstante Linien nicht übertrieben gespreizt werden
                if (yMax - yMin < 5) {
                    yMin = Math.max(0, yMin - 3);
                    yMax = Math.min(100, yMax + 3);
                }
            }

            function toY(valY) {
                var clamped = Math.max(yMin, Math.min(yMax, valY));
                return paddingTop + plotH - (((clamped - yMin) / (yMax - yMin)) * plotH);
            }

            // 1. Background grid (untere/mittlere/obere Achsenwerte)
            var gridVals = chartRoot.autoScaleY
                ? [yMin, Math.round((yMin + yMax) / 2), yMax]
                : [0, 50, 100];
            ctx.lineWidth = 1;
            ctx.strokeStyle = (typeof root !== "undefined" && root.isCustomLight)
                ? "rgba(0, 0, 0, 0.12)"
                : ((typeof root !== "undefined" && root.isGlass)
                    ? "rgba(255, 255, 255, 0.08)"
                    : Qt.rgba(Kirigami.Theme.disabledTextColor.r, Kirigami.Theme.disabledTextColor.g, Kirigami.Theme.disabledTextColor.b, 0.2));

            gridVals.forEach(function(pct) {
                var y = toY(pct);
                ctx.beginPath();
                ctx.moveTo(paddingLeft, y);
                ctx.lineTo(paddingLeft + plotW, y);
                ctx.stroke();

                // Y-axis label
                ctx.fillStyle = (typeof root !== "undefined") ? root.uiSubTextColor : Kirigami.Theme.disabledTextColor;
                ctx.font = "9px sans-serif";
                ctx.textAlign = "right";
                ctx.fillText(Math.round(pct) + "%", paddingLeft - 4, y + 3);
            });

            // 1b. Vertical segment separators (hours in session view, days in 7d view)
            if (chartRoot.separatorCount >= 2) {
                ctx.save();
                ctx.setLineDash([3, 3]);
                ctx.lineWidth = 1;
                ctx.strokeStyle = (typeof root !== "undefined" && root.isCustomLight)
                    ? "rgba(0, 0, 0, 0.18)"
                    : ((typeof root !== "undefined" && root.isGlass)
                        ? "rgba(255, 255, 255, 0.14)"
                        : Qt.rgba(Kirigami.Theme.disabledTextColor.r, Kirigami.Theme.disabledTextColor.g, Kirigami.Theme.disabledTextColor.b, 0.33));
                for (var s = 1; s < chartRoot.separatorCount; s++) {
                    var sepX = toX(s / chartRoot.separatorCount);
                    ctx.beginPath();
                    ctx.moveTo(sepX, paddingTop);
                    ctx.lineTo(sepX, paddingTop + plotH);
                    ctx.stroke();
                }
                ctx.restore();
            }

            // 2. Budget pace diagonal (from 0,0 to 1,100)
            if (chartRoot.showPaceLine) {
                ctx.save();
                ctx.setLineDash([4, 4]);
                ctx.strokeStyle = (typeof root !== "undefined" && root.isCustomLight) ? "#999999" : ((typeof root !== "undefined" && root.isGlass) ? "rgba(255, 255, 255, 0.4)" : "#888888");
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.moveTo(toX(0), toY(0));
                ctx.lineTo(toX(1), toY(100));
                ctx.stroke();
                ctx.restore();
            }

            // 3. "Now" vertical indicator line
            if (chartRoot.elapsedRatio > 0 && chartRoot.elapsedRatio < 1) {
                ctx.save();
                ctx.setLineDash([3, 3]);
                ctx.strokeStyle = "#3daee9"; // KDE Plasma cyan/blue
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                var nowX = toX(chartRoot.elapsedRatio);
                ctx.moveTo(nowX, paddingTop);
                ctx.lineTo(nowX, paddingTop + plotH);
                ctx.stroke();
                ctx.restore();
            }

            // 4. Usage curve with filled area (burn-up area)
            if (chartRoot.usagePoints && chartRoot.usagePoints.length > 0) {
                var pts = chartRoot.usagePoints;

                // Draw filled area (Grundlinie = untere Achsengrenze, bei AutoScale also yMin)
                ctx.beginPath();
                ctx.moveTo(toX(pts[0].x), toY(yMin));
                ctx.lineTo(toX(pts[0].x), toY(pts[0].y));
                for (var i = 1; i < pts.length; i++) {
                    ctx.lineTo(toX(pts[i].x), toY(pts[i].y));
                }
                ctx.lineTo(toX(pts[pts.length - 1].x), toY(yMin));
                ctx.closePath();

                var fillColor = chartRoot.hits100
                    ? "rgba(237, 21, 21, 0.35)"
                    : ((typeof root !== "undefined" && root.isGlass) ? "rgba(0, 229, 255, 0.22)" : "rgba(39, 174, 96, 0.35)");
                ctx.fillStyle = fillColor;
                ctx.fill();

                // Draw top contour stroke
                ctx.beginPath();
                ctx.moveTo(toX(pts[0].x), toY(pts[0].y));
                for (var j = 1; j < pts.length; j++) {
                    ctx.lineTo(toX(pts[j].x), toY(pts[j].y));
                }
                ctx.lineWidth = 2.5;
                ctx.strokeStyle = chartRoot.hits100
                    ? "#ed1515"
                    : ((typeof root !== "undefined" && root.isGlass) ? "#00e5ff" : "#27ae60");
                ctx.stroke();
            }

            // 5. Projection line (dashed starting from 'now')
            if (chartRoot.projectionPoints && chartRoot.projectionPoints.length >= 2) {
                var ppts = chartRoot.projectionPoints;
                ctx.save();
                ctx.setLineDash([4, 4]);
                ctx.beginPath();
                ctx.moveTo(toX(ppts[0].x), toY(ppts[0].y));
                for (var k = 1; k < ppts.length; k++) {
                    ctx.lineTo(toX(ppts[k].x), toY(ppts[k].y));
                }
                ctx.lineWidth = 2.5;
                ctx.strokeStyle = chartRoot.hits100
                    ? "#e67e22"
                    : ((typeof root !== "undefined" && root.isGlass) ? "#70e2ff" : "#2ecc71");
                ctx.stroke();
                ctx.restore();
            }

            // X-axis labels
            ctx.fillStyle = (typeof root !== "undefined") ? root.uiSubTextColor : "#888888";
            ctx.font = "9px sans-serif";
            ctx.textAlign = "left";
            ctx.fillText(chartRoot.startLabel, paddingLeft, height - 4);
            ctx.textAlign = "right";
            ctx.fillText(chartRoot.endLabel, paddingLeft + plotW, height - 4);
        }
    }

    onUsagePointsChanged: canvas.requestPaint()
    onProjectionPointsChanged: canvas.requestPaint()
    onElapsedRatioChanged: canvas.requestPaint()
    onHits100Changed: canvas.requestPaint()
    onStartLabelChanged: canvas.requestPaint()
    onEndLabelChanged: canvas.requestPaint()
    onShowPaceLineChanged: canvas.requestPaint()
    onSeparatorCountChanged: canvas.requestPaint()
    onAutoScaleYChanged: canvas.requestPaint()
    onWidthChanged: canvas.requestPaint()
    onHeightChanged: canvas.requestPaint()
    Component.onCompleted: canvas.requestPaint()
}
