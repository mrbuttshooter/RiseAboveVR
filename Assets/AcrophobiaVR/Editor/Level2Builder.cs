using UnityEngine;
using static AcrophobiaVR.EditorTools.BuildKit;

namespace AcrophobiaVR.EditorTools
{
    public static partial class LevelBuilder
    {
        // ------------------------------------------------------------------ LEVEL 2: CRANE RUSH (6-28 m)
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
                Mat("Bldg1", new Color(0.70f, 0.46f, 0.38f)), Mat("Bldg2", new Color(0.86f, 0.82f, 0.74f)),
                Mat("Bldg3", new Color(0.74f, 0.75f, 0.77f)), Mat("Glass Tower", new Color(0.45f, 0.6f, 0.75f), 0.85f, 0.4f),
            };

            Ground(env, 300f, dirt);
            City(env, new Vector2(10, 10), 7, 30f, new Vector2(10, 70), new Rect(-40, -40, 110, 110), 202, palette, Glow("WindowCool", new Color(0.7f, 0.85f, 1f), 0.8f));
            for (int i = 0; i < 14; i++)
                Box("Fence", env, new Vector3(-25 + i * 5f, 1f, -10f), new Vector3(4.8f, 2f, 0.08f), Mat("FenceMesh", new Color(0.3f, 0.5f, 0.35f)));
            // Photo-scanned concrete road barriers by the gate (cones as a fallback).
            if (PolyProp("concrete_road_barrier_02", env, new Vector3(-10.5f, 0f, -6f), 0f) != null)
            {
                PolyProp("concrete_road_barrier_02", env, new Vector3(-8.85f, 0f, -6f), 0f);
                PolyProp("concrete_road_barrier_02", env, new Vector3(-4.2f, 0f, -6f), 0f);
            }
            else
                for (int i = 0; i < 6; i++)
                    Cyl("Cone", env, new Vector3(-12 + i * 1.5f, 0, -6), 0.15f, 0.5f, hazard, false);
            // Realistic 20 ft shipping container (Gemini Argon, 6 m along its X); box fallback.
            var container = Model("Props/Container20", env, new Vector3(-20f, 0f, 4f), 0f, 90f);
            if (container != null) SolidBounds(container);
            else Box("Container", env, new Vector3(-20, 1.3f, 4), new Vector3(2.5f, 2.6f, 6f), Mat("ContainerBlue", new Color(0.2f, 0.4f, 0.65f)));
            // Realistic portable site office (Gemini Argon, 6 m along its X, door + steps on the front); box fallback.
            var cabin = Model("Props/SiteCabin", env, new Vector3(-20f, 0f, 12f), 0f, 90f);
            if (cabin != null) SolidBounds(cabin);
            else Box("SiteOffice", env, new Vector3(-20, 1.3f, 12), new Vector3(2.5f, 2.6f, 6f), Mat("ContainerWhite", new Color(0.9f, 0.9f, 0.88f)));

            // Photo-scanned site dressing (CC0 Poly Haven).
            var siteDress = Group("ScanDressing", env).transform;
            PolyProp("wooden_crate_01", siteDress, new Vector3(-14f, 0f, 6f), 15f);
            PolyProp("wooden_crate_01", siteDress, new Vector3(-14.9f, 0f, 7.2f), 70f);
            PolyProp("barrel_03", siteDress, new Vector3(-12.5f, 0f, 9f));
            PolyProp("barrel_03", siteDress, new Vector3(-11.8f, 0f, 9.6f), 40f);
            PolyProp("propane_tank", siteDress, new Vector3(-16f, 0f, 10.5f));
            PolyProp("hand_truck", siteDress, new Vector3(-10.6f, 0f, 7.6f), 200f);
            PolyProp("portable_welding_cart", siteDress, new Vector3(-17.2f, 0f, 8.4f), 80f);
            PolyProp("plastic_crate_01", siteDress, new Vector3(-13.2f, 0f, 11f), 10f);
            PolyProp("plastic_crate_01", siteDress, new Vector3(-13.1f, 0.27f, 11.05f), 25f);
            PolyProp("cardboard_box_01", siteDress, new Vector3(-12.4f, 0f, 11.8f), 60f);
            PolyProp("wooden_ladder", siteDress, new Vector3(-18.6f, 0f, 14.6f), 90f);
            PolyProp("covered_car", siteDress, new Vector3(-30f, 0f, 2f), 5f);

            var lc = BuildCraneRush(env, game, steel, yellow, concrete, plankMat, grate);
            lc.boardPoint = PanelPoint("Board", lc.transform, new Vector3(-4.8f, 1.8f, -3.2f), new Vector3(-7.75f, 1.6f, -5f));
            lc.introLines = new[]
            {
                "Storm's rolling in. That helipad up there? Be on it before the clock runs out.",
                "Ladders, a crane beam, a swinging hook and a turning jib. Don't miss.",
            };
            lc.finishLine = "Helipad! You beat the storm. Now beat your time.";
            Save(scene, GameManager.LevelScenes[1]);
        }

        static Collectible Tool(Transform parent, string name, Vector3 pos, Material mat, Vector3 size, string scan = null)
        {
            // Unscaled root holds the collider; the visual is a child (a photo-scanned prop when available).
            var go = Group(name, parent);
            go.transform.position = pos;
            var col = go.AddComponent<BoxCollider>();
            col.size = size;
            if (scan == null || PolyProp(scan, go.transform, new Vector3(0f, -size.y * 0.5f, 0f), 90f, 1f, 0f) == null)
                Box("Visual", go.transform, Vector3.zero, size, mat, false, false);
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