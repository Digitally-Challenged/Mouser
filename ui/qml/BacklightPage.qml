import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import "Theme.js" as Theme

Item {
    id: backlightPage
    readonly property var theme: Theme.palette(uiState.darkMode)

    ScrollView {
        id: pageScroll
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        Column {
            id: mainCol
            width: pageScroll.availableWidth
            spacing: 0

            Item {
                width: parent.width
                height: 96

                Column {
                    anchors {
                        left: parent.left
                        leftMargin: 36
                        verticalCenter: parent.verticalCenter
                    }
                    spacing: 4

                    Text {
                        text: "Backlight & Fn Keys"
                        font {
                            family: uiState.fontFamily
                            pixelSize: 24
                            bold: true
                        }
                        color: backlightPage.theme.textPrimary
                    }

                    Text {
                        text: "Control keyboard backlight brightness, mode, and function key behaviour"
                        font {
                            family: uiState.fontFamily
                            pixelSize: 13
                        }
                        color: backlightPage.theme.textSecondary
                    }
                }
            }

            Rectangle {
                width: parent.width - 72
                height: 1
                color: backlightPage.theme.border
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Item { width: 1; height: 24 }

            // Not connected notice
            Rectangle {
                visible: !backend.keyboardConnected
                width: parent.width - 72
                anchors.horizontalCenter: parent.horizontalCenter
                height: notConnectedText.implicitHeight + 32
                radius: Theme.radius
                color: backlightPage.theme.bgCard
                border.width: 1
                border.color: backlightPage.theme.border

                Text {
                    id: notConnectedText
                    anchors {
                        left: parent.left
                        right: parent.right
                        verticalCenter: parent.verticalCenter
                        margins: 20
                    }
                    text: "Connect your MX Mechanical keyboard to adjust backlight settings."
                    font {
                        family: uiState.fontFamily
                        pixelSize: 13
                    }
                    color: backlightPage.theme.textDim
                    wrapMode: Text.WordWrap
                }
            }

            // Backlight card
            Rectangle {
                visible: backend.keyboardConnected
                width: parent.width - 72
                anchors.horizontalCenter: parent.horizontalCenter
                height: backlightContent.implicitHeight + 40
                radius: Theme.radius
                color: backlightPage.theme.bgCard
                border.width: 1
                border.color: backlightPage.theme.border

                Column {
                    id: backlightContent
                    anchors {
                        left: parent.left
                        right: parent.right
                        top: parent.top
                        margins: 20
                    }
                    spacing: 16

                    Text {
                        text: "Backlight"
                        font {
                            family: uiState.fontFamily
                            pixelSize: 16
                            bold: true
                        }
                        color: backlightPage.theme.textPrimary
                    }

                    // Enable toggle row
                    Rectangle {
                        width: parent.width
                        height: 52
                        radius: 10
                        color: backlightPage.theme.bgSubtle

                        RowLayout {
                            anchors {
                                fill: parent
                                leftMargin: 16
                                rightMargin: 16
                            }

                            Text {
                                text: "Backlight enabled"
                                font {
                                    family: uiState.fontFamily
                                    pixelSize: 13
                                }
                                color: backlightPage.theme.textPrimary
                                Layout.fillWidth: true
                            }

                            Switch {
                                id: backlightSwitch
                                checked: backend.backlightEnabled
                                Material.accent: backlightPage.theme.accent
                                Accessible.name: "Backlight enabled"
                                onToggled: backend.setBacklight(checked, brightnessSlider.value, modeGroup.currentMode)
                            }
                        }
                    }

                    // Brightness slider
                    Column {
                        width: parent.width
                        spacing: 8
                        opacity: backend.backlightEnabled ? 1.0 : 0.4

                        Behavior on opacity { NumberAnimation { duration: 150 } }

                        RowLayout {
                            width: parent.width

                            Text {
                                text: "Brightness"
                                font {
                                    family: uiState.fontFamily
                                    pixelSize: 13
                                }
                                color: backlightPage.theme.textPrimary
                                Layout.fillWidth: true
                            }

                            Rectangle {
                                Layout.preferredWidth: 72
                                Layout.preferredHeight: 32
                                radius: 8
                                color: backlightPage.theme.accentDim

                                Text {
                                    anchors.centerIn: parent
                                    text: Math.round(brightnessSlider.value) + "%"
                                    font {
                                        family: uiState.fontFamily
                                        pixelSize: 13
                                        bold: true
                                    }
                                    color: backlightPage.theme.accent
                                }
                            }
                        }

                        Slider {
                            id: brightnessSlider
                            width: parent.width
                            from: 0
                            to: 100
                            stepSize: 5
                            value: backend.backlightBrightness
                            enabled: backend.backlightEnabled
                            Material.accent: backlightPage.theme.accent
                            Accessible.name: "Backlight brightness"
                            onPressedChanged: {
                                if (!pressed)
                                    backend.setBacklight(backend.backlightEnabled, value, modeGroup.currentMode)
                            }
                        }
                    }

                    // Mode selector
                    Column {
                        width: parent.width
                        spacing: 8
                        opacity: backend.backlightEnabled ? 1.0 : 0.4

                        Behavior on opacity { NumberAnimation { duration: 150 } }

                        Text {
                            text: "Mode"
                            font {
                                family: uiState.fontFamily
                                pixelSize: 13
                            }
                            color: backlightPage.theme.textPrimary
                        }

                        ButtonGroup { id: modeGroup; property string currentMode: backend.backlightMode }

                        Row {
                            spacing: 10

                            Repeater {
                                model: [
                                    { label: "Auto",   value: "auto"   },
                                    { label: "Manual", value: "manual" },
                                    { label: "Off",    value: "off"    }
                                ]

                                delegate: Rectangle {
                                    required property var modelData
                                    readonly property bool isChecked: modeGroup.currentMode === modelData.value
                                    width: Math.max(88, modeLabel.implicitWidth + 28)
                                    height: 38
                                    radius: 10
                                    color: isChecked ? backlightPage.theme.accentDim : backlightPage.theme.bgSubtle
                                    border.width: 1
                                    border.color: isChecked ? backlightPage.theme.accent : backlightPage.theme.border

                                    Behavior on color { ColorAnimation { duration: 120 } }

                                    Accessible.role: Accessible.Button
                                    Accessible.name: "Backlight mode " + modelData.label

                                    Text {
                                        id: modeLabel
                                        anchors.centerIn: parent
                                        text: modelData.label
                                        font {
                                            family: uiState.fontFamily
                                            pixelSize: 13
                                            bold: parent.isChecked
                                        }
                                        color: parent.isChecked ? backlightPage.theme.accent : backlightPage.theme.textPrimary
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: backend.backlightEnabled
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            modeGroup.currentMode = modelData.value
                                            backend.setBacklight(backend.backlightEnabled, brightnessSlider.value, modelData.value)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Item { visible: backend.keyboardConnected; width: 1; height: 16 }

            // Function Keys card
            Rectangle {
                visible: backend.keyboardConnected
                width: parent.width - 72
                anchors.horizontalCenter: parent.horizontalCenter
                height: fnContent.implicitHeight + 40
                radius: Theme.radius
                color: backlightPage.theme.bgCard
                border.width: 1
                border.color: backlightPage.theme.border

                Column {
                    id: fnContent
                    anchors {
                        left: parent.left
                        right: parent.right
                        top: parent.top
                        margins: 20
                    }
                    spacing: 12

                    Text {
                        text: "Function Keys"
                        font {
                            family: uiState.fontFamily
                            pixelSize: 16
                            bold: true
                        }
                        color: backlightPage.theme.textPrimary
                    }

                    Rectangle {
                        width: parent.width
                        height: fnRow.implicitHeight + 24
                        radius: 10
                        color: backlightPage.theme.bgSubtle

                        RowLayout {
                            id: fnRow
                            anchors {
                                fill: parent
                                leftMargin: 16
                                rightMargin: 16
                            }
                            spacing: 16

                            Column {
                                Layout.fillWidth: true
                                spacing: 4

                                Text {
                                    text: "Use F1\u2013F12 as standard function keys"
                                    font {
                                        family: uiState.fontFamily
                                        pixelSize: 13
                                    }
                                    color: backlightPage.theme.textPrimary
                                }

                                Text {
                                    width: parent.width
                                    text: "When on, press Fn + F-key for media controls. When off, F-keys act as media controls by default."
                                    font {
                                        family: uiState.fontFamily
                                        pixelSize: 11
                                    }
                                    color: backlightPage.theme.textDim
                                    wrapMode: Text.WordWrap
                                }
                            }

                            Switch {
                                id: fnSwitch
                                checked: backend.fnInversion
                                Material.accent: backlightPage.theme.accent
                                Accessible.name: "Use F1 through F12 as standard function keys"
                                onToggled: backend.setFnInversion(checked)
                            }
                        }
                    }
                }
            }

            Item { width: 1; height: 24 }
        }
    }

    Connections {
        target: backend
        function onSettingsChanged() {
            backlightSwitch.checked = backend.backlightEnabled
            if (!brightnessSlider.pressed)
                brightnessSlider.value = backend.backlightBrightness
            modeGroup.currentMode = backend.backlightMode
            fnSwitch.checked = backend.fnInversion
        }
    }
}
