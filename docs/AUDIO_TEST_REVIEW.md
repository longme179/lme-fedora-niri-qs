# Audio native test review (pending owner approval)

AGENTS.md requires asking before editing existing assertions/expected cases.
The provider-set update was approved separately and is already committed.
These two native routing test revisions remain unapplied.

1. Exercise the chosen same-core-verified metadata route; a raw Pulse move can
   be overridden by the session manager for explicitly targeted clients.
   Keep the actual destination and other-stream assertions unchanged.
2. Default-sink setup may itself move the other app before the tested operation.
   Compare that app to its observed pre-operation route, preserving independence.

No timeout, frozen fixture, production hook or production change is proposed.

```diff
--- a/tests/test_audio_session.py
+++ b/tests/test_audio_session.py
@@ -21,6 +21,8 @@
             for item in before:self.assertIn(item['properties']['object.serial'],nodes)
             self.assertTrue(any(item['index']!=nodes[item['properties']['object.serial']] for item in before))
-            target=next(s['index'] for s in session.json('list','sinks') if s['name']=='TestHeadset')
-            session.pulse('--','move-sink-input',str(stream['index']),str(target))
+            from audio_pipewire import route_plan, apply_route
+            sink=next(s for s in session.json('list','sinks') if s['name']=='TestHeadset');target=sink['index']
+            route=route_plan(session.json('info'),dump,stream['properties']['object.serial'],sink['properties']['object.serial'])
+            apply_route(lambda *argv:subprocess.check_output(argv,env=session.env,text=True,timeout=3),route)
             session.wait(lambda:next(s for s in session.json('list','sink-inputs') if s['index']==stream['index'])['sink']==target)
             after=session.json('list','sink-inputs')
@@ -58,3 +60,3 @@
             result=devices.change('audioRoute',dict(serverId=m['serverId'],streamId=m['streams'][0]['id'],sinkId=target['id']))
             self.assertEqual(result['state']['streams'][0]['sinkId'],target['id'])
-            self.assertNotEqual(result['state']['streams'][1]['sinkId'],target['id'])
+            self.assertEqual(result['state']['streams'][1]['sinkId'],m['streams'][1]['sinkId'])
--- a/tests/audio_session_fixture.py
+++ b/tests/audio_session_fixture.py
@@ -13,5 +13,5 @@
 class AudioSession:
     def __enter__(self):
-        self.tools={name:shutil.which(name) for name in ('pipewire','wireplumber','pactl','pacat','pw-dump')}
+        self.tools={name:shutil.which(name) for name in ('pipewire','wireplumber','pactl','pacat','pw-dump','pw-metadata')}
         if not all(self.tools.values()): raise unittest.SkipTest('private audio requires PipeWire, WirePlumber and pulseaudio-utils test tools')
         self.temp=tempfile.TemporaryDirectory(prefix='audio-session-');self.root=Path(self.temp.name)
```
