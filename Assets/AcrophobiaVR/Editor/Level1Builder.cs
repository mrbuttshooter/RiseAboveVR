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
            Sun(new Vector3(12, -35, 0), new Color(1f, 0.77f, 0.56f), 1.3f);

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
                Mat("Bldg1", new Color(0.70f, 0.46f, 0.38f)), Mat("Bldg2", new Color(0.86f, 0.82f, 0.74f)),
                Mat("Bldg3", new Color(0.74f, 0.75f, 0.77f)), Mat("Bldg4", new Color(0.48f, 0.36f, 0.32f)),
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

            Props.StreetDetails(env, new Vector3(-90f, 0.16f, -5.5f), new Vector3(90f, 0.16f, -5.5f), 2f, 7);
            Props.StreetDetails(env, new Vector3(-90f, 0.16f, -18.5f), new Vector3(90f, 0.16f, -18.5f), 2f, 8);
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
            // Three storeys: street cafe, the balcony floor, and a roof terrace at 13 m.
            const float RoofY = 13f;
            Box("Building", cafe, new Vector3(0, RoofY * 0.5f, 7), new Vector3(20, RoofY, 14), cafeWall);
            var frameMat = Mat("WindowFrame", new Color(0.22f, 0.16f, 0.12f), 0.3f);
            // Real window glass: dark and glossy (reflects the sky), with a faint warm glow from the lit interior.
            var cafeGlass = Mat("CafeGlassReal", new Color(0.05f, 0.055f, 0.06f), 0.96f, 0.1f);
            cafeGlass.EnableKeyword("_EMISSION");
            cafeGlass.SetColor("_EmissionColor", new Color(0.30f, 0.19f, 0.09f));
            cafeGlass.globalIlluminationFlags = MaterialGlobalIlluminationFlags.EmissiveIsBlack;
            var sillMat = Mat("Stone", new Color(0.75f, 0.75f, 0.78f));
            foreach (float y in new[] { 1.9f, 9.6f })
                for (int w = -4; w <= 4; w++)
                {
                    if (y > B && w == -3) continue; // the fire-escape ladder runs up here
                    Box("WindowFrame", cafe, new Vector3(w * 2.1f, y, -0.03f), new Vector3(1.25f, 1.65f, 0.06f), frameMat, false);
                    Box("Window", cafe, new Vector3(w * 2.1f, y, -0.07f), new Vector3(1.03f, 1.43f, 0.02f), cafeGlass, false);
                    Box("Sill", cafe, new Vector3(w * 2.1f, y - 0.86f, -0.12f), new Vector3(1.35f, 0.07f, 0.2f), sillMat, false);
                }
            // French doors onto the balcony
            foreach (float x in new[] { -3.6f, 0.4f })
            {
                Box("BalconyDoorFrame", cafe, new Vector3(x, B + 1.15f, -0.03f), new Vector3(1.5f, 2.35f, 0.06f), frameMat, false);
                Box("BalconyDoorGlass", cafe, new Vector3(x, B + 1.15f, -0.07f), new Vector3(1.3f, 2.15f, 0.02f), cafeGlass, false);
            }

            // Roof terrace: low parapet at the street edge (gap where the ladder arrives), taller walls elsewhere.
            var roof = Group("RoofTerrace", env).transform;
            Floor("RoofFloor", roof, -10f, 10f, 0f, 14f, RoofY + 0.05f, 0.3f, Mat("RoofGravel", new Color(0.55f, 0.55f, 0.55f)), true);
            var parapetMat = Mat("Concrete", new Color(0.7f, 0.7f, 0.68f));
            // Parapets only on Easy - on Normal / Hard the roof edge is a 10 cm kerb and a long drop.
            ShowIn(Box("ParapetFrontL", roof, new Vector3(-8.45f, RoofY + 0.25f, 0.15f), new Vector3(3.1f, 0.45f, 0.3f), parapetMat), true, false, false);
            ShowIn(Box("ParapetFrontR", roof, new Vector3(2.15f, RoofY + 0.25f, 0.15f), new Vector3(15.7f, 0.45f, 0.3f), parapetMat), true, false, false);
            ShowIn(Box("ParapetBack", roof, new Vector3(0f, RoofY + 0.55f, 13.85f), new Vector3(20f, 1.0f, 0.3f), parapetMat), true, false, false);
            ShowIn(Box("ParapetSideL", roof, new Vector3(-9.85f, RoofY + 0.55f, 7f), new Vector3(0.3f, 1.0f, 14f), parapetMat), true, false, false);
            ShowIn(Box("ParapetSideR", roof, new Vector3(9.85f, RoofY + 0.55f, 7f), new Vector3(0.3f, 1.0f, 14f), parapetMat), true, false, false);
            Kerb("KerbFront", roof, new Vector3(-10f, RoofY + 0.05f, 0.05f), new Vector3(10f, RoofY + 0.05f, 0.05f), parapetMat);
            Kerb("KerbBack", roof, new Vector3(-10f, RoofY + 0.05f, 13.95f), new Vector3(10f, RoofY + 0.05f, 13.95f), parapetMat);
            Kerb("KerbL", roof, new Vector3(-9.95f, RoofY + 0.05f, 0f), new Vector3(-9.95f, RoofY + 0.05f, 14f), parapetMat);
            Kerb("KerbR", roof, new Vector3(9.95f, RoofY + 0.05f, 0f), new Vector3(9.95f, RoofY + 0.05f, 14f), parapetMat);
            SafetyGlass("RoofGlassL", roof, new Vector3(-10f, RoofY, 0.1f), new Vector3(-6.9f, RoofY, 0.1f), 1.2f, glass);
            SafetyGlass("RoofGlassR", roof, new Vector3(-5.7f, RoofY, 0.1f), new Vector3(10f, RoofY, 0.1f), 1.2f, glass);
            // Classic New York rooftop water tower (Objaverse / Sketchfab, CC-BY); simple tank as a fallback.
            var tower = Model("Props/WaterTower", roof, new Vector3(-6.5f, RoofY + 0.05f, 11.2f), 7f, 15f);
            if (tower != null) SolidBounds(tower);
            else Cyl("WaterTank", roof, new Vector3(-6f, RoofY, 10f), 1.1f, 2.4f, Mat("TankWood", new Color(0.55f, 0.35f, 0.2f)));
            Props.RooftopUnits(roof, new Vector3(1f, RoofY + 0.05f, 10f), new Vector2(8f, 4f), 13);
            for (int s = 0; s < 3; s++)
                Props.Bench(roof, new Vector3(-2f + s * 3f, RoofY + 0.05f, 6.5f), 180f);
            // Sloped canvas awning (stops short of the window ledge) and a painted sign board with lettering.
            Prim(PrimitiveType.Cube, "Awning", cafe, new Vector3(-1f, 3.25f, -1f), new Vector3(10, 0.06f, 2.1f), cloth, false, true, new Vector3(-16f, 0f, 0f));
            Box("CafeSign", cafe, new Vector3(0, 4.2f, -0.1f), new Vector3(6, 0.9f, 0.12f), Mat("SignBoard", new Color(0.09f, 0.11f, 0.1f), 0.4f), false);
            var signText = new GameObject("CafeSignText").AddComponent<TMPro.TextMeshPro>();
            signText.transform.SetParent(cafe, false);
            signText.transform.localPosition = new Vector3(0f, 4.2f, -0.17f);
            signText.rectTransform.sizeDelta = new Vector2(5.6f, 0.8f);
            signText.text = "SUNSET CAFE";
            signText.fontSize = 6.5f;
            signText.characterSpacing = 12f;
            signText.alignment = TMPro.TextAlignmentOptions.Center;
            signText.color = new Color(0.93f, 0.78f, 0.45f);

            // Balcony slab, railings, decor
            var balcony = Group("Balcony", env).transform;
            Floor("BalconyFloor", balcony, -7f, 5f, -3f, 0f, B, 0.3f, wood, true);
            Box("BalconyTrim", balcony, new Vector3(-1, B - 0.4f, -3.02f), new Vector3(12.1f, 0.25f, 0.1f), trim, false);
            Kerb("BalconyKerbFront", balcony, new Vector3(-7f, B, -2.95f), new Vector3(5f, B, -2.95f), trim);
            Kerb("BalconyKerbL", balcony, new Vector3(-6.95f, B, -3f), new Vector3(-6.95f, B, 0f), trim);
            Railing("RailFrontLeft", balcony, new Vector3(-7f, B, -3f), new Vector3(-6f, B, -3f), 1.1f, metal);
            Railing("RailFrontRight", balcony, new Vector3(-4f, B, -3f), new Vector3(5f, B, -3f), 1.1f, metal);
            Railing("RailSideL", balcony, new Vector3(-7f, B, -3f), new Vector3(-7f, B, 0f), 1.1f, metal);
            // Gap at the wall end of the right rail: the narrow window ledge starts here.
            Railing("RailSideR", balcony, new Vector3(5f, B, -3f), new Vector3(5f, B, -0.75f), 1.1f, metal);
            SafetyGlass("GlassFrontRight", balcony, new Vector3(-4f, B, -3f), new Vector3(5f, B, -3f), 1.05f, glass);
            SafetyGlass("GlassFrontLeft", balcony, new Vector3(-7f, B, -3f), new Vector3(-6f, B, -3f), 1.05f, glass);
            SafetyGlass("GlassSideR", balcony, new Vector3(5f, B, -3f), new Vector3(5f, B, -0.75f), 1.05f, glass);
            // Photo-scanned bistro sets (Poly Haven, CC0); simple tables if the scan is missing.
            float[] setX = { -2.6f, 1.2f };
            for (int t = 0; t < setX.Length; t++)
            {
                var set = PolyProp("outdoor_table_chair_set_01", balcony, new Vector3(setX[t], B, -0.75f), t == 0 ? 0f : 180f);
                if (set != null) { SolidBounds(set); continue; }
                Cyl("TableLeg", balcony, new Vector3(setX[t], B, -0.8f), 0.05f, 0.72f, metal);
                Cyl("TableTop", balcony, new Vector3(setX[t], B + 0.72f, -0.8f), 0.4f, 0.04f, Mat("Marble", new Color(0.95f, 0.95f, 0.93f), 0.7f));
            }
            // Festoon lights: small bulbs hanging from a sagging black cable.
            var cable = Mat("Cable", new Color(0.03f, 0.03f, 0.03f), 0.4f);
            Vector3 Festoon(int i) => new Vector3(-6.8f + i * 1.0f, B + 2.6f - Mathf.Sin(i / 11f * Mathf.PI) * 0.35f, -2.6f);
            for (int s = 0; s < 12; s++)
            {
                if (s < 11) Bar("FestoonCable", balcony, Festoon(s) + Vector3.up * 0.06f, Festoon(s + 1) + Vector3.up * 0.06f, 0.008f, cable, false);
                Bar("BulbHolder", balcony, Festoon(s) + Vector3.up * 0.06f, Festoon(s) + Vector3.up * 0.02f, 0.015f, cable, false);
                Sphere("StringLight", balcony, Festoon(s), 0.05f, Glow("BulbWarm", new Color(1f, 0.85f, 0.5f), 4f));
            }
            Box("CafeDoor", balcony, new Vector3(4f, B + 1.1f, 0.02f), new Vector3(1.4f, 2.2f, 0.1f), Mat("DoorWood", new Color(0.35f, 0.2f, 0.12f)), false);
            SignBoard("DoorSign", balcony, new Vector3(4f, B + 2.45f, -0.05f), new Vector2(0.9f, 0.28f), "EXIT", Glow("ExitSignGreen", new Color(0.05f, 0.45f, 0.18f), 0.8f), Color.white, 2f);

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
                // Photo-scanned clay pot as the visual; the cylinder keeps its collider for the watering logic.
                if (PolyProp("planter_pot_clay", game, new Vector3(potX[i], B + 0.75f, -3.32f), 0f, 1f, 0.28f) != null)
                    pot.GetComponent<Renderer>().enabled = false;
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
            // Photo-scanned metal watering can as the visual (the primitive parts stay as hidden fallbacks).
            if (PolyProp("watering_can_metal_01", can.transform, new Vector3(0f, -0.12f, 0f), 0f, 1f, 0.3f) != null)
                foreach (var part in new[] { canBody.transform, spoutBar.transform, can.transform.Find("Handle") })
                    if (part != null) part.GetComponent<Renderer>().enabled = false;
            var wc = can.AddComponent<WateringCan>();
            wc.spout = spout;
            wc.water = WaterStream(spout);
            var box = can.AddComponent<BoxCollider>();
            box.size = new Vector3(0.22f, 0.3f, 0.5f);
            box.center = new Vector3(0, -0.02f, 0.05f);
            Object.DestroyImmediate(canBody.GetComponent<Collider>());
            var canGrab = MakeGrabbable(can, false);
            canGrab.attachTransform = Point("HandleAttach", can.transform, new Vector3(0f, 0.12f, -0.02f));
            can.AddComponent<ReturnIfLost>();

            // Street sights to spot by looking down
            var busker = LookTarget("Busker", game, new Vector3(1.5f, 0.16f, -6.5f), 0.5f);
            Person(busker, Vector3.zero, Mat("Jacket", new Color(0.2f, 0.45f, 0.75f)), skin);
            // Between songs: a real acoustic guitar leaning against the busker's leg (box fallback).
            var guitar = Model("Props/Guitar", busker, new Vector3(0.32f, 0f, 0.12f), 1.0f, 75f);
            if (guitar != null) guitar.transform.localRotation = Quaternion.Euler(0f, 0f, -12f) * guitar.transform.localRotation;
            else Box("Guitar", busker, new Vector3(0.25f, 0.9f, -0.2f), new Vector3(0.35f, 0.5f, 0.1f), Mat("GuitarWood", new Color(0.7f, 0.45f, 0.2f)), false, false);
            Cyl("Hat", busker, new Vector3(0.6f, 0, -0.3f), 0.18f, 0.08f, Mat("Felt", new Color(0.2f, 0.2f, 0.2f)), false, false);

            var fountain = LookTarget("Fountain", game, new Vector3(-9f, 0.16f, -18.5f), 1.2f);
            // Tiered stone fountain (Objaverse / Sketchfab, CC-BY), 3.4 m across; primitive basin as a fallback.
            var fountainModel = Model("Props/Fountain", fountain, Vector3.zero, 1.3f);
            if (fountainModel != null) SolidBounds(fountainModel);
            else
            {
                Cyl("Basin", fountain, Vector3.zero, 1.6f, 0.5f, Mat("Stone", new Color(0.75f, 0.75f, 0.78f)), true, false);
                Cyl("Water", fountain, new Vector3(0, 0.45f, 0), 1.45f, 0.05f, Mat("Pond", new Color(0.35f, 0.65f, 0.85f), 0.95f), false, false);
                Cyl("Column", fountain, Vector3.zero, 0.2f, 1.4f, Mat("Stone", new Color(0.75f, 0.75f, 0.78f)), false, false);
            }
            var splash = WaterStream(fountain);
            splash.transform.localPosition = new Vector3(0, fountainModel != null ? 1.3f : 1.45f, 0);
            splash.transform.localRotation = Quaternion.Euler(-90, 0, 0);
            var splashMain = splash.main;
            splashMain.playOnAwake = true;
            splashMain.loop = true;

            var dog = LookTarget("Dog", game, new Vector3(8f, 0.16f, -18f), 0.5f);
            // Gemini-made model; primitive fallback if the file is missing.
            // Realistic scanned/sculpted animals (Objaverse / Sketchfab, CC-BY - see Models/Animals/CREDITS.txt) first.
            if (Model("Animals/Biscuit", dog, Vector3.zero, 0.62f) == null && Model("Biscuit", dog, Vector3.zero, 0.6f) == null)
            {
                var dogBody = Group("DogBody", dog);
                var fur = Mat("Fur", new Color(0.85f, 0.65f, 0.35f));
                Box("Torso", dogBody.transform, new Vector3(0, 0.35f, 0), new Vector3(0.3f, 0.25f, 0.6f), fur, false, false);
                Box("Head", dogBody.transform, new Vector3(0, 0.5f, 0.35f), new Vector3(0.22f, 0.22f, 0.25f), fur, false, false);
                for (int leg = 0; leg < 4; leg++)
                    Box("Leg", dogBody.transform, new Vector3(leg % 2 == 0 ? -0.1f : 0.1f, 0.12f, leg < 2 ? 0.2f : -0.2f), new Vector3(0.07f, 0.24f, 0.07f), fur, false, false);
            }
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

            // ---- The window ledge: rescue Kiwi the parrot (narrow, 35 cm, street 6 m below)
            const float RoofTop = 13.05f;
            var ledgeRoot = Group("WindowLedge", game).transform;
            // A chunk of the ledge has crumbled away: a 35 cm gap you step over with the street right below.
            var ledgeStone = Mat("Stone", new Color(0.75f, 0.75f, 0.78f));
            BoxMinMax("Ledge", ledgeRoot, new Vector3(4.95f, B - 0.12f, -0.4f), new Vector3(7.25f, B, 0f), ledgeStone, true, false);
            BoxMinMax("Ledge2", ledgeRoot, new Vector3(7.6f, B - 0.12f, -0.4f), new Vector3(10.2f, B, 0f), ledgeStone, true, false);
            BoxMinMax("LedgeRubble", ledgeRoot, new Vector3(7.25f, B - 0.12f, -0.12f), new Vector3(7.6f, B - 0.07f, 0f), ledgeStone, false, false);
            Zone<SayZone>("GapHint", game, new Vector3(6.6f, B + 1.2f, -0.25f), new Vector3(0.6f, 2.4f, 0.8f)).line =
                "Part of the ledge has crumbled away! Step over the gap - long stride, don't look down... or do.";
            // Pigeons roost on the far half of the ledge - they burst out when you get close.
            var pigeons = Group("Pigeons", game);
            pigeons.transform.position = new Vector3(8.6f, B + 0.02f, -0.18f);
            pigeons.transform.rotation = Quaternion.Euler(0, -90, 0);
            var startle = pigeons.AddComponent<StartleBirds>();
            startle.fleeDirection = new Vector3(0.4f, 0f, -1f);
            startle.bodyMaterial = Mat("PigeonGrey", new Color(0.55f, 0.57f, 0.62f), 0.35f);
            startle.wingMaterial = Mat("PigeonWing", new Color(0.42f, 0.44f, 0.5f), 0.3f);
            startle.birdPrefab = UnityEditor.AssetDatabase.LoadAssetAtPath<GameObject>(ModelFolder + "Animals/Pigeon.fbx")
                ?? UnityEditor.AssetDatabase.LoadAssetAtPath<GameObject>(ModelFolder + "Pigeon.fbx");
            var ledgeBeam = ledgeRoot.gameObject.AddComponent<BalanceBeam>();
            ledgeBeam.start = Point("Start", ledgeRoot, new Vector3(5.0f, B, -0.2f));
            ledgeBeam.end = Point("End", ledgeRoot, new Vector3(10.0f, B, -0.2f));
            ledgeBeam.walkableHalfWidth = 0.2f;
            ledgeBeam.driftFillRate = 0.5f;
            var ledgeRail = Bar("LedgeHandrail", ledgeRoot, new Vector3(5.0f, B + 1.0f, -0.06f), new Vector3(10.0f, B + 1.0f, -0.06f), 0.04f, metal, true, false);
            ShowIn(ledgeRail, true, false, false);
            Zone<SayZone>("LedgeHint", game, new Vector3(4.3f, B + 1.2f, -0.5f), new Vector3(1.2f, 2.4f, 1f)).line =
                "Kiwi the parrot escaped onto the window ledge! Face the wall, side-step slowly and keep your body close to the building.";

            var parrot = Group("Kiwi (Parrot)", game);
            parrot.transform.position = new Vector3(9.6f, B + 0.02f, -0.2f);
            parrot.transform.rotation = Quaternion.Euler(0, -90, 0);
            // Gemini-made model (Assets/AcrophobiaVR/Models/Kiwi.fbx); primitive fallback if it is missing.
            if (Model("Animals/Kiwi", parrot.transform, Vector3.zero, 0.42f) == null && Model("Kiwi", parrot.transform, Vector3.zero, 0.42f) == null)
            {
                var feathers = Mat("ParrotGreen", new Color(0.2f, 0.75f, 0.3f), 0.5f);
                Prim(PrimitiveType.Capsule, "Body", parrot.transform, new Vector3(0, 0.2f, 0), new Vector3(0.16f, 0.16f, 0.16f), feathers, false, false);
                Sphere("Head", parrot.transform, new Vector3(0, 0.38f, 0.04f), 0.13f, Mat("ParrotRed", new Color(0.9f, 0.2f, 0.15f), 0.5f), false, false);
                Prim(PrimitiveType.Cube, "Beak", parrot.transform, new Vector3(0, 0.37f, 0.12f), new Vector3(0.04f, 0.05f, 0.07f), Mat("PipBeak", new Color(1f, 0.7f, 0.2f)), false, false);
                Bar("Tail", parrot.transform, new Vector3(0, 0.12f, -0.06f), new Vector3(0, 0.02f, -0.3f), 0.05f, Mat("ParrotBlue", new Color(0.2f, 0.35f, 0.9f), 0.5f), false, false);
            }
            var parrotCol = parrot.AddComponent<BoxCollider>();
            parrotCol.size = new Vector3(0.25f, 0.5f, 0.45f);
            parrotCol.center = new Vector3(0, 0.22f, 0);
            MakeGrabbable(parrot, true);
            var kiwi = parrot.AddComponent<Collectible>();
            kiwi.displayName = "Kiwi the parrot";
            kiwi.isBird = true;
            var rescue = Group("RescueParrot", game).AddComponent<CollectObjective>();
            rescue.description = "Rescue Kiwi the parrot from the window ledge";
            rescue.companionLineOnComplete = "Got her! Kiwi is safe - and you walked a ledge as wide as a shoebox.";
            rescue.items.Add(kiwi);

            // ---- Fire escape: climb the ladder to the roof terrace (13 m)
            var ladderGo = Group("FireEscapeLadder", game);
            var ladder = ladderGo.AddComponent<Ladder>();
            AddClimbRungs(ladderGo.transform, new Vector3(-6.3f, B, -0.15f), new Vector3(-6.3f, RoofTop + 1.2f, -0.15f), 0.6f, metal);
            ladder.bottom = Point("Bottom", ladderGo.transform, new Vector3(-6.3f, B, -0.15f));
            ladder.top = Point("Top", ladderGo.transform, new Vector3(-6.3f, RoofTop, -0.15f));
            ladder.topExit = Point("TopExit", ladderGo.transform, new Vector3(-6.3f, RoofTop, 1.3f), 0f);
            Zone<SayZone>("LadderHint", game, new Vector3(-6.3f, B + 1.2f, -0.7f), new Vector3(1.4f, 2.4f, 1f)).line =
                "The fire-escape ladder goes all the way to the roof. Hand over hand - and don't look down... unless you want to!";
            var climbRoof = Zone<ReachObjective>("ReachRoof", game, new Vector3(-6.3f, RoofTop + 1.2f, 2.0f), new Vector3(3f, 2.4f, 3f));
            climbRoof.description = "Climb the fire-escape ladder to the roof (13 m)";
            climbRoof.companionLineOnComplete = "Thirteen metres - more than double where we started. Look at that view!";
            var cpRoof = Zone<CheckpointZone>("CP Roof", game, new Vector3(-4f, RoofTop + 1.2f, 3f), new Vector3(8f, 2.4f, 5f));
            cpRoof.label = "Roof terrace (13 m)";
            cpRoof.respawnPoint = Point("CP Roof Spawn", game, new Vector3(-5f, RoofTop, 2.5f), 180f);
            // Wind on the roof: gusts shove you towards the street. Crouch to hold on.
            var roofWind = Group("RoofWind", game).AddComponent<GustZone>();
            // Covers the roof right up to the street edge, except the strip by the ladder where you arrive.
            roofWind.transform.position = new Vector3(2.75f, RoofTop + 1.5f, 6.5f);
            roofWind.size = new Vector3(14.5f, 4f, 13f);
            roofWind.pushDirection = new Vector3(0f, 0f, -1f);
            roofWind.interval = new Vector2(8f, 13f);
            roofWind.pushSpeed = 1.1f;

            // ---- Rooftop bell: the finale
            // A small bell frame (two posts and a beam) so the bell is visible from every side and swings from its pivot.
            Bar("BellPostL", game, new Vector3(6.05f, RoofTop, 2.3f), new Vector3(6.05f, RoofTop + 1.95f, 2.3f), 0.07f, metal, true, false);
            Bar("BellPostR", game, new Vector3(6.95f, RoofTop, 2.3f), new Vector3(6.95f, RoofTop + 1.95f, 2.3f), 0.07f, metal, true, false);
            Bar("BellBeam", game, new Vector3(6.0f, RoofTop + 1.95f, 2.3f), new Vector3(7.0f, RoofTop + 1.95f, 2.3f), 0.09f, metal, true, false);
            var bell = Group("Bell", game);
            bell.transform.position = new Vector3(6.5f, RoofTop + 1.9f, 2.3f); // pivot under the beam
            var brass = Mat("BellBrass", new Color(0.85f, 0.65f, 0.25f), 0.85f, 0.9f);
            Bar("BellHanger", bell.transform, Vector3.zero, new Vector3(0f, -0.14f, 0f), 0.04f, metal, false, false);
            Sphere("BellDome", bell.transform, new Vector3(0f, -0.26f, 0f), 0.3f, brass, false, false);
            Cyl("BellBody", bell.transform, new Vector3(0f, -0.62f, 0f), 0.19f, 0.36f, brass, true, false);
            Cyl("BellLip", bell.transform, new Vector3(0f, -0.66f, 0f), 0.23f, 0.06f, brass, false, false);
            Sphere("Clapper", bell.transform, new Vector3(0f, -0.7f, 0f), 0.09f, metal, false, false);
            var bellButton = bell.AddComponent<PressButton>();
            bellButton.hint = "Ring the bell!";
            bellButton.bell = true;
            bell.AddComponent<UnityEngine.XR.Interaction.Toolkit.Interactables.XRSimpleInteractable>();
            var ring = Group("RingBell", game).AddComponent<PressObjective>();
            ring.description = "Ring the bell on the rooftop";
            ring.button = bellButton;
            Zone<GoalZone>("Goal (Rooftop Bell)", game, new Vector3(6.5f, RoofTop + 1.2f, 2.5f), new Vector3(3.5f, 2.4f, 3.5f));

            Star(game, new Vector3(10.35f, B + 1.1f, -0.55f));
            Star(game, new Vector3(-9.4f, RoofTop + 1.3f, -0.05f)); // lean over the roof parapet

            // Photo-scanned street dressing (CC0 Poly Haven).
            var dress = Group("ScanDressing", env).transform;
            PolyProp("metal_trash_can", dress, new Vector3(7.2f, 0.16f, -4.8f), 20f);
            PolyProp("trashbag", dress, new Vector3(7.9f, 0.16f, -5.1f), 60f);
            PolyProp("trashbag", dress, new Vector3(7.6f, 0.16f, -4.4f), 200f);
            PolyProp("metal_trash_can", dress, new Vector3(-8.5f, 0.16f, -5.2f), -30f);
            PolyProp("utility_box_01", dress, new Vector3(-10.5f, 0.16f, -4.6f), 90f);
            PolyProp("utility_box_02", dress, new Vector3(13.5f, 0.16f, -4.4f), 0f);
            PolyProp("fire_hydrant", dress, new Vector3(-3.2f, 0.16f, -7.4f), 90f);
            foreach (float mx in new[] { -26f, -4f, 18f })
                PolyProp("water_manhole_cover", dress, new Vector3(mx, 0.03f, -12f), 15f);
            // Zebra crossing with a traffic light on each kerb (Objaverse / Sketchfab, CC-BY - see Models/Props/CREDITS.txt).
            var zebra = Mat("ZebraPaint", new Color(0.92f, 0.92f, 0.9f), 0.25f);
            for (int k = 0; k < 7; k++)
                Box("ZebraStripe", dress, new Vector3(-14f + (k - 3) * 0.95f, 0.026f, -12f), new Vector3(0.5f, 0.01f, 7.4f), zebra, false);
            Model("Props/TrafficLight", dress, new Vector3(-17.6f, 0.16f, -8.4f), 3.2f, 90f);
            Model("Props/TrafficLight", dress, new Vector3(-10.4f, 0.16f, -15.6f), 3.2f, -90f);
            // Patio umbrella over the roof-terrace benches.
            Model("Props/PatioUmbrella", dress, new Vector3(-5.2f, RoofY + 0.05f, 8.5f), 2.4f, 20f);
            // A potted money tree in the balcony corner.
            PolyProp("pachira_aquatica_01", dress, new Vector3(-6.45f, B, -0.45f), 30f, 1f, 1.6f);

            var lc = CommonLevel(0, "Level 1 - The Cafe", new Vector3(0f, B, -1.6f), 180f, 0f, 30f, 0.6f);
            lc.objectives = new Objective[] { water, lookBusker, lookFountain, lookDog, reach, rescue, climbRoof, ring };
            lc.boardPoint = PanelPoint("Board", lc.transform, new Vector3(-2.2f, B + 1.75f, -0.06f), new Vector3(-2.2f, B + 1.6f, -2f));
            lc.introLines = new[]
            {
                "Welcome to the Sunset Cafe! We start on the balcony, six metres up - and we'll finish on the roof at thirteen.",
                "Kiwi, the cafe's parrot, has escaped onto the window ledge. We'll need your help to get her back.",
                "No railings out here, and you've got three lives. Your tasks are on the board behind you - press Esc or X to pause.",
            };
            lc.finishLine = "Ding ding! Level one complete - a ledge, a ladder and a rooftop. That was brave!";
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