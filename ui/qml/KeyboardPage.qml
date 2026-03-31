import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import "Theme.js" as Theme

/*  Keyboard key-mapping page.
    Shows remappable keys grouped by region with action selectors.
    No SVG diagram yet — uses a clean text-based key list instead. */

Item {
    id: keyboardPage
    readonly property var theme: Theme.palette(uiState.darkMode)

    // ── Region classification ─────────────────────────────────
    readonly property var regionOrder: ["fn_row", "modifiers", "nav", "special", "utility"]
    readonly property var regionLabels: ({
        "fn_row": "Function Row",
        "modifiers": "Modifiers",
        "nav": "Navigation",
        "special": "Special Keys",
        "utility": "Utility"
    })

    function classifyRegion(name) {
        if (/^F\d/.test(name) || name === "Escape")
            return "fn_row"
        if (/Ctrl|Alt|Cmd|Win|Opt|Shift|Fn$|Fn Lock/.test(name))
            return "modifiers"
        if (/Delete|Home|End|PgUp|PgDn|Insert|Page/.test(name))
            return "nav"
        if (/Caps|Tab|Backspace|Enter|Return/.test(name))
            return "special"
        return "utility"
    }

    // Group keyboard buttons by region — returns [{region, label, keys: [...]}]
    property var groupedButtons: {
        if (!backend.keyboardConnected)
            return []
        var buttons = backend.keyboardButtons
        var groups = {}
        for (var i = 0; i < buttons.length; i++) {
            var btn = buttons[i]
            var region = classifyRegion(btn.name)
            if (!groups[region])
                groups[region] = []
            groups[region].push(btn)
        }
        var result = []
        for (var r = 0; r < regionOrder.length; r++) {
            var regionKey = regionOrder[r]
            if (groups[regionKey] && groups[regionKey].length > 0) {
                result.push({
                    "region": regionKey,
                    "label": regionLabels[regionKey],
                    "keys": groups[regionKey]
                })
            }
        }
        return result
    }

    // ── Action picker state ───────────────────────────────────
    property string selectedKey: ""
    property string selectedKeyName: ""

    ScrollView {
        id: pageScroll
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        Column {
            width: pageScroll.availableWidth
            padding: 32
            spacing: 24

            // ── Header with connection status ─────────────────
            RowLayout {
                width: parent.width - 64
                spacing: 12

                Text {
                    text: "Keyboard"
                    font { pixelSize: 24; bold: true; family: uiState.fontFamily }
                    color: keyboardPage.theme.textPrimary
                    Layout.fillWidth: true
                }

                Row {
                    spacing: 8

                    Rectangle {
                        width: 10; height: 10; radius: 5
                        anchors.verticalCenter: parent.verticalCenter
                        color: backend.keyboardConnected
                               ? keyboardPage.theme.accent
                               : keyboardPage.theme.textDim
                    }

                    Text {
                        text: backend.keyboardConnected ? "Connected" : "Not Connected"
                        color: keyboardPage.theme.textSecondary
                        font { pixelSize: 13; family: uiState.fontFamily }
                    }

                    Text {
                        visible: backend.keyboardConnected && backend.keyboardBatteryLevel >= 0
                        text: backend.keyboardBatteryLevel + "%"
                        color: keyboardPage.theme.textSecondary
                        font { pixelSize: 13; family: uiState.fontFamily }
                    }
                }
            }

            Rectangle {
                width: parent.width - 64; height: 1
                color: keyboardPage.theme.border
            }

            // ── Disconnected placeholder ──────────────────────
            Column {
                visible: !backend.keyboardConnected
                width: parent.width - 64
                spacing: 12
                topPadding: 40

                Text {
                    text: "No keyboard detected"
                    font { pixelSize: 18; bold: true; family: uiState.fontFamily }
                    color: keyboardPage.theme.textSecondary
                    anchors.horizontalCenter: parent.horizontalCenter
                }

                Text {
                    text: "Connect your MX Mechanical keyboard to configure key mappings."
                    font { pixelSize: 14; family: uiState.fontFamily }
                    color: keyboardPage.theme.textDim
                    anchors.horizontalCenter: parent.horizontalCenter
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    width: Math.min(parent.width, 400)
                }
            }

            // ── Grouped key list ──────────────────────────────
            Repeater {
                model: keyboardPage.groupedButtons

                delegate: Column {
                    width: pageScroll.availableWidth - 64
                    spacing: 6
                    topPadding: index > 0 ? 8 : 0

                    Text {
                        text: modelData.label
                        font {
                            pixelSize: 11; bold: true; family: uiState.fontFamily
                            capitalization: Font.AllUppercase; letterSpacing: 1
                        }
                        color: keyboardPage.theme.textDim
                        bottomPadding: 4
                    }

                    Repeater {
                        model: modelData.keys

                        delegate: Rectangle {
                            width: pageScroll.availableWidth - 64
                            height: 48
                            radius: 10
                            color: keyboardPage.selectedKey === modelData.key
                                   ? Qt.rgba(keyboardPage.theme.accent.r,
                                             keyboardPage.theme.accent.g,
                                             keyboardPage.theme.accent.b, 0.10)
                                   : keyRowMa.containsMouse
                                     ? Qt.rgba(keyboardPage.theme.accent.r,
                                               keyboardPage.theme.accent.g,
                                               keyboardPage.theme.accent.b, 0.04)
                                     : "transparent"
                            border.width: keyboardPage.selectedKey === modelData.key ? 1 : 0
                            border.color: keyboardPage.theme.accent

                            Behavior on color { ColorAnimation { duration: 120 } }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 16
                                anchors.rightMargin: 16
                                spacing: 12

                                Rectangle {
                                    Layout.preferredWidth: keyNameText.implicitWidth + 20
                                    Layout.preferredHeight: 28
                                    radius: 6
                                    color: uiState.darkMode
                                           ? Qt.rgba(1, 1, 1, 0.06)
                                           : Qt.rgba(0, 0, 0, 0.05)

                                    Text {
                                        id: keyNameText
                                        anchors.centerIn: parent
                                        text: modelData.name
                                        font { pixelSize: 12; bold: true; family: uiState.fontFamily }
                                        color: keyboardPage.theme.textPrimary
                                    }
                                }

                                Text {
                                    text: "\u2192"
                                    color: keyboardPage.theme.textDim
                                    font.pixelSize: 14
                                }

                                Text {
                                    text: modelData.actionLabel
                                    color: modelData.actionId === "none"
                                           ? keyboardPage.theme.textDim
                                           : keyboardPage.theme.accent
                                    font { pixelSize: 13; family: uiState.fontFamily }
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }

                                Text {
                                    text: "\u25B8"
                                    color: keyboardPage.theme.textDim
                                    font.pixelSize: 14
                                }
                            }

                            MouseArea {
                                id: keyRowMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    keyboardPage.selectedKey = modelData.key
                                    keyboardPage.selectedKeyName = modelData.name
                                    actionPicker.open()
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ── Action picker popup ───────────────────────────────────
    Popup {
        id: actionPicker
        anchors.centerIn: parent
        width: Math.min(keyboardPage.width * 0.7, 520)
        height: Math.min(keyboardPage.height * 0.8, 620)
        modal: true
        dim: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        Overlay.modal: Rectangle {
            color: Qt.rgba(0, 0, 0, 0.45)
        }

        background: Rectangle {
            radius: 16
            color: keyboardPage.theme.bgElevated
            border.width: 1
            border.color: keyboardPage.theme.border
        }

        onOpened: pickerFlick.contentY = 0

        Column {
            anchors.fill: parent
            spacing: 0

            // Header
            RowLayout {
                width: parent.width
                height: 56

                Column {
                    Layout.fillWidth: true
                    Layout.leftMargin: 20
                    spacing: 2

                    Text {
                        text: keyboardPage.selectedKeyName
                              ? keyboardPage.selectedKeyName + " \u2014 Choose Action"
                              : "Choose Action"
                        font { pixelSize: 16; bold: true; family: uiState.fontFamily }
                        color: keyboardPage.theme.textPrimary
                    }

                    Text {
                        text: "Select what happens when you press this key"
                        font { pixelSize: 12; family: uiState.fontFamily }
                        color: keyboardPage.theme.textSecondary
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 32; Layout.preferredHeight: 32; radius: 10
                    Layout.rightMargin: 16
                    color: closeMa.containsMouse
                           ? Qt.rgba(1, 1, 1, uiState.darkMode ? 0.08 : 0.65)
                           : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: "\u2715"
                        font.pixelSize: 14
                        color: keyboardPage.theme.textSecondary
                    }

                    MouseArea {
                        id: closeMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: actionPicker.close()
                    }
                }
            }

            Rectangle {
                width: parent.width; height: 1
                color: keyboardPage.theme.border
            }

            // Action list grouped by category
            Flickable {
                id: pickerFlick
                width: parent.width
                height: parent.height - 57
                contentHeight: pickerCol.implicitHeight + 24
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: pickerCol
                    width: parent.width
                    topPadding: 12
                    bottomPadding: 12

                    Repeater {
                        model: backend.actionCategories

                        delegate: Column {
                            width: pickerCol.width
                            spacing: 4
                            topPadding: index > 0 ? 12 : 0

                            Text {
                                text: modelData.category
                                font {
                                    pixelSize: 11; bold: true; family: uiState.fontFamily
                                    capitalization: Font.AllUppercase; letterSpacing: 1
                                }
                                color: keyboardPage.theme.textDim
                                leftPadding: 20
                                bottomPadding: 4
                            }

                            Repeater {
                                model: modelData.actions

                                delegate: Rectangle {
                                    width: pickerCol.width
                                    height: 38
                                    color: modelData.id === keyboardPage.currentActionForSelected()
                                           ? Qt.rgba(keyboardPage.theme.accent.r,
                                                     keyboardPage.theme.accent.g,
                                                     keyboardPage.theme.accent.b, 0.12)
                                           : actionItemMa.containsMouse
                                             ? Qt.rgba(keyboardPage.theme.accent.r,
                                                       keyboardPage.theme.accent.g,
                                                       keyboardPage.theme.accent.b, 0.06)
                                             : "transparent"

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 20
                                        anchors.rightMargin: 20

                                        Text {
                                            text: modelData.label
                                            font { pixelSize: 13; family: uiState.fontFamily }
                                            color: modelData.id === keyboardPage.currentActionForSelected()
                                                   ? keyboardPage.theme.accent
                                                   : keyboardPage.theme.textPrimary
                                            Layout.fillWidth: true
                                        }

                                        Text {
                                            visible: modelData.id === keyboardPage.currentActionForSelected()
                                            text: "\u2713"
                                            font { pixelSize: 14; bold: true }
                                            color: keyboardPage.theme.accent
                                        }
                                    }

                                    MouseArea {
                                        id: actionItemMa
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            backend.setKeyboardMapping(
                                                keyboardPage.selectedKey, modelData.id)
                                            actionPicker.close()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ── Helper: look up current action for the selected key ───
    function currentActionForSelected() {
        if (!selectedKey)
            return ""
        var buttons = backend.keyboardButtons
        for (var i = 0; i < buttons.length; i++) {
            if (buttons[i].key === selectedKey)
                return buttons[i].actionId
        }
        return ""
    }
}
