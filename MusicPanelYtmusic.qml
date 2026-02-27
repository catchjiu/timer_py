import QtQuick
import QtQuick.Controls

Item {
    id: root

    readonly property color colorGold: "#D4AF37"
    readonly property color colorWhite: "#FFFFFF"
    readonly property color colorMuted: "#888888"

    Rectangle {
        anchors.fill: parent
        color: "#0a0a0a"
    }

    Column {
        anchors.fill: parent

        // Header
        Rectangle {
            width: parent.width - 0
            height: 48
            color: Qt.rgba(0, 0, 0, 0.6)

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                text: "YouTube Music"
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: colorGold
            }

            Text {
                anchors.right: closeBtn.left
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                text: "Turn to scroll  •  Press to play  •  Long press to close"
                font.pixelSize: 11
                color: colorMuted
            }

            Rectangle {
                id: closeBtn
                anchors.right: parent.right
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                width: 80
                height: 32
                radius: 4
                color: Qt.rgba(0.83, 0.69, 0.22, 0.2)
                border.color: colorGold

                Text {
                    anchors.centerIn: parent
                    text: "Close"
                    font.pixelSize: 12
                    color: colorGold
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: musicController.close_music_panel()
                }
            }
        }

        // Track list container
        Item {
            width: parent.width
            height: parent.height - 48

            ListView {
                id: trackList
                anchors.fill: parent
                clip: true
                model: musicController ? musicController.trackModel : null
                currentIndex: musicController ? musicController.selectedIndex : 0

                onCurrentIndexChanged: {
                    if (musicController && currentIndex !== musicController.selectedIndex) {
                        musicController.selectedIndex = currentIndex
                    }
                }

                Connections {
                    target: musicController
                    function onSelectedIndexChanged() {
                        var idx = musicController.selectedIndex
                        trackList.currentIndex = idx
                        if (idx >= 0 && idx < musicController.trackCount) {
                            trackList.positionViewAtIndex(idx, ListView.Center)
                        }
                    }
                }

                delegate: Rectangle {
                width: trackList.width - 24
                height: 56
                x: 12
                color: (musicController && index === musicController.selectedIndex)
                       ? Qt.rgba(0.83, 0.69, 0.22, 0.25)
                       : "transparent"
                border.width: (musicController && index === musicController.selectedIndex) ? 2 : 0
                border.color: colorGold
                radius: 6

                Behavior on color { ColorAnimation { duration: 150 } }

                Column {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 12
                    spacing: 2

                    Text {
                        text: model.title || "—"
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                        color: colorWhite
                        elide: Text.ElideRight
                        width: parent.width - 24
                    }

                    Text {
                        text: model.artists || ""
                        font.pixelSize: 12
                        color: colorMuted
                        elide: Text.ElideRight
                        width: parent.width - 24
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (musicController) {
                            musicController.selectedIndex = index
                            musicController.play_selected_track()
                        }
                    }
                }
            }

                ScrollIndicator.vertical: ScrollIndicator { }
            }

            // Empty state overlay
            Rectangle {
                anchors.fill: parent
                color: "#0a0a0a"
                visible: !musicController || musicController.trackCount === 0
                z: 1

                Column {
                    anchors.centerIn: parent
                    spacing: 16

                    Text {
                        text: "Loading playlist…"
                        font.pixelSize: 16
                        color: colorMuted
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Button {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Open playlist in browser"
                        font.pixelSize: 14
                        onClicked: musicController.open_playlist_in_browser()
                    }
                }
            }
        }
    }
}
