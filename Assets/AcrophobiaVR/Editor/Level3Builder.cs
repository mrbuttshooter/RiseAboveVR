using UnityEngine;
using static AcrophobiaVR.EditorTools.BuildKit;

namespace AcrophobiaVR.EditorTools
{
    public static partial class LevelBuilder
    {
        // ------------------------------------------------------------------ LEVEL 3: SKYSCRAPER BEAM (150 m)
        static void BuildLevel3()
        {
            var scene = NewScene();
            Atmosphere(Sky("SkyGolden", new Color(0.78f, 0.56f, 0.5f), new Color(0.3f, 0.28f, 0.3f), 0.07f, 1.15f, 1.35f),
                new Color(0.78f, 0.77f, 0.8f), new Color(0.9f, 0.7f, 0.6f));
            // 150 m up you see kilometres of city: thinner, cooler aerial haze so distant towers keep their own colours.
            RenderSettings.fogDensity = 0.0014f;
            // Golden hour, but a real one: warm, not orange (the old 1 / 0.68 / 0.42 painted the whole city peach).
            Sun(new Vector3(6, -70, 0), new Color(1f, 0.8f, 0.62f), 1.25f);

            const float H = 150f;
            var env = Group("Environment").transform;
            var game = Group("Gameplay").transform;

            var concrete = Mat("Concrete", new Color(0.7f, 0.7f, 0.68f));
            var roofMat = Mat("RoofGrey", new Color(0.5f, 0.52f, 0.55f));
            var steel = Mat("SteelRed", new Color(0.65f, 0.2f, 0.15f), 0.4f, 0.6f);
            var steelDark = Mat("SteelDark", new Color(0.2f, 0.22f, 0.25f), 0.5f, 0.8f);
            var rope = Mat("Rope", new Color(0.85f, 0.75f, 0.45f));
            var plankMat = Mat("Plank", new Color(0.72f, 0.55f, 0.32f));
            var tileMat = Mat("Tile", new Color(0.55f, 0.55f, 0.58f), 0.3f, 0.5f);
            var netMat = Transparent("SafetyNet", new Color(1f, 0.55f, 0.15f, 0.35f));
            var glass = Transparent("SafetyGlass", new Color(0.75f, 0.9f, 1f, 0.22f));
            var towerGlass = Mat("Glass Tower", new Color(0.45f, 0.6f, 0.75f), 0.85f, 0.4f);
            var windowGlow = Glow("WindowWarm", new Color(1f, 0.8f, 0.5f), 1.5f);
            Material[] palette =
            {
                // A downtown skyline is mostly glass and dark curtain walls, with some stone / brick / office blocks.
                towerGlass, Mat("Bldg1", new Color(0.70f, 0.46f, 0.38f)), Mat("Bldg2", new Color(0.86f, 0.82f, 0.74f)),
                Mat("Bldg4", new Color(0.48f, 0.36f, 0.32f)), Mat("TowerDark", new Color(0.3f, 0.33f, 0.4f), 0.8f, 0.3f),
                towerGlass, Mat("TowerDark", new Color(0.3f, 0.33f, 0.4f), 0.8f, 0.3f), Mat("Bldg3", new Color(0.74f, 0.75f, 0.77f)),
            };

            // Ground, streets, cars far below
            Ground(env, 600f, Mat("Pavement", new Color(0.62f, 0.6f, 0.58f)));
            var asphalt = Mat("Asphalt", new Color(0.18f, 0.18f, 0.2f), 0.2f);
            for (int i = -6; i <= 6; i++)
            {
                Box("RoadX", env, new Vector3(0, 0.02f, i * 40f + 20f), new Vector3(1200, 0.02f, 10), asphalt, false);
                Box("RoadZ", env, new Vector3(i * 40f + 20f, 0.02f, 0), new Vector3(10, 0.02f, 1200), asphalt, false);
            }
            var carGlass = Mat("CarGlass", new Color(0.2f, 0.25f, 0.3f), 0.9f);
            var carColors = new[] { new Color(0.8f, 0.2f, 0.2f), new Color(0.2f, 0.4f, 0.8f), new Color(0.95f, 0.85f, 0.3f), new Color(0.9f, 0.9f, 0.92f) };
            for (int r = 0; r < 3; r++)
            {
                float z = -20f + r * 40f;
                var loop = new[] { new Vector3(-300, 0, z + 2), new Vector3(300, 0, z + 2), new Vector3(300, 0, z - 2), new Vector3(-300, 0, z - 2) };
                for (int i = 0; i < 8; i++) Car(env, loop, i / 8f, 9f + i % 3, Mat("Car" + (i % 4), carColors[i % 4], 0.7f, 0.4f), carGlass);
            }
            City(env, new Vector2(25, 0), 8, 40f, new Vector2(30, 230), new Rect(-30, -30, 110, 60), 303, palette, windowGlow, 0f, 200f);

            // Tower A (start) and Tower B (cat + fireworks)
            var towers = Group("Towers", env).transform;
            Box("TowerA", towers, new Vector3(0, H * 0.5f - 0.15f, 0), new Vector3(16, H - 0.3f, 16), towerGlass);
            Floor("RoofA", towers, -8f, 8f, -8f, 8f, H, 0.3f, roofMat, true);
            Box("TowerB", towers, new Vector3(50, H * 0.5f - 0.15f, 0), new Vector3(16, H - 0.3f, 16), towerGlass);
            Floor("RoofB", towers, 42f, 58f, -8f, 8f, H, 0.3f, roofMat, true);
            for (int f = 1; f < 30; f++)
            {
                Box("BandA", towers, new Vector3(0, f * 5f, 0), new Vector3(16.1f, 0.3f, 16.1f), steelDark, false);
                Box("BandB", towers, new Vector3(50, f * 5f, 0), new Vector3(16.1f, 0.3f, 16.1f), steelDark, false);
            }
            foreach (var cx in new[] { 0f, 50f })
            {
                // Parapets with gaps where the crossings start (Easy only - otherwise just a kerb and 150 m of air)
                ShowIn(Box("ParapetS", towers, new Vector3(cx, H + 0.25f, -8f), new Vector3(16f, 0.5f, 0.3f), concrete), true, false, false);
                ShowIn(Box("ParapetN1", towers, new Vector3(cx - 4.5f, H + 0.25f, 8f), new Vector3(7f, 0.5f, 0.3f), concrete), true, false, false);
                ShowIn(Box("ParapetN2", towers, new Vector3(cx + 4.5f, H + 0.25f, 8f), new Vector3(7f, 0.5f, 0.3f), concrete), true, false, false);
                Kerb("KerbS", towers, new Vector3(cx - 8f, H, -7.95f), new Vector3(cx + 8f, H, -7.95f), concrete);
                Kerb("KerbN", towers, new Vector3(cx - 8f, H, 7.95f), new Vector3(cx + 8f, H, 7.95f), concrete);
                Kerb("KerbW", towers, new Vector3(cx - 7.95f, H, -8f), new Vector3(cx - 7.95f, H, 8f), concrete);
                Kerb("KerbE", towers, new Vector3(cx + 7.95f, H, -8f), new Vector3(cx + 7.95f, H, 8f), concrete);
            }
            ShowIn(Box("ParapetA_W", towers, new Vector3(-8f, H + 0.25f, 0), new Vector3(0.3f, 0.5f, 16f), concrete), true, false, false);
            ShowIn(Box("ParapetA_E1", towers, new Vector3(8f, H + 0.25f, -4.5f), new Vector3(0.3f, 0.5f, 7f), concrete), true, false, false);
            ShowIn(Box("ParapetA_E2", towers, new Vector3(8f, H + 0.25f, 4.5f), new Vector3(0.3f, 0.5f, 7f), concrete), true, false, false);
            ShowIn(Box("ParapetB_E", towers, new Vector3(58f, H + 0.25f, 0), new Vector3(0.3f, 0.5f, 16f), concrete), true, false, false);
            ShowIn(Box("ParapetB_W1", towers, new Vector3(42f, H + 0.25f, -4.5f), new Vector3(0.3f, 0.5f, 7f), concrete), true, false, false);
            ShowIn(Box("ParapetB_W2", towers, new Vector3(42f, H + 0.25f, 4.5f), new Vector3(0.3f, 0.5f, 7f), concrete), true, false, false);
            // Gentle-mode glass fence around both roofs
            SafetyGlass("FenceA_S", towers, new Vector3(-8, H, -8), new Vector3(8, H, -8), 1.3f, glass);
            SafetyGlass("FenceA_W", towers, new Vector3(-8, H, -8), new Vector3(-8, H, 8), 1.3f, glass);
            SafetyGlass("FenceB_E", towers, new Vector3(58, H, -8), new Vector3(58, H, 8), 1.3f, glass);
            SafetyGlass("FenceB_S", towers, new Vector3(42, H, -8), new Vector3(58, H, -8), 1.3f, glass);
            // Rooftop props
            // Photo-scanned AC units (CC0 Poly Haven) with solid colliders; boxes as a fallback.
            var ac1 = PolyProp("exterior_aircon_unit", towers, new Vector3(-4f, H, -4f), 0f, 1.3f, 0f, 1);
            if (ac1 != null)
            {
                SolidBounds(ac1);
                SolidBounds(PolyProp("exterior_aircon_unit", towers, new Vector3(-4f, H, 3f), 180f, 1.3f));
            }
            else
            {
                Box("ACUnit", towers, new Vector3(-4, H + 0.6f, -4), new Vector3(2.4f, 1.2f, 1.6f), steelDark);
                Box("ACUnit2", towers, new Vector3(-4, H + 0.6f, 3), new Vector3(2.4f, 1.2f, 1.6f), steelDark);
            }
            Cyl("WaterTank", towers, new Vector3(-5, H, 6), 1.2f, 2.5f, Mat("TankWood", new Color(0.55f, 0.35f, 0.2f)));
            Bar("Antenna", towers, new Vector3(-6.5f, H, -6.5f), new Vector3(-6.5f, H + 12f, -6.5f), 0.15f, steelDark);
            Sphere("AntennaLight", towers, new Vector3(-6.5f, H + 12.2f, -6.5f), 0.35f, Glow("BeaconRed", new Color(1f, 0.2f, 0.15f), 4f));
            Cyl("Helipad", towers, new Vector3(50, H + 0.01f, -1.5f), 3f, 0.02f, Glow("HelipadGlow", new Color(0.3f, 1f, 0.5f), 0.8f), false);
            Box("HelipadH1", towers, new Vector3(49.2f, H + 0.03f, -1.5f), new Vector3(0.3f, 0.02f, 2.2f), Mat("PoleWhite", Color.white), false);
            Box("HelipadH2", towers, new Vector3(50.8f, H + 0.03f, -1.5f), new Vector3(0.3f, 0.02f, 2.2f), Mat("PoleWhite", Color.white), false);
            Box("HelipadH3", towers, new Vector3(50f, H + 0.03f, -1.5f), new Vector3(1.6f, 0.02f, 0.3f), Mat("PoleWhite", Color.white), false);

            // Section 1: steel beam A -> window-cleaning cradle (variants by exposure mode)
            BuildBeam(game, "Beam Gentle", 0.6f, steel, rope, netMat, true, false, false, 2, true);
            BuildBeam(game, "Beam Standard", 0.36f, steel, rope, netMat, false, true, false, 0, false);
            BuildBeam(game, "Beam Brave", 0.3f, steel, rope, netMat, false, false, true, 0, false);

            var cradle = Group("WindowCradle", env).transform;
            Floor("CradleDeck", cradle, 20f, 23f, -1.5f, 1.5f, H, 0.12f, Mat("Grate", new Color(0.35f, 0.37f, 0.4f), 0.5f, 0.7f), true);
            Railing("CradleRailN", cradle, new Vector3(20f, H, 1.5f), new Vector3(23f, H, 1.5f), 1.05f, steelDark);
            Railing("CradleRailS", cradle, new Vector3(20f, H, -1.5f), new Vector3(23f, H, -1.5f), 1.05f, steelDark);
            foreach (var x in new[] { 20.1f, 22.9f })
                Bar("CradleCable", cradle, new Vector3(x, H + 1.05f, 0), new Vector3(x, H + 30f, 0), 0.04f, Mat("Cable", new Color(0.15f, 0.15f, 0.15f), 0.6f, 0.8f), false);
            var cpCradle = Zone<CheckpointZone>("CP Cradle", game, new Vector3(21.5f, H + 1.2f, 0), new Vector3(2.8f, 2.4f, 2.8f));
            cpCradle.label = "Window cradle";
            cpCradle.respawnPoint = Point("CP Cradle Spawn", game, new Vector3(21.2f, H, 0), 90f);
            cpCradle.companionLine = "Halfway! Checkpoint saved. Next up: tiles that crumble under your feet.";
            var reachCradle = Zone<ReachObjective>("ReachCradle", game, new Vector3(21.5f, H + 1.2f, 0), new Vector3(2.8f, 2.4f, 2.8f));
            reachCradle.description = "Cross the steel beam to the window cradle";

            // Section 2: crumbling tiles
            var tiles = Group("CrumblingWalkway", game).transform;
            Bar("GirderN", tiles, new Vector3(23f, H - 0.25f, 0.5f), new Vector3(29.6f, H - 0.25f, 0.5f), 0.12f, steelDark, false, true);
            Bar("GirderS", tiles, new Vector3(23f, H - 0.25f, -0.5f), new Vector3(29.6f, H - 0.25f, -0.5f), 0.12f, steelDark, false, true);
            for (int i = 0; i < 6; i++)
            {
                var tile = Box("Tile" + i, tiles, new Vector3(23.55f + i * 1.1f, H - 0.06f, 0), new Vector3(1.0f, 0.12f, 0.9f), tileMat, true, false);
                tile.AddComponent<CrumblingTile>().delay = 1.2f;
            }
            var tileNet = Box("TileNet", tiles, new Vector3(26.3f, H - 3f, 0), new Vector3(7f, 0.02f, 4f), netMat, false, false);
            ShowIn(tileNet, true, false, false);
            Zone<SayZone>("TilesHint", game, new Vector3(22.6f, H + 1.2f, 0), new Vector3(0.8f, 2.4f, 2.8f)).line =
                "Careful - these tiles are loose! They'll fall a moment after you step on them. Keep moving and don't stop.";

            // Section 3: rope bridge
            var bridge = Group("RopeBridge", game).transform;
            const float bx0 = 29.7f, bx1 = 42f;
            int planks = 28;
            for (int i = 0; i < planks; i++)
            {
                float t = (i + 0.5f) / planks;
                float x = Mathf.Lerp(bx0, bx1, t);
                float y = H - Mathf.Sin(t * Mathf.PI) * 0.55f;
                bool broken = i == 7 || i == 13 || i == 19 || i == 23;
                var p = Box("Plank", bridge, new Vector3(x, y - 0.03f, 0), new Vector3(0.36f, 0.06f, 0.95f), plankMat, true, false);
                if (broken)
                {
                    // On Normal / Hard this plank has snapped in half - only the left half is left to step on.
                    ShowIn(p, true, false, false);
                    var half = Box("BrokenPlank", bridge, new Vector3(x, y - 0.03f, -0.235f), new Vector3(0.36f, 0.06f, 0.48f), plankMat, true, false);
                    half.transform.localRotation = Quaternion.Euler(0f, 0f, 4f);
                    ShowIn(half, false, true, true);
                    var halfSpin = half.AddComponent<Spinner>();
                    halfSpin.oscillate = true;
                    halfSpin.degreesPerSecond = new Vector3(100f, 0, 0);
                    halfSpin.oscillateAmplitude = 4f;
                }
                var sp = p.AddComponent<Spinner>();
                sp.oscillate = true;
                sp.degreesPerSecond = new Vector3(100f, 0, 0);
                sp.oscillateAmplitude = 1.5f + Mathf.Sin(t * Mathf.PI) * 3f;
            }
            for (int side = -1; side <= 1; side += 2)
            {
                Vector3 prev = new Vector3(bx0, H + 1f, side * 0.55f);
                for (int s = 1; s <= 12; s++)
                {
                    float t = s / 12f;
                    Vector3 cur = new Vector3(Mathf.Lerp(bx0, bx1, t), H + 1f - Mathf.Sin(t * Mathf.PI) * 0.45f, side * 0.55f);
                    // The right-hand rope has snapped on Normal; on Hard both are gone.
                    ShowIn(Bar("HandRope", bridge, prev, cur, 0.035f, rope, false, false), true, side < 0, false);
                    prev = cur;
                }
                Bar("Post", bridge, new Vector3(bx0, H, side * 0.55f), new Vector3(bx0, H + 1.1f, side * 0.55f), 0.1f, steelDark);
                Bar("Post", bridge, new Vector3(bx1, H, side * 0.55f), new Vector3(bx1, H + 1.1f, side * 0.55f), 0.1f, steelDark);
            }
            var bridgeBeam = bridge.gameObject.AddComponent<BalanceBeam>();
            bridgeBeam.start = Point("Start", bridge, new Vector3(bx0, H, 0));
            bridgeBeam.end = Point("End", bridge, new Vector3(bx1, H, 0));
            bridgeBeam.walkableHalfWidth = 0.45f;
            bridgeBeam.heightAbove = 3f;
            bridgeBeam.gusts = true;
            bridgeBeam.gustFillRate = 0.45f;
            var reachB = Zone<ReachObjective>("ReachTowerB", game, new Vector3(45f, H + 1.2f, 0), new Vector3(4f, 2.4f, 6f));
            reachB.description = "Cross the loose tiles and rope bridge to Tower B";
            reachB.companionLineOnComplete = "You made it across! Solid roof under your feet again.";
            var cpB = Zone<CheckpointZone>("CP TowerB", game, new Vector3(46f, H + 1.2f, 0), new Vector3(6f, 2.4f, 10f));
            cpB.label = "Tower B roof";
            cpB.respawnPoint = Point("CP TowerB Spawn", game, new Vector3(45f, H, 0), 90f);

            // A helicopter thunders past while you're in the middle of the rope bridge - crouch for the downdraft!
            var heli = Group("Helicopter", env);
            var heliBody = Group("Body", heli.transform).transform;
            // Gemini-made helicopter (Body + separately spinning MainRotor / TailRotor); primitive fallback if missing.
            var heliModel = Model("Helicopter", heliBody, new Vector3(0f, -1.3f, 0f), 3.3f);
            if (heliModel != null)
            {
                foreach (var part in heliModel.GetComponentsInChildren<Transform>(true))
                {
                    if (part.name != "MainRotor" && part.name != "TailRotor") continue;
                    // Spin about whichever local axis points up (main rotor) or sideways (tail rotor) after import.
                    Vector3 want = part.name == "MainRotor" ? Vector3.up : heliBody.right;
                    Vector3 local = part.InverseTransformDirection(want);
                    Vector3 axis = Mathf.Abs(local.x) > Mathf.Abs(local.y) && Mathf.Abs(local.x) > Mathf.Abs(local.z) ? Vector3.right
                        : (Mathf.Abs(local.y) > Mathf.Abs(local.z) ? Vector3.up : Vector3.forward);
                    part.gameObject.AddComponent<Spinner>().degreesPerSecond = axis * (part.name == "MainRotor" ? 1100f : 1600f);
                }
            }
            else
            {
                var heliRed = Mat("HeliRed", new Color(0.75f, 0.12f, 0.1f), 0.7f, 0.3f);
                var heliDark = Mat("HeliDark", new Color(0.08f, 0.08f, 0.09f), 0.5f, 0.6f);
                Prim(PrimitiveType.Capsule, "Cabin", heliBody, Vector3.zero, new Vector3(1.7f, 1.9f, 1.7f), heliRed, false, false, new Vector3(90f, 0f, 0f));
                Sphere("Canopy", heliBody, new Vector3(0f, 0.15f, 1.35f), 1.5f, Mat("HeliGlass", new Color(0.15f, 0.22f, 0.3f), 0.95f, 0.2f), false, false);
                Box("TailBoom", heliBody, new Vector3(0f, 0.35f, -3.4f), new Vector3(0.35f, 0.35f, 4.2f), heliRed, false, false);
                Box("TailFin", heliBody, new Vector3(0f, 1.0f, -5.35f), new Vector3(0.12f, 1.3f, 0.8f), heliRed, false, false);
                foreach (var sx in new[] { -0.85f, 0.85f })
                {
                    Box("Skid", heliBody, new Vector3(sx, -1.25f, 0.2f), new Vector3(0.09f, 0.09f, 3.4f), heliDark, false, false);
                    Bar("Strut", heliBody, new Vector3(sx, -1.25f, 0.9f), new Vector3(sx * 0.6f, -0.7f, 0.9f), 0.07f, heliDark, false, false);
                    Bar("Strut", heliBody, new Vector3(sx, -1.25f, -0.5f), new Vector3(sx * 0.6f, -0.7f, -0.5f), 0.07f, heliDark, false, false);
                }
                var mainRotor = Group("MainRotor", heliBody).transform;
                mainRotor.localPosition = new Vector3(0f, 1.15f, 0.2f);
                Cyl("Hub", mainRotor, new Vector3(0f, -0.15f, 0f), 0.18f, 0.3f, heliDark, false, false);
                Box("BladeA", mainRotor, Vector3.zero, new Vector3(10f, 0.04f, 0.32f), heliDark, false, false);
                Box("BladeB", mainRotor, Vector3.zero, new Vector3(0.32f, 0.04f, 10f), heliDark, false, false);
                mainRotor.gameObject.AddComponent<Spinner>().degreesPerSecond = new Vector3(0f, 1100f, 0f);
                var tailRotor = Group("TailRotor", heliBody).transform;
                tailRotor.localPosition = new Vector3(0.12f, 1.0f, -5.5f);
                Box("TailBlade", tailRotor, Vector3.zero, new Vector3(0.04f, 1.5f, 0.14f), heliDark, false, false);
                tailRotor.gameObject.AddComponent<Spinner>().degreesPerSecond = new Vector3(1600f, 0f, 0f);
            }
            Sphere("Beacon", heliBody, new Vector3(0f, 0.95f, -1.6f), 0.18f, Glow("BeaconRed", new Color(1f, 0.2f, 0.15f), 4f), false, false);
            var heliEngine = Group("Engine", heliBody).AddComponent<SoundEmitter>();
            heliEngine.kind = EmitterKind.Rotor;
            heliEngine.volume = 1f;
            var flyBy = heli.AddComponent<FlyBy>();
            flyBy.path = new[]
            {
                new Vector3(-60f, H + 30f, -90f),
                new Vector3(25f, H + 9f, -16f),
                new Vector3(46f, H + 11f, 16f),
                new Vector3(140f, H + 40f, 110f),
            };
            flyBy.triggerPoint = new Vector3(35f, H + 1.3f, 0f);
            flyBy.triggerRadius = 2.6f;
            flyBy.washRadius = 30f;

            // The stranded cat at the end of a plank sticking out from Tower B
            var catPlank = Group("CatPlank", game).transform;
            var catVisual = Group("Visual", catPlank).transform;
            catVisual.position = new Vector3(50f, H, 10f);
            Box("Plank", catVisual, new Vector3(0, -0.04f, 0), new Vector3(0.55f, 0.08f, 4f), plankMat, true, false);
            var catBeam = catPlank.gameObject.AddComponent<BalanceBeam>();
            catBeam.start = Point("Start", catPlank, new Vector3(50f, H, 8f));
            catBeam.end = Point("End", catPlank, new Vector3(50f, H, 12f));
            catBeam.walkableHalfWidth = 0.27f;
            catBeam.wobbleVisual = catVisual;
            catBeam.gusts = true;

            var cat = Group("Cat", game);
            cat.transform.position = new Vector3(50f, H + 0.02f, 11.5f);
            cat.transform.rotation = Quaternion.Euler(0, 180, 0);
            // Photo-scanned calico (Objaverse / Sketchfab, CC-BY - see Models/Animals/CREDITS.txt); stylized model, then primitives as fallbacks.
            if (Model("Animals/Mittens", cat.transform, Vector3.zero, 0.3f) == null && Model("Mittens", cat.transform, Vector3.zero, 0.3f) == null)
            {
                var fur = Mat("CatFur", new Color(0.95f, 0.6f, 0.25f));
                var furWhite = Mat("CatWhite", new Color(0.98f, 0.96f, 0.92f));
                Box("Body", cat.transform, new Vector3(0, 0.16f, 0), new Vector3(0.2f, 0.18f, 0.38f), fur, false, false);
                Sphere("Head", cat.transform, new Vector3(0, 0.3f, 0.2f), 0.18f, fur, false, false);
                Sphere("Muzzle", cat.transform, new Vector3(0, 0.27f, 0.28f), 0.08f, furWhite, false, false);
                Prim(PrimitiveType.Cube, "EarL", cat.transform, new Vector3(-0.05f, 0.4f, 0.2f), new Vector3(0.05f, 0.07f, 0.02f), fur, false, false, new Vector3(0, 0, 20));
                Prim(PrimitiveType.Cube, "EarR", cat.transform, new Vector3(0.05f, 0.4f, 0.2f), new Vector3(0.05f, 0.07f, 0.02f), fur, false, false, new Vector3(0, 0, -20));
                var tail = Bar("Tail", cat.transform, new Vector3(0, 0.2f, -0.18f), new Vector3(0, 0.42f, -0.32f), 0.035f, fur, false, false);
                tail.AddComponent<Spinner>().degreesPerSecond = new Vector3(0, 0, 60f);
                tail.GetComponent<Spinner>().oscillate = true;
                tail.GetComponent<Spinner>().oscillateAmplitude = 20f;
                for (int leg = 0; leg < 4; leg++)
                    Box("Leg", cat.transform, new Vector3(leg % 2 == 0 ? -0.07f : 0.07f, 0.04f, leg < 2 ? 0.12f : -0.12f), new Vector3(0.05f, 0.1f, 0.05f), furWhite, false, false);
            }
            var catCol = cat.AddComponent<BoxCollider>();
            catCol.size = new Vector3(0.3f, 0.45f, 0.6f);
            catCol.center = new Vector3(0, 0.22f, 0.02f);
            MakeGrabbable(cat, true);
            var catItem = cat.AddComponent<Collectible>();
            catItem.displayName = "Mittens the cat";
            catItem.isCat = true;
            var rescue = Group("RescueCat", game).AddComponent<CollectObjective>();
            rescue.description = "Rescue the cat at the end of the plank";
            rescue.companionLineOnComplete = "Mittens is safe! Purr... You walked out over 150 metres of air for a friend.";
            rescue.items.Add(catItem);
            Zone<SayZone>("CatHint", game, new Vector3(50f, H + 1.2f, 7f), new Vector3(2f, 2.4f, 1.2f)).line =
                "There's Mittens! Walk out slowly, crouch down at the end and pick her up gently.";

            // Fireworks launcher
            var launcher = Group("FireworksLauncher", game);
            launcher.transform.position = new Vector3(54f, H, -5f);
            Box("Crate", launcher.transform, new Vector3(0, 0.45f, 0), new Vector3(1.2f, 0.9f, 0.8f), Mat("CrateRed", new Color(0.7f, 0.15f, 0.12f)), true, false);
            for (int i = 0; i < 6; i++)
                Cyl("Tube", launcher.transform, new Vector3(-0.4f + (i % 3) * 0.4f, 0.9f, -0.15f + (i / 3) * 0.3f), 0.08f, 0.4f, Mat("TubeGold", new Color(0.9f, 0.75f, 0.3f), 0.6f, 0.5f), false, false);
            var btnGo = Cyl("BigButton", launcher.transform, new Vector3(0.45f, 0.9f, 0.25f), 0.12f, 0.08f, Glow("ButtonRed", new Color(1f, 0.15f, 0.1f), 2.5f), true, false);
            var btn = btnGo.AddComponent<PressButton>();
            btn.hint = "Launch the fireworks!";
            btn.cap = btnGo.transform;
            btnGo.AddComponent<UnityEngine.XR.Interaction.Toolkit.Interactables.XRSimpleInteractable>();
            var press = Group("LaunchFireworks", game).AddComponent<PressObjective>();
            press.description = "Launch the celebration fireworks";
            press.button = btn;

            var show = Group("FireworksShow", game).AddComponent<FireworksShow>();
            show.transform.position = new Vector3(50f, H, 48f);
            show.area = 40f;
            show.height = 35f;
            UnityEditor.Events.UnityEventTools.AddPersistentListener(btn.onPressed, show.Play);

            // Birds and clouds below and around you
            var flock = Group("BirdFlock", env).AddComponent<BirdFlock>();
            flock.transform.position = new Vector3(25f, H - 35f, 0f);
            flock.radius = 35f;
            flock.material = Mat("BirdWhite", new Color(0.95f, 0.95f, 0.95f));
            var flock2 = Group("BirdFlock2", env).AddComponent<BirdFlock>();
            flock2.transform.position = new Vector3(-40f, H - 70f, 40f);
            flock2.radius = 25f;
            flock2.count = 8;
            flock2.material = Mat("BirdWhite", new Color(0.95f, 0.95f, 0.95f));
            // Clouds come from the real HDRI sky (sphere puffs read as toys).

            Star(game, new Vector3(21.5f, H + 1.15f, 1.95f));
            Star(game, new Vector3(50f, H + 0.9f, 12.45f));
            Star(game, new Vector3(36f, H + 0.5f, -0.9f));

            Zone<GoalZone>("Goal (Helipad)", game, new Vector3(50f, H + 1.2f, -1.5f), new Vector3(5.5f, 2.4f, 5.5f));

            // Photo-scanned rooftop dressing (CC0 Poly Haven).
            var roofDress = Group("ScanDressing", env).transform;
            PolyProp("utility_box_01", roofDress, new Vector3(3f, H, -5.5f), 0f);
            PolyProp("utility_box_01", roofDress, new Vector3(5f, H, 5.5f), 180f);
            PolyProp("utility_box_01", roofDress, new Vector3(54f, H, -5.5f), 0f);

            var lc = CommonLevel(2, "Level 3 - The Skyscraper", new Vector3(0f, H, 0f), 90f, 0f, 160f, 0.35f);
            lc.objectives = new Objective[] { reachCradle, reachB, rescue, press };
            lc.boardPoint = PanelPoint("Board", lc.transform, new Vector3(2.5f, H + 1.8f, -3.2f), new Vector3(0, H + 1.6f, 0));
            lc.introLines = new[]
            {
                "Welcome to the top of the city. One hundred and fifty metres - and not a single railing. Three lives. Let's go!",
                "Mittens the cat is stuck on the tower across the gap. We're going to cross over and rescue her.",
                "The wind is strong up here. When I warn you about a gust - crouch down low until it passes!",
            };
            lc.finishLine = "You did it! You crossed the sky and rescued Mittens. Let's light it up!";
            lc.finaleSeconds = 7f;
            UnityEditor.Events.UnityEventTools.AddPersistentListener(lc.onFinale, show.Play);
            Save(scene, GameManager.LevelScenes[2]);
        }

        static void BuildBeam(Transform game, string name, float width, Material steel, Material rope, Material net,
            bool gentle, bool standard, bool brave, int ropes, bool withNet)
        {
            const float H = 150f;
            var root = Group(name, game).transform;
            var visual = Group("Visual", root).transform;
            visual.position = new Vector3(14f, H, 0f);
            Box("BeamTop", visual, new Vector3(0, -0.04f, 0), new Vector3(12.2f, 0.08f, width), steel, true, false);
            Box("BeamWeb", visual, new Vector3(0, -0.3f, 0), new Vector3(12.2f, 0.45f, 0.06f), steel, false, false);
            Box("BeamFlange", visual, new Vector3(0, -0.55f, 0), new Vector3(12.2f, 0.06f, width), steel, false, false);
            for (int r = 0; r < ropes; r++)
            {
                float z = (r == 0 ? 1f : -1f) * (width * 0.5f + 0.35f);
                Bar("SafetyCable", visual, new Vector3(-6f, 1.05f, z), new Vector3(6f, 1.05f, z), 0.03f, rope, false, false);
                for (int p = 0; p <= 4; p++)
                    Bar("CablePost", visual, new Vector3(-6f + p * 3f, 0, z), new Vector3(-6f + p * 3f, 1.05f, z), 0.04f, steel, false, false);
            }
            if (withNet) Box("Net", visual, new Vector3(0, -3f, 0), new Vector3(12f, 0.02f, 4f), net, false, false);
            var beam = root.gameObject.AddComponent<BalanceBeam>();
            beam.start = Point("Start", root, new Vector3(8f, H, 0f));
            beam.end = Point("End", root, new Vector3(20f, H, 0f));
            beam.walkableHalfWidth = width * 0.5f;
            beam.wobbleVisual = visual;
            beam.gusts = true;
            beam.gustInterval = gentle ? new Vector2(14f, 20f) : new Vector2(8f, 13f);
            ShowIn(root.gameObject, gentle, standard, brave);
            Zone<SayZone>("BeamHint", root, new Vector3(7.2f, H + 1.2f, 0f), new Vector3(1.2f, 2.4f, 3f)).line =
                "The beam. Arms out if it helps. Eyes on the cradle ahead. Small steps - and crouch when the wind comes.";
        }
    }
}