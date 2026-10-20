using UnityEngine;
using static AcrophobiaVR.EditorTools.BuildKit;

namespace AcrophobiaVR.EditorTools
{
    public static partial class LevelBuilder
    {
        /// <summary>
        /// LEVEL 3 - SKYLINE GAUNTLET (150 m). Tower A -> a 22 cm steel tightrope in side wind -> Tower M ->
        /// zipline down to Tower B -> a tilting window-washer cradle lowers you 8 m -> a glass bridge that shatters
        /// behind you -> Tower C -> run and jump for the rope ladder of a helicopter that won't wait.
        /// </summary>
        static LevelController BuildSkylineGauntlet(Transform env, Transform game, Material towerGlass, Material steel, Material steelDark, Material concrete, Material roofMat, Material plankMat)
        {
            const float HA = 150f, HB = 147f, HC = 139f;
            var sky = Group("SkylineCourse", env).transform;
            var cable = Mat("SteelCable", new Color(0.12f, 0.12f, 0.13f), 0.5f, 0.8f);
            var rope = Mat("Rope", new Color(0.62f, 0.52f, 0.33f), 0.15f);
            var bridgeGlass = Transparent("BridgeGlass", new Color(0.7f, 0.88f, 0.95f, 0.32f));

            void Tower(string name, float x0, float x1, float z0, float z1, float top)
            {
                Box(name, sky, new Vector3((x0 + x1) * 0.5f, (top - 0.3f) * 0.5f, (z0 + z1) * 0.5f), new Vector3(x1 - x0, top - 0.3f, z1 - z0), towerGlass);
                Floor(name + "Roof", sky, x0, x1, z0, z1, top, 0.3f, roofMat, false);
                for (int f = 1; f * 5f < top - 2f; f++)
                    Box(name + "Band", sky, new Vector3((x0 + x1) * 0.5f, f * 5f, (z0 + z1) * 0.5f), new Vector3(x1 - x0 + 0.1f, 0.3f, z1 - z0 + 0.1f), steelDark, false);
                Kerb(name + "KerbS", sky, new Vector3(x0, top, z0 + 0.05f), new Vector3(x1, top, z0 + 0.05f), concrete);
                Kerb(name + "KerbN", sky, new Vector3(x0, top, z1 - 0.05f), new Vector3(x1, top, z1 - 0.05f), concrete);
            }

            void Checkpoint(string label, Vector3 center, Vector3 size, Vector3 spawn, float yaw)
            {
                var cp = Zone<CheckpointZone>("CP " + label, game, center, size);
                cp.label = label;
                cp.respawnPoint = Point("CP " + label + " Spawn", game, spawn, yaw);
            }

            void Unit(string id, Vector3 pos, float yaw, float height)
            {
                var p = PolyProp(id, sky, pos, yaw, 1f, height);
                if (p != null) SolidBounds(p);
            }

            // ---- Tower A (start).
            Tower("TowerA", -8f, 8f, -8f, 8f, HA);
            Unit("exterior_aircon_unit", new Vector3(-4f, HA, -4.5f), 0f, 1.2f);
            Unit("exterior_aircon_unit", new Vector3(-4f, HA, 4.5f), 180f, 1.2f);
            Unit("utility_box_01", new Vector3(3f, HA, -6f), 0f, 1.1f);
            Unit("utility_box_01", new Vector3(5f, HA, 6f), 180f, 1.1f);

            // ---- 1. Tightrope: a 22 cm steel beam to Tower M, with side gusts.
            var ropeRoot = Group("Tightrope", game).transform;
            BoxMinMax("TightropeBeam", ropeRoot, new Vector3(7.9f, HA - 0.18f, -0.11f), new Vector3(18.1f, HA, 0.11f), steel, true, false);
            Bar("GuyCable", ropeRoot, new Vector3(8f, HA - 0.2f, 0f), new Vector3(13f, HA - 2.4f, 0f), 0.02f, cable, false, false);
            Bar("GuyCable", ropeRoot, new Vector3(13f, HA - 2.4f, 0f), new Vector3(18f, HA - 0.2f, 0f), 0.02f, cable, false, false);
            var tight = ropeRoot.gameObject.AddComponent<BalanceBeam>();
            tight.start = Point("Start", ropeRoot, new Vector3(8f, HA, 0f));
            tight.end = Point("End", ropeRoot, new Vector3(18f, HA, 0f));
            tight.walkableHalfWidth = 0.11f;
            tight.gusts = true;
            tight.gustInterval = new Vector2(4f, 7f);
            tight.gustWarning = 1.6f;
            tight.gustDuration = 1.8f;
            Zone<SayZone>("RopeHint", game, new Vector3(6.5f, HA + 1.2f, 0f), new Vector3(2f, 2.4f, 3f)).line = "Twenty-two centimetres of steel. Gust coming? Crouch on it. Don't stop for long.";
            Star(game, new Vector3(13f, HA + 1.3f, 0.5f));

            // ---- 2. Tower M: zipline down to Tower B.
            Tower("TowerM", 18f, 24f, -3f, 3f, HA);
            Checkpoint("Tower M", new Vector3(20f, HA + 1.2f, 0f), new Vector3(3f, 2.4f, 4f), new Vector3(19.2f, HA, 0f), 90f);
            Bar("GantryL", sky, new Vector3(23.3f, HA, -0.8f), new Vector3(23.3f, HA + 2.4f, -0.8f), 0.1f, steelDark, true, true);
            Bar("GantryR", sky, new Vector3(23.3f, HA, 0.8f), new Vector3(23.3f, HA + 2.4f, 0.8f), 0.1f, steelDark, true, true);
            Bar("GantryTop", sky, new Vector3(23.3f, HA + 2.4f, -0.8f), new Vector3(23.3f, HA + 2.4f, 0.8f), 0.1f, steelDark, false, true);
            Vector3 zipStart = new Vector3(23.3f, HA + 2.0f, 0f), zipEnd = new Vector3(44.5f, HB + 2.05f, 0f);
            Bar("ZipCable", sky, zipStart + Vector3.up * 0.12f, zipEnd + Vector3.up * 0.12f, 0.025f, cable, false, true);
            var zipRoot = Group("Zipline", game).transform;
            var handle = Group("Handle", zipRoot).transform;
            handle.position = zipStart;
            Bar("Grip", handle, new Vector3(0f, 0f, -0.3f), new Vector3(0f, 0f, 0.3f), 0.05f, Mat("GripBlack", new Color(0.05f, 0.05f, 0.05f), 0.3f), true, false);
            Bar("Trolley", handle, Vector3.zero, new Vector3(0f, 0.12f, 0f), 0.04f, steelDark, false, false);
            var zip = zipRoot.gameObject.AddComponent<Zipline>();
            zip.handle = handle;
            zip.end = zipEnd;
            Zone<SayZone>("ZipHint", game, new Vector3(22f, HA + 1.2f, 0f), new Vector3(2f, 2.4f, 3f)).line = "Reach up and grab the zipline handle. One go per life!";
            // Bonus star: climb the aircon unit, then jump for it.
            Unit("exterior_aircon_unit", new Vector3(21f, HA, 2.2f), 180f, 1.2f);
            Star(game, new Vector3(21f, HA + 2.9f, 2.2f));

            // ---- 3. Tower B and the window-washer cradle on its east face.
            Tower("TowerB", 42f, 58f, -8f, 8f, HB);
            Checkpoint("Tower B", new Vector3(45f, HB + 1.2f, 0f), new Vector3(3f, 2.4f, 5f), new Vector3(44.6f, HB, 0f), 90f);
            Unit("exterior_aircon_unit", new Vector3(48f, HB, 5f), 180f, 1.2f);
            Unit("exterior_aircon_unit", new Vector3(51f, HB, 5f), 180f, 1.2f);
            Unit("exterior_aircon_unit", new Vector3(49.5f, HB, -5f), 0f, 1.2f);
            Unit("utility_box_01", new Vector3(54f, HB, -6.2f), 0f, 1.1f);
            // Deck x 58.05..59.15 (flush with the roof edge at 58); it rides two guide cables from the davit down to the bridge.
            const float CX = 58.6f;
            var cradle = Group("Cradle", game).transform;
            cradle.position = new Vector3(CX, HB - 0.05f, 0f);
            var down = cradle.gameObject.AddComponent<PathMover>();
            down.points = new[] { Vector3.zero, new Vector3(0f, -(HB - HC), 0f) };
            down.speed = 1.6f;
            down.pauseAtPoints = 2.2f;
            down.startDelay = 2f;
            var tilt = Group("Tilt", cradle).transform;
            var wob = tilt.gameObject.AddComponent<Pendulum>();
            wob.axis = Vector3.forward;
            wob.amplitude = 5f;
            wob.period = 2.6f;
            var deck = Box("CradleDeck", tilt, Vector3.zero, new Vector3(1.1f, 0.1f, 3.2f), Mat("Grate", new Color(0.35f, 0.37f, 0.4f), 0.5f, 0.7f), true, false);
            deck.AddComponent<Carrier>();
            // Outer rail with a gap in the middle: that's the way out onto the glass bridge at the bottom.
            Railing("CradleRailOutS", tilt, new Vector3(0.55f, 0.05f, -1.6f), new Vector3(0.55f, 0.05f, -0.75f), 1.0f, steel, true, 0.85f);
            Railing("CradleRailOutN", tilt, new Vector3(0.55f, 0.05f, 0.75f), new Vector3(0.55f, 0.05f, 1.6f), 1.0f, steel, true, 0.85f);
            Railing("CradleRailEndS", tilt, new Vector3(-0.55f, 0.05f, -1.6f), new Vector3(0.55f, 0.05f, -1.6f), 1.0f, steel, true, 1.1f);
            Railing("CradleRailEndN", tilt, new Vector3(-0.55f, 0.05f, 1.6f), new Vector3(0.55f, 0.05f, 1.6f), 1.0f, steel, true, 1.1f);
            foreach (float z in new[] { -1.5f, 1.5f })
            {
                Bar("CradleCable", sky, new Vector3(CX, HB + 3.2f, z), new Vector3(CX, HC - 0.3f, z), 0.02f, cable, false, true);
                Bar("Davit", sky, new Vector3(56.5f, HB + 3.2f, z), new Vector3(CX + 0.1f, HB + 3.2f, z), 0.14f, steelDark, false, true);
                Bar("DavitPost", sky, new Vector3(56.5f, HB, z), new Vector3(56.5f, HB + 3.3f, z), 0.14f, steelDark, true, true);
            }
            Zone<SayZone>("CradleHint", game, new Vector3(56.5f, HB + 1.2f, 0f), new Vector3(2f, 2.4f, 4f)).line = "Window-washer cradle. Step in, ride it down eight metres, then sprint across the glass!";

            // ---- 4. Glass bridge to Tower C: every pane cracks and shatters a moment after you step on it.
            var bridge = Group("GlassBridge", game).transform;
            const int panes = 10;
            float bx0 = 59.15f, bx1 = 72f, paneLen = (bx1 - bx0) / panes;
            for (int i = 0; i < panes; i++)
            {
                var pane = Box("BridgePane" + i, bridge, new Vector3(bx0 + (i + 0.5f) * paneLen, HC - 0.04f, 0f), new Vector3(paneLen - 0.04f, 0.08f, 1.2f), bridgeGlass, true, false);
                var cp = pane.AddComponent<CollapsingPlatform>();
                cp.shatter = true;
                cp.delay = 0.55f;
            }
            foreach (float z in new[] { -0.65f, 0.65f })
                Bar("BridgeRail", sky, new Vector3(bx0, HC - 0.06f, z), new Vector3(bx1, HC - 0.06f, z), 0.06f, steel, false, true);
            Star(game, new Vector3(66f, HC + 1.4f, 0.95f));

            // ---- 5. Tower C and the helicopter finale.
            Tower("TowerC", 72f, 84f, -6f, 6f, HC);
            Checkpoint("Tower C", new Vector3(74f, HC + 1.2f, 0f), new Vector3(3f, 2.4f, 6f), new Vector3(73.5f, HC, 0f), 90f);
            Unit("exterior_aircon_unit", new Vector3(79f, HC, -4.6f), 0f, 1.2f);
            Unit("utility_box_01", new Vector3(80f, HC, 5f), 180f, 1.1f);
            var heliRoot = Group("RescueHelicopter", game).transform;
            // Ladder at x 87 (zone x 86.2..87.8, 1.9 m out from the roof edge): walking off falls short, a running jump makes it.
            heliRoot.position = new Vector3(88f, HC + 5f, 0f);
            var bob = heliRoot.gameObject.AddComponent<PathMover>();
            bob.points = new[] { Vector3.zero, new Vector3(0f, 1.4f, 0f), new Vector3(0.6f, 0.6f, 0f) };
            bob.speed = 0.7f;
            bob.pauseAtPoints = 0.3f;
            bob.fixedSpeed = true;
            var heliBody = Group("Body", heliRoot).transform;
            BuildHelicopter(heliBody);
            heliRoot.gameObject.AddComponent<SoundEmitter>().kind = EmitterKind.Rotor;
            // Rope ladder hanging on the tower side of the cabin.
            var ladderTop = new Vector3(-1.0f, -1.3f, 0f);
            foreach (float z in new[] { -0.25f, 0.25f })
                Bar("LadderRope", heliRoot, ladderTop + new Vector3(0f, 0f, z), ladderTop + new Vector3(0f, -4.2f, z), 0.025f, rope, false, false);
            for (int i = 1; i <= 13; i++)
                Bar("LadderRung", heliRoot, ladderTop + new Vector3(0f, -i * 0.3f, -0.25f), ladderTop + new Vector3(0f, -i * 0.3f, 0.25f), 0.03f, plankMat, false, false);
            var catchHeli = Zone<HeliLadderCatch>("CatchLadder (Goal)", heliRoot, new Vector3(-1.0f, -3.0f, 0f), new Vector3(1.6f, 3.0f, 1.6f));
            catchHeli.description = "Jump for the helicopter's rope ladder";
            catchHeli.heli = heliRoot;
            catchHeli.ladderLocal = new Vector3(-1.0f, 0f, 0f);
            catchHeli.rungRange = new Vector2(-1.3f - 3.9f, -1.6f);
            var wash = Group("RotorWash", game).AddComponent<GustZone>();
            wash.transform.position = new Vector3(80f, HC + 1.5f, 0f);
            wash.size = new Vector3(8f, 4f, 12f);
            wash.pushDirection = Vector3.forward;
            wash.randomSide = true;
            wash.interval = new Vector2(2.5f, 4.5f);
            wash.warning = 1.0f;
            wash.pushSpeed = 0.8f;
            Zone<SayZone>("HeliHint", game, new Vector3(77f, HC + 1.2f, 0f), new Vector3(2f, 2.4f, 6f)).line = "There's our ride! Full sprint, jump off the edge and grab that ladder!";

            var show = Group("FireworksShow", game).AddComponent<FireworksShow>();
            show.transform.position = new Vector3(78f, HC, 45f);
            show.area = 40f;
            show.height = 35f;

            var lc = CommonLevel(2, GameManager.LevelTitles[2], new Vector3(0f, HA, 0f), 90f, 0f, 160f, 0.35f);
            lc.GetComponent<FallGuard>().killY = HC - 9f;
            lc.objectives = new Objective[] { catchHeli };
            lc.finaleSeconds = 6f;
            UnityEditor.Events.UnityEventTools.AddPersistentListener(lc.onFinale, show.Play);
            lc.timeLimit = 150f;
            lc.goldTime = 70f;
            lc.silverTime = 90f;
            lc.bronzeTime = 115f;
            return lc;
        }

        /// <summary>Gemini-made helicopter (Body + spinning MainRotor / TailRotor); primitive fallback if missing.</summary>
        static void BuildHelicopter(Transform heliBody)
        {
            var heliModel = Model("Helicopter", heliBody, new Vector3(0f, -1.3f, 0f), 3.3f);
            if (heliModel != null)
            {
                foreach (var part in heliModel.GetComponentsInChildren<Transform>(true))
                {
                    if (part.name != "MainRotor" && part.name != "TailRotor") continue;
                    Vector3 want = part.name == "MainRotor" ? Vector3.up : heliBody.right;
                    Vector3 local = part.InverseTransformDirection(want);
                    Vector3 axis = Mathf.Abs(local.x) > Mathf.Abs(local.y) && Mathf.Abs(local.x) > Mathf.Abs(local.z) ? Vector3.right
                        : (Mathf.Abs(local.y) > Mathf.Abs(local.z) ? Vector3.up : Vector3.forward);
                    part.gameObject.AddComponent<Spinner>().degreesPerSecond = axis * (part.name == "MainRotor" ? 1100f : 1600f);
                }
                return;
            }
            var heliRed = Mat("HeliRed", new Color(0.75f, 0.12f, 0.1f), 0.7f, 0.3f);
            var heliDark = Mat("HeliDark", new Color(0.08f, 0.08f, 0.09f), 0.5f, 0.6f);
            Prim(PrimitiveType.Capsule, "Cabin", heliBody, Vector3.zero, new Vector3(1.7f, 1.9f, 1.7f), heliRed, false, false, new Vector3(90f, 0f, 0f));
            Box("TailBoom", heliBody, new Vector3(0f, 0.35f, -3.4f), new Vector3(0.35f, 0.35f, 4.2f), heliRed, false, false);
            var mainRotor = Group("MainRotor", heliBody).transform;
            mainRotor.localPosition = new Vector3(0f, 1.15f, 0.2f);
            Box("BladeA", mainRotor, Vector3.zero, new Vector3(10f, 0.04f, 0.32f), heliDark, false, false);
            Box("BladeB", mainRotor, Vector3.zero, new Vector3(0.32f, 0.04f, 10f), heliDark, false, false);
            mainRotor.gameObject.AddComponent<Spinner>().degreesPerSecond = new Vector3(0f, 1100f, 0f);
        }
    }
}
