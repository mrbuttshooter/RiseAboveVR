using UnityEngine;
using static AcrophobiaVR.EditorTools.BuildKit;

namespace AcrophobiaVR.EditorTools
{
    public static partial class LevelBuilder
    {
        /// <summary>
        /// LEVEL 1 - ROOFTOP CHASE. Kiwi escapes from the cafe roof (13 m) and you chase her east across four
        /// more rooftops: a 2 m gap, a courtyard of shattering glass, a swinging scaffold board over a 5 m gap,
        /// a 60 cm ledge in the wind with pigeons, a drop to a roof with collapsing planks and walls to vault,
        /// a jump to a fire escape, a ladder to the 16 m roof - and a plank over the street where she's cornered.
        /// </summary>
        static ChaseObjective BuildRooftopChase(Transform env, Transform game, Material[] palette, Material metal, out LevelController lc)
        {
            const float CafeTop = 13.05f;
            var stone = Mat("Concrete", new Color(0.7f, 0.7f, 0.68f));
            var gravel = Mat("RoofGravel", new Color(0.55f, 0.55f, 0.55f));
            var wood = Mat("Plank", new Color(0.72f, 0.55f, 0.32f));
            var glassPane = Transparent("SkylightGlass", new Color(0.75f, 0.88f, 0.95f, 0.35f));
            var dark = Mat("Interior", new Color(0.12f, 0.12f, 0.13f));
            var course = Group("RooftopCourse", env).transform;

            // Rooftop: a facade box topped with a gravel slab whose top is at 'top'.
            void Roof(string name, float x0, float x1, float z0, float z1, float top, Material facade)
            {
                Box(name, course, new Vector3((x0 + x1) * 0.5f, (top - 0.25f) * 0.5f, (z0 + z1) * 0.5f), new Vector3(x1 - x0, top - 0.25f, z1 - z0), facade, true);
                Floor(name + "Roof", course, x0, x1, z0, z1, top, 0.25f, gravel, false);
                Kerb(name + "KerbS", course, new Vector3(x0, top, z0 + 0.05f), new Vector3(x1, top, z0 + 0.05f), stone);
                Kerb(name + "KerbN", course, new Vector3(x0, top, z1 - 0.05f), new Vector3(x1, top, z1 - 0.05f), stone);
            }

            // ---- B1 (12.4 m): two blocks around a courtyard; the only way across is a strip of skylight glass.
            const float B1 = 12.4f;
            Roof("B1West", 12f, 18f, 0f, 14f, B1, palette[0]);
            Roof("B1East", 26f, 32f, 0f, 14f, B1, palette[0]);
            Box("B1Courtyard", course, new Vector3(22f, 2f, 7f), new Vector3(8f, 4f, 14f), dark, true);
            for (int i = 0; i < 4; i++)
            {
                float x = 18.05f + i * 2f;
                var pane = Box("Skylight" + i, course, new Vector3(x + 0.975f, B1 - 0.05f, 7f), new Vector3(1.95f, 0.06f, 1.7f), glassPane, true, false);
                var cp = pane.AddComponent<CollapsingPlatform>();
                cp.shatter = true;
                cp.delay = 0.75f;
            }
            // Steel frame of the glass canopy (too thin to walk, but it looks the part).
            foreach (float z in new[] { 6.1f, 7.9f })
                Bar("CanopyRail", course, new Vector3(18f, B1 - 0.08f, z), new Vector3(26f, B1 - 0.08f, z), 0.08f, metal, false, true);
            for (int i = 0; i <= 4; i++)
                Bar("CanopyRib", course, new Vector3(18f + i * 2f, B1 - 0.08f, 0.5f), new Vector3(18f + i * 2f, B1 - 0.08f, 13.5f), 0.07f, metal, false, true);
            Zone<SayZone>("GlassHint", game, new Vector3(16.5f, B1 + 1.2f, 7f), new Vector3(2f, 2.4f, 4f)).line = "Skylights! Don't stop on the glass - it won't hold you for long.";

            // ---- Gap 2 (5 m): a scaffold board swinging on chains from a steel arm on B2's wall.
            var pivot = Group("SwingPivot", game).transform;
            pivot.position = new Vector3(34.5f, B1 + 3.21f, 7f); // board top 0.15 m above B1 at its west end (walk on), 0.35 m below it mid-swing
            Bar("SwingArm", course, new Vector3(37f, B1 + 3.21f, 7f), new Vector3(34.3f, B1 + 3.21f, 7f), 0.14f, metal, false, true);
            var pend = pivot.gameObject.AddComponent<Pendulum>();
            pend.axis = Vector3.forward;
            pend.amplitude = 30f;
            pend.period = 3.4f;
            var board = Box("SwingBoard", pivot, new Vector3(0f, -3.6f, 0f), new Vector3(1.6f, 0.12f, 1.3f), wood, true, false);
            pend.keepLevel = new[] { board.transform };
            board.AddComponent<Carrier>();
            // Parallel chains: each hangs from its own hinge on the arm and swings in step, so the board stays level.
            foreach (var c in new[] { new Vector3(-0.7f, 0, -0.55f), new Vector3(0.7f, 0, -0.55f), new Vector3(-0.7f, 0, 0.55f), new Vector3(0.7f, 0, 0.55f) })
            {
                var hinge = Group("ChainHinge", game).transform;
                hinge.position = pivot.position + c;
                var hp = hinge.gameObject.AddComponent<Pendulum>();
                hp.axis = pend.axis; hp.amplitude = pend.amplitude; hp.period = pend.period;
                Bar("Chain", hinge, Vector3.zero, new Vector3(0f, -3.55f, 0f), 0.025f, metal, false, false);
            }
            var swingStar = Star(game, board.transform.position + Vector3.up * 0.75f);
            swingStar.transform.SetParent(pivot, true);
            Zone<SayZone>("SwingHint", game, new Vector3(31f, B1 + 1.2f, 7f), new Vector3(1.5f, 2.4f, 4f)).line = "Wait for the board to swing to you - then jump on, ride it, and jump off.";

            // ---- B2 (13.6 m): the roof is taken by a plant room - only a 60 cm ledge along the street side remains.
            const float B2 = 12.9f;
            Roof("B2", 37f, 54f, 0f, 14f, B2, palette[1]);
            Box("PlantRoom", course, new Vector3(46.75f, B2 + 1.75f, 7.45f), new Vector3(14.5f, 3.5f, 13.1f), stone, true); // 2.5 m landing pad at the west end, then an 85 cm ledge
            Props.RooftopUnits(course, new Vector3(46.75f, B2 + 3.5f, 7.3f), new Vector2(13f, 11f), 31);
            var cp1 = Zone<CheckpointZone>("CP Ledge", game, new Vector3(38.2f, B2 + 1.2f, 7f), new Vector3(2.4f, 2.4f, 6f));
            cp1.label = "The ledge";
            cp1.respawnPoint = Point("CP Ledge Spawn", game, new Vector3(38.3f, B2, 4f), 180f);
            var ledgeWind = Group("LedgeWind", game).AddComponent<GustZone>();
            ledgeWind.transform.position = new Vector3(47f, B2 + 1.5f, 0.3f);
            ledgeWind.size = new Vector3(14f, 4f, 2f);
            ledgeWind.pushDirection = new Vector3(0f, 0f, -1f);
            ledgeWind.interval = new Vector2(3.5f, 6f);
            ledgeWind.warning = 1.4f;
            ledgeWind.pushSpeed = 1.2f;
            var pigeons = Group("Pigeons", game);
            pigeons.transform.position = new Vector3(48f, B2 + 0.02f, 0.3f);
            pigeons.transform.rotation = Quaternion.Euler(0, 90, 0);
            var startle = pigeons.AddComponent<StartleBirds>();
            startle.fleeDirection = new Vector3(0.3f, 0.2f, -1f);
            startle.bodyMaterial = Mat("PigeonGrey", new Color(0.55f, 0.57f, 0.62f), 0.35f);
            startle.wingMaterial = Mat("PigeonWing", new Color(0.42f, 0.44f, 0.5f), 0.3f);
            startle.birdPrefab = UnityEditor.AssetDatabase.LoadAssetAtPath<GameObject>(ModelFolder + "Animals/Pigeon.fbx")
                ?? UnityEditor.AssetDatabase.LoadAssetAtPath<GameObject>(ModelFolder + "Pigeon.fbx");
            Zone<SayZone>("LedgeHint", game, new Vector3(38.8f, B2 + 1.2f, 1.2f), new Vector3(1.6f, 2.4f, 1.6f)).line = "Ledge! When I shout GUST, crouch - or you're going over.";

            // ---- B3 (11 m): drop down; a light well bridged by two planks that give way; low walls to vault.
            const float B3 = 11f;
            Roof("B3West", 56.6f, 64f, 0f, 14f, B3, palette[2]);
            Roof("B3East", 68f, 76f, 0f, 14f, B3, palette[2]);
            Box("B3Well", course, new Vector3(66f, 1.5f, 7f), new Vector3(4f, 3f, 14f), dark, true);
            var cp2 = Zone<CheckpointZone>("CP Light well", game, new Vector3(58.5f, B3 + 1.2f, 7f), new Vector3(3f, 2.4f, 6f));
            cp2.label = "The light well";
            cp2.respawnPoint = Point("CP Well Spawn", game, new Vector3(57.8f, B3, 7f), 90f);
            Bar("WellBeam", course, new Vector3(66f, B3 - 0.35f, 5.5f), new Vector3(66f, B3 - 0.35f, 8.5f), 0.2f, metal, true, true);
            for (int i = 0; i < 2; i++)
            {
                var plank = Box("WellPlank" + i, course, new Vector3(65f + i * 2f, B3 - 0.04f, 7f), new Vector3(2f, 0.08f, 0.42f), wood, true, false);
                plank.AddComponent<CollapsingPlatform>().delay = 0.7f;
            }
            foreach (float x in new[] { 70.5f, 73.5f })
                Box("VaultWall", course, new Vector3(x, B3 + 0.35f, 7f), new Vector3(0.3f, 0.7f, 14f), stone, true);
            Props.RooftopUnits(course, new Vector3(60f, B3, 11f), new Vector2(6f, 4f), 37, true);

            // ---- Fire escape on B4's west wall: jump to the platform, climb to the 16 m roof.
            const float B4 = 16f;
            Roof("B4", 79f, 100f, 0f, 14f, B4, palette[3]);
            Floor("FireEscape", course, 77.6f, 79f, 5f, 8.2f, B3 + 0.2f, 0.1f, Mat("Grate", new Color(0.35f, 0.37f, 0.4f), 0.5f, 0.7f), false);
            Railing("FireEscapeRail", course, new Vector3(77.6f, B3 + 0.2f, 8.2f), new Vector3(79f, B3 + 0.2f, 8.2f), 1f, metal);
            var ladderGo = Group("FireEscapeLadder", game);
            var ladder = ladderGo.AddComponent<Ladder>();
            AddClimbRungs(ladderGo.transform, new Vector3(78.82f, B3 + 0.2f, 6.2f), new Vector3(78.82f, B4 + 1.1f, 6.2f), 0.6f, metal, Vector3.forward);
            ladder.bottom = Point("Bottom", ladderGo.transform, new Vector3(78.6f, B3 + 0.2f, 6.2f));
            ladder.top = Point("Top", ladderGo.transform, new Vector3(78.6f, B4, 6.2f));
            ladder.topExit = Point("TopExit", ladderGo.transform, new Vector3(80.2f, B4, 6.2f), 90f);
            ladder.climbSpeed = 1.6f;
            var cp3 = Zone<CheckpointZone>("CP Top roof", game, new Vector3(81f, B4 + 1.2f, 6.2f), new Vector3(3f, 2.4f, 4f));
            cp3.label = "Top roof (16 m)";
            cp3.respawnPoint = Point("CP Top Spawn", game, new Vector3(80.5f, B4, 6.2f), 90f);
            Props.RooftopUnits(course, new Vector3(90f, B4, 10f), new Vector2(14f, 6f), 41, true);

            // ---- The plank over the street: Kiwi is cornered at the end of it.
            var plankRoot = Group("DivingPlank", game).transform;
            BoxMinMax("Plank", plankRoot, new Vector3(91.8f, B4 - 0.08f, -5.6f), new Vector3(92.2f, B4, 0.3f), wood, true, false);
            Box("PlankWeight", plankRoot, new Vector3(92f, B4 + 0.3f, 1.2f), new Vector3(1f, 0.6f, 1.2f), stone, true);
            var plankWind = Group("PlankWind", game).AddComponent<GustZone>();
            plankWind.transform.position = new Vector3(92f, B4 + 1.5f, -2.8f);
            plankWind.size = new Vector3(3f, 4f, 6f);
            plankWind.pushDirection = Vector3.right;
            plankWind.randomSide = true;
            plankWind.interval = new Vector2(3f, 5f);
            plankWind.warning = 1.2f;
            plankWind.pushSpeed = 0.9f;

            // ---- Kiwi and her perches.
            var parrot = Group("Kiwi (Parrot)", game);
            if (Model("Animals/Kiwi", parrot.transform, Vector3.zero, 0.42f) == null && Model("Kiwi", parrot.transform, Vector3.zero, 0.42f) == null)
                Prim(PrimitiveType.Capsule, "Body", parrot.transform, new Vector3(0, 0.2f, 0), new Vector3(0.16f, 0.16f, 0.16f), Mat("ParrotGreen", new Color(0.2f, 0.75f, 0.3f), 0.5f), false, false);
            Vector3[] perchPos =
            {
                new Vector3(9.3f, CafeTop + 0.05f, 7f),     // cafe roof edge
                new Vector3(31.2f, B1 + 0.05f, 7f),         // past the skylights
                new Vector3(53.4f, B2 + 0.05f, 0.35f),      // end of the ledge
                new Vector3(75.4f, B3 + 0.05f, 7f),         // past the planks and walls
                new Vector3(92f, B4 + 0.05f, -5.3f),        // end of the plank: cornered
            };
            var perches = new Transform[perchPos.Length];
            for (int i = 0; i < perchPos.Length; i++) perches[i] = Point("KiwiPerch" + i, game, perchPos[i], -90f);
            var chase = Group("ChaseKiwi", game).AddComponent<ChaseObjective>();
            chase.description = "Catch Kiwi before she gets away";
            chase.target = parrot.transform;
            chase.perches = perches;
            chase.fleeRadius = 3.4f;
            chase.catchRadius = 1.25f;

            // Stars at the risky spots: over the courtyard, on the swinging board (above), on a rooftop unit.
            Star(game, new Vector3(22f, B1 + 1.4f, 8.5f));
            Star(game, new Vector3(97f, B4 + 1.6f, 3f));
            // Scanned wooden crate to climb for the star (box fallback if the scan is missing).
            var crate = PolyProp("wooden_crate_01", course, new Vector3(97f, B4, 3f), 15f, 1f, 1f);
            if (crate != null) SolidBounds(crate);
            else Box("StarCrate", course, new Vector3(97f, B4 + 0.5f, 3f), new Vector3(1.2f, 1f, 1.2f), Mat("Plank", new Color(0.72f, 0.55f, 0.32f)), true);

            lc = CommonLevel(0, GameManager.LevelTitles[0], new Vector3(-7f, CafeTop, 7f), 90f, 0f, 30f, 0.6f);
            lc.GetComponent<FallGuard>().killY = 8.5f;
            lc.timeLimit = 150f;
            lc.goldTime = 70f;
            lc.silverTime = 90f;
            lc.bronzeTime = 115f;
            return chase;
        }
    }
}
