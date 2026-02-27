import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes

ApplicationWindow {
    id: root
    width: 800
    height: 480
    visible: true
    color: "#0D0D0D"
    title: "BJJ Gym Timer"

    // Design tokens - green accent (reference design)
    readonly property color colorBg: "#0D0D0D"
    readonly property color colorGreen: "#2ECC71"
    readonly property color colorGreenDim: "#1E8449"
    readonly property color colorWhite: "#E8E8E8"
    readonly property color colorMuted: "#6B6B6B"
    readonly property real arcStroke: 6
    readonly property real arcRadius: 140
    readonly property string fontFamily: "Segoe UI Light"
    readonly property string gymName: "CATCH JIU JITSU"

    // Keyboard simulation for mock/dev mode
    Item {
        anchors.fill: parent
        focus: true
        Keys.onPressed: function(event) {
            if (musicController && musicController.musicPanelOpen && event.key === Qt.Key_Escape) {
                musicController.close_music_panel()
                event.accepted = true
            } else if (hardwareBridge.is_mock()) {
                if (event.key === Qt.Key_Up || event.key === Qt.Key_Plus) {
                    hardwareBridge.simulate_encoder_delta(1)
                    event.accepted = true
                } else if (event.key === Qt.Key_Down || event.key === Qt.Key_Minus) {
                    hardwareBridge.simulate_encoder_delta(-1)
                    event.accepted = true
                } else if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    hardwareBridge.simulate_short_press()
                    event.accepted = true
                } else if (event.key === Qt.Key_Escape || event.key === Qt.Key_Backspace) {
                    hardwareBridge.simulate_long_press()
                    event.accepted = true
                } else if (event.key === Qt.Key_M && !(event.modifiers & Qt.ControlModifier)) {
                    hardwareBridge.simulate_triple_press()
                    event.accepted = true
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // --- HEADER ---
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            color: "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 24
                anchors.rightMargin: 24
                spacing: 16

                // Clock (left)
                Text {
                    text: sensorProvider.timeString12h
                    font.family: fontFamily
                    font.pixelSize: 14
                    font.weight: Font.Light
                    color: colorMuted
                }

                Item { Layout.fillWidth: true }

                // Weather & humidity (right)
                RowLayout {
                    spacing: 20
                    RowLayout {
                        spacing: 6
                        Text {
                            text: "○"
                            font.pixelSize: 10
                            color: colorMuted
                        }
                        Text {
                            text: Math.round(sensorProvider.temp * 9/5 + 32) + "°F " + sensorProvider.weatherDescription.toUpperCase()
                            font.family: fontFamily
                            font.pixelSize: 12
                            font.weight: Font.Light
                            color: colorMuted
                        }
                    }
                    RowLayout {
                        spacing: 6
                        Text {
                            text: "◐"
                            font.pixelSize: 10
                            color: colorMuted
                        }
                        Text {
                            text: sensorProvider.humidity.toFixed(0) + "% HUMIDITY"
                            font.family: fontFamily
                            font.pixelSize: 12
                            font.weight: Font.Light
                            color: colorMuted
                        }
                    }
                }
            }
        }

        // --- MAIN CONTENT ---
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // --- MAIN MENU ---
            ColumnLayout {
                id: menuView
                anchors.centerIn: parent
                visible: timerLogic.mode === "main_menu"
                spacing: 24

                Rectangle {
                    Layout.preferredWidth: 220
                    Layout.preferredHeight: 36
                    radius: 18
                    color: colorGreen
                    Layout.alignment: Qt.AlignHCenter

                    Text {
                        anchors.centerIn: parent
                        text: gymName
                        font.family: fontFamily
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                        color: colorBg
                    }
                }

                Text {
                    text: "BJJ TIMER"
                    font.family: fontFamily
                    font.pixelSize: 32
                    font.weight: Font.Light
                    color: colorWhite
                    Layout.alignment: Qt.AlignHCenter
                }

                Repeater {
                    model: ["DRILLING", "SPARRING"]
                    delegate: Rectangle {
                        width: 260
                        height: 52
                        radius: 8
                        color: index === timerLogic.menuIndex ? Qt.rgba(0.18, 0.8, 0.44, 0.2) : "transparent"
                        border.width: index === timerLogic.menuIndex ? 2 : 1
                        border.color: index === timerLogic.menuIndex ? colorGreen : colorMuted

                        Text {
                            anchors.centerIn: parent
                            text: modelData
                            font.family: fontFamily
                            font.pixelSize: 18
                            color: index === timerLogic.menuIndex ? colorGreen : colorWhite
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
                        ? "MOCK: ▲▼ scroll  •  SPACE select  •  ESC back  •  M playlist"
                        : "Turn to scroll  •  Press to select  •  Long press back  •  Triple press playlist"
                    font.pixelSize: 11
                    color: colorMuted
                    Layout.alignment: Qt.AlignHCenter
                }
            }

            // --- CONFIG VIEW ---
            ColumnLayout {
                id: configView
                anchors.centerIn: parent
                visible: timerLogic.mode === "config_drilling" || timerLogic.mode === "config_sparring"
                spacing: 16

                Rectangle {
                    Layout.preferredWidth: 200
                    Layout.preferredHeight: 32
                    radius: 16
                    color: colorGreen
                    Layout.alignment: Qt.AlignHCenter

                    Text {
                        anchors.centerIn: parent
                        text: timerLogic.mode === "config_drilling" ? "DRILLING" : "SPARRING"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: colorBg
                    }
                }

                RowLayout {
                    Layout.preferredWidth: 320
                    spacing: 12
                    Text { text: "Work time:"; font.pixelSize: 14; color: timerLogic.configStep === 0 ? colorGreen : colorMuted; Layout.preferredWidth: 120 }
                    Text {
                        text: Math.floor(timerLogic.configWorkSec / 60) + ":" + (timerLogic.configWorkSec % 60 < 10 ? "0" : "") + (timerLogic.configWorkSec % 60)
                        font.pixelSize: 16
                        font.weight: timerLogic.configStep === 0 ? Font.DemiBold : Font.Normal
                        color: colorWhite
                    }
                }
                RowLayout {
                    Layout.preferredWidth: 320
                    spacing: 12
                    Text {
                        text: (timerLogic.mode === "config_drilling" ? "Switch:" : "Rest:")
                        font.pixelSize: 14
                        color: timerLogic.configStep === 1 ? colorGreen : colorMuted
                        Layout.preferredWidth: 120
                    }
                    Text {
                        text: Math.floor(timerLogic.configRestSwitchSec / 60) + ":" + (timerLogic.configRestSwitchSec % 60 < 10 ? "0" : "") + (timerLogic.configRestSwitchSec % 60)
                        font.pixelSize: 16
                        font.weight: timerLogic.configStep === 1 ? Font.DemiBold : Font.Normal
                        color: colorWhite
                    }
                }
                RowLayout {
                    Layout.preferredWidth: 320
                    spacing: 12
                    Text { text: "Rounds:"; font.pixelSize: 14; color: timerLogic.configStep === 2 ? colorGreen : colorMuted; Layout.preferredWidth: 120 }
                    Text {
                        text: timerLogic.configRounds
                        font.pixelSize: 16
                        font.weight: timerLogic.configStep === 2 ? Font.DemiBold : Font.Normal
                        color: colorWhite
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 260
                    Layout.preferredHeight: 44
                    radius: 8
                    color: timerLogic.configStep === 3 ? Qt.rgba(0.18, 0.8, 0.44, 0.3) : "transparent"
                    border.width: timerLogic.configStep === 3 ? 2 : 1
                    border.color: timerLogic.configStep === 3 ? colorGreen : colorMuted

                    Text {
                        anchors.centerIn: parent
                        text: timerLogic.configStep === 3 ? "READY – Press to START" : "Press to confirm"
                        font.pixelSize: 13
                        color: timerLogic.configStep === 3 ? colorGreen : colorMuted
                    }
                }
            }

            // --- TIMER VIEW ---
            ColumnLayout {
                id: timerView
                anchors.fill: parent
                anchors.margins: 24
                visible: timerLogic.mode === "drilling" || timerLogic.mode === "sparring"
                spacing: 12

                Item { Layout.fillHeight: true }

                // Gym badge
                Rectangle {
                    Layout.preferredWidth: 200
                    Layout.preferredHeight: 32
                    Layout.alignment: Qt.AlignHCenter
                    radius: 16
                    color: colorGreen

                    Text {
                        anchors.centerIn: parent
                        text: gymName
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: colorBg
                    }
                }

                // Mode title
                Text {
                    text: timerLogic.mode === "drilling" ? "Drilling" : "Sparring"
                    font.family: fontFamily
                    font.pixelSize: 28
                    font.weight: Font.DemiBold
                    color: colorWhite
                    Layout.alignment: Qt.AlignHCenter
                }

                // Session details
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 24
                    Text {
                        text: "♯ Round " + timerLogic.currentRound + "/" + timerLogic.totalRounds
                        font.pixelSize: 13
                        color: colorMuted
                    }
                    Text {
                        text: timerLogic.nextPhaseSec > 0
                            ? "● Next: " + timerLogic.nextPhaseLabel + " (" + timerLogic.nextPhaseSec + "s)"
                            : ""
                        font.pixelSize: 13
                        color: colorMuted
                    }
                }

                // Circular progress + countdown
                Item {
                    Layout.preferredWidth: (arcRadius + arcStroke) * 2
                    Layout.preferredHeight: (arcRadius + arcStroke) * 2
                    Layout.alignment: Qt.AlignHCenter

                    // Background ring
                    Shape {
                        anchors.fill: parent
                        antialiasing: true
                        layer.enabled: true
                        layer.smooth: true

                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: Qt.rgba(0.18, 0.8, 0.44, 0.15)
                            strokeWidth: arcStroke
                            capStyle: ShapePath.RoundCap

                            PathAngleArc {
                                centerX: (arcRadius + arcStroke)
                                centerY: (arcRadius + arcStroke)
                                radiusX: arcRadius
                                radiusY: arcRadius
                                startAngle: 0
                                sweepAngle: 360
                            }
                        }
                    }

                    // Progress arc (green, depletes clockwise from top)
                    Shape {
                        anchors.fill: parent
                        antialiasing: true
                        layer.enabled: true
                        layer.smooth: true

                        ShapePath {
                            fillColor: "transparent"
                            strokeColor: colorGreen
                            strokeWidth: arcStroke
                            capStyle: ShapePath.RoundCap

                            PathAngleArc {
                                centerX: (arcRadius + arcStroke)
                                centerY: (arcRadius + arcStroke)
                                radiusX: arcRadius
                                radiusY: arcRadius
                                startAngle: -90
                                sweepAngle: 360 * (1 - timerLogic.progress)
                            }
                        }
                    }

                    // Countdown
                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 0
                        Text {
                            text: timerLogic.displayTime
                            font.family: fontFamily
                            font.pixelSize: 72
                            font.weight: Font.DemiBold
                            color: colorGreen
                            Layout.alignment: Qt.AlignHCenter
                        }
                        Text {
                            text: "REMAINING"
                            font.pixelSize: 11
                            font.letterSpacing: 2
                            color: colorMuted
                            Layout.alignment: Qt.AlignHCenter
                        }
                    }
                }

                // Horizontal progress bar
                ColumnLayout {
                    Layout.preferredWidth: 400
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 4

                    RowLayout {
                        Text {
                            text: "TOTAL PROGRESS"
                            font.pixelSize: 10
                            font.letterSpacing: 1
                            color: colorMuted
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: Math.round(timerLogic.progress * 100) + "%"
                            font.pixelSize: 11
                            color: colorMuted
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 6
                        radius: 3
                        color: Qt.rgba(0.18, 0.8, 0.44, 0.2)
                        clip: true

                        Rectangle {
                            width: parent.width * timerLogic.progress
                            height: parent.height
                            radius: 3
                            color: colorGreen
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                // Footer controls
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 24

                    // Left: Back/Reset
                    Rectangle {
                        width: 56
                        height: 56
                        radius: 28
                        color: "transparent"
                        border.width: 1
                        border.color: colorMuted

                        Text {
                            anchors.centerIn: parent
                            text: "⟲"
                            font.pixelSize: 22
                            color: colorMuted
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: hardwareBridge.simulate_long_press()
                        }
                    }

                    // Middle: Pause/Play (primary)
                    Rectangle {
                        width: 72
                        height: 72
                        radius: 12
                        color: colorGreen

                        Text {
                            anchors.centerIn: parent
                            text: timerLogic.state === "paused" ? "▶" : "⏸"
                            font.pixelSize: 28
                            color: colorBg
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: hardwareBridge.simulate_short_press()
                        }
                    }

                    // Right: Skip (add 30s)
                    Rectangle {
                        width: 56
                        height: 56
                        radius: 28
                        color: "transparent"
                        border.width: 1
                        border.color: colorMuted

                        Text {
                            anchors.centerIn: parent
                            text: "»"
                            font.pixelSize: 24
                            color: colorMuted
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: hardwareBridge.simulate_encoder_delta(1)
                        }
                    }
                }

                Item { Layout.preferredHeight: 16 }
            }
        }
        Item { Layout.preferredHeight: 0 }
    }

    // Pause overlay
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.7)
        visible: timerLogic.state === "paused"
        opacity: visible ? 1 : 0
        z: 100

        Behavior on opacity { NumberAnimation { duration: 200 } }

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 12
            Text {
                text: "PAUSED"
                font.pixelSize: 36
                font.weight: Font.DemiBold
                color: colorGreen
                Layout.alignment: Qt.AlignHCenter
            }
            Text {
                text: "Press to resume"
                font.pixelSize: 14
                color: colorMuted
                Layout.alignment: Qt.AlignHCenter
            }
        }
    }

    // Switch! overlay
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0.18, 0.8, 0.44, 0.12)
        visible: timerLogic.switchAlert
        opacity: visible ? 1 : 0
        z: 99

        Behavior on opacity { NumberAnimation { duration: 100 } }

        Text {
            anchors.centerIn: parent
            text: "SWITCH!"
            font.pixelSize: 48
            font.weight: Font.Bold
            color: colorGreen
        }
    }

    Component.onCompleted: {
        menuView.visible = true
        configView.visible = true
        timerView.visible = true
    }
}
