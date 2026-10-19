using System.Collections.Generic;
using UnityEngine;
using static AcrophobiaVR.EditorTools.BuildKit;

namespace AcrophobiaVR.EditorTools
{
    /// <summary>
    /// More realistic (but still primitive-based, Quest-friendly) props: trees, bushes, cars, street lamps,
    /// benches, people, rooftop plant and street furniture. Deterministic via System.Random(seed).
    /// </summary>
    public static class Props
    {
        // ---------- shared materials (names are cache keys => shared assets) ----------
        static Material Bark => Mat("Bark", new Color(0.33f, 0.23f, 0.15f), 0.15f);
        static Material LampMetal => Mat("LampMetal", new Color(0.12f, 0.12f, 0.13f), 0.5f, 0.8f);
        static Material BenchWood => Mat("BenchWood", new Color(0.5f, 0.33f, 0.2f), 0.3f);
        static Material LampWarm => Glow("LampWarm", new Color(1f, 0.85f, 0.6f), 3f);

        static Material Leaf(int i)
        {
            switch (i % 3)
            {
                case 0: return Mat("Leaf0", new Color(0.18f, 0.36f, 0.13f), 0.12f);
                case 1: return Mat("Leaf1", new Color(0.25f, 0.45f, 0.17f), 0.12f);
                default: return Mat("Leaf2", new Color(0.13f, 0.28f, 0.11f), 0.12f);
            }
        }

        static float R(System.Random rng, float a, float b) => a + (float)rng.NextDouble() * (b - a);

        static Transform Anchor(string name, Transform parent, Vector3 pos, float yaw)
        {
            var t = Group(name, parent).transform;
            t.localPosition = pos;
            t.localRotation = Quaternion.Euler(0f, yaw, 0f);
            return t;
        }

        // =====================================================================================
        // Vegetation
        // =====================================================================================

        /// <summary>Tapered, slightly leaning trunk, a few branches and a lumpy multi-shade canopy (~13 prims).</summary>
        public static void Tree(Transform parent, Vector3 basePos, float scale, int seed)
        {
            var rng = new System.Random(seed);
            float s = Mathf.Max(0.1f, scale);
            var g = Group("Tree", parent).transform;
            g.localPosition = basePos;
            g.localRotation = Quaternion.Euler(R(rng, -4f, 4f), R(rng, 0f, 360f), R(rng, -4f, 4f));

            float h1 = R(rng, 1.4f, 1.8f) * s;
            float h2 = R(rng, 1.1f, 1.5f) * s;
            Cyl("Trunk", g, Vector3.zero, 0.17f * s, h1, Bark, true, true);
            Cyl("TrunkUpper", g, new Vector3(0f, h1, 0f), 0.11f * s, h2, Bark, false, true);

            int branches = 2 + rng.Next(2);
            float a0 = R(rng, 0f, Mathf.PI * 2f);
            for (int i = 0; i < branches; i++)
            {
                float a = a0 + i * Mathf.PI * 2f / branches + R(rng, -0.4f, 0.4f);
                float y = h1 * R(rng, 0.75f, 1.05f);
                Vector3 from = new Vector3(0f, y, 0f);
                Vector3 to = new Vector3(Mathf.Cos(a) * 0.95f * s, y + R(rng, 0.6f, 0.9f) * s, Mathf.Sin(a) * 0.95f * s);
                Bar("Branch", g, from, to, 0.08f * s, Bark, false, true);
            }

            float cy = h1 + h2 * 0.75f + 0.5f * s;
            int blobs = 5 + rng.Next(4);
            for (int i = 0; i < blobs; i++)
            {
                Vector3 off = i == 0
                    ? new Vector3(0f, 0.35f * s, 0f)
                    : new Vector3(R(rng, -0.95f, 0.95f), R(rng, -0.45f, 0.55f), R(rng, -0.95f, 0.95f)) * s;
                float d = (i == 0 ? R(rng, 1.9f, 2.3f) : R(rng, 1.25f, 1.9f)) * s;
                float flat = R(rng, 0.7f, 0.92f);
                Prim(PrimitiveType.Sphere, "Leaves", g, new Vector3(off.x, cy + off.y, off.z),
                    new Vector3(d, d * flat, d * R(rng, 0.9f, 1.1f)), Leaf(rng.Next(3)), false, true);
            }
        }

        /// <summary>Low cluster of 3-4 flattened leaf spheres.</summary>
        public static void Bush(Transform parent, Vector3 pos, float scale, int seed)
        {
            var rng = new System.Random(seed);
            float s = Mathf.Max(0.1f, scale);
            var g = Anchor("Bush", parent, pos, R(rng, 0f, 360f));
            int n = 3 + rng.Next(2);
            for (int i = 0; i < n; i++)
            {
                float d = R(rng, 0.65f, 1.05f) * s;
                Vector3 off = i == 0 ? Vector3.zero : new Vector3(R(rng, -0.4f, 0.4f), 0f, R(rng, -0.4f, 0.4f)) * s;
                float flat = R(rng, 0.7f, 0.9f);
                Prim(PrimitiveType.Sphere, "BushLeaves", g, new Vector3(off.x, d * flat * 0.42f, off.z),
                    new Vector3(d, d * flat, d), Leaf(rng.Next(3)), false, true);
            }
        }

        // =====================================================================================
        // Vehicles
        // =====================================================================================

        /// <summary>
        /// Sedan/hatchback (~4.3m along local +Z, 1.8 wide, 1.45 tall) driven by LoopMover. 18 prims, no colliders, not static.
        /// </summary>
        public static GameObject Car(Transform parent, Vector3[] loop, float offset, float speed, Color bodyColor, int seed)
        {
            var rng = new System.Random(seed);
            var root = Group("Car", parent);
            var t = root.transform;

            var paint = Mat("CarPaint_" + ColorUtility.ToHtmlStringRGB(bodyColor), bodyColor, 0.85f, 0.5f);
            var glass = Mat("CarGlass", new Color(0.12f, 0.15f, 0.2f), 0.95f, 0.2f);
            var tyre = Mat("Tyre", new Color(0.05f, 0.05f, 0.05f), 0.2f);
            var rim = Mat("CarRim", new Color(0.72f, 0.73f, 0.75f), 0.7f, 0.9f);
            var trim = Mat("CarTrim", new Color(0.08f, 0.08f, 0.09f), 0.4f);
            var head = Glow("CarHeadlight", new Color(1f, 0.95f, 0.8f), 2.5f);
            var tail = Glow("CarTaillight", new Color(0.95f, 0.06f, 0.05f), 2f);

            bool hatch = rng.NextDouble() < 0.3;
            float cabinBack = hatch ? -1.75f : -1.15f;
            float cabinFront = R(rng, 0.95f, 1.1f);

            // Lower body (sills + doors), hood, trunk
            Box("Body", t, new Vector3(0f, 0.57f, 0f), new Vector3(1.76f, 0.44f, 4.1f), paint, false, false);
            float hoodLen = 2.05f - cabinFront;
            Box("Hood", t, new Vector3(0f, 0.85f, cabinFront + hoodLen * 0.5f), new Vector3(1.7f, 0.14f, hoodLen), paint, false, false);
            float trunkLen = cabinBack + 2.05f;
            Box("Trunk", t, new Vector3(0f, 0.87f, -2.05f + trunkLen * 0.5f), new Vector3(1.7f, 0.18f, trunkLen), paint, false, false);

            // Glass cabin with painted roof slab
            float cabLen = cabinFront - cabinBack;
            float cabMid = (cabinFront + cabinBack) * 0.5f;
            Box("Cabin", t, new Vector3(0f, 1.08f, cabMid), new Vector3(1.56f, 0.6f, cabLen), glass, false, false);
            Box("Roof", t, new Vector3(0f, 1.415f, cabMid - 0.05f), new Vector3(1.5f, 0.07f, cabLen * 0.8f), paint, false, false);

            // Wheels + rims (cylinder axis rotated onto X)
            for (int i = 0; i < 4; i++)
            {
                float x = (i % 2 == 0 ? -1f : 1f) * 0.8f;
                float z = i < 2 ? 1.35f : -1.35f;
                var p = new Vector3(x, 0.33f, z);
                Prim(PrimitiveType.Cylinder, "Wheel", t, p, new Vector3(0.66f, 0.12f, 0.66f), tyre, false, false, new Vector3(0f, 0f, 90f));
                Prim(PrimitiveType.Cylinder, "Rim", t, p, new Vector3(0.4f, 0.125f, 0.4f), rim, false, false, new Vector3(0f, 0f, 90f));
            }

            // Lights and bumpers
            Box("HeadlightL", t, new Vector3(-0.62f, 0.69f, 2.065f), new Vector3(0.36f, 0.12f, 0.04f), head, false, false);
            Box("HeadlightR", t, new Vector3(0.62f, 0.69f, 2.065f), new Vector3(0.36f, 0.12f, 0.04f), head, false, false);
            Box("TaillightL", t, new Vector3(-0.65f, 0.71f, -2.065f), new Vector3(0.32f, 0.1f, 0.04f), tail, false, false);
            Box("TaillightR", t, new Vector3(0.65f, 0.71f, -2.065f), new Vector3(0.32f, 0.1f, 0.04f), tail, false, false);
            Box("BumperFront", t, new Vector3(0f, 0.42f, 2.12f), new Vector3(1.8f, 0.2f, 0.16f), trim, false, false);
            Box("BumperRear", t, new Vector3(0f, 0.42f, -2.12f), new Vector3(1.8f, 0.2f, 0.16f), trim, false, false);

            var mover = root.AddComponent<LoopMover>();
            mover.points = loop;
            mover.speed = speed;
            mover.startOffset = offset;

            PlaceOnLoop(t, loop, offset);
            return root;
        }

        /// <summary>Editor preview: put the car where LoopMover will start it (LoopMover uses world space).</summary>
        static void PlaceOnLoop(Transform t, Vector3[] loop, float offset)
        {
            if (loop == null || loop.Length < 2) return;
            float total = 0f;
            for (int i = 0; i < loop.Length; i++) total += Vector3.Distance(loop[i], loop[(i + 1) % loop.Length]);
            if (total <= 0f) { t.position = loop[0]; return; }
            float dist = Mathf.Repeat(offset, 1f) * total;
            for (int i = 0; i < loop.Length; i++)
            {
                Vector3 a = loop[i], b = loop[(i + 1) % loop.Length];
                float seg = Vector3.Distance(a, b);
                if (dist <= seg || i == loop.Length - 1)
                {
                    t.position = Vector3.Lerp(a, b, seg > 0f ? Mathf.Clamp01(dist / seg) : 0f);
                    if ((b - a).sqrMagnitude > 0.001f) t.rotation = Quaternion.LookRotation(b - a);
                    return;
                }
                dist -= seg;
            }
        }

        // =====================================================================================
        // Street furniture
        // =====================================================================================

        /// <summary>5m dark-metal lamp post with curved arm reaching along local +Z; emissive lens, no Light (7 prims).</summary>
        public static void StreetLamp(Transform parent, Vector3 basePos, float yaw)
        {
            var g = Anchor("StreetLamp", parent, basePos, yaw);
            var metal = LampMetal;
            Cyl("Base", g, Vector3.zero, 0.14f, 0.4f, metal, true, true);
            // No collider on the pole: a player falling off a balcony must not end up balanced on top of it.
            Cyl("Pole", g, new Vector3(0f, 0.4f, 0f), 0.065f, 4.6f, metal, false, true);
            Sphere("Cap", g, new Vector3(0f, 5.0f, 0f), 0.15f, metal, false, true);
            Bar("ArmA", g, new Vector3(0f, 4.82f, 0f), new Vector3(0f, 5.16f, 0.45f), 0.07f, metal, false, true);
            Bar("ArmB", g, new Vector3(0f, 5.16f, 0.45f), new Vector3(0f, 5.12f, 1.35f), 0.07f, metal, false, true);
            Box("Head", g, new Vector3(0f, 5.08f, 1.5f), new Vector3(0.32f, 0.14f, 0.62f), metal, false, true);
            Box("Lens", g, new Vector3(0f, 5.0f, 1.5f), new Vector3(0.26f, 0.03f, 0.52f), LampWarm, false, true);
        }

        /// <summary>1.8m slatted bench (length along local X, sitting side facing +Z) on metal legs (11 prims).</summary>
        public static void Bench(Transform parent, Vector3 pos, float yaw)
        {
            var g = Anchor("Bench", parent, pos, yaw);
            var wood = BenchWood;
            var metal = LampMetal;

            for (int i = 0; i < 4; i++)
            {
                float z = -0.165f + i * 0.11f;
                Box("SeatSlat", g, new Vector3(0f, 0.45f, z), new Vector3(1.8f, 0.04f, 0.1f), wood, false, true);
            }

            const float tilt = 12f;
            float tan = Mathf.Tan(tilt * Mathf.Deg2Rad);
            for (int i = 0; i < 3; i++)
            {
                float y = 0.6f + i * 0.12f;
                float z = -0.25f - (y - 0.5f) * tan;
                Prim(PrimitiveType.Cube, "BackSlat", g, new Vector3(0f, y, z), new Vector3(1.8f, 0.09f, 0.03f), wood, false, true, new Vector3(-tilt, 0f, 0f));
            }

            for (int side = -1; side <= 1; side += 2)
            {
                float x = side * 0.75f;
                Bar("LegFront", g, new Vector3(x, 0f, 0.17f), new Vector3(x, 0.43f, 0.17f), 0.05f, metal, false, true);
                Bar("LegBack", g, new Vector3(x, 0f, -0.2f), new Vector3(x, 0.9f, -0.33f), 0.05f, metal, false, true);
            }
        }

        // =====================================================================================
        // People
        // =====================================================================================

        /// <summary>~1.75m pedestrian: trousers, shoes, torso, arms, hands, neck, head and hair cap. No colliders, not static (12 prims).</summary>
        public static void Person(Transform parent, Vector3 basePos, Color clothes, int seed)
        {
            var rng = new System.Random(seed);
            var g = Anchor("Person", parent, basePos, R(rng, 0f, 360f));

            Color[] skins = { new Color(0.96f, 0.80f, 0.69f), new Color(0.78f, 0.57f, 0.44f), new Color(0.45f, 0.31f, 0.22f) };
            Color[] hairs = { new Color(0.08f, 0.06f, 0.05f), new Color(0.32f, 0.2f, 0.11f), new Color(0.62f, 0.48f, 0.3f) };
            Color[] pants = { new Color(0.12f, 0.14f, 0.2f), new Color(0.17f, 0.16f, 0.14f) };

            int si = rng.Next(3), hi = rng.Next(3), pi = rng.Next(2);
            var skin = Mat("Skin" + si, skins[si], 0.35f);
            var hair = Mat("Hair" + hi, hairs[hi], 0.25f);
            var trousers = Mat("Trousers" + pi, pants[pi], 0.15f);
            var shoes = Mat("Shoes", new Color(0.06f, 0.06f, 0.06f), 0.4f);
            var cloth = Mat("Clothes_" + ColorUtility.ToHtmlStringRGB(clothes), clothes, 0.2f);

            float sc = R(rng, 0.95f, 1.03f);

            // Gemini Argon pedestrian model, recoloured per person (jacket / skin / hair / trousers).
            var person = Model("Pedestrian", g, Vector3.zero, 1.75f * sc);
            if (person != null)
            {
                foreach (var r in person.GetComponentsInChildren<Renderer>(true))
                {
                    var mats = r.sharedMaterials;
                    for (int i = 0; i < mats.Length; i++)
                    {
                        string n = mats[i] != null ? mats[i].name : "";
                        if (n.StartsWith("Mat_Jacket")) mats[i] = cloth;
                        else if (n.StartsWith("Mat_Skin")) mats[i] = skin;
                        else if (n.StartsWith("Mat_Hair")) mats[i] = hair;
                        else if (n.StartsWith("Mat_Jeans")) mats[i] = trousers;
                    }
                    r.sharedMaterials = mats;
                }
                return;
            }
            g.localScale = Vector3.one * sc;

            for (int side = -1; side <= 1; side += 2)
            {
                float x = side * 0.1f;
                Prim(PrimitiveType.Capsule, "Leg", g, new Vector3(x, 0.46f, 0f), new Vector3(0.14f, 0.43f, 0.15f), trousers, false, false);
                Box("Shoe", g, new Vector3(x, 0.04f, 0.04f), new Vector3(0.11f, 0.08f, 0.26f), shoes, false, false);
                Prim(PrimitiveType.Capsule, "Arm", g, new Vector3(side * 0.25f, 1.14f, 0f), new Vector3(0.1f, 0.31f, 0.1f), cloth, false, false, new Vector3(0f, 0f, side * 6f));
                Sphere("Hand", g, new Vector3(side * 0.285f, 0.8f, 0f), 0.09f, skin, false, false);
            }

            Prim(PrimitiveType.Capsule, "Torso", g, new Vector3(0f, 1.18f, 0f), new Vector3(0.38f, 0.33f, 0.24f), cloth, false, false);
            Cyl("Neck", g, new Vector3(0f, 1.47f, 0f), 0.05f, 0.1f, skin, false, false);
            Prim(PrimitiveType.Sphere, "Head", g, new Vector3(0f, 1.64f, 0f), new Vector3(0.19f, 0.23f, 0.21f), skin, false, false);
            Prim(PrimitiveType.Sphere, "Hair", g, new Vector3(0f, 1.685f, -0.025f), new Vector3(0.205f, 0.2f, 0.21f), hair, false, false);
        }

        // =====================================================================================
        // Rooftops
        // =====================================================================================

        /// <summary>
        /// Rooftop plant inside 80% of the roof: stair/elevator housing with door, 2-5 AC units with fan grilles,
        /// and 2-3 vent pipes. roofCenter.y = roof top height. Static, no colliders (~18 prims).
        /// </summary>
        public static void RooftopUnits(Transform parent, Vector3 roofCenter, Vector2 roofSize, int seed)
        {
            var rng = new System.Random(seed);
            float hx = Mathf.Abs(roofSize.x) * 0.4f;
            float hz = Mathf.Abs(roofSize.y) * 0.4f;
            if (hx < 0.6f || hz < 0.6f) return; // too small: don't leave an empty group behind
            var g = Anchor("RooftopUnits", parent, roofCenter, 0f);

            var housingMat = Mat("RoofHousing", new Color(0.55f, 0.54f, 0.52f), 0.15f);
            var doorMat = Mat("RoofDoor", new Color(0.22f, 0.23f, 0.25f), 0.35f, 0.5f);
            var acMat = Mat("ACUnit", new Color(0.72f, 0.73f, 0.72f), 0.35f, 0.3f);
            var grille = Mat("FanGrille", new Color(0.08f, 0.08f, 0.09f), 0.3f, 0.5f);
            var pipe = Mat("VentPipe", new Color(0.6f, 0.6f, 0.62f), 0.5f, 0.7f);

            var used = new List<Rect>();

            // Stair / elevator housing
            float hw = Mathf.Min(3.2f, hx * 0.8f), hd = Mathf.Min(3.6f, hz * 0.8f), hh = 2.8f;
            Vector2 hp = Pick(rng, hx, hz, hw * 0.5f, hd * 0.5f);
            if (hw >= 1.2f && hd >= 1.2f) // skip on tiny roofs (would be a thin 2.8m pillar)
            {
                Box("StairHousing", g, new Vector3(hp.x, hh * 0.5f, hp.y), new Vector3(hw, hh, hd), housingMat, false, true);
                Box("HousingCap", g, new Vector3(hp.x, hh + 0.06f, hp.y), new Vector3(hw + 0.15f, 0.12f, hd + 0.15f), housingMat, false, true);
                Box("Door", g, new Vector3(hp.x, 1.05f, hp.y + hd * 0.5f + 0.02f), new Vector3(0.9f, 2.1f, 0.04f), doorMat, false, true);
                used.Add(new Rect(hp.x - hw * 0.5f - 0.6f, hp.y - hd * 0.5f - 1.2f, hw + 1.2f, hd + 2.4f));
            }

            // AC units
            int units = 2 + rng.Next(4);
            for (int i = 0; i < units; i++)
            {
                float w = Mathf.Min(R(rng, 1.0f, 1.6f), hx), d = Mathf.Min(R(rng, 1.0f, 1.6f), hz), h = R(rng, 0.8f, 1.2f);
                if (!TryPlace(rng, used, hx, hz, w, d, 0.4f, out Vector2 p)) continue;
                Box("ACUnit", g, new Vector3(p.x, h * 0.5f, p.y), new Vector3(w, h, d), acMat, false, true);
                Cyl("FanGrille", g, new Vector3(p.x, h, p.y), Mathf.Min(w, d) * 0.35f, 0.05f, grille, false, true);
            }

            // Vent pipes with caps
            int vents = 2 + rng.Next(2);
            for (int i = 0; i < vents; i++)
            {
                if (!TryPlace(rng, used, hx, hz, 0.35f, 0.35f, 0.3f, out Vector2 p)) continue;
                float h = R(rng, 0.8f, 1.4f);
                Cyl("VentPipe", g, new Vector3(p.x, 0f, p.y), 0.1f, h, pipe, false, true);
                Cyl("VentCap", g, new Vector3(p.x, h, p.y), 0.17f, 0.07f, pipe, false, true);
            }
        }

        static Vector2 Pick(System.Random rng, float hx, float hz, float halfW, float halfD)
        {
            float x = hx > halfW ? R(rng, -hx + halfW, hx - halfW) : 0f;
            float z = hz > halfD ? R(rng, -hz + halfD, hz - halfD) : 0f;
            return new Vector2(x, z);
        }

        static bool TryPlace(System.Random rng, List<Rect> used, float hx, float hz, float w, float d, float pad, out Vector2 p)
        {
            for (int attempt = 0; attempt < 8; attempt++)
            {
                p = Pick(rng, hx, hz, w * 0.5f, d * 0.5f);
                var r = new Rect(p.x - w * 0.5f - pad, p.y - d * 0.5f - pad, w + pad * 2f, d + pad * 2f);
                bool clash = false;
                foreach (var u in used)
                    if (u.Overlaps(r)) { clash = true; break; }
                if (clash) continue;
                used.Add(r);
                return true;
            }
            p = Vector2.zero;
            return false;
        }

        // =====================================================================================
        // Street dressing
        // =====================================================================================

        /// <summary>
        /// Along the line from->to (parent-local): lamps every ~18m alternating sides at +-sideOffset with arms
        /// reaching over the street, plus occasional benches and planters/bushes between them. Max 14 lamps.
        /// </summary>
        public static void StreetDetails(Transform parent, Vector3 from, Vector3 to, float sideOffset, int seed)
        {
            var rng = new System.Random(seed);
            Vector3 dir = to - from;
            dir.y = 0f;
            float len = dir.magnitude;
            if (len < 1f) return;
            Vector3 fwd = dir / len;
            Vector3 right = new Vector3(fwd.z, 0f, -fwd.x);

            var g = Group("StreetDetails", parent).transform;
            const float spacing = 18f;
            int lamps = Mathf.Min(14, Mathf.FloorToInt(len / spacing) + 1);
            float start = Mathf.Max(0f, (len - (lamps - 1) * spacing) * 0.5f);
            var planterMat = Mat("Planter", new Color(0.5f, 0.49f, 0.47f), 0.1f);

            for (int i = 0; i < lamps; i++)
            {
                float t = start + i * spacing;
                float side = i % 2 == 0 ? 1f : -1f;
                Vector3 inward = -right * side;
                float yawIn = Mathf.Atan2(inward.x, inward.z) * Mathf.Rad2Deg;

                Vector3 lampPos = from + fwd * t + right * side * sideOffset;
                StreetLamp(g, lampPos, yawIn);

                float tm = t + spacing * 0.5f;
                if (tm > len - 1f) continue;
                double roll = rng.NextDouble();
                float propSide = rng.NextDouble() < 0.5 ? 1f : -1f;
                Vector3 propInward = -right * propSide;
                float propYaw = Mathf.Atan2(propInward.x, propInward.z) * Mathf.Rad2Deg;
                Vector3 basePos = from + fwd * tm + right * propSide * (sideOffset + 0.6f);

                if (roll < 0.35)
                {
                    Bench(g, basePos, propYaw);
                }
                else if (roll < 0.6)
                {
                    Box("Planter", g, basePos + Vector3.up * 0.25f, new Vector3(1.2f, 0.5f, 1.2f), planterMat, false, true);
                    Bush(g, basePos + Vector3.up * 0.5f, 0.8f, seed * 31 + i);
                }
                else if (roll < 0.75)
                {
                    Bush(g, basePos, 1f, seed * 17 + i);
                }
            }
        }
    }
}
