pragma Singleton
import QtQuick
import Quickshell.Services.Mpris
import "../components"

QtObject {
    id: root
    property string preferredPlayer: ""
    property bool demoPlaying: true
    readonly property var players: ShellState.demo ? [] : Mpris.players.values
    readonly property var player: players.find(p => p.dbusName === preferredPlayer) || players.find(p => p.isPlaying) || players[0] || null
    property MediaPresentation presentation: MediaPresentation { player: root.player; enabled: ShellState.preferences.mediaStability !== false }
    readonly property var display: presentation.current
    readonly property bool hasMedia: ShellState.demo || player !== null
    readonly property bool playing: ShellState.demo ? demoPlaying : player ? player.isPlaying : false
    readonly property string track: ShellState.demo ? "A little more space" : display ? display.title || display.identity : "No player connected"
    property LyricsSession lyrics: LyricsSession {
        player: root.player
        active: ShellState.preferences.activityLyrics !== false && ShellState.preferences.activityEnabled !== false && root.kind === "media" && root.playing && !ShellState.demo
    }
    readonly property string mediaTitle: playing && ShellState.preferences.activityLyrics !== false && ShellState.preferences.lyricsEnabled !== false && lyrics.wanted && lyrics.currentText.trim()
        ? lyrics.currentText.replace(/\s+/g, " ") : track
    readonly property string artist: ShellState.demo ? ShellState.shellName + " Sessions" : display ? display.artist || display.identity : "Open a music or video application"
    readonly property string artwork: ShellState.demo ? "" : display ? display.artUrl : ""
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
        : kind === "media" ? mediaTitle : (ShellState.niri.windows || []).find(w => w.is_focused)?.title || "Activity Island"
    readonly property string icon: kind === "recording" ? "record" : kind === "timer" || kind === "stopwatch" ? "clock" : kind === "media" ? "media" : "applications"
    function togglePlaying() { if (ShellState.demo) demoPlaying = !demoPlaying; else if (canPlay) player.togglePlaying(); }
    function previous() { if (!ShellState.demo && canPrevious) player.previous(); }
    function next() { if (!ShellState.demo && canNext) player.next(); }
}
