using UnityEngine;
using static AcrophobiaVR.EditorTools.BuildKit;

namespace AcrophobiaVR.EditorTools
{
    public static partial class LevelBuilder
    {
        /// <summary>
        /// LEVEL 2 - CRANE RUSH. A storm is coming; race to the helipad roof. Scaffold ladder -> 6 m walkway of
        /// collapsing planks under falling debris -> ride a crane-carried steel beam to the 12 m slab -> a sweeping
        /// boom (jump the low arm, duck the high one) -> ladder to an 18 m steel beam in the gusts -> jump on a
        /// swinging crane-hook pallet -> climb the scaffold tower -> ride the rotating crane jib -> drop onto the roof.
        /// </summary>
        static LevelController BuildCraneRush(Transform env, Transform game, Material steel, Material yellow, Material concrete, Material plankMat, Material grate)
        {
            var site = Group("SiteCourse", env).transform;
            var cable = Mat("SteelCable", new Color(0.12f, 0.12f, 0.13f), 0.5f, 0.8f);
            var orange = Mat("SafetyOrange", new Color(1f, 0.45f, 0.08f), 0.4f);
            var warn = Transparent("DebrisWarning", new Color(1f, 0.35f, 0.1f, 0.45f), true);

            Ladder MakeLadder(string name, Vector3 bottom, Vector3 top, Vector3 exit, float exitYaw, Material mat)
            {
                var go = Group(name, game);
                var l = go.AddComponent<Ladder>();
                AddClimbRungs(go.transform, bottom, top + Vector3.up * 1.1f, 0.6f, mat);
                l.bottom = Point("Bottom", go.transform, bottom);
                l.top = Point("Top", go.transform, top);
                l.topExit = Point("TopExit", go.transform, exit, exitYaw);
                l.climbSpeed = 1.6f;
                return l;
            }

            CheckpointZone Checkpoint(string label, Vector3 center, Vector3 size, Vector3 spawn, float yaw)
            {
                var cp = Zone<CheckpointZone>("CP " + label, game, center, size);
                cp.label = label;
                cp.respawnPoint = Point("CP " + label + " Spawn", game, spawn, yaw);
                return cp;
            }

            // ---- Building A: steel frame (columns to 25 m), full slab at 12 m, perimeter beams at 18 m.
            var bldg = Group("BuildingA", env).transform;
            foreach (var x in new[] { -6f, 0f, 6f })
                foreach (var z in new[] { 0f, 6f, 12f })
                {
                    // The north line tops out under the walkable 18 m beam (columns there would block the walk).
                    float h = z > 11f ? 17.7f : 25f;
                    Box("Column", bldg, new Vector3(x, h * 0.5f, z), new Vector3(0.4f, h, 0.4f), steel);
                }
            Floor("Slab12", bldg, -6.2f, 6.2f, -0.2f, 12.2f, 12f, 0.3f, concrete, false);
            Box("BeamN18", bldg, new Vector3(0f, 17.85f, 12f), new Vector3(12.4f, 0.3f, 0.3f), steel);   // the walkable one
            Box("BeamS18", bldg, new Vector3(0f, 17.85f, 0f), new Vector3(12.4f, 0.3f, 0.3f), steel);
            Box("BeamW18", bldg, new Vector3(-6f, 17.85f, 6f), new Vector3(0.3f, 0.3f, 12f), steel);
            Box("BeamE18", bldg, new Vector3(6f, 17.85f, 6f), new Vector3(0.3f, 0.3f, 12f), steel);
            Box("BeamTop", bldg, new Vector3(0f, 24.85f, 3f), new Vector3(12.4f, 0.3f, 6.4f), steel);

            // ---- 1. Scaffold ladder to the 6 m walkway along the south face.
            MakeLadder("ScaffoldLadder", new Vector3(-5f, 0f, -2.45f), new Vector3(-5f, 6f, -2.45f), new Vector3(-5f, 6f, -1.4f), 90f, steel);
            Checkpoint("Walkway (6 m)", new Vector3(-5f, 7.2f, -1.4f), new Vector3(1.6f, 2.4f, 1.6f), new Vector3(-5.4f, 6f, -1.4f), 90f);
            var walk = Group("Walkway6", site).transform;
            for (int i = 0; i < 13; i++)
            {
                float x = -6.5f + i + 0.5f;
                var plank = Box("WalkPlank" + i, walk, new Vector3(x, 5.95f, -1.4f), new Vector3(0.98f, 0.1f, 1.5f), plankMat, true, false);
                if (i == 4 || i == 7 || i == 10) plank.AddComponent<CollapsingPlatform>().delay = 0.55f;
            }
            for (int i = 0; i <= 13; i += 2)
            {
                Bar("ScaffoldPost", walk, new Vector3(-6.5f + i, 0f, -2.2f), new Vector3(-6.5f + i, 7.2f, -2.2f), 0.06f, steel, false, true);
                Bar("ScaffoldPost", walk, new Vector3(-6.5f + i, 0f, -0.6f), new Vector3(-6.5f + i, 7.2f, -0.6f), 0.06f, steel, false, true);
            }
            Bar("Ledger", walk, new Vector3(-6.5f, 5.85f, -2.2f), new Vector3(6.5f, 5.85f, -2.2f), 0.06f, steel, false, true);
            Bar("Ledger", walk, new Vector3(-6.5f, 5.85f, -0.6f), new Vector3(6.5f, 5.85f, -0.6f), 0.06f, steel, false, true);
            var debris = Group("Debris6", game).AddComponent<DebrisDropper>();
            debris.transform.position = new Vector3(0f, 6f, -1.4f);
            debris.areaSize = new Vector3(12f, 0f, 1.4f);
            debris.interval = 2.0f;
            debris.dropHeight = 11f;
            debris.debrisMaterial = steel;
            debris.warningMaterial = warn;
            Zone<SayZone>("WalkHint", game, new Vector3(-4f, 7.2f, -1.4f), new Vector3(1.4f, 2.4f, 1.6f)).line = "Loose planks and falling steel - watch for the orange circles and keep running!";

            // ---- 2. Crane-carried steel beam: from the walkway end up to the 12 m slab.
            var beamRoot = Group("CraneBeam", game).transform;
            beamRoot.position = new Vector3(7.1f, 5.85f, -1.4f);
            var mover = beamRoot.gameObject.AddComponent<PathMover>();
            mover.points = new[] { Vector3.zero, new Vector3(0f, 6.1f, 0f), new Vector3(0f, 6.1f, 8f) };
            mover.speed = 1.7f;
            mover.pauseAtPoints = 1.6f;
            mover.startDelay = 2f; // waits at the walkway after the start / a respawn
            Box("BeamFlange", beamRoot, new Vector3(0f, 0.12f, 0f), new Vector3(0.6f, 0.06f, 3.2f), steel, true, false).AddComponent<Carrier>();
            Box("BeamWeb", beamRoot, new Vector3(0f, -0.1f, 0f), new Vector3(0.06f, 0.4f, 3.2f), steel, false, false);
            Box("BeamFlangeLow", beamRoot, new Vector3(0f, -0.32f, 0f), new Vector3(0.6f, 0.06f, 3.2f), steel, false, false);
            Bar("SlingA", beamRoot, new Vector3(0f, 0.15f, -1.4f), new Vector3(0f, 2.2f, 0f), 0.03f, cable, false, false);
            Bar("SlingB", beamRoot, new Vector3(0f, 0.15f, 1.4f), new Vector3(0f, 2.2f, 0f), 0.03f, cable, false, false);
            Bar("HoistCable", beamRoot, new Vector3(0f, 2.2f, 0f), new Vector3(0f, 40f, 0f), 0.04f, cable, false, false);
            Zone<SayZone>("BeamHint", game, new Vector3(5.8f, 7.2f, -1.4f), new Vector3(1.4f, 2.4f, 1.6f)).line = "Step onto the beam when it's down - it'll lift you to the next floor.";

            // ---- 3. 12 m slab: a boom sweeping round - jump the low arm, duck the high arm.
            Checkpoint("Slab (12 m)", new Vector3(5f, 13.2f, 6.6f), new Vector3(2.2f, 2.4f, 3f), new Vector3(5.4f, 12f, 6.6f), -90f);
            var boom = Group("SweepBoom", game).transform;
            boom.position = new Vector3(0f, 12f, 6f);
            var sweep = boom.gameObject.AddComponent<Sweeper>();
            sweep.degreesPerSecond = 55f;
            Cyl("BoomHub", boom, Vector3.zero, 0.35f, 1.9f, yellow, true, false);
            var low = Box("LowArm", boom, new Vector3(3.4f, 0.4f, 0f), new Vector3(6.4f, 0.2f, 0.2f), orange, true, false);   // reaches past the slab edge: no safe lane
            var high = Box("HighArm", boom, new Vector3(0f, 1.45f, 3.4f), new Vector3(0.2f, 0.2f, 6.4f), orange, true, false);
            low.AddComponent<HitBox>().bodyRadius = 0.25f;
            high.AddComponent<HitBox>().bodyRadius = 0.25f;
            Zone<SayZone>("BoomHint", game, new Vector3(5f, 13.2f, 4.5f), new Vector3(2f, 2.4f, 2f)).line = "Low arm: jump it. High arm: duck it. Get to the ladder in the far corner!";
            MakeLadder("SlabLadder", new Vector3(-4.5f, 12f, 12.7f), new Vector3(-4.5f, 18f, 12.7f), new Vector3(-4.5f, 18f, 12f), 90f, steel);

            // ---- 4. The 18 m beam in the storm gusts.
            Checkpoint("Steel beam (18 m)", new Vector3(-4.2f, 19.2f, 12f), new Vector3(1.2f, 2.4f, 1f), new Vector3(-4.3f, 18f, 12f), 90f);
            var beamWind = Group("BeamWind", game).AddComponent<GustZone>();
            beamWind.transform.position = new Vector3(1f, 19.5f, 12f);
            beamWind.size = new Vector3(10f, 4f, 3f);
            beamWind.pushDirection = Vector3.forward;
            beamWind.randomSide = true;
            beamWind.interval = new Vector2(3.5f, 6f);
            beamWind.warning = 1.3f;
            beamWind.pushSpeed = 0.9f;

            // ---- 5. Swinging crane-hook pallet from the beam end to the scaffold tower.
            var hookPivot = Group("HookPivot", game).transform;
            hookPivot.position = new Vector3(10.25f, 29.49f, 12f);
            var hookSwing = hookPivot.gameObject.AddComponent<Pendulum>();
            hookSwing.axis = Vector3.forward;
            hookSwing.amplitude = 18f;
            hookSwing.period = 4.2f;
            var pallet = Box("HookPallet", hookPivot, new Vector3(0f, -12f, 0f), new Vector3(1.3f, 0.15f, 1.3f), plankMat, true, false);
            hookSwing.keepLevel = new[] { pallet.transform };
            pallet.AddComponent<Carrier>();
            foreach (var c in new[] { new Vector3(-0.6f, 0, -0.6f), new Vector3(0.6f, 0, -0.6f), new Vector3(-0.6f, 0, 0.6f), new Vector3(0.6f, 0, 0.6f) })
            {
                var hinge = Group("HookChainHinge", game).transform;
                hinge.position = hookPivot.position + c;
                var hp = hinge.gameObject.AddComponent<Pendulum>();
                hp.axis = hookSwing.axis; hp.amplitude = hookSwing.amplitude; hp.period = hookSwing.period;
                Bar("HookChain", hinge, Vector3.zero, new Vector3(0f, -11.95f, 0f), 0.03f, cable, false, false);
            }
            var hookStar = Star(game, pallet.transform.position + Vector3.up * 0.8f);
            hookStar.transform.SetParent(hookPivot, true);
            Zone<SayZone>("HookHint", game, new Vector3(4.5f, 19.2f, 12f), new Vector3(1.2f, 2.4f, 1f)).line = "The hook swings out to you. Time it, step on, ride it over, step off.";

            // ---- 6. Scaffold tower B: deck at 18.3 m, ladder to the top deck at 27.6 m (next to the crane).
            var tower = Group("ScaffoldTower", env).transform;
            foreach (var x in new[] { 14.6f, 18.6f })
                foreach (var z in new[] { 10f, 14f })
                    Bar("TowerPost", tower, new Vector3(x, 0f, z), new Vector3(x, 28.6f, z), 0.08f, steel, false, true);
            for (float y = 3f; y < 28f; y += 3f)
            {
                Bar("TowerTie", tower, new Vector3(14.6f, y, 10f), new Vector3(18.6f, y, 14f), 0.05f, steel, false, true);
                Bar("TowerTie", tower, new Vector3(18.6f, y, 10f), new Vector3(14.6f, y, 14f), 0.05f, steel, false, true);
            }
            Floor("TowerDeck18", tower, 14.6f, 18.6f, 10f, 14f, 18.3f, 0.12f, grate, false);
            Floor("TowerDeck27", tower, 14.6f, 18.6f, 10f, 14f, 27.6f, 0.12f, grate, false);
            Checkpoint("Scaffold tower", new Vector3(16f, 19.5f, 12f), new Vector3(3f, 2.4f, 3f), new Vector3(15.6f, 18.3f, 12f), 90f);
            MakeLadder("TowerLadder", new Vector3(16.6f, 18.3f, 14.7f), new Vector3(16.6f, 27.6f, 14.7f), new Vector3(16.6f, 27.6f, 13.6f), 180f, steel);
            Checkpoint("Crane deck (27.6 m)", new Vector3(16.6f, 28.8f, 12.6f), new Vector3(3f, 2.4f, 2.4f), new Vector3(16f, 27.6f, 12f), 45f);

            // ---- 7. Tower crane: mast and a jib that keeps turning - ride it over to roof C.
            var crane = Group("Crane", env).transform;
            Vector3 mast = new Vector3(26f, 0f, 20f);
            Lattice("MastLattice", crane, mast, mast + Vector3.up * 27.6f, 1.6f, 1.6f, yellow, 1.6f);
            Box("Slewing", crane, mast + new Vector3(0f, 27.4f, 0f), new Vector3(2.2f, 0.5f, 2.2f), yellow, true);
            var jib = Group("Jib", game).transform;
            jib.position = mast + new Vector3(0f, 27.65f, 0f);
            jib.rotation = Quaternion.Euler(0f, 160f, 0f); // starts pointing away from both the tower and the roof
            var jibSweep = jib.gameObject.AddComponent<Sweeper>();
            jibSweep.degreesPerSecond = 20f;
            var walkway = BoxMinMax("JibWalkway", jib, new Vector3(1.2f, 0f, -0.5f), new Vector3(10.6f, 0.15f, 0.5f), grate, true, false);
            walkway.AddComponent<Carrier>();
            Lattice("JibLattice", jib, new Vector3(1f, 0.85f, 0f), new Vector3(10.8f, 0.85f, 0f), 1.0f, 1.2f, yellow, 1.4f);
            Lattice("CounterJib", jib, new Vector3(-1f, 0.85f, 0f), new Vector3(-6f, 0.85f, 0f), 1.0f, 1.2f, yellow, 1.4f);
            Box("CounterWeight", jib, new Vector3(-5.2f, 0.3f, 0f), new Vector3(1.6f, 1.6f, 1.4f), concrete, false, false);
            Box("Cab", jib, new Vector3(0f, 1.2f, 1.3f), new Vector3(1.6f, 1.8f, 1.6f), Mat("CabGlass", new Color(0.3f, 0.4f, 0.5f), 0.9f), false, false);
            var jibWind = Group("JibWind", game).AddComponent<GustZone>();
            jibWind.transform.position = mast + new Vector3(0f, 29f, 0f);
            jibWind.size = new Vector3(22f, 4f, 22f);
            jibWind.pushDirection = Vector3.right;
            jibWind.randomSide = true;
            jibWind.interval = new Vector2(5f, 8f);
            jibWind.warning = 1.5f;
            jibWind.pushSpeed = 0.7f;
            Zone<SayZone>("JibHint", game, new Vector3(17.6f, 28.8f, 13.2f), new Vector3(2f, 2.4f, 2f)).line = "Here comes the jib - hop on, ride it round, and drop onto the roof!";
            Star(game, jib.position + jib.rotation * new Vector3(10.4f, 0.9f, 0f)).transform.SetParent(jib, true);

            // ---- 8. Roof C (26.6 m) with the helipad - the goal.
            const float RoofC = 26.6f;
            var roofC = Group("BuildingC", env).transform;
            Box("Building", roofC, new Vector3(23f, (RoofC - 0.25f) * 0.5f, 28f), new Vector3(14f, RoofC - 0.25f, 12f), Mat("Bldg3", new Color(0.74f, 0.75f, 0.77f)));
            Floor("RoofC", roofC, 16f, 30f, 22f, 34f, RoofC, 0.25f, Mat("RoofGravel", new Color(0.55f, 0.55f, 0.55f)), false);
            Cyl("Helipad", roofC, new Vector3(23f, RoofC + 0.01f, 29.5f), 3.2f, 0.02f, Mat("HelipadPaint", new Color(0.2f, 0.22f, 0.24f), 0.3f), false);
            var white = Mat("PoleWhite", Color.white);
            Box("HelipadH1", roofC, new Vector3(22.2f, RoofC + 0.03f, 29.5f), new Vector3(0.3f, 0.02f, 2.2f), white, false);
            Box("HelipadH2", roofC, new Vector3(23.8f, RoofC + 0.03f, 29.5f), new Vector3(0.3f, 0.02f, 2.2f), white, false);
            Box("HelipadH3", roofC, new Vector3(23f, RoofC + 0.03f, 29.5f), new Vector3(1.6f, 0.02f, 0.3f), white, false);
            foreach (var (id, pos, yaw, h) in new[] { ("exterior_aircon_unit", new Vector3(18f, RoofC, 32.6f), 180f, 1.2f), ("exterior_aircon_unit", new Vector3(20.6f, RoofC, 32.6f), 180f, 1.2f), ("utility_box_01", new Vector3(28.6f, RoofC, 33f), 180f, 1.1f) })
            {
                var unit = PolyProp(id, roofC, pos, yaw, 1f, h);
                if (unit != null) SolidBounds(unit);
            }
            var reach = Zone<ReachObjective>("ReachHelipad", game, new Vector3(23f, RoofC + 1.2f, 29.5f), new Vector3(5f, 2.4f, 5f));
            reach.description = "Reach the helipad before the storm";
            Zone<GoalZone>("Goal (Helipad)", game, new Vector3(23f, RoofC + 1.2f, 29.5f), new Vector3(5f, 2.4f, 5f));

            var lc = CommonLevel(1, GameManager.LevelTitles[1], new Vector3(-7.75f, 0f, -5f), 0f, 0f, 45f, 0.5f);
            lc.GetComponent<FallGuard>().killY = -5f; // the race starts on the ground: falls are caught by the drop check
            lc.objectives = new Objective[] { reach };
            lc.timeLimit = 180f;
            lc.goldTime = 90f;
            lc.silverTime = 115f;
            lc.bronzeTime = 145f;
            return lc;
        }
    }
}
