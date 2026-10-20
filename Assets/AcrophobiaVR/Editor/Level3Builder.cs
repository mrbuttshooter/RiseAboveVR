using UnityEngine;
using static AcrophobiaVR.EditorTools.BuildKit;

namespace AcrophobiaVR.EditorTools
{
    public static partial class LevelBuilder
    {
        // ------------------------------------------------------------------ LEVEL 3: SKYLINE GAUNTLET (139-150 m)
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
            var steel = Mat("SteelRed", new Color(0.65f, 0.2f, 0.15f), 0.4f, 0.6f);
            var steelDark = Mat("SteelDark", new Color(0.2f, 0.22f, 0.25f), 0.5f, 0.8f);
            var plankMat = Mat("Plank", new Color(0.72f, 0.55f, 0.32f));
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
            City(env, new Vector2(25, 0), 8, 40f, new Vector2(30, 230), new Rect(-30, -30, 140, 60), 303, palette, windowGlow, 0f, 200f);

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

            var lc = BuildSkylineGauntlet(env, game, towerGlass, steel, steelDark, concrete, Mat("RoofGravel", new Color(0.55f, 0.55f, 0.55f)), plankMat);
            lc.boardPoint = PanelPoint("Board", lc.transform, new Vector3(2.5f, H + 1.8f, -3.2f), new Vector3(0, H + 1.6f, 0));
            lc.introLines = new[]
            {
                "One hundred and fifty metres. Tightrope, zipline, a window cradle, a glass bridge - and a helicopter that won't wait.",
                "Miss the ladder at the end and it's a long way down. Go!",
            };
            lc.finishLine = "You caught the ladder! Skyline conquered. Enjoy the show!";
            Save(scene, GameManager.LevelScenes[2]);
        }
    }
}