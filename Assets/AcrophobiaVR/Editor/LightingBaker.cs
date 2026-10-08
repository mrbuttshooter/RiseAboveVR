using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.XR.Interaction.Toolkit.Locomotion.Teleportation;

namespace AcrophobiaVR.EditorTools
{
    /// <summary>
    /// Bakes Quest-friendly lighting for the generated scenes: realtime sun and shadows (Mixed,
    /// Indirect Only) plus baked bounce light and AO, light probes over the walkable areas and baked
    /// reflection probes. The lightmap budget is bounded by distance from the play area so the huge
    /// city/ground boxes never blow up texture memory or bake time.
    /// </summary>
    public static class LightingBaker
    {
        public const string LightingDir = "Assets/AcrophobiaVR/Generated/Lighting";

        // Lightmap budget
        const float LightmapResolution = 2.5f;      // texels per metre
        const int LightmapMaxSize = 1024;
        const float MaxTexelsPerRenderer = 512f * 512f;
        const double MaxTotalTexels = 6.0 * 1024 * 1024; // ~8 lightmaps of 1024 after packing (Quest memory)
        const float NearDistance = 40f, MidDistance = 120f, FarDistance = 300f;
        const float NearScale = 1f, MidScale = 0.35f, FarScale = 0.12f, MinScale = 0.01f;
        const float GroundSizeThreshold = 100f;     // colliders wider than this are "ground", not play area

        // Light probes
        const float ProbeSpacing = 3f;
        const float ProbeLowHeight = 0.4f, ProbeHighHeight = 2.0f;
        const float PlayAreaMargin = 4f;
        const int MaxProbes = 1200;
        const int MaxEnvironmentProbes = 300;
        const float EnvironmentSpacing = 12f, EnvironmentMargin = 36f;
        const string ProbeGroupName = "Light Probes";

        // ------------------------------------------------------------------ menu / entry points

        [MenuItem("Rise Above/Bake Lighting (All Scenes)", priority = 10)]
        public static void BakeAll()
        {
            if (!CanBake()) return;
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;

            string previous = SceneManager.GetActiveScene().path;
            var paths = new List<string>();
            foreach (var s in EditorBuildSettings.scenes)
                if (s != null && s.enabled && !string.IsNullOrEmpty(s.path) && File.Exists(s.path)) paths.Add(s.path);
            if (paths.Count == 0)
            {
                Debug.LogWarning("[Bake] No enabled scenes in Build Settings. Run 'Rise Above/Build All Scenes' first.");
                return;
            }

            var summary = new StringBuilder();
            int okCount = 0;
            var total = System.Diagnostics.Stopwatch.StartNew();
            for (int i = 0; i < paths.Count; i++)
            {
                string name = Path.GetFileNameWithoutExtension(paths[i]);
                var sw = System.Diagnostics.Stopwatch.StartNew();
                bool ok = BakeScene(paths[i]);
                sw.Stop();
                int lightmaps = ok ? LightmapCount() : 0;
                if (ok) okCount++;
                string line = string.Format(CultureInfo.InvariantCulture, "[Bake] {0} took {1:0.0}s, lightmaps={2}{3}",
                    name, sw.Elapsed.TotalSeconds, lightmaps, ok ? "" : " (FAILED)");
                Debug.Log(line);
                summary.AppendLine(line);
            }
            total.Stop();

            AssetDatabase.SaveAssets();
            Debug.Log(string.Format(CultureInfo.InvariantCulture, "[Bake] Finished {0}/{1} scenes in {2:0.0}s\n{3}",
                okCount, paths.Count, total.Elapsed.TotalSeconds, summary));

            // Return to the scene the user had open.
            if (!string.IsNullOrEmpty(previous) && File.Exists(previous) && SceneManager.GetActiveScene().path != previous)
            {
                try { EditorSceneManager.OpenScene(previous, OpenSceneMode.Single); }
                catch (System.Exception e) { Debug.LogWarning("[Bake] Could not reopen " + previous + ": " + e.Message); }
            }
        }

        [MenuItem("Rise Above/Bake Lighting (Current Scene)", priority = 11)]
        public static void BakeCurrentScene()
        {
            if (!CanBake()) return;
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            string path = SceneManager.GetActiveScene().path;
            if (string.IsNullOrEmpty(path))
            {
                Debug.LogWarning("[Bake] Save the scene first.");
                return;
            }
            var sw = System.Diagnostics.Stopwatch.StartNew();
            bool ok = BakeScene(path);
            sw.Stop();
            Debug.Log(string.Format(CultureInfo.InvariantCulture, "[Bake] {0} took {1:0.0}s, lightmaps={2}{3}",
                Path.GetFileNameWithoutExtension(path), sw.Elapsed.TotalSeconds, ok ? LightmapCount() : 0, ok ? "" : " (FAILED)"));
            AssetDatabase.SaveAssets();
        }

        /// <summary>Opens the scene, prepares it (settings, lights, lightmap scales, probes), bakes synchronously and saves it.</summary>
        public static bool BakeScene(string scenePath)
        {
            if (string.IsNullOrEmpty(scenePath) || !CanBake()) return false;
            try
            {
                Scene scene = EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);
                if (!scene.IsValid())
                {
                    Debug.LogError("[Bake] Could not open " + scenePath);
                    return false;
                }

                Prepare();

                bool ok = Lightmapping.Bake();
                if (!ok) Debug.LogWarning("[Bake] Lightmapping.Bake() returned false for " + scenePath + " (cancelled or failed).");

                Scene active = SceneManager.GetActiveScene();
                if (!EditorSceneManager.SaveScene(active))
                    Debug.LogWarning("[Bake] Could not save " + active.path);
                return ok;
            }
            catch (System.Exception e)
            {
                Debug.LogError("[Bake] " + scenePath + " failed: " + e);
                return false;
            }
            finally
            {
                EditorUtility.ClearProgressBar();
            }
        }

        static bool CanBake()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                Debug.LogWarning("[Bake] Exit Play Mode before baking.");
                return false;
            }
            if (EditorApplication.isCompiling)
            {
                Debug.LogWarning("[Bake] Wait for script compilation to finish before baking.");
                return false;
            }
            if (Lightmapping.isRunning)
            {
                Debug.LogWarning("[Bake] A lighting bake is already running.");
                return false;
            }
            return true;
        }

        static int LightmapCount()
        {
            var maps = LightmapSettings.lightmaps;
            return maps != null ? maps.Length : 0;
        }

        // ------------------------------------------------------------------ prepare

        /// <summary>
        /// Prepares the active scene for baking: per-scene LightingSettings asset, Mixed directional
        /// lights, bounded lightmap scales, a light probe group over the walkable areas and baked
        /// reflection probes. Safe to run repeatedly.
        /// </summary>
        public static void Prepare()
        {
            Scene scene = SceneManager.GetActiveScene();
            if (!scene.IsValid()) throw new System.InvalidOperationException("No active scene to prepare.");
            string sceneName = string.IsNullOrEmpty(scene.name) ? "Untitled" : scene.name;

            LightingSettings settings = GetOrCreateLightingSettings(sceneName);
            Lightmapping.lightingSettings = settings;

            int lights = ConfigureLights();
            var playBoxes = new List<Bounds>();
            Bounds play = ComputePlayArea(out int playSources, playBoxes);
            string scaleStats = AssignLightmapScales(play, playBoxes);
            int probes = BuildLightProbes(play);
            int reflection = ConfigureReflectionProbes();

            EditorSceneManager.MarkSceneDirty(scene);
            Debug.Log(string.Format(CultureInfo.InvariantCulture,
                "[Bake] Prepared {0}: play area centre {1} size {2} ({3} sources), mixed suns={4}, {5}, light probes={6}, reflection probes={7}",
                sceneName, play.center, play.size, playSources, lights, scaleStats, probes, reflection));
        }

        // ------------------------------------------------------------------ lighting settings

        static LightingSettings GetOrCreateLightingSettings(string sceneName)
        {
            EnsureFolder(LightingDir);
            // ".lighting" is the native extension of LightingSettings assets.
            string path = LightingDir + "/" + sceneName + "_Lighting.lighting";
            var ls = AssetDatabase.LoadAssetAtPath<LightingSettings>(path);
            bool created = false;
            if (ls == null)
            {
                ls = new LightingSettings();
                ls.name = sceneName + "_Lighting";
                created = true;
            }

            ConfigureSettings(ls);

            if (created)
            {
                AssetDatabase.CreateAsset(ls, path);
                if (!EditorUtility.IsPersistent(ls))
                    Debug.LogWarning("[Bake] Could not save " + path + "; the settings are used for this bake only.");
            }
            else EditorUtility.SetDirty(ls);
            return ls;
        }

        static void ConfigureSettings(LightingSettings ls)
        {
            ls.lightmapper = LightingSettings.Lightmapper.ProgressiveGPU;
            ls.bakedGI = true;
#pragma warning disable 618
            ls.realtimeGI = false;
#pragma warning restore 618
            ls.mixedBakeMode = MixedLightingMode.IndirectOnly;   // realtime sun + shadows, baked bounce
            ls.lightmapResolution = LightmapResolution;
            ls.lightmapMaxSize = LightmapMaxSize;
            ls.lightmapPadding = 2;
            ls.directSampleCount = 32;
            ls.indirectSampleCount = 128;
            ls.environmentSampleCount = 128;
            ls.maxBounces = 2;
            ls.ao = true;
            ls.aoMaxDistance = 1.2f;
            ls.aoExponentIndirect = 1f;
            ls.aoExponentDirect = 0f;
            ls.filteringMode = LightingSettings.FilterMode.Auto;
            ls.lightmapCompression = LightmapCompression.NormalQuality;
            ls.directionalityMode = LightmapsMode.NonDirectional;  // half the lightmap memory/cost on Quest
        }

        // ------------------------------------------------------------------ lights

        static int ConfigureLights()
        {
            int n = 0;
            foreach (var l in FindAll<Light>())
            {
                if (l.type != LightType.Directional) continue; // point/spot lights keep their mode (Realtime)
                l.lightmapBakeType = LightmapBakeType.Mixed;
                EditorUtility.SetDirty(l);
                n++;
            }
            return n;
        }

        // ------------------------------------------------------------------ play area

        /// <summary>
        /// Union of the teleport floors, head zones, reach objectives and the level start point.
        /// Ground-sized colliders (wider than 100 m) are left out so the area stays where the player is.
        /// </summary>
        static Bounds ComputePlayArea(out int sources, List<Bounds> used)
        {
            var boxes = new List<Bounds>();
            foreach (var ta in FindAll<TeleportationArea>()) AddBoxBounds(ta.gameObject, boxes);
            foreach (var hz in FindAll<HeadZone>()) AddBoxBounds(hz.gameObject, boxes);
            foreach (var ro in FindAll<ReachObjective>()) AddBoxBounds(ro.gameObject, boxes);

            var points = new List<Vector3>();
            foreach (var lc in FindAll<LevelController>())
                if (lc.startPoint != null) points.Add(lc.startPoint.position);

            sources = boxes.Count + points.Count;
            bool any = false;
            Bounds play = new Bounds();
            foreach (var b in boxes)
            {
                if (IsGroundSized(b)) continue;
                Encapsulate(ref play, ref any, b);
                used.Add(b);
            }
            foreach (var p in points)
            {
                var pb = new Bounds(p + Vector3.up, new Vector3(2f, 2f, 2f));
                Encapsulate(ref play, ref any, pb);
                used.Add(pb);
            }

            if (!any)
                foreach (var b in boxes) Encapsulate(ref play, ref any, b);
            if (!any)
            {
                Debug.LogWarning("[Bake] No play area found (no teleport areas / zones / start point); using 40 m around the origin.");
                play = new Bounds(Vector3.zero, new Vector3(40f, 10f, 40f));
            }
            if (used.Count == 0) used.Add(play);
            return play;
        }

        static void AddBoxBounds(GameObject go, List<Bounds> into)
        {
            foreach (var bc in go.GetComponents<BoxCollider>())
                if (bc != null) into.Add(WorldBounds(bc));
        }

        static bool IsGroundSized(Bounds b) => b.size.x > GroundSizeThreshold || b.size.z > GroundSizeThreshold;

        static void Encapsulate(ref Bounds into, ref bool any, Bounds b)
        {
            if (!any) { into = b; any = true; }
            else into.Encapsulate(b);
        }

        static Bounds WorldBounds(BoxCollider bc)
        {
            Transform t = bc.transform;
            Vector3 c = bc.center;
            Vector3 h = bc.size * 0.5f;
            var b = new Bounds(t.TransformPoint(c), Vector3.zero);
            for (int i = 0; i < 8; i++)
            {
                var corner = new Vector3(
                    (i & 1) == 0 ? -h.x : h.x,
                    (i & 2) == 0 ? -h.y : h.y,
                    (i & 4) == 0 ? -h.z : h.z);
                b.Encapsulate(t.TransformPoint(c + corner));
            }
            return b;
        }

        /// <summary>Gap between two boxes (0 when they overlap).</summary>
        static float BoxDistance(Bounds a, Bounds b)
        {
            float dx = Mathf.Max(0f, Mathf.Max(a.min.x - b.max.x, b.min.x - a.max.x));
            float dy = Mathf.Max(0f, Mathf.Max(a.min.y - b.max.y, b.min.y - a.max.y));
            float dz = Mathf.Max(0f, Mathf.Max(a.min.z - b.max.z, b.min.z - a.max.z));
            return Mathf.Sqrt(dx * dx + dy * dy + dz * dz);
        }

        // ------------------------------------------------------------------ lightmap budget

        /// <summary>
        /// Lightmap scale falls off with distance from the play area (1 / 0.35 / 0.12, probe-lit past
        /// 300 m). Meshes without a lightmap UV set become probe-lit. Each renderer is capped so its
        /// largest face never needs more than 512x512 texels (ground boxes, towers).
        /// </summary>
        static string AssignLightmapScales(Bounds play, List<Bounds> playBoxes)
        {
            int near = 0, mid = 0, far = 0, probeLit = 0, noUV = 0, inactive = 0, capped = 0;
            var baked = new List<MeshRenderer>();
            var bakedArea = new List<float>();
            foreach (var mr in FindAll<MeshRenderer>())
            {
                GameObject go = mr.gameObject;
                StaticEditorFlags flags = GameObjectUtility.GetStaticEditorFlags(go);
                StaticEditorFlags original = flags;

                // Static scenery shows up in the baked reflection probes.
                if ((flags & (StaticEditorFlags.ContributeGI | StaticEditorFlags.BatchingStatic)) != 0)
                    flags |= StaticEditorFlags.ReflectionProbeStatic;

                if ((flags & StaticEditorFlags.ContributeGI) != 0)
                {
                    if (!go.activeInHierarchy || !mr.enabled)
                    {
                        // Not baked while hidden (e.g. exposure-mode variants): light it from probes when it appears.
                        mr.receiveGI = ReceiveGI.LightProbes;
                        inactive++;
                    }
                    else
                    {
                        var mf = go.GetComponent<MeshFilter>();
                        Mesh mesh = mf != null ? mf.sharedMesh : null;
                        if (mesh == null || !mesh.HasVertexAttribute(VertexAttribute.TexCoord1))
                        {
                            flags &= ~StaticEditorFlags.ContributeGI;
                            mr.receiveGI = ReceiveGI.LightProbes;
                            noUV++;
                        }
                        else
                        {
                            // Distance to the nearest play-area piece (not to their union box, which on a
                            // long route would put every tower in between at full resolution).
                            Bounds rb = mr.bounds;
                            float d = float.MaxValue;
                            for (int i = 0; i < playBoxes.Count; i++) d = Mathf.Min(d, BoxDistance(playBoxes[i], rb));
                            if (playBoxes.Count == 0) d = BoxDistance(play, rb);
                            float scale;
                            if (d < NearDistance) { scale = NearScale; near++; }
                            else if (d < MidDistance) { scale = MidScale; mid++; }
                            else if (d < FarDistance) { scale = FarScale; far++; }
                            else scale = 0f;

                            if (scale <= 0f)
                            {
                                flags &= ~StaticEditorFlags.ContributeGI;
                                mr.receiveGI = ReceiveGI.LightProbes;
                                probeLit++;
                            }
                            else
                            {
                                Vector3 ls = go.transform.lossyScale;
                                Vector3 s = Vector3.Scale(mesh.bounds.size, new Vector3(Mathf.Abs(ls.x), Mathf.Abs(ls.y), Mathf.Abs(ls.z)));
                                float face = Mathf.Max(s.x * s.y, Mathf.Max(s.y * s.z, s.x * s.z));
                                if (face > 0f)
                                {
                                    float maxScale = Mathf.Sqrt(MaxTexelsPerRenderer / face) / LightmapResolution;
                                    if (scale > maxScale)
                                    {
                                        scale = Mathf.Max(MinScale, maxScale);
                                        capped++;
                                    }
                                }
                                mr.scaleInLightmap = scale;
                                mr.receiveGI = ReceiveGI.Lightmaps;
                                baked.Add(mr);
                                bakedArea.Add(2f * (s.x * s.y + s.y * s.z + s.x * s.z)); // box surface estimate
                            }
                        }
                    }
                    EditorUtility.SetDirty(mr);
                }

                if (flags != original) GameObjectUtility.SetStaticEditorFlags(go, flags);
            }

            // Whole-scene budget: if the estimated texels exceed the budget, scale everything down evenly.
            double total = 0;
            for (int i = 0; i < baked.Count; i++)
            {
                double k = baked[i].scaleInLightmap * LightmapResolution;
                total += bakedArea[i] * k * k;
            }
            float budgetFactor = 1f;
            if (total > MaxTotalTexels)
            {
                budgetFactor = Mathf.Sqrt((float)(MaxTotalTexels / total));
                for (int i = 0; i < baked.Count; i++)
                    baked[i].scaleInLightmap = Mathf.Max(MinScale, baked[i].scaleInLightmap * budgetFactor);
            }
            if (noUV > 0 && noUV >= baked.Count)
                Debug.LogWarning("[Bake] " + noUV + " ContributeGI meshes have no lightmap UVs (uv2). Rebuild the scenes (Rise Above menu) so the tiled cubes get uv2, then bake again.");

            return string.Format(CultureInfo.InvariantCulture,
                "lightmapped near={0} mid={1} far={2} (capped {3}, est. {4:0.0} M texels, budget x{5:0.00}), probe-lit: far={6} noUV2={7} hidden={8}",
                near, mid, far, capped, total / 1e6, budgetFactor, probeLit, noUV, inactive);
        }

        // ------------------------------------------------------------------ light probes

        static int BuildLightProbes(Bounds play)
        {
            Bounds area = play;
            area.Expand(PlayAreaMargin * 2f); // Expand grows the total size: 4 m on each side

            // Detail probes: 3 m grid on every walkable top surface, at foot and head height.
            var detail = new List<Vector3>();
            foreach (var ta in FindAll<TeleportationArea>())
                foreach (var bc in ta.GetComponents<BoxCollider>())
                {
                    if (bc == null || bc.isTrigger) continue;
                    bool huge = IsGroundSized(WorldBounds(bc));
                    SampleTop(bc, detail, huge, area);
                }
            foreach (var beam in FindAll<BalanceBeam>())
                foreach (var bc in beam.GetComponentsInChildren<BoxCollider>(true))
                    if (bc != null && !bc.isTrigger) SampleTop(bc, detail, false, area);
            foreach (var mp in FindAll<MovingPlatform>())
                SamplePlatform(mp, detail);

            // Environment probes: coarse grid on whatever is below (street, roofs) around the play
            // area, for probe-lit props, distant buildings and dynamic objects.
            var environment = new List<Vector3>();
            try { SampleEnvironment(play, environment); }
            catch (System.Exception e) { Debug.LogWarning("[Bake] Environment probes skipped: " + e.Message); }

            // Both lists hold probe columns (surface points); each column becomes two probes, so dedupe and
            // thin columns, never single probes (thinning a low/high interleaved list by an even stride
            // would keep only one height layer).
            var seen = new HashSet<Vector3Int>();
            detail = Dedupe(detail, seen);
            environment = Dedupe(environment, seen);

            int maxColumns = MaxProbes / 2;
            int envAllot = Mathf.Min(environment.Count, MaxEnvironmentProbes / 2);
            detail = Thin(detail, maxColumns - envAllot);
            environment = Thin(environment, maxColumns - detail.Count);

            var positions = new List<Vector3>(2 * (detail.Count + environment.Count));
            foreach (var p in detail)
            {
                positions.Add(p + Vector3.up * ProbeLowHeight);
                positions.Add(p + Vector3.up * ProbeHighHeight);
            }
            foreach (var p in environment)
            {
                positions.Add(p + Vector3.up * 1.0f);
                positions.Add(p + Vector3.up * 4.0f);
            }
            if (positions.Count < 4)
                Debug.LogWarning("[Bake] Only " + positions.Count + " light probes; dynamic objects will use the ambient probe.");

            LightProbeGroup group = null;
            foreach (var g in FindAll<LightProbeGroup>())
                if (g.gameObject.name == ProbeGroupName) { group = g; break; }
            if (group == null)
            {
                var go = new GameObject(ProbeGroupName);
                group = go.AddComponent<LightProbeGroup>();
            }
            Transform tr = group.transform;
            tr.SetParent(null, false);
            tr.localPosition = Vector3.zero;
            tr.localRotation = Quaternion.identity;
            tr.localScale = Vector3.one;
            group.probePositions = positions.ToArray(); // local == world (identity transform)
            EditorUtility.SetDirty(group);
            return positions.Count;
        }

        /// <summary>Samples a ProbeSpacing grid on the upward-facing face of a box collider.</summary>
        static void SampleTop(BoxCollider bc, List<Vector3> into, bool clipToArea, Bounds area)
        {
            Transform t = bc.transform;
            int upAxis = 1;
            float best = -1f, sign = 1f;
            for (int a = 0; a < 3; a++)
            {
                float dot = Vector3.Dot(t.TransformDirection(Axis(a)), Vector3.up);
                if (Mathf.Abs(dot) > best) { best = Mathf.Abs(dot); upAxis = a; sign = dot >= 0f ? 1f : -1f; }
            }
            if (best < 0.5f) return; // too steep to stand on

            int ua = (upAxis + 1) % 3, va = (upAxis + 2) % 3;
            Vector3 size = bc.size;
            float lenU = t.TransformVector(Axis(ua) * size[ua]).magnitude;
            float lenV = t.TransformVector(Axis(va) * size[va]).magnitude;
            int nu = Mathf.Clamp(Mathf.CeilToInt(lenU / ProbeSpacing), 1, 400);
            int nv = Mathf.Clamp(Mathf.CeilToInt(lenV / ProbeSpacing), 1, 400);

            Vector3 top = bc.center;
            top[upAxis] += sign * size[upAxis] * 0.5f;
            for (int i = 0; i < nu; i++)
                for (int j = 0; j < nv; j++)
                {
                    Vector3 lp = top;
                    lp[ua] += ((i + 0.5f) / nu - 0.5f) * size[ua];
                    lp[va] += ((j + 0.5f) / nv - 0.5f) * size[va];
                    Vector3 wp = t.TransformPoint(lp);
                    if (clipToArea && (wp.x < area.min.x || wp.x > area.max.x || wp.z < area.min.z || wp.z > area.max.z)) continue;
                    into.Add(wp); // column base; heights are added in BuildLightProbes
                }
        }

        /// <summary>Probes on the platform deck where it rests, then along its waypoint path.</summary>
        static void SamplePlatform(MovingPlatform mp, List<Vector3> into)
        {
            var decks = new List<BoxCollider>();
            foreach (var bc in mp.GetComponentsInChildren<BoxCollider>(true))
                if (bc != null && !bc.isTrigger) decks.Add(bc);
            if (decks.Count == 0) return;

            var dummy = new Bounds();
            foreach (var bc in decks) SampleTop(bc, into, false, dummy);

            if (mp.waypoints == null || mp.waypoints.Length < 2) return;
            // One column per step along the path, at the centre of the deck (lowest collider top, i.e.
            // the floor rather than the railings).
            Bounds all = WorldBounds(decks[0]);
            float floorY = all.max.y;
            foreach (var bc in decks)
            {
                Bounds db = WorldBounds(bc);
                all.Encapsulate(db);
                floorY = Mathf.Min(floorY, db.max.y);
            }
            Vector3 deckTop = new Vector3(all.center.x, floorY, all.center.z);
            Vector3 origin = mp.transform.position;
            for (int w = 1; w < mp.waypoints.Length; w++)
            {
                Transform a = mp.waypoints[w - 1], b = mp.waypoints[w];
                if (a == null || b == null) continue;
                float dist = Vector3.Distance(a.position, b.position);
                int steps = Mathf.Clamp(Mathf.CeilToInt(dist / ProbeSpacing), 1, 200);
                for (int s = 0; s <= steps; s++)
                    into.Add(deckTop + Vector3.Lerp(a.position, b.position, s / (float)steps) - origin);
            }
        }

        static void SampleEnvironment(Bounds play, List<Vector3> into)
        {
            Physics.SyncTransforms();
            Bounds env = play;
            env.Expand(EnvironmentMargin * 2f);
            float top = Mathf.Max(env.max.y + 300f, 600f);
            float maxDist = top + 1000f;
            for (float x = env.min.x; x <= env.max.x; x += EnvironmentSpacing)
                for (float z = env.min.z; z <= env.max.z; z += EnvironmentSpacing)
                {
                    RaycastHit hit;
                    if (!Physics.Raycast(new Vector3(x, top, z), Vector3.down, out hit, maxDist, ~0, QueryTriggerInteraction.Ignore))
                        continue;
                    into.Add(hit.point); // column base; +1 m and +4 m are added in BuildLightProbes
                }
        }

        static Vector3 Axis(int a) => a == 0 ? Vector3.right : (a == 1 ? Vector3.up : Vector3.forward);

        static List<Vector3> Dedupe(List<Vector3> src, HashSet<Vector3Int> seen)
        {
            var result = new List<Vector3>(src.Count);
            foreach (var p in src)
            {
                var key = new Vector3Int(Mathf.RoundToInt(p.x), Mathf.RoundToInt(p.y * 2f), Mathf.RoundToInt(p.z));
                if (seen.Add(key)) result.Add(p);
            }
            return result;
        }

        /// <summary>Keeps at most max items, picked evenly across the list.</summary>
        static List<Vector3> Thin(List<Vector3> src, int max)
        {
            if (max <= 0) return new List<Vector3>();
            if (src.Count <= max) return src;
            var result = new List<Vector3>(max);
            for (int i = 0; i < max; i++)
                result.Add(src[(int)((long)i * src.Count / max)]);
            return result;
        }

        // ------------------------------------------------------------------ reflection probes

        static int ConfigureReflectionProbes()
        {
            int n = 0;
            foreach (var rp in FindAll<ReflectionProbe>())
            {
                rp.mode = ReflectionProbeMode.Baked; // baked by Lightmapping.Bake
                EditorUtility.SetDirty(rp);
                n++;
            }
            return n;
        }

        // ------------------------------------------------------------------ helpers

        static List<T> FindAll<T>() where T : Component
        {
            Scene scene = SceneManager.GetActiveScene();
            var list = new List<T>();
            foreach (var c in Object.FindObjectsByType<T>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                if (c != null && c.gameObject.scene == scene) list.Add(c);
            return list;
        }

        static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            int slash = path.LastIndexOf('/');
            string parent = path.Substring(0, slash);
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, path.Substring(slash + 1));
        }
    }
}
