using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace AcrophobiaVR.EditorTools
{
    /// <summary>
    /// Play-mode course checks: drives the desktop rig with simulated keys (walk speed = VR stick speed, so a jump
    /// that works here works in a headset) from a start pose, then logs where the player ended up and whether they
    /// fell. Run from code: CourseTests.Run(CourseTests.Level1()). Results are logged as "[RA] TEST ...".
    /// </summary>
    public static class CourseTests
    {
        public struct Case
        {
            public string label;
            public Vector3 start;
            public float yaw;
            public float run;       // seconds holding W
            public float[] jumps;   // seconds at which Space is tapped
            public float total;     // seconds before reading the result
            public bool sprint;
            public float[] walk;    // optional (start, end) pairs replacing 'run'
            public float useAt;     // > 0: "click" every desktop-usable thing (zipline) at this second
        }

        static readonly Queue<Case> queue = new Queue<Case>();
        static Case current;
        static float t0;
        static int slips0;
        static bool running;
        static Key[] lastKeys;
        public static bool Trace;
        static float nextTrace;

        public static void Run(IEnumerable<Case> cases)
        {
            queue.Clear();
            foreach (var c in cases) queue.Enqueue(c);
            if (!running)
            {
                running = true;
                EditorApplication.update += Tick;
                Next();
            }
        }

        public static Case C(string label, Vector3 start, float yaw, float run, float total, params float[] jumps) =>
            new Case { label = label, start = start, yaw = yaw, run = run, total = total, jumps = jumps };

        public static Case W(string label, Vector3 start, float yaw, float[] walk, float total, params float[] jumps) =>
            new Case { label = label, start = start, yaw = yaw, walk = walk, total = total, jumps = jumps };

        public static List<Case> Level1() => new List<Case>
        {
            C("L1 gap1 cafe->B1", new Vector3(8.6f, 13.05f, 7f), 90f, 1.4f, 2.5f, 0.36f),
            C("L1 skylights run", new Vector3(16.8f, 12.4f, 7f), 90f, 3.3f, 4.2f),
            W("L1 swing: step on, ride, jump off", new Vector3(31.6f, 12.4f, 7f), 90f, new[] { 1.85f, 2.25f, 3.7f, 4.4f }, 5.5f, 3.78f),
            C("L1 ledge walk", new Vector3(39.8f, 12.9f, 0.45f), 90f, 4.0f, 4.6f),
            C("L1 drop B2->B3", new Vector3(53.2f, 12.9f, 0.45f), 90f, 1.2f, 3f, 0.2f),
            C("L1 planks run", new Vector3(62.5f, 11f, 7f), 90f, 2.2f, 3.2f),
            C("L1 vault walls", new Vector3(69f, 11f, 7f), 90f, 1.8f, 3.2f, 0.22f, 1.1f),
            C("L1 jump to fire escape", new Vector3(75.1f, 11f, 6.4f), 90f, 0.7f, 2.2f, 0.22f),
            C("L1 plank to the end", new Vector3(92f, 16f, 0.2f), 180f, 1.5f, 2.5f),
        };

        public static List<Case> Level3() => new List<Case>
        {
            C("L3 tightrope (gusts)", new Vector3(6.5f, 150f, 0f), 90f, 4.0f, 5f),
            new Case { label = "L3 zipline", start = new Vector3(22.6f, 150f, 0f), yaw = 90f, useAt = 0.3f, total = 5f },
            W("L3 cradle ride + glass bridge", new Vector3(56.8f, 147f, 0f), 90f, new[] { 0f, 0.5f, 7.0f, 11.5f }, 12f),
            C("L3 walk off the roof (must miss)", new Vector3(82.5f, 139f, 0f), 90f, 3f, 4f),
            C("L3 heli ladder jump", new Vector3(82.5f, 139f, 0f), 90f, 1.5f, 3f, 0.4f),
        };

        public static List<Case> Level2() => new List<Case>
        {
            C("L2 scaffold ladder", new Vector3(-5f, 0f, -3.3f), 0f, 4.4f, 5.5f),
            C("L2 walkway run (planks + debris)", new Vector3(-5.4f, 6f, -1.4f), 90f, 3.5f, 4.2f),
            W("L2 crane beam ride", new Vector3(7.1f, 6.05f, -1.4f), -90f, new[] { 11.6f, 12.4f }, 13.5f, 11.7f),
            C("L2 boom knocks a still player", new Vector3(3.5f, 12f, 4f), 0f, 0f, 7f),
            C("L2 slab ladder", new Vector3(-4.5f, 12f, 11.7f), 0f, 4.6f, 5.5f),
            C("L2 beam walk (gusts off)", new Vector3(-4.3f, 18f, 12f), 90f, 3.0f, 3.6f),
            W("L2 hook pallet ride", new Vector3(5.9f, 18f, 12f), 90f, new[] { 2.6f, 3.0f, 4.75f, 5.6f }, 6.5f, 4.8f),
            C("L2 tower ladder", new Vector3(16.6f, 18.3f, 13.7f), 0f, 6.6f, 7.5f),
            C("L2 jib scoop + ride", new Vector3(18.2f, 27.6f, 13.7f), 0f, 0f, 22f),
            W("L2 jib -> drop onto roof C (finish)", new Vector3(17.54f, 27.8f, 16.92f), 0f, new[] { 4.4f, 5.4f }, 7f),
            C("L2 roof C walk to helipad (finish)", new Vector3(22f, 26.6f, 25f), 0f, 1.4f, 3f),
        };

        static void Next()
        {
            if (queue.Count == 0)
            {
                Send();
                running = false;
                EditorApplication.update -= Tick;
                Debug.Log("[RA] TESTS DONE");
                return;
            }
            current = queue.Dequeue();
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            if (rig == null || lc == null) { Debug.Log("[RA] TEST abort: no rig / level"); queue.Clear(); Next(); return; }
            Hazard.ResetAll();
            lc.DevRefillLives();
            rig.TeleportTo(current.start, Quaternion.Euler(0f, current.yaw, 0f) * Vector3.forward);
            var dr = rig.Root.GetComponent<DesktopRig>();
            if (dr != null)
            {
                var bf = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
                typeof(DesktopRig).GetField("yaw", bf).SetValue(dr, current.yaw);
                typeof(DesktopRig).GetField("pitch", bf).SetValue(dr, 10f);
            }
            slips0 = lc.Slips;
            nextTrace = 0f;
            t0 = Time.time + 0.4f; // let the teleport settle
        }

        static void Send(params Key[] keys)
        {
            if (Keyboard.current == null) return;
            if (lastKeys != null && keys.Length == lastKeys.Length && System.Linq.Enumerable.SequenceEqual(keys, lastKeys)) return;
            lastKeys = keys;
            InputSystem.QueueStateEvent(Keyboard.current, new KeyboardState(keys));
        }

        static void Tick()
        {
            if (!EditorApplication.isPlaying) { running = false; EditorApplication.update -= Tick; return; }
            var lc = LevelController.Instance;
            float t = Time.time - t0;
            if (t < 0f) { Send(); return; }
            if (lc != null && lc.Finished && lc.IsRespawning)
            {
                Debug.Log("[RA] TEST game over - remaining tests skipped");
                queue.Clear();
                current.label = null;
                Next();
                return;
            }
            if (lc != null && lc.IsRespawning)
            {
                // Fell: report straight away and move on once the respawn is over.
                if (current.label != null)
                {
                    Debug.Log("[RA] TEST " + current.label + ": FELL at t=" + t.ToString("F2"));
                    current.label = null;
                }
                Send();
                return;
            }
            if (current.label == null) { Next(); return; }

            if (Trace && t >= nextTrace)
            {
                nextTrace = t + 0.25f;
                var r = PlayerRig.Instance;
                var g = r != null ? r.GroundCollider() : null;
                var board = GameObject.Find("SwingBoard");
                Debug.Log("[RA] TRACE t=" + t.ToString("F2") + " feet=" + new Vector3(r.Head.position.x, r.FeetY, r.Head.position.z).ToString("F2") +
                          " ground=" + (g ? g.name : "-") + (board ? " board=" + board.transform.position.ToString("F2") : ""));
            }
            var keys = new List<Key>();
            bool w = t < current.run;
            if (current.walk != null)
            {
                w = false;
                for (int i = 0; i + 1 < current.walk.Length; i += 2) if (t >= current.walk[i] && t < current.walk[i + 1]) w = true;
            }
            if (w) keys.Add(Key.W);
            if (current.useAt > 0f && t >= current.useAt)
            {
                current.useAt = 0f;
                foreach (var z in Object.FindObjectsByType<Zipline>(FindObjectsSortMode.None)) z.DesktopUse();
            }
            if (current.sprint && t < current.run) keys.Add(Key.LeftShift);
            if (current.jumps != null)
                foreach (float j in current.jumps)
                    if (t >= j && t < j + 0.08f) keys.Add(Key.Space);
            Send(keys.ToArray());

            if (t >= current.total)
            {
                var rig = PlayerRig.Instance;
                Vector3 p = rig != null ? new Vector3(rig.Head.position.x, rig.FeetY, rig.Head.position.z) : Vector3.zero;
                Debug.Log("[RA] TEST " + current.label + ": ok, ended at " + p.ToString("F2") + (lc != null && lc.Slips > slips0 ? " (slipped)" : "") + (lc != null && lc.Finished ? " (FINISHED)" : ""));
                current.label = null;
                Send();
                Next();
            }
        }
    }
}
