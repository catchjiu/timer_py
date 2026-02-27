import QtQuick
import QtQuick.Controls
import QtWebEngine

Item {
    id: root
    property string playlistUrl: musicController ? musicController.playlistUrl : "https://music.youtube.com"

    Rectangle {
        anchors.fill: parent
        color: "#0a0a0a"
    }

    // Header
    Rectangle {
        id: header
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 48
        color: Qt.rgba(0, 0, 0, 0.6)

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            text: "YouTube Music"
            font.pixelSize: 16
            font.weight: Font.DemiBold
            color: "#D4AF37"
        }

        Text {
            anchors.right: closeBtn.left
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            text: "Scroll: wheel  •  Select: press  •  Close: long press"
            font.pixelSize: 11
            color: "#888"
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
            border.color: "#D4AF37"

            Text {
                anchors.centerIn: parent
                text: "Close"
                font.pixelSize: 12
                color: "#D4AF37"
            }

            MouseArea {
                anchors.fill: parent
                onClicked: musicController.close_music_panel()
            }
        }
    }

    WebEngineView {
        id: webView
        anchors.top: header.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        url: playlistUrl || "https://music.youtube.com"

        onLoadingChanged: {
            if (loadRequest.status === WebEngineLoadRequest.LoadSucceededStatus) {
                webView.forceActiveFocus()
            }
        }
    }

    Connections {
        target: musicController
        function onMusicScroll(delta) {
            webView.runJavaScript("window.scrollBy(0, " + (delta * 100) + ");")
        }
        function onMusicSelect() {
            webView.runJavaScript(
                "var e = new KeyboardEvent('keydown', {key:'Enter', keyCode:13, bubbles:true}); " +
                "document.activeElement.dispatchEvent(e);"
            )
        }
    }

    Component.onCompleted: {
        webView.forceActiveFocus()
    }
}
