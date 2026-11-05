"""Niri event-stream cache contracts."""
import json
import unittest

from niri_events import NiriStateCache, read_niri_state


def workspace(ident, output="eDP-1", idx=1, active=False, focused=False, active_window=None):
    return {"id": ident, "idx": idx, "output": output, "name": None, "is_active": active,
            "is_focused": focused, "is_urgent": False, "active_window_id": active_window}


def window(ident, workspace_id=1, focused=False):
    return {"id": ident, "title": "Window " + str(ident), "app_id": "app", "workspace_id": workspace_id,
            "is_focused": focused, "is_floating": False, "is_urgent": False,
            "layout": {"pos_in_scrolling_layout": [1, 1]}, "focus_timestamp": None}


def event(name, payload):
    return json.dumps({name: payload}).encode() + b"\n"


class NiriEventCacheCase(unittest.TestCase):
    def setUp(self):
        self.cache = NiriStateCache(); self.cache.connect()
        self.cache.seed({"available": True, "workspaces": [workspace(1, active=True, focused=True)],
                         "windows": [window(10)]})

    def test_events_mutate_the_cache_like_full_snapshots(self):
        self.cache.feed(event("WorkspacesChanged", {"workspaces": [
            workspace(1, active=True, focused=True), workspace(2, idx=2, active=False, focused=False)]}))
        self.cache.feed(event("WindowsChanged", {"windows": [window(10, 1), window(11, 2)]}))
        self.cache.feed(event("WorkspaceActivated", {"id": 2, "focused": True}))
        self.cache.feed(event("WorkspaceActiveWindowChanged", {"workspace_id": 2, "active_window_id": 11}))
        self.cache.feed(event("WindowOpenedOrChanged", {"window": window(10, 1, focused=False)}))
        self.assertEqual([item["id"] for item in self.cache.snapshot()["windows"]], [10, 11])
        self.cache.feed(event("WindowOpenedOrChanged", {"window": window(11, 2, focused=True)}))
        self.cache.feed(event("WindowOpenedOrChanged", {"window": window(12, 2, focused=True)}))
        self.cache.feed(event("WindowClosed", {"id": 10}))
        self.cache.feed(event("WindowFocusChanged", {"id": 11}))
        self.cache.feed(event("WindowFocusTimestampChanged", {"id": 11, "focus_timestamp": 42}))
        self.cache.feed(event("WindowUrgencyChanged", {"id": 11, "urgent": True}))
        self.cache.feed(event("WindowLayoutsChanged", {"changes": [[11, {"pos_in_scrolling_layout": [2, 1]}]]}))
        state = self.cache.snapshot()
        self.assertTrue(state["available"])
        self.assertEqual([item["id"] for item in state["workspaces"]], [1, 2])
        self.assertTrue(state["workspaces"][1]["is_active"])
        self.assertTrue(state["workspaces"][1]["is_focused"])
        self.assertEqual(state["workspaces"][1]["active_window_id"], 11)
        self.assertEqual([item["id"] for item in state["windows"]], [11, 12])
        focused = next(item for item in state["windows"] if item["id"] == 11)
        self.assertTrue(focused["is_focused"]); self.assertTrue(focused["is_urgent"])
        self.assertEqual(focused["focus_timestamp"], 42)
        self.assertEqual(focused["layout"]["pos_in_scrolling_layout"], [2, 1])
        self.assertFalse(next(item for item in state["windows"] if item["id"] == 12)["is_focused"])

    def test_ignored_events_keep_state_and_unknown_events_invalidate(self):
        before = self.cache.revision
        self.cache.feed(event("KeyboardLayoutSwitched", {"idx": 1}))
        self.assertEqual(self.cache.revision, before)
        self.assertIsNotNone(self.cache.snapshot())
        self.cache.feed(event("FutureEvent", {"value": 1}))
        self.assertIsNone(self.cache.snapshot())
        self.cache.seed({"available": True, "workspaces": [workspace(3, focused=True)], "windows": []})
        self.assertEqual(self.cache.snapshot()["workspaces"][0]["id"], 3)

    def test_cache_without_a_live_stream_never_serves_stale_state(self):
        cache = NiriStateCache()
        cache.seed({"available": True, "workspaces": [workspace(7)], "windows": []})
        self.assertIsNone(cache.snapshot())
        cache.connect(); cache.seed({"available": True, "workspaces": [workspace(7)], "windows": []})
        self.assertIsNotNone(cache.snapshot())
        cache.close(); self.assertIsNone(cache.snapshot())
        cache.connect(); self.assertIsNone(cache.snapshot())

    def test_feed_survives_partial_lines_and_bounds_the_buffer(self):
        line = event("WorkspacesChanged", {"workspaces": [workspace(4, focused=True)]})
        self.cache.feed(line[:7]); self.cache.feed(line[7:])
        self.assertEqual(self.cache.snapshot()["workspaces"][0]["id"], 4)
        self.cache.feed(b"x" * (8 * 1024 * 1024 + 1))
        self.assertIsNone(self.cache.snapshot())

    def test_malformed_and_out_of_order_events_invalidate(self):
        for payload in (b"[]\n", b"{}\n", event("WindowClosed", {"id": 999}),
                        event("WorkspaceActivated", {"id": 999, "focused": True})):
            with self.subTest(payload=payload):
                self.cache.valid = True
                self.cache.feed(payload)
                self.assertIsNone(self.cache.snapshot())


class NiriSnapshotCase(unittest.TestCase):
    def test_snapshot_sorts_workspaces_and_reports_unavailable(self):
        def run(name, *args):
            if args[-1] == "workspaces":
                return json.dumps([workspace(2, output="DP-1", idx=2), workspace(1, output="eDP-1")])
            return json.dumps([window(10)])
        state = read_niri_state(run)
        self.assertTrue(state["available"])
        self.assertEqual([item["id"] for item in state["workspaces"]], [2, 1])
        self.assertFalse(read_niri_state(lambda *args: "not json")["available"])
        self.assertFalse(read_niri_state(lambda *args: None)["available"])


if __name__ == "__main__":
    unittest.main()
