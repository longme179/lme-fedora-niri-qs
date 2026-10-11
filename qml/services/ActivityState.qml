pragma Singleton
import QtQuick
import Quickshell.Services.Mpris

QtObject {
    id: root
    property string preferredPlayer: ""
    property bool demoPlaying: true
    readonly property var players: ShellState.demo ? [] : Mpris.players.values
    readonly property var player: players.find(p => p.uniqueId === preferredPlayer) || players.find(p => p.isPlaying) || players[0] || null
    readonly property bool hasMedia: ShellState.demo || player !== null
    readonly property bool playing: ShellState.demo ? demoPlaying : player ? player.isPlaying : false
    readonly property string track: ShellState.demo ? "A little more space" : player ? player.trackTitle || player.identity : "No player connected"
    readonly property string artist: ShellState.demo ? "Liquid Sessions" : player ? player.trackArtist || player.identity : "Open a music or video application"
    readonly property string artwork: ShellState.demo ? "" : player ? player.trackArtUrl : ""
    readonly property bool canPlay: ShellState.demo || !!(player && player.canTogglePlaying)
    readonly property bool canPrevious: ShellState.demo || !!(player && player.canGoPrevious)
    readonly property bool canNext: ShellState.demo || !!(player && player.canGoNext)
    readonly property var recording: ShellState.system.recording || {active: false}
    readonly property bool timerActive: FocusTimer.running || FocusTimer.remaining !== FocusTimer.durations[FocusTimer.mode]
    readonly property bool stopwatchActive: FocusTimer.stopwatchRunning || FocusTimer.stopwatchElapsed > 0
    readonly property string kind: recording.active ? "recording" : timerActive ? "timer" : stopwatchActive ? "stopwatch" : hasMedia ? "media" : "idle"
    readonly property string title: kind === "recording" ? "Recording · " + FocusTimer.format(recording.elapsed || 0)
        : kind === "timer" ? (FocusTimer.mode === 0 ? "Focus" : "Break") + " · " + FocusTimer.format(FocusTimer.remaining)
        : kind === "stopwatch" ? "Stopwatch · " + FocusTimer.format(FocusTimer.stopwatchElapsed)
        : kind === "media" ? track : ShellState.focusedTitle
    readonly property string icon: kind === "recording" ? "record" : kind === "timer" || kind === "stopwatch" ? "clock" : kind === "media" ? "media" : "applications"
    function togglePlaying() { if (ShellState.demo) demoPlaying = !demoPlaying; else if (canPlay) player.togglePlaying(); }
    function previous() { if (!ShellState.demo && canPrevious) player.previous(); }
    function next() { if (!ShellState.demo && canNext) player.next(); }
}
