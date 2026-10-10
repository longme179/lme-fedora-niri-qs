pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Services.Notifications

// Keep immutable, plain-text snapshots after expiry. Expired history has no
// actionable references to the destroyed native notification object.
Singleton {
    id: root

    property var history: []
    property var live: ({})
    property int unreadCount: 0
    property bool dnd: false
    readonly property var popups: dnd ? [] : history.filter(entry => entry.popup && entry.active).slice(0, 3)
    readonly property int count: history.length

    function snapshot(notification, timestamp, popup) {
        return {
            id: notification.id,
            appName: notification.appName || "Application",
            appIcon: notification.appIcon || "",
            summary: notification.summary || "Notification",
            body: notification.body || "",
            timestamp: timestamp,
            urgency: notification.urgency,
            actions: notification.actions.map(action => ({ identifier: action.identifier, text: action.text })),
            active: true,
            popup: popup,
            transient: notification.transient
        };
    }

    function receive(notification) {
        notification.tracked = true;
        const wrapper = watcherComponent.createObject(root, { notification: notification });
        const next = Object.assign({}, live);
        next[notification.id] = wrapper;
        live = next;
        history = [snapshot(notification, Date.now(), !dnd && !notification.lastGeneration && !ShellState.notificationsOpen), ...history.filter(entry => entry.id !== notification.id)].slice(0, 80);
        if (!notification.lastGeneration && !ShellState.notificationsOpen) unreadCount++;
    }

    function refresh(notification) {
        const previous = history.find(entry => entry.id === notification.id);
        if (!previous) return;
        history = history.map(entry => entry.id === notification.id ? snapshot(notification, previous.timestamp, previous.popup) : entry);
    }

    function closed(id, reason) {
        const next = Object.assign({}, live);
        const wrapper = next[id];
        delete next[id];
        live = next;
        history = history.filter(entry => entry.id !== id || (!entry.transient && reason !== NotificationCloseReason.CloseRequested)).map(entry => {
            if (entry.id !== id) return entry;
            return Object.assign({}, entry, { active: false, popup: false, actions: [] });
        });
        if (wrapper) Qt.callLater(() => wrapper.destroy());
    }

    function hidePopup(id) {
        history = history.map(entry => entry.id === id ? Object.assign({}, entry, { popup: false }) : entry);
    }

    function dismiss(id) {
        const wrapper = live[id];
        if (wrapper && wrapper.notification) wrapper.notification.dismiss();
        history = history.filter(entry => entry.id !== id);
        if (history.length === 0) unreadCount = 0;
    }

    function dismissAll() {
        Object.keys(live).forEach(id => {
            const wrapper = live[id];
            if (wrapper && wrapper.notification) wrapper.notification.dismiss();
        });
        history = [];
        unreadCount = 0;
    }

    function markRead() {
        unreadCount = 0;
        history = history.map(entry => Object.assign({}, entry, { popup: false }));
    }
    function local(summary, body) {
        const timestamp = Date.now();
        history = [{id: "local-" + timestamp, appName: "LME Shell", appIcon: "", summary: summary, body: body,
                    timestamp: timestamp, urgency: 1, actions: [], active: true, popup: !dnd && !ShellState.notificationsOpen,
                    transient: false, local: true}, ...history].slice(0, 80);
        if (!ShellState.notificationsOpen) unreadCount++;
    }
    Timer {
        interval: 1000; repeat: true
        running: root.history.some(entry => entry.local && entry.active)
        onTriggered: root.history = root.history.map(entry => entry.local && Date.now() - entry.timestamp >= 7000
                                                     ? Object.assign({}, entry, {active: false, popup: false}) : entry)
    }

    function invokeAction(id, identifier) {
        const wrapper = live[id];
        if (!wrapper || !wrapper.notification) return;
        const action = wrapper.notification.actions.find(candidate => candidate.identifier === identifier);
        if (action) action.invoke();
        hidePopup(id);
    }

    onDndChanged: {
        if (dnd) history = history.map(entry => Object.assign({}, entry, { popup: false }));
    }

    LazyLoader {
        active: !ShellState.demo && !ShellState.settingsApp
        component: NotificationServer {
            keepOnReload: true
            persistenceSupported: true
            bodySupported: true
            bodyMarkupSupported: false
            bodyHyperlinksSupported: false
            bodyImagesSupported: false
            actionsSupported: true
            imageSupported: false
            onNotification: notification => root.receive(notification)
        }
    }

    Component {
        id: watcherComponent
        QtObject {
            id: watcher
            required property var notification
            property int notificationId: notification ? notification.id : 0
            Component.onCompleted: resetTimeout()

            function resetTimeout() {
                expiry.stop();
                if (!notification || notification.expireTimeout === 0) return;
                // The freedesktop protocol and Quickshell use milliseconds.
                // Critical notifications with a default timeout stay until dismissed.
                if (notification.expireTimeout < 0 && notification.urgency === NotificationUrgency.Critical) return;
                expiry.interval = notification.expireTimeout < 0 ? 7000 : Math.max(1, notification.expireTimeout);
                expiry.start();
            }

            property Timer expiry: Timer {
                onTriggered: {
                    if (watcher.notification) watcher.notification.expire();
                }
            }

            property Connections changes: Connections {
                target: watcher.notification
                function onClosed(reason) { root.closed(watcher.notificationId, reason); }
                function onSummaryChanged() { root.refresh(watcher.notification); watcher.resetTimeout(); }
                function onBodyChanged() { root.refresh(watcher.notification); watcher.resetTimeout(); }
                function onAppNameChanged() { root.refresh(watcher.notification); }
                function onAppIconChanged() { root.refresh(watcher.notification); }
                function onActionsChanged() { root.refresh(watcher.notification); }
                function onUrgencyChanged() { root.refresh(watcher.notification); watcher.resetTimeout(); }
                function onExpireTimeoutChanged() { watcher.resetTimeout(); }
            }
        }
    }
}
