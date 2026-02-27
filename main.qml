import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes

ApplicationWindow {
    id: root
    width: 800
    height: 480
    visible: true
    color: "#121212"
    title: "BJJ Gym Timer"

    // Design tokens
    readonly property color colorBg: "#121212"
    readonly property color colorGold: "#D4AF37"
    readonly property color colorWhite: "#FFFFFF"
    readonly property color colorMuted: "#888888"
    readonly property real arcStroke: 4
    readonly property real arcRadius: 160

    // Roboto Light fallback: use system light font
    readonly property string fontFamily: "Segoe UI Light"

    // Keyboard simulation for mock/dev mode
    Item {
        anchors.fill: parent
        focus: true
        Keys.onPressed: function(event) {
            if (hardwareBridge.is_mock()) {
                if (event.key === Qt.Key_Up || event.key === Qt.Key_Plus) {
                    hardwareBridge.simulate_encoder_delta(1)
                    event.accepted = true
                } else if (event.key === Qt.Key_Down || event.key === Qt.Key_Minus) {
                    hardwareBridge.simulate_encoder_delta(-1)
                    event.accepted = true
                } else if (event.key === Qt.Key_Space) {
                    hardwareBridge.simulate_short_press()
                    event.accepted = true
                } else if (event.key === Qt.Key_Escape) {
                    hardwareBridge.simulate_long_press()
                    event.accepted = true
                }
            }
        }
    }

    Item {
        id: contentRoot
        anchors.fill: parent

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        // Main content area
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // --- MAIN MENU ---
            ColumnLayout {
                id: menuView
                anchors.centerIn: parent
                visible: timerLogic.mode === "main_menu"
                spacing: 20

                Text {
                    text: "BJJ TIMER"
                    font.family: fontFamily
                    font.pixelSize: 28
                    font.weight: Font.Light
                    color: colorGold
                    Layout.alignment: Qt.AlignHCenter
                }

                Repeater {
                    model: ["DRILLING", "SPARRING"]
                    delegate: Rectangle {
                        width: 280
                        height: 56
                        radius: 8
                        color: index === timerLogic.menuIndex ? Qt.rgba(0.83, 0.69, 0.22, 0.25) : "transparent"
                        border.width: index === timerLogic.menuIndex ? 2 : 1
                        border.color: index === timerLogic.menuIndex ? colorGold : colorMuted

                        Behavior on color { ColorAnimation { duration: 200 } }
                        Behavior on border.color { ColorAnimation { duration: 200 } }

                        Text {
                            anchors.centerIn: parent
                            text: modelData
                            font.family: fontFamily
                            font.pixelSize: 20
                            color: index === timerLogic.menuIndex ? colorGold : colorWhite
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                timerLogic.menuIndex = index
                                hardwareBridge.simulate_short_press()
                            }
                        }
                    }
                }

                Text {
                    text: hardwareBridge.is_mock()
                        ? "MOCK MODE: ▲▼ scroll  •  SPACE select  •  ESC back"
                        : "Turn to scroll  •  Press to select  •  Long press to back"
                    font.pixelSize: 11
                    color: hardwareBridge.is_mock() ? "#E67E22" : colorMuted
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 12
                }
            }

            // --- TIMER VIEW (Drilling / Sparring) ---
            Item {
                id: timerView
                anchors.fill: parent
                visible: timerLogic.mode !== "main_menu"

                // Circular progress arc (depletes clockwise from top)
                Shape {
                    id: progressArc
                    anchors.centerIn: parent
                    width: (arcRadius + arcStroke) * 2
                    height: (arcRadius + arcStroke) * 2
                    antialiasing: true
                    smooth: true
                    layer.enabled: true
                    layer.smooth: true
                    layer.samples: 4

                    ShapePath {
                        fillColor: "transparent"
                        strokeColor: colorGold
                        strokeWidth: arcStroke
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin

                        PathAngleArc {
                            centerX: arcRadius + arcStroke
                            centerY: arcRadius + arcStroke
                            radiusX: arcRadius
                            radiusY: arcRadius
                            startAngle: -90
                            sweepAngle: 360 * (1 - timerLogic.progress)
                        }
                    }
                }

                // Background ring (subtle)
                Shape {
                    anchors.centerIn: parent
                    width: (arcRadius + arcStroke) * 2
                    height: (arcRadius + arcStroke) * 2
                    antialiasing: true
                    layer.enabled: true
                    layer.smooth: true

                    ShapePath {
                        fillColor: "transparent"
                        strokeColor: Qt.rgba(0.83, 0.69, 0.22, 0.15)
                        strokeWidth: arcStroke
                        capStyle: ShapePath.RoundCap
                        startX: (arcRadius + arcStroke) + arcRadius
                        startY: arcRadius + arcStroke
                        PathAngleArc {
                            centerX: arcRadius + arcStroke
                            centerY: arcRadius + arcStroke
                            radiusX: arcRadius
                            radiusY: arcRadius
                            startAngle: 0
                            sweepAngle: 360
                        }
                    }
                }

                // Phase label (WORK / REST / SWITCH!)
                Text {
                    id: phaseLabel
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: clockDisplay.top
                    anchors.bottomMargin: 8
                    text: timerLogic.phaseLabel
                    font.family: fontFamily
                    font.pixelSize: 14
                    color: timerLogic.switchAlert ? colorGold : colorMuted
                    opacity: timerLogic.phaseLabel ? 1 : 0

                    Behavior on color { ColorAnimation { duration: 150 } }
                    Behavior on opacity { NumberAnimation { duration: 200 } }
                }

                // Main clock display
                Text {
                    id: clockDisplay
                    anchors.centerIn: parent
                    text: timerLogic.displayTime
                    font.family: fontFamily
                    font.pixelSize: 96
                    font.weight: Font.Light
                    color: colorWhite

                    Behavior on text { PropertyAnimation { duration: 100 } }
                }

                // Round indicator (Sparring only)
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: clockDisplay.bottom
                    anchors.topMargin: 12
                    text: timerLogic.mode === "sparring" ? "Round %1 / %2".arg(timerLogic.currentRound).arg(timerLogic.totalRounds) : ""
                    font.pixelSize: 14
                    color: colorMuted
                    visible: timerLogic.mode === "sparring"
                }

                // Pause overlay
                Rectangle {
                    anchors.fill: parent
                    color: Qt.rgba(0, 0, 0, 0.6)
                    visible: timerLogic.state === "paused"
                    opacity: visible ? 1 : 0

                    Behavior on opacity { NumberAnimation { duration: 200 } }

                    Text {
                        anchors.centerIn: parent
                        text: "PAUSED"
                        font.pixelSize: 32
                        color: colorGold
                    }
                }

                // Switch! flash overlay
                Rectangle {
                    anchors.fill: parent
                    color: Qt.rgba(0.83, 0.69, 0.22, 0.15)
                    visible: timerLogic.switchAlert
                    opacity: visible ? 1 : 0

                    Behavior on opacity { NumberAnimation { duration: 100 } }

                    Text {
                        anchors.centerIn: parent
                        text: "SWITCH!"
                        font.pixelSize: 48
                        font.weight: Font.Bold
                        color: colorGold
                    }
                }
            }
        }

        // --- INFO BAR (Footer) ---
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 24
            spacing: 24

            Text {
                text: "TEMP  " + sensorProvider.temp.toFixed(1) + "°C"
                font.pixelSize: 11
                font.letterSpacing: 1
                color: colorMuted
            }
            Text {
                text: "HUM  " + sensorProvider.humidity.toFixed(0) + "%"
                font.pixelSize: 11
                font.letterSpacing: 1
                color: colorMuted
            }
            Item { Layout.fillWidth: true }
            Text {
                text: sensorProvider.timeString
                font.pixelSize: 12
                font.letterSpacing: 1
                color: colorGold
            }
            Text {
                text: hardwareBridge.is_mock() ? "MOCK" : "GPIO"
                font.pixelSize: 10
                color: hardwareBridge.is_mock() ? "#E67E22" : "#2ECC71"
                Layout.leftMargin: 8
            }
        }
    }

    // Transitions between views (on Item, not ApplicationWindow)
    states: [
        State {
            name: "menu"
            when: timerLogic.mode === "main_menu"
            PropertyChanges { target: menuView; opacity: 1 }
            PropertyChanges { target: timerView; opacity: 0 }
        },
        State {
            name: "timer"
            when: timerLogic.mode !== "main_menu"
            PropertyChanges { target: menuView; opacity: 0 }
            PropertyChanges { target: timerView; opacity: 1 }
        }
    ]

    transitions: Transition {
        NumberAnimation { properties: "opacity"; duration: 300; easing.type: Easing.InOutQuad }
    }

    Component.onCompleted: {
        menuView.visible = true
        timerView.visible = true
    }
    }
}
