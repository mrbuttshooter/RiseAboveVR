using UnityEngine;
using static AcrophobiaVR.EditorTools.BuildKit;

namespace AcrophobiaVR.EditorTools
{
    public static partial class LevelBuilder
    {
        // ------------------------------------------------------------------ LEVEL 2: CONSTRUCTION SITE (25-31 m)
        static void BuildLevel2()
        {
            var scene = NewScene();
            Atmosphere(Sky("SkyNoon", new Color(0.4f, 0.6f, 0.95f), new Color(0.45f, 0.42f, 0.38f), 0.04f, 0.8f, 1.3f),
                new Color(0.78f, 0.86f, 0.95f), new Color(0.75f, 0.8f, 0.9f));
            Sun(new Vector3(55, 35, 0), new Color(1f, 0.97f, 0.9f), 1.35f);

            var env = Group("Environment").transform;
            var game = Group("Gameplay").transform;

            var dirt = Mat("Dirt", new Color(0.55f, 0.45f, 0.35f));
            var concrete = Mat("Concrete", new Color(0.7f, 0.7f, 0.68f));
            var steel = Mat("SteelRed", new Color(0.65f, 0.2f, 0.15f), 0.4f, 0.6f);
            var yellow = Mat("CraneYellow", new Color(1f, 0.78f, 0.15f), 0.4f, 0.3f);
            var scaffold = Mat("Scaffold", new Color(0.6f, 0.62f, 0.65f), 0.5f, 0.8f);
            var plankMat = Mat("Plank", new Color(0.72f, 0.55f, 0.32f));
            var rope = Mat("Rope", new Color(0.85f, 0.75f, 0.45f));
            var mesh = Transparent("SafetyMesh", new Color(1f, 0.55f, 0.15f, 0.35f));
            var grate = Mat("Grate", new Color(0.35f, 0.37f, 0.4f), 0.5f, 0.7f);
            var hazard = Glow("HazardStripe", new Color(1f, 0.6f, 0.1f), 0.6f);
            Material[] palette =
            {
                Mat("Bldg1", new Color(0.82f, 0.7f, 0.6f)), Mat("Bldg2", new Color(0.7f, 0.62f, 0.58f)),
                Mat("Bldg3", new Color(0.88f, 0.82f, 0.72f)), Mat("Glass Tower", new Color(0.45f, 0.6f, 0.75f), 0.85f, 0.4f),
            };

            Ground(env, 300f, dirt);
            City(env, new Vector2(10, 10), 7, 30f, new Vector2(10, 70), new Rect(-40, -40, 110, 110), 202, palette, Glow("WindowCool", new Color(0.7f, 0.85f, 1f), 0.8f));
            for (int i = 0; i < 14; i++)
                Box("Fence", env, new Vector3(-25 + i * 5f, 1f, -10f), new Vector3(4.8f, 2f, 0.08f), Mat("FenceMesh", new Color(0.3f, 0.5f, 0.35f)));
            for (int i = 0; i < 6; i++)
                Cyl("Cone", env, new Vector3(-12 + i * 1.5f, 0, -6), 0.15f, 0.5f, hazard, false);
            Box("Container", env, new Vector3(-20, 1.3f, 4), new Vector3(2.5f, 2.6f, 6f), Mat("ContainerBlue", new Color(0.2f, 0.4f, 0.65f)));
            Box("SiteOffice", env, new Vector3(-20, 1.3f, 12), new Vector3(2.5f, 2.6f, 6f), Mat("ContainerWhite", new Color(0.9f, 0.9f, 0.88f)));

            // Building A: steel frame, slab at 12 m and roof slab at 25 m
            var bldg = Group("BuildingA", env).transform;
            foreach (var x in new[] { -6f, 0f, 6f })
                foreach (var z in new[] { 0f, 6f, 12f })
                    Box("Column", bldg, new Vector3(x, 12.5f, z), new Vector3(0.4f, 25f, 0.4f), steel);
            Floor("Slab12", bldg, -6f, 6f, 6f, 12f, 12f, 0.3f, concrete, false);
            Floor("Roof25", bldg, -6.2f, 6.2f, -0.2f, 12.2f, 25f, 0.3f, concrete, true);
            // Edge barriers on the roof (gentle + standard), with gaps for lift and plank
            void Barrier(Vector3 a, Vector3 b)
            {
                var r = Railing("EdgeBarrier", bldg, a, b, 1.0f, yellow, true, 2f);
                ShowIn(r, true, true, false);
                SafetyGlass("EdgeMesh", bldg, a, b, 0.95f, mesh);
            }
            Barrier(new Vector3(-6.2f, 25f, -0.2f), new Vector3(6.2f, 25f, -0.2f));
            Barrier(new Vector3(-6.2f, 25f, 12.2f), new Vector3(-0.6f, 25f, 12.2f));
            Barrier(new Vector3(0.6f, 25f, 12.2f), new Vector3(6.2f, 25f, 12.2f));
            Barrier(new Vector3(-6.2f, 25f, -0.2f), new Vector3(-6.2f, 25f, 2.6f));
            Barrier(new Vector3(-6.2f, 25f, 5.4f), new Vector3(-6.2f, 25f, 12.2f));
            Barrier(new Vector3(6.2f, 25f, -0.2f), new Vector3(6.2f, 25f, 5.3f));
            Barrier(new Vector3(6.2f, 25f, 6.7f), new Vector3(6.2f, 25f, 12.2f));
            // Brave mode: just a low toe-board
            var toe = Box("ToeBoard", bldg, new Vector3(0, 25.08f, -0.15f), new Vector3(12.4f, 0.15f, 0.06f), hazard, false, false);
            ShowIn(toe, false, false, true);

            // Lift tower + platform
            var liftTower = Group("LiftTower", env).transform;
            foreach (var x in new[] { -9.2f, -6.3f })
                foreach (var z in new[] { 2.5f, 5.5f })
                    Box("LiftMast", liftTower, new Vector3(x, 13.5f, z), new Vector3(0.18f, 27f, 0.18f), yellow);
            Box("LiftHead", liftTower, new Vector3(-7.75f, 27f, 4f), new Vector3(3.2f, 0.3f, 3.4f), yellow);
            var lift = Group("Lift", game);
            lift.transform.position = new Vector3(-7.75f, 0f, 4f);
            var liftVisual = Group("Visual", lift.transform).transform;
            var deck = Box("Deck", liftVisual, new Vector3(0, -0.1f, 0), new Vector3(2.5f, 0.2f, 2.5f), grate, true, false);
            Railing("LiftRailBack", liftVisual, new Vector3(-1.2f, 0, -1.2f), new Vector3(-1.2f, 0, 1.2f), 1.1f, yellow, true, 1.2f);
            Railing("LiftRailL", liftVisual, new Vector3(-1.2f, 0, -1.2f), new Vector3(1.2f, 0, -1.2f), 1.1f, yellow, true, 1.2f);
            Railing("LiftRailR", liftVisual, new Vector3(-1.2f, 0, 1.2f), new Vector3(1.2f, 0, 1.2f), 1.1f, yellow, true, 1.2f);
            SafetyGlass("LiftMeshL", liftVisual, new Vector3(-1.2f, 0, -1.2f), new Vector3(1.2f, 0, -1.2f), 1.05f, mesh);
            SafetyGlass("LiftMeshR", liftVisual, new Vector3(-1.2f, 0, 1.2f), new Vector3(1.2f, 0, 1.2f), 1.05f, mesh);
            SafetyGlass("LiftMeshBack", liftVisual, new Vector3(-1.2f, 0, -1.2f), new Vector3(-1.2f, 0, 1.2f), 1.05f, mesh);
            var mp = lift.AddComponent<MovingPlatform>();
            mp.swingVisual = liftVisual;
            mp.speed = 1.1f;
            mp.waypoints = new[]
            {
                Point("Bottom", env, new Vector3(-7.75f, 0f, 4f)),
                Point("Middle", env, new Vector3(-7.75f, 12f, 4f)),
                Point("Top", env, new Vector3(-7.75f, 25f, 4f)),
            };
            mp.stallAtWaypoint = 1;
            mp.stallSeconds = 6f;
            mp.startLine = "Going up! Hold the rail if you like. Watch the ground get smaller.";
            mp.rideZone = Zone<HeadZoneRide>("RideZone", lift.transform, new Vector3(0, 1.2f, 0), new Vector3(2.3f, 2.6f, 2.3f));
            Box("CallSign", env, new Vector3(-7.75f, 2.4f, 1.6f), new Vector3(1.6f, 0.4f, 0.05f), Glow("ExitGreen", new Color(0.3f, 1f, 0.5f), 2f), false);
            var liftArrive = Zone<CheckpointZone>("CP Roof", game, new Vector3(-4.5f, 26.2f, 4f), new Vector3(3f, 2.4f, 3f));
            liftArrive.label = "Roof (25 m)";
            liftArrive.respawnPoint = Point("CP Roof Spawn", game, new Vector3(-4.5f, 25f, 4f), 90f);
            liftArrive.companionLine = "Twenty-five metres up. Feel your feet on the concrete. Solid.";
            mp.arrivalCheckpoint = liftArrive;
            var rideUp = Zone<ReachObjective>("ReachRoof", game, new Vector3(-3f, 26.2f, 4f), new Vector3(5f, 2.4f, 6f));
            rideUp.description = "Ride the open lift to the roof (25 m)";

            // Diving plank off the north edge (hammer at the end)
            var dive = Group("DivingPlank", game).transform;
            var diveVisual = Group("Visual", dive).transform;
            diveVisual.position = new Vector3(0, 25f, 13.7f);
            Box("Plank", diveVisual, new Vector3(0, -0.04f, 0), new Vector3(0.8f, 0.08f, 3f), plankMat, true, false);
            var diveBeam = dive.gameObject.AddComponent<BalanceBeam>();
            diveBeam.start = Point("Start", dive, new Vector3(0, 25f, 12.2f));
            diveBeam.end = Point("End", dive, new Vector3(0, 25f, 15.2f));
            diveBeam.walkableHalfWidth = 0.4f;
            diveBeam.wobbleVisual = diveVisual;

            // Plank bridge to the scaffold tower: three variants by exposure mode
            BuildPlankVariant(game, "PlankBridge Gentle", 1.0f, plankMat, rope, mesh, true, true, true, false, false);
            BuildPlankVariant(game, "PlankBridge Standard", 0.6f, plankMat, rope, mesh, false, true, false, true, false);
            BuildPlankVariant(game, "PlankBridge Brave", 0.45f, plankMat, rope, mesh, false, false, false, false, true);

            // Scaffold tower B (25 m deck) and crane base (31 m deck)
            var tower = Group("ScaffoldTower", env).transform;
            foreach (var x in new[] { 12f, 16f })
                foreach (var z in new[] { 4f, 8f })
                    Box("Pole", tower, new Vector3(x, 12.5f, z), new Vector3(0.1f, 25f, 0.1f), scaffold);
            for (int lvl = 1; lvl <= 4; lvl++)
            {
                Bar("Brace", tower, new Vector3(12, lvl * 6f - 3f, 4), new Vector3(16, lvl * 6f, 4), 0.06f, scaffold);
                Bar("Brace", tower, new Vector3(12, lvl * 6f - 3f, 8), new Vector3(16, lvl * 6f, 8), 0.06f, scaffold);
            }
            Floor("TowerDeck", tower, 12f, 16f, 4f, 8f, 25f, 0.15f, plankMat, true);
            Railing("TowerRailS", tower, new Vector3(12, 25, 4), new Vector3(16, 25, 4), 1.05f, scaffold);
            Railing("TowerRailN", tower, new Vector3(12, 25, 8), new Vector3(16, 25, 8), 1.05f, scaffold);
            var cpTower = Zone<CheckpointZone>("CP Tower", game, new Vector3(14f, 26.2f, 6f), new Vector3(3.6f, 2.4f, 3.6f));
            cpTower.label = "Scaffold tower";
            cpTower.respawnPoint = Point("CP Tower Spawn", game, new Vector3(13.5f, 25f, 6f), 90f);
            cpTower.offerBreathingBreak = true;
            cpTower.companionLine = "You crossed the plank! Let's take a few slow breaths before the climb.";

            foreach (var x in new[] { 16.6f, 20.6f })
                foreach (var z in new[] { 4f, 8f })
                    Box("CranePole", tower, new Vector3(x, 15.5f, z), new Vector3(0.12f, 31f, 0.12f), yellow);
            Floor("CraneDeck", tower, 16.6f, 20.6f, 4f, 8f, 31f, 0.15f, grate, true);
            Railing("CraneRailS", tower, new Vector3(16.6f, 31, 4), new Vector3(20.6f, 31, 4), 1.05f, yellow);
            Railing("CraneRailN", tower, new Vector3(16.6f, 31, 8), new Vector3(20.6f, 31, 8), 1.05f, yellow);

            // Ladder between the decks
            var ladderGo = Group("Ladder", game);
            var ladder = ladderGo.AddComponent<Ladder>();
            AddClimbRungs(ladderGo.transform, new Vector3(16.3f, 25f, 6f), new Vector3(16.3f, 32.2f, 6f), 0.6f, yellow);
            ladder.bottom = Point("Bottom", ladderGo.transform, new Vector3(16.3f, 25f, 6f));
            ladder.top = Point("Top", ladderGo.transform, new Vector3(16.3f, 31f, 6f));
            ladder.topExit = Point("TopExit", ladderGo.transform, new Vector3(17.6f, 31f, 6f), 90f);
            var climb = Zone<ReachObjective>("ReachCraneDeck", game, new Vector3(18.6f, 32.2f, 6f), new Vector3(3.6f, 2.4f, 3.6f));
            climb.description = "Climb the ladder to the crane deck (31 m)";
            climb.companionLineOnComplete = "Thirty-one metres! You climbed it hand over hand.";
            var cpCrane = Zone<CheckpointZone>("CP Crane", game, new Vector3(18.6f, 32.2f, 6f), new Vector3(3.6f, 2.4f, 3.6f));
            cpCrane.label = "Crane deck";
            cpCrane.respawnPoint = Point("CP Crane Spawn", game, new Vector3(18f, 31f, 6f), 90f);

            // Catwalk along the jib
            BuildCatwalk(game, "Catwalk Gentle", 1.4f, grate, yellow, mesh, true, false, false, 2);
            BuildCatwalk(game, "Catwalk Standard", 1.0f, grate, yellow, mesh, false, true, false, 2);
            BuildCatwalk(game, "Catwalk Brave", 0.8f, grate, yellow, mesh, false, false, true, 1);

            // Tools to collect
            var tools = Group("CollectTools", game).AddComponent<CollectObjective>();
            tools.description = "Find the 3 lost tools";
            tools.companionLineOnComplete = "All the tools! The foreman owes you a coffee.";
            tools.items.Add(Tool(game, "Wrench", new Vector3(5.2f, 25.25f, 11.3f), Mat("ToolSteel", new Color(0.7f, 0.72f, 0.75f), 0.8f, 0.9f), new Vector3(0.35f, 0.05f, 0.08f)));
            tools.items.Add(Tool(game, "Hammer", new Vector3(0f, 25.25f, 14.8f), Mat("ToolRed", new Color(0.8f, 0.15f, 0.12f)), new Vector3(0.1f, 0.06f, 0.35f)));
            tools.items.Add(Tool(game, "Hard hat", new Vector3(15.3f, 25.2f, 7.3f), yellow, new Vector3(0.28f, 0.16f, 0.32f)));

            // Flag to plant at the end of the jib
            var flag = Group("Flag", game);
            flag.transform.position = new Vector3(19.8f, 31.6f, 7.4f);
            Bar("FlagPole", flag.transform, new Vector3(0, -0.5f, 0), new Vector3(0, 0.9f, 0), 0.04f, Mat("PoleWhite", Color.white), false, false);
            Box("FlagCloth", flag.transform, new Vector3(0.28f, 0.7f, 0), new Vector3(0.5f, 0.32f, 0.01f), Glow("FlagCloth", new Color(0.2f, 0.75f, 1f), 0.6f), false, false);
            var flagCol = flag.AddComponent<BoxCollider>();
            flagCol.size = new Vector3(0.6f, 1.4f, 0.15f);
            flagCol.center = new Vector3(0.15f, 0.2f, 0);
            MakeGrabbable(flag, true);
            flag.AddComponent<ReturnIfLost>();
            var deliver = Group("PlantFlag", game).AddComponent<DeliverObjective>();
            deliver.description = "Plant the flag at the end of the crane jib";
            deliver.companionLineOnComplete = "Topping out! The flag is flying at the highest point of the site.";
            deliver.item = flag.transform;
            var socket = Cyl("FlagSocket", game, new Vector3(30.1f, 31f, 6f), 0.12f, 0.35f, hazard, false, false);
            var targetGo = new GameObject("FlagTarget");
            targetGo.transform.SetParent(game, false);
            targetGo.transform.position = new Vector3(30.1f, 31.8f, 6f);
            var tbox = targetGo.AddComponent<BoxCollider>();
            tbox.isTrigger = true;
            tbox.size = new Vector3(0.9f, 1.8f, 0.9f);
            targetGo.layer = 2;
            deliver.target = tbox;
            deliver.snapPoint = Point("FlagSnap", game, new Vector3(30.1f, 31.85f, 6f), 90f);

            // Crane: mast, jib and the hanging beam that carries you to the next roof
            var crane = Group("Crane", env).transform;
            Box("Mast", crane, new Vector3(36f, 21f, 6f), new Vector3(1.6f, 42f, 1.6f), yellow);
            Box("Jib", crane, new Vector3(24f, 42f, 6f), new Vector3(36f, 1.2f, 1.2f), yellow);
            Box("Cab", crane, new Vector3(36f, 40f, 4.5f), new Vector3(2f, 2f, 2f), Mat("CabGlass", new Color(0.3f, 0.4f, 0.5f), 0.9f));
            Box("CounterWeight", crane, new Vector3(44f, 41f, 6f), new Vector3(4f, 3f, 2f), concrete);

            var ride = Group("CraneBeamRide", game);
            ride.transform.position = new Vector3(32.2f, 31f, 6f);
            var rideVisual = Group("Visual", ride.transform).transform;
            Box("IBeam", rideVisual, new Vector3(0, -0.1f, 0), new Vector3(3f, 0.2f, 1.0f), steel, true, false);
            Box("IBeamWeb", rideVisual, new Vector3(0, -0.45f, 0), new Vector3(3f, 0.5f, 0.12f), steel, false, false);
            foreach (var x in new[] { -1.3f, 1.3f })
            {
                Bar("Cable", rideVisual, new Vector3(x, 0, 0), new Vector3(0, 9f, 0), 0.03f, Mat("Cable", new Color(0.15f, 0.15f, 0.15f), 0.6f, 0.8f), false, false);
            }
            Bar("HoldCable", rideVisual, new Vector3(0.3f, 0, 0.42f), new Vector3(0, 9f, 0), 0.04f, Mat("Cable", new Color(0.15f, 0.15f, 0.15f), 0.6f, 0.8f), false, false);
            var rideMp = ride.AddComponent<MovingPlatform>();
            rideMp.swingVisual = rideVisual;
            rideMp.swingDegrees = 2.5f;
            rideMp.speed = 1.6f;
            rideMp.requiredObjective = deliver;
            rideMp.lockedHint = "Plant the flag first - then the crane will carry you across";
            rideMp.startLine = "All aboard the crane beam! Hold the cable and enjoy the view.";
            rideMp.waypoints = new[]
            {
                Point("RideStart", env, new Vector3(32.2f, 31f, 6f)),
                Point("RideUp", env, new Vector3(32.2f, 34f, 15f)),
                Point("RideEnd", env, new Vector3(25f, 28f, 27f)),
            };
            rideMp.rideZone = Zone<HeadZoneRide>("RideZone", ride.transform, new Vector3(0, 1.2f, 0), new Vector3(2.8f, 2.6f, 1.2f));

            // Roof C - the goal
            var roofC = Group("BuildingC", env).transform;
            Box("Building", roofC, new Vector3(23f, 13.85f, 28f), new Vector3(14f, 27.7f, 12f), Mat("Bldg3", new Color(0.88f, 0.82f, 0.72f)));
            Floor("RoofC", roofC, 16f, 30f, 22f, 34f, 28f, 0.3f, concrete, true);
            Railing("RoofCRail", roofC, new Vector3(16, 28, 34), new Vector3(30, 28, 34), 1.1f, scaffold);
            Cyl("Helipad", roofC, new Vector3(22f, 28.01f, 30.5f), 2.5f, 0.02f, Glow("HelipadGlow", new Color(0.3f, 1f, 0.5f), 0.8f), false);
            var cpRoofC = Zone<CheckpointZone>("CP RoofC", game, new Vector3(23f, 29.2f, 29f), new Vector3(12f, 2.4f, 8f));
            cpRoofC.label = "Site office roof";
            cpRoofC.respawnPoint = Point("CP RoofC Spawn", game, new Vector3(23f, 28f, 29f), 0f);
            rideMp.arrivalCheckpoint = cpRoofC;
            Zone<GoalZone>("Goal (Helipad)", game, new Vector3(22f, 29.2f, 30.5f), new Vector3(4.5f, 2.4f, 4.5f));

            Star(game, new Vector3(0f, 26.2f, 15.45f));
            Star(game, new Vector3(25f, 32.0f, 7.15f));
            Star(game, new Vector3(-6.0f, 26.0f, 12.6f));

            var lc = CommonLevel(1, "Level 2 - The Construction Site", new Vector3(-7.75f, 0f, -5f), 0f, 0f, 45f, 0.5f);
            lc.objectives = new Objective[] { rideUp, tools, climb, deliver };
            lc.boardPoint = PanelPoint("Board", lc.transform, new Vector3(-4.5f, 1.8f, -3f), new Vector3(-7.75f, 1.6f, -5f));
            lc.introLines = new[]
            {
                "This is the Skyline Tower construction site! Our job: plant the topping-out flag at the end of the crane.",
                "First, the open lift to the roof. It's slow and steady... mostly.",
                "Three tools were left up there - grab them on the way. Then a plank, a ladder and the crane.",
            };
            lc.finishLine = "Incredible! You rode a crane beam across the sky. Level two complete!";
            Save(scene, GameManager.LevelScenes[1]);
        }

        static Collectible Tool(Transform parent, string name, Vector3 pos, Material mat, Vector3 size)
        {
            var go = Box(name, parent, pos, size, mat, true, false);
            MakeGrabbable(go, true);
            var c = go.AddComponent<Collectible>();
            c.displayName = name;
            var glow = new GameObject("Glow").AddComponent<Light>();
            glow.transform.SetParent(go.transform, false);
            glow.type = LightType.Point;
            glow.range = 1.2f;
            glow.intensity = 1.2f;
            glow.color = new Color(1f, 0.85f, 0.4f);
            return c;
        }

        static void BuildPlankVariant(Transform game, string name, float width, Material plank, Material rope, Material mesh,
            bool bothRails, bool oneRail, bool gentle, bool standard, bool brave)
        {
            var root = Group(name, game).transform;
            var visual = Group("Visual", root).transform;
            visual.position = new Vector3(9.1f, 25f, 6f);
            Box("Plank", visual, new Vector3(0, -0.04f, 0), new Vector3(6.2f, 0.08f, width), plank, true, false);
            float h = 1.05f;
            if (bothRails || oneRail)
                Bar("RopeL", visual, new Vector3(-3.1f, h, width * 0.5f + 0.1f), new Vector3(3.1f, h, width * 0.5f + 0.1f), 0.035f, rope, false, false);
            if (bothRails)
            {
                Bar("RopeR", visual, new Vector3(-3.1f, h, -width * 0.5f - 0.1f), new Vector3(3.1f, h, -width * 0.5f - 0.1f), 0.035f, rope, false, false);
                Box("Net", visual, new Vector3(0, -2.5f, 0), new Vector3(6.2f, 0.02f, 3f), mesh, false, false);
            }
            var beam = root.gameObject.AddComponent<BalanceBeam>();
            beam.start = Point("Start", root, new Vector3(6.1f, 25f, 6f));
            beam.end = Point("End", root, new Vector3(12.1f, 25f, 6f));
            beam.walkableHalfWidth = width * 0.5f;
            beam.wobbleVisual = visual;
            beam.gusts = brave;
            ShowIn(root.gameObject, gentle, standard, brave);
            Zone<SayZone>("PlankHint", root, new Vector3(5.2f, 26.2f, 6f), new Vector3(1.5f, 2.4f, 2f)).line =
                "The plank. Keep your head over the middle and look at the far end, not down. One foot, then the other.";
        }

        static void BuildCatwalk(Transform game, string name, float width, Material grate, Material rail, Material mesh,
            bool gentle, bool standard, bool brave, int rails)
        {
            var root = Group(name, game).transform;
            var visual = Group("Visual", root).transform;
            visual.position = new Vector3(25.6f, 31f, 6f);
            Box("Walkway", visual, new Vector3(0, -0.05f, 0), new Vector3(10f, 0.1f, width), grate, true, false);
            Railing("RailN", visual, new Vector3(-5f, 0, width * 0.5f), new Vector3(5f, 0, width * 0.5f), 1.05f, rail, rails > 1, 2f);
            if (rails > 1) Railing("RailS", visual, new Vector3(-5f, 0, -width * 0.5f), new Vector3(5f, 0, -width * 0.5f), 1.05f, rail, true, 2f);
            if (gentle)
            {
                SafetyGlass("MeshN", visual, new Vector3(-5f, 0, width * 0.5f), new Vector3(5f, 0, width * 0.5f), 1f, mesh);
                SafetyGlass("MeshS", visual, new Vector3(-5f, 0, -width * 0.5f), new Vector3(5f, 0, -width * 0.5f), 1f, mesh);
            }
            var beam = root.gameObject.AddComponent<BalanceBeam>();
            beam.start = Point("Start", root, new Vector3(20.6f, 31f, 6f));
            beam.end = Point("End", root, new Vector3(30.6f, 31f, 6f));
            beam.walkableHalfWidth = width * 0.5f;
            beam.gusts = !gentle;
            beam.gustFillRate = 0.35f;
            ShowIn(root.gameObject, gentle, standard, brave);
        }
    }
}