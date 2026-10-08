using UnityEngine;
using static AcrophobiaVR.EditorTools.BuildKit;

namespace AcrophobiaVR.EditorTools
{
    public static partial class LevelBuilder
    {
        // ------------------------------------------------------------------ LEVEL 1: SUNSET CAFE BALCONY (6 m)
        static void BuildLevel1()
        {
            var scene = NewScene();
            Atmosphere(Sky("SkySunset", new Color(0.85f, 0.6f, 0.52f), new Color(0.35f, 0.3f, 0.3f), 0.06f, 1.2f, 1.35f),
                new Color(0.95f, 0.72f, 0.55f), new Color(0.85f, 0.65f, 0.55f));
            Sun(new Vector3(12, -35, 0), new Color(1f, 0.72f, 0.48f), 1.3f);

            const float B = 6f; // balcony floor height
            var env = Group("Environment").transform;
            var game = Group("Gameplay").transform;

            var asphalt = Mat("Asphalt", new Color(0.18f, 0.18f, 0.2f), 0.2f);
            var pavement = Mat("Pavement", new Color(0.62f, 0.6f, 0.58f));
            var lane = Mat("LaneWhite", new Color(0.95f, 0.95f, 0.9f));
            var cafeWall = Mat("CafeWall", new Color(0.9f, 0.72f, 0.55f));
            var trim = Mat("Trim", new Color(0.35f, 0.22f, 0.15f));
            var metal = Mat("RailMetal", new Color(0.15f, 0.15f, 0.17f), 0.6f, 0.8f);
            var wood = Mat("Deck", new Color(0.55f, 0.38f, 0.25f));
            var glass = Transparent("SafetyGlass", new Color(0.75f, 0.9f, 1f, 0.22f));
            var floorGlass = Transparent("FloorGlass", new Color(0.7f, 0.9f, 1f, 0.3f));
            var windowGlow = Glow("WindowWarm", new Color(1f, 0.8f, 0.5f), 1.5f);
            var cloth = Mat("Cloth", new Color(0.85f, 0.25f, 0.3f));
            var skin = Mat("Skin", new Color(0.9f, 0.72f, 0.6f));
            Material[] palette =
            {
                Mat("Bldg1", new Color(0.82f, 0.7f, 0.6f)), Mat("Bldg2", new Color(0.7f, 0.62f, 0.58f)),
                Mat("Bldg3", new Color(0.88f, 0.82f, 0.72f)), Mat("Bldg4", new Color(0.6f, 0.55f, 0.6f)),
            };

            // Street level
            Ground(env, 260f, pavement);
            Box("Road", env, new Vector3(0, 0.01f, -12), new Vector3(400, 0.02f, 8), asphalt, false);
            for (int i = -40; i <= 40; i++)
                Box("Lane", env, new Vector3(i * 5f, 0.025f, -12), new Vector3(2.2f, 0.01f, 0.15f), lane, false);
            Box("SidewalkNear", env, new Vector3(0, 0.08f, -5.5f), new Vector3(400, 0.16f, 5), pavement);
            Box("SidewalkFar", env, new Vector3(0, 0.08f, -18.5f), new Vector3(400, 0.16f, 5), pavement);
            var carColors = new[] { new Color(0.8f, 0.2f, 0.2f), new Color(0.2f, 0.4f, 0.8f), new Color(0.95f, 0.85f, 0.3f), new Color(0.9f, 0.9f, 0.92f) };
            var carGlass = Mat("CarGlass", new Color(0.2f, 0.25f, 0.3f), 0.9f);
            var loop = new[] { new Vector3(-180, 0, -10.2f), new Vector3(180, 0, -10.2f), new Vector3(180, 0, -13.8f), new Vector3(-180, 0, -13.8f) };
            for (int i = 0; i < 10; i++)
                Car(env, loop, i / 10f, 7f + (i % 3), Mat("Car" + (i % 4), carColors[i % 4], 0.7f, 0.4f), carGlass);

            // Neighbouring buildings along the street + city behind
            for (int i = -6; i <= 6; i++)
            {
                if (i == 0) continue;
                float h = 10f + Mathf.Abs(Mathf.Sin(i * 1.7f)) * 18f;
                Box("StreetBuilding", env, new Vector3(i * 22f, h * 0.5f, 7), new Vector3(20, h, 14), palette[(i + 12) % 4], false);
                float h2 = 9f + Mathf.Abs(Mathf.Cos(i * 1.3f)) * 22f;
                Box("FarBuilding", env, new Vector3(i * 22f + 6, h2 * 0.5f, -30), new Vector3(20, h2, 14), palette[(i + 13) % 4], false);
            }
            City(env, new Vector2(0, 40), 6, 24f, new Vector2(12, 45), new Rect(-140, -40, 280, 60), 101, palette, windowGlow);

            // The cafe building
            var cafe = Group("SunsetCafe", env).transform;
            Box("Building", cafe, new Vector3(0, 11, 7), new Vector3(20, 22, 14), cafeWall);
            for (int f = 0; f < 6; f++)
                for (int w = -4; w <= 4; w++)
                {
                    float y = 2f + f * 3.5f;
                    if (Mathf.Abs(y - B - 1.2f) < 1.6f && w > -4 && w < 3) continue; // balcony doors area
                    Box("Window", cafe, new Vector3(w * 2.1f, y, -0.04f), new Vector3(1.1f, 1.5f, 0.08f), windowGlow, false);
                }
            Box("Awning", cafe, new Vector3(0, 3.2f, -1f), new Vector3(16, 0.1f, 2f), cloth, false);
            Box("CafeSign", cafe, new Vector3(0, 4.2f, -0.1f), new Vector3(6, 0.9f, 0.15f), Glow("SignGlow", new Color(1f, 0.55f, 0.3f), 2.5f), false);

            // Balcony slab, railings, decor
            var balcony = Group("Balcony", env).transform;
            Floor("BalconyFloor", balcony, -7f, 5f, -3f, 0f, B, 0.3f, wood, true);
            Box("BalconyTrim", balcony, new Vector3(-1, B - 0.4f, -3.02f), new Vector3(12.1f, 0.25f, 0.1f), trim, false);
            Railing("RailFrontLeft", balcony, new Vector3(-7f, B, -3f), new Vector3(-6f, B, -3f), 1.1f, metal);
            Railing("RailFrontRight", balcony, new Vector3(-4f, B, -3f), new Vector3(5f, B, -3f), 1.1f, metal);
            Railing("RailSideL", balcony, new Vector3(-7f, B, -3f), new Vector3(-7f, B, 0f), 1.1f, metal);
            Railing("RailSideR", balcony, new Vector3(5f, B, -3f), new Vector3(5f, B, 0f), 1.1f, metal);
            SafetyGlass("GlassFrontRight", balcony, new Vector3(-4f, B, -3f), new Vector3(5f, B, -3f), 1.05f, glass);
            SafetyGlass("GlassFrontLeft", balcony, new Vector3(-7f, B, -3f), new Vector3(-6f, B, -3f), 1.05f, glass);
            SafetyGlass("GlassSideR", balcony, new Vector3(5f, B, -3f), new Vector3(5f, B, 0f), 1.05f, glass);
            for (int t = 0; t < 3; t++)
            {
                float x = -2.5f + t * 2.2f;
                Cyl("TableLeg", balcony, new Vector3(x, B, -0.8f), 0.05f, 0.72f, metal);
                Cyl("TableTop", balcony, new Vector3(x, B + 0.72f, -0.8f), 0.4f, 0.04f, Mat("Marble", new Color(0.95f, 0.95f, 0.93f), 0.7f));
            }
            for (int s = 0; s < 12; s++)
                Sphere("StringLight", balcony, new Vector3(-6.8f + s * 1.0f, B + 2.6f - Mathf.Sin(s / 11f * Mathf.PI) * 0.35f, -2.6f), 0.1f, Glow("BulbWarm", new Color(1f, 0.85f, 0.5f), 4f));
            Cyl("Umbrella Pole", balcony, new Vector3(3.6f, B, -1.2f), 0.04f, 2.3f, metal);
            Cyl("Umbrella", balcony, new Vector3(3.6f, B + 2.2f, -1.2f), 1.3f, 0.12f, cloth, false);
            Box("CafeDoor", balcony, new Vector3(4f, B + 1.1f, 0.02f), new Vector3(1.4f, 2.2f, 0.1f), Mat("DoorWood", new Color(0.35f, 0.2f, 0.12f)), false);
            Box("DoorSign", balcony, new Vector3(4f, B + 2.45f, -0.05f), new Vector3(1.2f, 0.3f, 0.05f), Glow("ExitGreen", new Color(0.3f, 1f, 0.5f), 2f), false);

            // Glass skywalk extension (left end)
            var sky = Group("GlassSkywalk", env).transform;
            var glassRoot = new GameObject("GlassFloor");
            glassRoot.transform.SetParent(sky, false);
            glassRoot.transform.localPosition = new Vector3(-5f, B - 0.05f, -5f);
            var glassCol = glassRoot.AddComponent<BoxCollider>();
            glassCol.size = new Vector3(2f, 0.1f, 4f);
            var glassVisual = Box("Panel", glassRoot.transform, Vector3.zero, new Vector3(2f, 0.1f, 4f), floorGlass, false, false);
            var crack = glassRoot.AddComponent<CrackingGlass>();
            crack.panel = glassVisual.GetComponent<Renderer>();
            crack.cracks = Cracks(glassRoot.transform, 8, new Vector2(1f, 2f), 0.056f, 7);
            crack.secondsToBreak = 10f;
            Bar("FrameL", sky, new Vector3(-6f, B - 0.1f, -3f), new Vector3(-6f, B - 0.1f, -7f), 0.1f, metal);
            Bar("FrameR", sky, new Vector3(-4f, B - 0.1f, -3f), new Vector3(-4f, B - 0.1f, -7f), 0.1f, metal);
            Bar("Strut", sky, new Vector3(-5f, B - 0.1f, -7f), new Vector3(-5f, B - 2.5f, -3.1f), 0.12f, metal);
            Railing("SkyRailL", sky, new Vector3(-6f, B, -3f), new Vector3(-6f, B, -7f), 1.1f, metal);
            Railing("SkyRailR", sky, new Vector3(-4f, B, -3f), new Vector3(-4f, B, -7f), 1.1f, metal);
            Railing("SkyRailEnd", sky, new Vector3(-6f, B, -7f), new Vector3(-4f, B, -7f), 1.1f, metal);
            SafetyGlass("SkyGlassL", sky, new Vector3(-6f, B, -3f), new Vector3(-6f, B, -7f), 1.05f, glass);
            SafetyGlass("SkyGlassR", sky, new Vector3(-4f, B, -3f), new Vector3(-4f, B, -7f), 1.05f, glass);

            // Flower pots on a shelf just outside the railing
            var water = Group("WaterTask", game).AddComponent<WaterObjective>();
            water.description = "Water the 3 flowers on the ledge";
            water.companionLineOnComplete = "Beautiful! And you leaned right over the railing to do it.";
            float[] potX = { -2f, 0.6f, 3.2f };
            Color[] petals = { new Color(1f, 0.45f, 0.6f), new Color(1f, 0.85f, 0.25f), new Color(0.65f, 0.5f, 1f) };
            for (int i = 0; i < 3; i++)
            {
                Box("Shelf", env, new Vector3(potX[i], B + 0.72f, -3.32f), new Vector3(0.7f, 0.06f, 0.4f), wood);
                Bar("ShelfBracket", env, new Vector3(potX[i], B + 0.7f, -3.5f), new Vector3(potX[i], B + 0.3f, -3.02f), 0.04f, metal);
                var pot = Cyl("Pot", game, new Vector3(potX[i], B + 0.75f, -3.32f), 0.15f, 0.26f, Mat("Terracotta", new Color(0.75f, 0.4f, 0.25f)), true, false);
                var fp = pot.AddComponent<FlowerPot>();
                var flower = Group("Flower", game).transform;
                flower.position = new Vector3(potX[i], B + 1.01f, -3.32f);
                Cyl("Stem", flower, Vector3.zero, 0.015f, 0.3f, Mat("Stem", new Color(0.3f, 0.6f, 0.25f)), false, false);
                Sphere("Bloom", flower, new Vector3(0, 0.33f, 0), 0.16f, Mat("Petal" + i, petals[i]), false, false);
                fp.flower = flower;
                water.pots.Add(fp);
            }
            var can = Group("WateringCan", game);
            can.transform.position = new Vector3(-0.3f, B + 0.86f, -0.8f);
            var canBody = Cyl("Body", can.transform, new Vector3(0, -0.12f, 0), 0.1f, 0.22f, Mat("CanGreen", new Color(0.3f, 0.65f, 0.45f), 0.6f, 0.3f), true, false);
            var spoutBar = Bar("Spout", can.transform, new Vector3(0, -0.02f, 0.08f), new Vector3(0, 0.08f, 0.3f), 0.03f, Mat("CanGreen", new Color(0.3f, 0.65f, 0.45f), 0.6f, 0.3f), false, false);
            Bar("Handle", can.transform, new Vector3(0, 0.12f, -0.1f), new Vector3(0, 0.12f, 0.06f), 0.025f, metal, false, false);
            var spout = Point("SpoutTip", can.transform, new Vector3(0, 0.09f, 0.31f));
            var wc = can.AddComponent<WateringCan>();
            wc.spout = spout;
            wc.water = WaterStream(spout);
            var box = can.AddComponent<BoxCollider>();
            box.size = new Vector3(0.22f, 0.3f, 0.5f);
            box.center = new Vector3(0, -0.02f, 0.05f);
            Object.DestroyImmediate(canBody.GetComponent<Collider>());
            MakeGrabbable(can, false);
            can.AddComponent<ReturnIfLost>();

            // Street sights to spot by looking down
            var busker = LookTarget("Busker", game, new Vector3(1.5f, 0.16f, -6.5f), 0.5f);
            Person(busker, Vector3.zero, Mat("Jacket", new Color(0.2f, 0.45f, 0.75f)), skin);
            Box("Guitar", busker, new Vector3(0.25f, 0.9f, -0.2f), new Vector3(0.35f, 0.5f, 0.1f), Mat("GuitarWood", new Color(0.7f, 0.45f, 0.2f)), false, false);
            Cyl("Hat", busker, new Vector3(0.6f, 0, -0.3f), 0.18f, 0.08f, Mat("Felt", new Color(0.2f, 0.2f, 0.2f)), false, false);

            var fountain = LookTarget("Fountain", game, new Vector3(-9f, 0.16f, -18.5f), 1.2f);
            Cyl("Basin", fountain, Vector3.zero, 1.6f, 0.5f, Mat("Stone", new Color(0.75f, 0.75f, 0.78f)), true, false);
            Cyl("Water", fountain, new Vector3(0, 0.45f, 0), 1.45f, 0.05f, Mat("Pond", new Color(0.35f, 0.65f, 0.85f), 0.95f), false, false);
            Cyl("Column", fountain, Vector3.zero, 0.2f, 1.4f, Mat("Stone", new Color(0.75f, 0.75f, 0.78f)), false, false);
            var splash = WaterStream(fountain);
            splash.transform.localPosition = new Vector3(0, 1.45f, 0);
            splash.transform.localRotation = Quaternion.Euler(-90, 0, 0);
            var splashMain = splash.main;
            splashMain.playOnAwake = true;
            splashMain.loop = true;

            var dog = LookTarget("Dog", game, new Vector3(8f, 0.16f, -18f), 0.5f);
            var dogBody = Group("DogBody", dog);
            var fur = Mat("Fur", new Color(0.85f, 0.65f, 0.35f));
            Box("Torso", dogBody.transform, new Vector3(0, 0.35f, 0), new Vector3(0.3f, 0.25f, 0.6f), fur, false, false);
            Box("Head", dogBody.transform, new Vector3(0, 0.5f, 0.35f), new Vector3(0.22f, 0.22f, 0.25f), fur, false, false);
            for (int leg = 0; leg < 4; leg++)
                Box("Leg", dogBody.transform, new Vector3(leg % 2 == 0 ? -0.1f : 0.1f, 0.12f, leg < 2 ? 0.2f : -0.2f), new Vector3(0.07f, 0.24f, 0.07f), fur, false, false);
            var walk = dog.gameObject.AddComponent<LoopMover>();
            walk.points = new[] { new Vector3(4f, 0.16f, -18f), new Vector3(14f, 0.16f, -18f), new Vector3(14f, 0.16f, -19.5f), new Vector3(4f, 0.16f, -19.5f) };
            walk.speed = 1.2f;

            LookDownObjective Look(string desc, Transform target, string label)
            {
                var o = Group("Spot " + target.name, game).AddComponent<LookDownObjective>();
                o.description = desc;
                o.target = target;
                o.spotLabel = label;
                return o;
            }
            var lookBusker = Look("Look down: find the street musician", busker, "Listening to the busker...");
            var lookFountain = Look("Look down: find the fountain", fountain, "Watching the fountain...");
            var lookDog = Look("Look down: spot the dog on a walk", dog, "Following the dog...");
            lookDog.companionLineOnComplete = "Good boy! You looked straight down - huge step.";

            var reach = Zone<ReachObjective>("SkywalkEnd", game, new Vector3(-5f, B + 1.2f, -6.3f), new Vector3(2f, 2.4f, 1.2f));
            reach.description = "Walk to the end of the glass skywalk";
            reach.companionLineOnComplete = "You're standing on glass, six metres up. Look down - that's courage!";
            Zone<SayZone>("SkywalkHint", game, new Vector3(-5f, B + 1.2f, -2.2f), new Vector3(2.4f, 2.4f, 1.2f)).line =
                "The glass skywalk! It's strong, but it creaks. Keep walking, don't stop on it too long.";

            Star(game, new Vector3(-5f, B + 1.25f, -7.4f));
            Star(game, new Vector3(4.3f, B + 1.2f, -3.45f));
            Star(game, new Vector3(5.4f, B + 1.0f, -1.6f));

            Zone<GoalZone>("Goal (Cafe Door)", game, new Vector3(4f, B + 1.2f, -0.5f), new Vector3(1.6f, 2.4f, 1f));

            var lc = CommonLevel(0, "Level 1 - The Balcony", new Vector3(0f, B, -1.6f), 180f, 0f, 30f, 0.6f);
            lc.objectives = new Objective[] { water, lookBusker, lookFountain, lookDog, reach };
            lc.boardPoint = PanelPoint("Board", lc.transform, new Vector3(-2.2f, B + 1.75f, -0.06f), new Vector3(-2.2f, B + 1.6f, -2f));
            lc.introLines = new[]
            {
                "Welcome to the Sunset Cafe! We're on the balcony, two floors up - about six metres.",
                "Your tasks are on the board behind you. There's no rush. Go at your own pace.",
                "Remember: press X, or Esc, anytime to visit the Calm Meadow.",
            };
            lc.finishLine = "Level one complete! You looked down, leaned out and walked on glass.";
            Save(scene, GameManager.LevelScenes[0]);
        }

        /// <summary>Water particle stream (watering can, fountain).</summary>
        static ParticleSystem WaterStream(Transform parent)
        {
            var go = new GameObject("Water");
            go.transform.SetParent(parent, false);
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.playOnAwake = false;
            main.loop = true;
            main.startLifetime = 0.8f;
            main.startSpeed = 1.6f;
            main.startSize = new ParticleSystem.MinMaxCurve(0.02f, 0.05f);
            main.startColor = new Color(0.6f, 0.85f, 1f, 0.8f);
            main.gravityModifier = 1f;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            var em = ps.emission;
            em.rateOverTime = 80f;
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Cone;
            shape.angle = 6f;
            shape.radius = 0.01f;
            go.GetComponent<ParticleSystemRenderer>().sharedMaterial = ParticleMat();
            ps.Stop();
            return ps;
        }
    }
}