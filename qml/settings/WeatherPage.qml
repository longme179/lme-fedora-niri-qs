pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    spacing: 20
    readonly property var weather: ShellState.weather
    readonly property var search: weather.search || {}
    readonly property var place: weather.location || {}
    SettingsCard {
        title: "Find me automatically"
        description: "Use your public IP address to find an approximate city. This may follow your VPN location. No GPS or location history is used."
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Automatic location"; font.weight: Font.Bold; Layout.fillWidth: true }
            ExpressiveSwitch {
                checked: ShellState.preferences.weatherAutoLocation !== false
                enabled: ShellState.backendReady && !ShellState.pendingActions.setting
                Accessible.name: "Detect weather location automatically by IP"
                onClicked: ShellState.run("setting", {key: "weatherAutoLocation", value: checked})
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            LabelText {
                text: root.place.name ? root.place.name + (root.place.country ? ", " + root.place.country : "")
                      : root.weather.loading ? "Finding your approximate location…" : "Location has not been detected yet"
                Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
            }
            LiquidButton {
                text: "Detect now"
                enabled: ShellState.backendReady && ShellState.preferences.weatherAutoLocation !== false && !root.weather.loading && !ShellState.pendingActions.weatherDetect
                onClicked: ShellState.run("weatherDetect")
            }
        }
        LabelText { visible: !!root.weather.error; text: root.weather.error || ""; color: Theme.yellow; Layout.fillWidth: true; wrapMode: Text.Wrap }
    }
    SettingsCard {
        title: "Choose a city"
        description: "Select a search result to switch to a fixed location. Turn automatic location back on whenever you want."
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            ExpressiveField {
                id: query
                Layout.fillWidth: true; placeholderText: "Search city…"; Accessible.name: "Weather city search"
                onAccepted: if (searchButton.enabled) searchButton.clicked()
            }
            LiquidButton {
                id: searchButton
                text: root.search.loading ? "Searching…" : "Search"
                enabled: ShellState.backendReady && query.text.trim().length >= 2 && query.text.trim().length <= 100 && !root.search.loading && !ShellState.pendingActions.weatherSearch
                onClicked: ShellState.run("weatherSearch", {query: query.text.trim()})
            }
        }
        Repeater {
            model: root.search.results || []
            delegate: LiquidButton {
                required property var modelData
                Layout.fillWidth: true
                text: modelData.name + (modelData.country ? ", " + modelData.country : "")
                enabled: ShellState.backendReady && !ShellState.pendingActions.weatherSelect
                onClicked: ShellState.run("weatherSelect", {location: modelData})
            }
        }
        LabelText {
            visible: !!root.search.error || !!root.search.query && !root.search.loading && (root.search.results || []).length === 0
            text: root.search.error || "No matching cities. Try a nearby town."; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap
        }
    }
    SettingsCard {
        title: "Temperature units"
        description: "Forecasts update every 15 minutes. Automatic location refreshes hourly."
        RowLayout {
            Layout.fillWidth: true
            LiquidButton { text: "Celsius · °C"; Layout.fillWidth: true; selected: ShellState.preferences.weatherUnit !== "fahrenheit"; enabled: ShellState.backendReady && !ShellState.pendingActions.setting; onClicked: ShellState.run("setting", {key: "weatherUnit", value: "celsius"}) }
            LiquidButton { text: "Fahrenheit · °F"; Layout.fillWidth: true; selected: ShellState.preferences.weatherUnit === "fahrenheit"; enabled: ShellState.backendReady && !ShellState.pendingActions.setting; onClicked: ShellState.run("setting", {key: "weatherUnit", value: "fahrenheit"}) }
        }
        LabelText {
            text: "Forecasts and city search: Open-Meteo. Approximate IP location: IPwho.is. Network failures retain the latest forecast and retry after two minutes."
            Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 12
        }
    }
}
