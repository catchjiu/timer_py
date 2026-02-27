import QtQuick
import QtQuick.Controls

Item {
    id: root

    Rectangle {
        anchors.fill: parent
        color: "#0a0a0a"
    }

    Column {
        anchors.centerIn: parent
        spacing: 24

        Text {
            text: "♪ YouTube Music"
            font.pixelSize: 24
            font.weight: Font.DemiBold
            color: "#D4AF37"
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Text {
            text: "Install PySide6-WebEngine for embedded playback:\npip install PySide6-WebEngine"
            font.pixelSize: 14
            color: "#888"
            horizontalAlignment: Text.AlignHCenter
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Button {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Open in Browser"
            font.pixelSize: 14
            onClicked: musicController.open_playlist_in_browser()
        }

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 120
            height: 40
            radius: 8
            color: Qt.rgba(0.83, 0.69, 0.22, 0.2)
            border.color: "#D4AF37"

            Text {
                anchors.centerIn: parent
                text: "Close"
                font.pixelSize: 14
                color: "#D4AF37"
            }

            MouseArea {
                anchors.fill: parent
                onClicked: musicController.close_music_panel()
            }
        }
    }
}
