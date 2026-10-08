using System.Collections.Generic;
using System.IO;
using Unity.XR.CoreUtils;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.XR.Interaction.Toolkit.Interactables;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Climbing;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Teleportation;

namespace AcrophobiaVR.EditorTools
{
    /// <summary>Primitive-based building blocks and material helpers for the scene builder.</summary>
    public static class BuildKit
    {
        public const string Root = "Assets/AcrophobiaVR";
        public const string MatDir = Root + "/Generated/Materials";
        public const string SceneDir = Root + "/Scenes";

        static readonly Dictionary<string, Material> Cache = new Dictionary<string, Material>();
        static readonly Dictionary<string, Vector2> TileByName = new Dictionary<string, Vector2>();

        /// <summary>Material names that get procedural PBR textures (albedo + normal, facades also lit-window emission).</summary>
        static readonly Dictionary<string, Surface> SurfaceFor = new Dictionary<string, Surface>
        {
            { "Concrete", Surface.Concrete }, { "RoofGrey", Surface.Concrete }, { "Stone", Surface.Concrete }, { "CafeWall", Surface.Concrete },
            { "Asphalt", Surface.Asphalt }, { "Pavement", Surface.Pavement }, { "Path", Surface.Pavement },
            { "Grass", Surface.Grass }, { "MeadowGrass", Surface.Grass }, { "Dirt", Surface.Dirt },
            { "Deck", Surface.Wood }, { "Plank", Surface.Wood }, { "Bench", Surface.Wood }, { "BenchWood", Surface.Wood }, { "DoorWood", Surface.Wood }, { "TankWood", Surface.Wood },
            { "SteelRed", Surface.Metal }, { "SteelDark", Surface.Metal }, { "Scaffold", Surface.Metal }, { "RailMetal", Surface.Metal }, { "CraneYellow", Surface.Metal },
            { "ContainerBlue", Surface.Metal }, { "ContainerWhite", Surface.Metal }, { "LampMetal", Surface.Metal },
            { "Grate", Surface.Grate }, { "Tile", Surface.Tiles }, { "RoofGravel", Surface.RoofGravel },
            { "Bldg1", Surface.BrickFacade }, { "Bldg2", Surface.PlasterFacade }, { "Bldg3", Surface.OfficeFacade }, { "Bldg4", Surface.BrickFacade },
            { "Glass Tower", Surface.GlassFacade }, { "TowerDark", Surface.GlassFacade },
        };

        /// <summary>Surfaces whose albedo already carries natural colour, so the material tint is kept near white.</summary>
        static bool NaturalColour(Surface s) => s == Surface.Grass || s == Surface.Dirt || s == Surface.Asphalt || s == Surface.Wood || s == Surface.GlassFacade;

        /// <summary>
        /// Tint for real (photo) textures: natural surfaces stay near white (the albedo already has colour);
        /// concrete / painted metal keep the requested colour, lightened, so red / yellow steel stays red / yellow.
        /// </summary>
        static Color RealTint(Surface s, Color requested)
        {
            switch (s)
            {
                case Surface.Concrete:
                case Surface.Metal:
                case Surface.Grate:
                    return Color.Lerp(requested, Color.white, 0.35f);
                default:
                    return Color.Lerp(Color.white, requested, 0.15f);
            }
        }

        static void ApplySurface(Material m, string name, Color color)
        {
            if (!SurfaceFor.TryGetValue(name, out var s)) return;

            // Real Poly Haven PBR set (non-facade surfaces): albedo + normal + packed metallic/smoothness mask.
            if (RealAssets.TryGetTextures(s, out var realAlbedo, out var realNormal, out var realMask, out var realTile))
            {
                TileByName[name] = realTile;
                m.SetColor("_BaseColor", RealTint(s, color));
                m.SetTexture("_BaseMap", realAlbedo);
                m.mainTexture = realAlbedo;
                m.SetTexture("_BumpMap", realNormal);
                m.SetFloat("_BumpScale", 1f);
                m.EnableKeyword("_NORMALMAP");
                m.SetTexture("_MetallicGlossMap", realMask);
                m.EnableKeyword("_METALLICSPECGLOSSMAP");
                m.SetFloat("_Smoothness", 1f);                // scales the mask alpha when a gloss map is present
                m.SetFloat("_SmoothnessTextureChannel", 0f);  // smoothness from metallic map alpha
                m.DisableKeyword("_SMOOTHNESS_TEXTURE_ALBEDO_CHANNEL_A");
                m.DisableKeyword("_EMISSION");
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.EmissiveIsBlack;
                return;
            }

            var ts = ProceduralTextures.Get(s);
            TileByName[name] = ts.tileMeters;
            if (NaturalColour(s)) m.SetColor("_BaseColor", Color.Lerp(Color.white, color, 0.25f));
            if (ts.albedo != null) { m.SetTexture("_BaseMap", ts.albedo); m.mainTexture = ts.albedo; }
            if (ts.normal != null)
            {
                m.SetTexture("_BumpMap", ts.normal);
                m.SetFloat("_BumpScale", 1f);
                m.EnableKeyword("_NORMALMAP");
            }
            if (ts.emission != null)
            {
                m.SetTexture("_EmissionMap", ts.emission);
                m.SetColor("_EmissionColor", new Color(1.4f, 1.3f, 1.15f));
                m.EnableKeyword("_EMISSION");
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
            }
        }

        public static void EnsureFolders()
        {
            foreach (var dir in new[] { Root + "/Generated", MatDir, SceneDir })
                if (!AssetDatabase.IsValidFolder(dir))
                {
                    string parent = Path.GetDirectoryName(dir).Replace('\\', '/');
                    AssetDatabase.CreateFolder(parent, Path.GetFileName(dir));
                }
        }

        static Shader Lit => Shader.Find("Universal Render Pipeline/Lit");
        static Shader Unlit => Shader.Find("Universal Render Pipeline/Unlit");

        static Material Save(string name, Material m)
        {
            string path = MatDir + "/" + name + ".mat";
            var existing = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (existing != null)
            {
                existing.shader = m.shader;
                existing.CopyPropertiesFromMaterial(m);
                existing.shaderKeywords = m.shaderKeywords;
                existing.renderQueue = m.renderQueue;
                EditorUtility.SetDirty(existing);
                Cache[name] = existing;
                return existing;
            }
            AssetDatabase.CreateAsset(m, path);
            Cache[name] = m;
            return m;
        }

        public static Material Mat(string name, Color color, float smoothness = 0.3f, float metallic = 0f)
        {
            if (Cache.TryGetValue(name, out var cached) && cached != null)
            {
                if (SurfaceFor.TryGetValue(name, out var cs) && !TileByName.ContainsKey(name))
                    TileByName[name] = RealAssets.TryGetTextures(cs, out _, out _, out _, out var realTile) ? realTile : ProceduralTextures.TileMeters(cs);
                return cached;
            }
            var m = new Material(Lit);
            m.SetColor("_BaseColor", color);
            m.SetFloat("_Smoothness", smoothness);
            m.SetFloat("_Metallic", metallic);
            m.enableInstancing = true;
            ApplySurface(m, name, color);
            return Save(name, m);
        }

        public static Material Glow(string name, Color color, float intensity = 2f)
        {
            if (Cache.TryGetValue(name, out var cached) && cached != null) return cached;
            var m = new Material(Lit);
            m.SetColor("_BaseColor", color);
            m.EnableKeyword("_EMISSION");
            m.SetColor("_EmissionColor", color * intensity);
            m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
            return Save(name, m);
        }

        public static Material Transparent(string name, Color color, bool emissive = false)
        {
            if (Cache.TryGetValue(name, out var cached) && cached != null) return cached;
            var m = new Material(emissive ? Unlit : Lit);
            m.SetColor("_BaseColor", color);
            m.SetFloat("_Surface", 1f);
            m.SetFloat("_Blend", emissive ? 2f : 0f);
            m.SetOverrideTag("RenderType", "Transparent");
            m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
            m.SetFloat("_DstBlend", emissive ? (float)BlendMode.One : (float)BlendMode.OneMinusSrcAlpha);
            m.SetFloat("_ZWrite", 0f);
            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            if (!emissive) m.SetFloat("_Smoothness", 0.95f);
            m.renderQueue = (int)RenderQueue.Transparent;
            return Save(name, m);
        }

        public static Material UnlitColor(string name, Color color)
        {
            if (Cache.TryGetValue(name, out var cached) && cached != null) return cached;
            var m = new Material(Unlit);
            m.SetColor("_BaseColor", color);
            return Save(name, m);
        }

        public static Material ParticleMat()
        {
            const string name = "Particles";
            if (Cache.TryGetValue(name, out var cached) && cached != null) return cached;
            var m = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"));
            m.SetFloat("_Surface", 1f);
            m.SetFloat("_Blend", 2f);
            m.SetOverrideTag("RenderType", "Transparent");
            m.SetFloat("_SrcBlend", (float)BlendMode.SrcAlpha);
            m.SetFloat("_DstBlend", (float)BlendMode.One);
            m.SetFloat("_ZWrite", 0f);
            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            m.renderQueue = (int)RenderQueue.Transparent;
            m.SetTexture("_BaseMap", SoftDot());
            return Save(name, m);
        }

        /// <summary>Soft radial dot texture for particles (saved as an asset so builds include it).</summary>
        static Texture2D SoftDot()
        {
            string path = MatDir + "/SoftDot.asset";
            var existing = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            if (existing != null) return existing;
            const int size = 64;
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, name = "SoftDot" };
            float r = size * 0.5f;
            for (int y = 0; y < size; y++)
            for (int x = 0; x < size; x++)
            {
                float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), new Vector2(r, r)) / r;
                float a = Mathf.Clamp01(1f - d);
                tex.SetPixel(x, y, new Color(1f, 1f, 1f, a * a));
            }
            tex.Apply();
            AssetDatabase.CreateAsset(tex, path);
            return tex;
        }

        public static Material Sky(string name, Color tint, Color ground, float sunSize, float thickness, float exposure)
        {
            var m = new Material(Shader.Find("Skybox/Procedural"));
            m.SetColor("_SkyTint", tint);
            m.SetColor("_GroundColor", ground);
            m.SetFloat("_SunSize", sunSize);
            m.SetFloat("_AtmosphereThickness", thickness);
            m.SetFloat("_Exposure", exposure);
            return Save(name, m);
        }

        public static GameObject Group(string name, Transform parent = null)
        {
            var go = new GameObject(name);
            if (parent != null) go.transform.SetParent(parent, false);
            return go;
        }

        public static GameObject Prim(PrimitiveType type, string name, Transform parent, Vector3 pos, Vector3 scale, Material mat,
            bool collider = true, bool isStatic = true, Vector3? euler = null)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            if (parent != null) go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localScale = scale;
            if (euler.HasValue) go.transform.localRotation = Quaternion.Euler(euler.Value);
            if (mat != null) go.GetComponent<Renderer>().sharedMaterial = mat;
            if (!collider) Object.DestroyImmediate(go.GetComponent<Collider>());
            if (type == PrimitiveType.Cube && mat != null && TileByName.TryGetValue(mat.name, out var tile)) MeshUtil.ApplyTiledUVs(go, tile);
            else if (type == PrimitiveType.Cylinder || type == PrimitiveType.Capsule || type == PrimitiveType.Sphere) { }
            if (isStatic)
            {
                var flags = StaticEditorFlags.BatchingStatic | StaticEditorFlags.OccluderStatic | StaticEditorFlags.OccludeeStatic;
                // Only large pieces go into the lightmap; small props are lit by light probes (bounded lightmap budget).
                // World size = mesh size * lossyScale (cylinder / capsule primitive meshes are 2 units tall, cube / sphere 1).
                var mf = go.GetComponent<MeshFilter>();
                Vector3 ls = Vector3.Scale(go.transform.lossyScale, mf != null && mf.sharedMesh != null ? mf.sharedMesh.bounds.size : Vector3.one);
                if (Mathf.Max(Mathf.Abs(ls.x), Mathf.Max(Mathf.Abs(ls.y), Mathf.Abs(ls.z))) >= 1.2f) flags |= StaticEditorFlags.ContributeGI;
                GameObjectUtility.SetStaticEditorFlags(go, flags);
            }
            return go;
        }

        /// <summary>Box from its centre and size.</summary>
        public static GameObject Box(string name, Transform parent, Vector3 center, Vector3 size, Material mat, bool collider = true, bool isStatic = true)
            => Prim(PrimitiveType.Cube, name, parent, center, size, mat, collider, isStatic);

        /// <summary>Box defined by min/max corners - handy for floors and slabs.</summary>
        public static GameObject BoxMinMax(string name, Transform parent, Vector3 min, Vector3 max, Material mat, bool collider = true, bool isStatic = true)
            => Box(name, parent, (min + max) * 0.5f, max - min, mat, collider, isStatic);

        /// <summary>Walkable floor slab whose top surface is at topY. Optionally teleportable.</summary>
        public static GameObject Floor(string name, Transform parent, float xMin, float xMax, float zMin, float zMax, float topY, float thickness, Material mat, bool teleport)
        {
            var go = BoxMinMax(name, parent, new Vector3(xMin, topY - thickness, zMin), new Vector3(xMax, topY, zMax), mat);
            if (teleport) MakeTeleportable(go);
            return go;
        }

        public static void MakeTeleportable(GameObject go)
        {
            if (go.GetComponent<TeleportationArea>() == null) go.AddComponent<TeleportationArea>();
        }

        public static GameObject Cyl(string name, Transform parent, Vector3 basePos, float radius, float height, Material mat, bool collider = true, bool isStatic = true)
            => Prim(PrimitiveType.Cylinder, name, parent, basePos + Vector3.up * height * 0.5f, new Vector3(radius * 2, height * 0.5f, radius * 2), mat, collider, isStatic);

        public static GameObject Sphere(string name, Transform parent, Vector3 center, float diameter, Material mat, bool collider = false, bool isStatic = true)
            => Prim(PrimitiveType.Sphere, name, parent, center, Vector3.one * diameter, mat, collider, isStatic);

        /// <summary>Thin bar between two points (rails, cables, poles).</summary>
        public static GameObject Bar(string name, Transform parent, Vector3 a, Vector3 b, float thickness, Material mat, bool collider = true, bool isStatic = true)
        {
            var go = Prim(PrimitiveType.Cube, name, parent, (a + b) * 0.5f, new Vector3(thickness, thickness, Vector3.Distance(a, b)), mat, collider, isStatic);
            if ((b - a).sqrMagnitude > 0.0001f) go.transform.localRotation = Quaternion.LookRotation(b - a);
            return go;
        }

        /// <summary>Railing along a line: posts, top rail and optional middle rail (middle rail hidden in Brave).</summary>
        public static GameObject Railing(string name, Transform parent, Vector3 from, Vector3 to, float height, Material mat, bool middleRail = true, float postSpacing = 1.5f)
        {
            var g = Group(name, parent);
            float len = Vector3.Distance(from, to);
            int posts = Mathf.Max(2, Mathf.CeilToInt(len / postSpacing) + 1);
            for (int i = 0; i < posts; i++)
            {
                Vector3 p = Vector3.Lerp(from, to, i / (float)(posts - 1));
                Bar("Post", g.transform, p, p + Vector3.up * height, 0.06f, mat);
            }
            Bar("TopRail", g.transform, from + Vector3.up * height, to + Vector3.up * height, 0.07f, mat);
            if (middleRail)
            {
                var mid = Bar("MidRail", g.transform, from + Vector3.up * height * 0.5f, to + Vector3.up * height * 0.5f, 0.04f, mat);
                var ev = mid.AddComponent<ExposureVisual>();
                ev.gentle = true; ev.standard = true; ev.brave = false;
            }
            return g;
        }

        /// <summary>Gentle-mode safety glass panel between two points.</summary>
        public static GameObject SafetyGlass(string name, Transform parent, Vector3 from, Vector3 to, float height, Material glass)
        {
            Vector3 center = (from + to) * 0.5f + Vector3.up * height * 0.5f;
            var go = Box(name, parent, center, new Vector3(0.03f, height, Vector3.Distance(from, to)), glass, true, false);
            go.transform.localRotation = Quaternion.LookRotation(to - from);
            var ev = go.AddComponent<ExposureVisual>();
            ev.gentle = true; ev.standard = false; ev.brave = false;
            return go;
        }

        public static T Exposure<T>(GameObject go, bool gentle, bool standard, bool brave) where T : Component
        {
            var ev = go.AddComponent<ExposureVisual>();
            ev.gentle = gentle; ev.standard = standard; ev.brave = brave;
            return go.GetComponent<T>();
        }

        public static void ShowIn(GameObject go, bool gentle, bool standard, bool brave)
        {
            var ev = go.AddComponent<ExposureVisual>();
            ev.gentle = gentle; ev.standard = standard; ev.brave = brave;
        }

        public static Transform Point(string name, Transform parent, Vector3 pos, float yaw = 0f)
        {
            var t = new GameObject(name).transform;
            t.SetParent(parent, false);
            t.localPosition = pos;
            t.localRotation = Quaternion.Euler(0f, yaw, 0f);
            return t;
        }

        /// <summary>Point whose forward faces away from the viewer (world position) so world-space UI reads correctly.</summary>
        public static Transform PanelPoint(string name, Transform parent, Vector3 pos, Vector3 viewer)
        {
            var t = Point(name, parent, pos);
            Vector3 dir = t.position - viewer;
            dir.y = 0f;
            if (dir.sqrMagnitude > 0.001f) t.rotation = Quaternion.LookRotation(dir);
            return t;
        }

        public static T Zone<T>(string name, Transform parent, Vector3 center, Vector3 size) where T : Component
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = center;
            var box = go.AddComponent<BoxCollider>();
            box.isTrigger = true;
            box.size = size;
            go.layer = 2;
            return go.AddComponent<T>();
        }

        public static Light Sun(Vector3 euler, Color color, float intensity)
        {
            var go = new GameObject("Sun");
            var l = go.AddComponent<Light>();
            l.type = LightType.Directional;
            l.color = color;
            l.intensity = intensity;
            l.shadows = LightShadows.Soft;
            l.shadowStrength = 0.9f;
            l.shadowNormalBias = 0.3f;
            go.transform.rotation = Quaternion.Euler(euler);
            RenderSettings.sun = l;
            return l;
        }

        public static GameObject InstantiateRig(Vector3 pos, float yaw)
        {
            string[] candidates =
            {
                "Assets/VRTemplateAssets/Prefabs/Setup/Complete XR Origin Set Up Variant.prefab",
                "Assets/Samples/XR Interaction Toolkit/3.5.1/Starter Assets/Prefabs/XR Origin (XR Rig).prefab",
            };
            GameObject prefab = null;
            foreach (var c in candidates)
            {
                prefab = AssetDatabase.LoadAssetAtPath<GameObject>(c);
                if (prefab != null) break;
            }
            if (prefab == null)
            {
                foreach (var guid in AssetDatabase.FindAssets("XR Origin t:Prefab"))
                {
                    prefab = AssetDatabase.LoadAssetAtPath<GameObject>(AssetDatabase.GUIDToAssetPath(guid));
                    if (prefab != null && prefab.GetComponentInChildren<XROrigin>(true) != null) break;
                }
            }
            if (prefab == null) throw new System.Exception("Could not find an XR Origin prefab. Import the XRI Starter Assets sample.");

            var rig = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            rig.transform.position = pos;
            rig.transform.rotation = Quaternion.Euler(0f, yaw, 0f);
            var origin = rig.GetComponentInChildren<XROrigin>(true);
            if (origin.GetComponent<PlayerRig>() == null) origin.gameObject.AddComponent<PlayerRig>();
            if (origin.GetComponent<DesktopRig>() == null) origin.gameObject.AddComponent<DesktopRig>();
            return rig;
        }

        /// <summary>Pip, the companion: glowing body, beak, eyes, flapping wings and a soft light.</summary>
        public static Companion CreatePip(Vector3 pos)
        {
            var root = new GameObject("Pip (Companion)");
            root.transform.position = pos;
            var comp = root.AddComponent<Companion>();
            var body = Sphere("Body", root.transform, Vector3.zero, 0.16f, Glow("PipBody", new Color(0.45f, 0.9f, 1f), 1.2f), false, false);
            Sphere("Belly", body.transform, new Vector3(0, -0.12f, 0.2f), 0.7f, Mat("PipBelly", new Color(1f, 0.97f, 0.85f)), false, false);
            Sphere("EyeL", body.transform, new Vector3(-0.22f, 0.15f, 0.42f), 0.18f, Mat("PipEye", new Color(0.05f, 0.05f, 0.08f), 0.9f), false, false);
            Sphere("EyeR", body.transform, new Vector3(0.22f, 0.15f, 0.42f), 0.18f, Mat("PipEye", new Color(0.05f, 0.05f, 0.08f), 0.9f), false, false);
            var beak = Prim(PrimitiveType.Cube, "Beak", body.transform, new Vector3(0, -0.02f, 0.52f), new Vector3(0.14f, 0.1f, 0.22f), Mat("PipBeak", new Color(1f, 0.7f, 0.2f)), false, false, new Vector3(0, 45, 0));
            beak.transform.localRotation = Quaternion.Euler(0, 45, 0);
            comp.body = body.transform;
            comp.leftWing = WingPivot(root.transform, -1);
            comp.rightWing = WingPivot(root.transform, 1);
            var lightGo = new GameObject("Glow");
            lightGo.transform.SetParent(root.transform, false);
            var l = lightGo.AddComponent<Light>();
            l.type = LightType.Point;
            l.range = 1.5f;
            l.color = new Color(0.5f, 0.9f, 1f);
            l.intensity = 1.2f;
            l.shadows = LightShadows.None;
            comp.glow = l;
            return comp;
        }

        static Transform WingPivot(Transform parent, int side)
        {
            var pivot = Point(side < 0 ? "WingL" : "WingR", parent, new Vector3(0.06f * side, 0.02f, 0f));
            Prim(PrimitiveType.Cube, "Feather", pivot, new Vector3(0.06f * side, 0, -0.01f), new Vector3(0.1f, 0.015f, 0.08f), Glow("PipWing", new Color(0.7f, 0.95f, 1f), 0.8f), false, false);
            return pivot;
        }

        public static void AddClimbRungs(Transform ladder, Vector3 bottom, Vector3 top, float width, Material mat)
        {
            Bar("RailL", ladder, bottom + Vector3.left * width * 0.5f, top + Vector3.left * width * 0.5f, 0.05f, mat, true, false);
            Bar("RailR", ladder, bottom + Vector3.right * width * 0.5f, top + Vector3.right * width * 0.5f, 0.05f, mat, true, false);
            int rungs = Mathf.FloorToInt(Vector3.Distance(bottom, top) / 0.3f);
            for (int i = 1; i < rungs; i++)
            {
                Vector3 p = Vector3.Lerp(bottom, top, i / (float)rungs);
                var rung = Bar("Rung", ladder, p + Vector3.left * width * 0.5f, p + Vector3.right * width * 0.5f, 0.04f, mat, true, false);
                rung.AddComponent<ClimbInteractable>();
                // ClimbInteractable requires a Rigidbody and Unity adds a dynamic one, which drops every rung on play.
                var rungBody = rung.GetComponent<Rigidbody>();
                rungBody.isKinematic = true;
                rungBody.useGravity = false;
            }
        }

        /// <summary>Makes an object grabbable in VR (XRGrabInteractable) with a kinematic rigidbody.</summary>
        public static XRGrabInteractable MakeGrabbable(GameObject go, bool kinematic = true)
        {
            var rb = go.GetComponent<Rigidbody>();
            if (rb == null) rb = go.AddComponent<Rigidbody>();
            rb.isKinematic = kinematic;
            rb.useGravity = !kinematic;
            rb.interpolation = RigidbodyInterpolation.Interpolate;
            var grab = go.GetComponent<XRGrabInteractable>();
            if (grab == null) grab = go.AddComponent<XRGrabInteractable>();
            grab.throwOnDetach = false;
            return grab;
        }

        /// <summary>Random city blocks of boxes, avoiding a rectangle where the level is.</summary>
        public static void City(Transform parent, Vector2 center, int halfCount, float spacing, Vector2 heightRange, Rect avoid, int seed, Material[] palette, Material windowMat, float groundY = 0f)
        {
            // Facade textures (with lit windows in their emission maps) replace the old glowing window bands.
            var rng = new System.Random(seed);
            var city = Group("City", parent).transform;
            int roofProps = 0;
            for (int ix = -halfCount; ix <= halfCount; ix++)
            for (int iz = -halfCount; iz <= halfCount; iz++)
            {
                float x = center.x + ix * spacing;
                float z = center.y + iz * spacing;
                if (avoid.Contains(new Vector2(x, z))) continue;
                if (rng.NextDouble() < 0.15) continue;
                float w = spacing * (0.45f + (float)rng.NextDouble() * 0.3f);
                float d = spacing * (0.45f + (float)rng.NextDouble() * 0.3f);
                float t = (float)rng.NextDouble();
                float h = Mathf.Lerp(heightRange.x, heightRange.y, t * t);
                var mat = palette[rng.Next(palette.Length)];
                Box("Building", city, new Vector3(x, groundY + h * 0.5f, z), new Vector3(w, h, d), mat, false);
                // Tall towers get a setback crown, like real skyscrapers.
                if (h > 60f && rng.NextDouble() < 0.6)
                {
                    float ch = h * (0.12f + (float)rng.NextDouble() * 0.12f);
                    Box("Crown", city, new Vector3(x, groundY + h + ch * 0.5f, z), new Vector3(w * 0.7f, ch, d * 0.7f), mat, false);
                    h += ch;
                }
                // Roof parapet edge and gravel roof
                Box("Parapet", city, new Vector3(x, groundY + h + 0.4f, z), new Vector3(w + 0.3f, 0.8f, d + 0.3f), Mat("RoofGrey", new Color(0.5f, 0.52f, 0.55f)), false);
                Box("RoofTop", city, new Vector3(x, groundY + h + 0.45f, z), new Vector3(w - 0.4f, 0.8f, d - 0.4f), Mat("RoofGravel", new Color(0.55f, 0.55f, 0.55f)), false);
                if (roofProps < 40 && rng.NextDouble() < 0.55)
                {
                    roofProps++;
                    Props.RooftopUnits(city, new Vector3(x, groundY + h + 0.85f, z), new Vector2(w - 1f, d - 1f), rng.Next());
                }
            }
        }

        static int Seed(Vector3 p) => Mathf.RoundToInt(p.x * 73.1f + p.y * 19.7f + p.z * 37.3f);

        public static void Tree(Transform parent, Vector3 basePos, float scale, Material trunk, Material leaves)
            => Props.Tree(parent, basePos, scale, Seed(basePos));

        public static void Car(Transform parent, Vector3[] loop, float offset, float speed, Material body, Material glass)
            => Props.Car(parent, loop, offset, speed, body != null ? body.GetColor("_BaseColor") : Color.red, Mathf.RoundToInt(offset * 1000f) + Mathf.RoundToInt(speed * 7f));

        public static void Person(Transform parent, Vector3 basePos, Material clothes, Material skin)
            => Props.Person(parent, basePos, clothes != null ? clothes.GetColor("_BaseColor") : Color.blue, Seed(basePos));
        public static Transform LookTarget(string name, Transform parent, Vector3 pos, float ringRadius)
        {
            var t = Point(name, parent, pos);
            var ring = Cyl("Marker", t, new Vector3(0, 2.6f, 0), ringRadius, 0.06f, Glow("MarkerGlow", new Color(1f, 0.85f, 0.3f), 3f), false, false);
            ring.AddComponent<Bobber>().amplitude = 0.25f;
            var arrow = Prim(PrimitiveType.Cube, "Arrow", t, new Vector3(0, 3.4f, 0), new Vector3(0.3f, 0.3f, 0.3f), Glow("MarkerGlow", new Color(1f, 0.85f, 0.3f), 3f), false, false, new Vector3(45, 0, 45));
            arrow.AddComponent<Spinner>().degreesPerSecond = new Vector3(0, 90, 0);
            arrow.AddComponent<Bobber>().amplitude = 0.25f;
            return t;
        }

        public static CourageStar Star(Transform parent, Vector3 pos)
        {
            var root = new GameObject("CourageStar");
            root.transform.SetParent(parent, false);
            root.transform.localPosition = pos;
            var mat = Glow("StarGold", new Color(1f, 0.8f, 0.2f), 3f);
            Prim(PrimitiveType.Cube, "A", root.transform, Vector3.zero, new Vector3(0.22f, 0.22f, 0.05f), mat, false, false, new Vector3(0, 0, 45));
            Prim(PrimitiveType.Cube, "B", root.transform, Vector3.zero, new Vector3(0.22f, 0.22f, 0.05f), mat, false, false);
            var l = new GameObject("Light").AddComponent<Light>();
            l.transform.SetParent(root.transform, false);
            l.type = LightType.Point;
            l.range = 2f;
            l.intensity = 1.5f;
            l.color = new Color(1f, 0.85f, 0.4f);
            return root.AddComponent<CourageStar>();
        }

        /// <summary>Crack lines drawn on a glass panel (revealed progressively by CrackingGlass).</summary>
        public static LineRenderer[] Cracks(Transform glass, int count, Vector2 halfSize, float y, int seed)
        {
            var rng = new System.Random(seed);
            var lines = new LineRenderer[count];
            var mat = UnlitColor("CrackWhite", new Color(0.95f, 0.98f, 1f));
            for (int i = 0; i < count; i++)
            {
                var go = new GameObject("Crack" + i);
                go.transform.SetParent(glass, false);
                var lr = go.AddComponent<LineRenderer>();
                lr.useWorldSpace = false;
                lr.widthMultiplier = 0.012f;
                lr.sharedMaterial = mat;
                int pts = 6;
                lr.positionCount = pts;
                Vector2 p = new Vector2((float)(rng.NextDouble() * 2 - 1) * halfSize.x * 0.5f, (float)(rng.NextDouble() * 2 - 1) * halfSize.y * 0.5f);
                Vector2 dir = new Vector2((float)(rng.NextDouble() * 2 - 1), (float)(rng.NextDouble() * 2 - 1)).normalized;
                for (int k = 0; k < pts; k++)
                {
                    lr.SetPosition(k, new Vector3(p.x, y, p.y));
                    dir = (dir + new Vector2((float)(rng.NextDouble() - 0.5), (float)(rng.NextDouble() - 0.5)) * 0.9f).normalized;
                    p += dir * (0.15f + (float)rng.NextDouble() * 0.25f);
                }
                lines[i] = lr;
            }
            return lines;
        }
    }
}