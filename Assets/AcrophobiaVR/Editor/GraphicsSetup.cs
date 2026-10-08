using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;

namespace AcrophobiaVR.EditorTools
{
    /// <summary>
    /// Project-wide and per-scene graphics setup: URP asset tuning (PC vs Quest),
    /// SSAO on the PC renderer, per-mood post-processing profiles, reflection probes.
    /// </summary>
    public static class GraphicsSetup
    {
        public const string PostFXDir = "Assets/AcrophobiaVR/Generated/PostFX";
        static readonly string[] Moods = { "park", "sunset", "noon", "golden" };

        // ------------------------------------------------------------------ project

        public static void ConfigureProject()
        {
            try { ConfigurePipelineAssets(); }
            catch (System.Exception e) { Debug.LogWarning("[GraphicsSetup] Pipeline asset tuning skipped: " + e.Message); }

            foreach (var mood in Moods)
            {
                try { BuildProfile(mood); }
                catch (System.Exception e) { Debug.LogWarning("[GraphicsSetup] PostFX profile '" + mood + "' skipped: " + e.Message); }
            }

            AssetDatabase.SaveAssets();
        }

        static void ConfigurePipelineAssets()
        {
            var all = new List<UniversalRenderPipelineAsset>();
            foreach (var guid in AssetDatabase.FindAssets("t:UniversalRenderPipelineAsset"))
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                if (!path.StartsWith("Assets/")) continue;
                var a = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(path);
                if (a != null && !all.Contains(a)) all.Add(a);
            }
            if (all.Count == 0)
            {
                Debug.LogWarning("[GraphicsSetup] No UniversalRenderPipelineAsset found under Assets/.");
                return;
            }

            UniversalRenderPipelineAsset pc = null, quest = null;
            foreach (var a in all)
            {
                string n = a.name.ToLowerInvariant();
                if (pc == null && (n.Contains("quality") || n.Contains("pc") || n.Contains("high"))) pc = a;
                else if (quest == null && (n.Contains("performance") || n.Contains("mobile") || n.Contains("quest") || n.Contains("android"))) quest = a;
            }

            // Fallbacks: PC = pipeline of the highest quality level; Quest = project default pipeline.
            if (pc == null)
            {
                for (int i = QualitySettings.names.Length - 1; i >= 0 && pc == null; i--)
                    pc = QualitySettings.GetRenderPipelineAssetAt(i) as UniversalRenderPipelineAsset;
            }
            if (quest == null)
                quest = GraphicsSettings.defaultRenderPipeline as UniversalRenderPipelineAsset;
            if (pc == quest)
            {
                Debug.LogWarning("[GraphicsSetup] PC and Quest share one URP asset - only light settings applied.");
                pc = null;
            }

            if (pc != null) TunePC(pc);
            if (quest != null) TuneQuest(quest);
        }

        static void TunePC(UniversalRenderPipelineAsset a)
        {
            a.shadowDistance = 150f;
            a.shadowCascadeCount = 4;
            a.supportsHDR = true;
            a.msaaSampleCount = 4;
            try { a.mainLightShadowmapResolution = 2048; } catch { }

            var so = new SerializedObject(a);
            var soft = so.FindProperty("m_SoftShadowsSupported");
            if (soft != null) soft.boolValue = true;
            so.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(a);

            try { AddSSAO(a); }
            catch (System.Exception e) { Debug.LogWarning("[GraphicsSetup] SSAO skipped: " + e.Message); }
        }

        static void TuneQuest(UniversalRenderPipelineAsset a)
        {
            a.shadowDistance = 40f;
            a.msaaSampleCount = 4;
            // Longer shadow distance means more casters; cap the shadow map so Quest never gets heavier.
            try { if (a.mainLightShadowmapResolution > 2048) a.mainLightShadowmapResolution = 2048; } catch { }
            EditorUtility.SetDirty(a);
        }

        static void AddSSAO(UniversalRenderPipelineAsset pc)
        {
            var list = pc.rendererDataList;
            if (list.Length == 0 || list[0] == null)
            {
                Debug.LogWarning("[GraphicsSetup] PC URP asset has no renderer data; SSAO not added.");
                return;
            }

            int index = 0;
            var aso = new SerializedObject(pc);
            var idxProp = aso.FindProperty("m_DefaultRendererIndex");
            if (idxProp != null && idxProp.intValue >= 0 && idxProp.intValue < list.Length && list[idxProp.intValue] != null)
                index = idxProp.intValue;
            var data = list[index];

            if (!(data is UniversalRendererData))
            {
                Debug.LogWarning("[GraphicsSetup] PC renderer is not a UniversalRendererData; SSAO not added.");
                return;
            }
            if (!EditorUtility.IsPersistent(data))
            {
                Debug.LogWarning("[GraphicsSetup] PC renderer data is not an asset; SSAO not added.");
                return;
            }

            // Never add SSAO to a renderer that the Quest pipeline also uses.
            foreach (var guid in AssetDatabase.FindAssets("t:UniversalRenderPipelineAsset"))
            {
                var other = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(AssetDatabase.GUIDToAssetPath(guid));
                if (other == null || other == pc) continue;
                var ol = other.rendererDataList;
                for (int i = 0; i < ol.Length; i++)
                    if (ol[i] == data)
                    {
                        Debug.LogWarning("[GraphicsSetup] PC renderer data is shared with '" + other.name + "'; SSAO not added.");
                        return;
                    }
            }

            ScreenSpaceAmbientOcclusion ssao = null;
            foreach (var f in data.rendererFeatures)
                if (f is ScreenSpaceAmbientOcclusion s) { ssao = s; break; }

            if (ssao == null)
            {
                ssao = ScriptableObject.CreateInstance<ScreenSpaceAmbientOcclusion>();
                ssao.name = "ScreenSpaceAmbientOcclusion";
                AssetDatabase.AddObjectToAsset(ssao, data);
                AssetDatabase.TryGetGUIDAndLocalFileIdentifier(ssao, out string _, out long localId);

                var dso = new SerializedObject(data);
                var feats = dso.FindProperty("m_RendererFeatures");
                var map = dso.FindProperty("m_RendererFeatureMap");
                if (feats == null || map == null)
                {
                    Debug.LogWarning("[GraphicsSetup] Renderer feature list not found; SSAO not added.");
                    AssetDatabase.RemoveObjectFromAsset(ssao);
                    Object.DestroyImmediate(ssao, true);
                    return;
                }
                feats.arraySize++;
                feats.GetArrayElementAtIndex(feats.arraySize - 1).objectReferenceValue = ssao;
                map.arraySize++;
                map.GetArrayElementAtIndex(map.arraySize - 1).longValue = localId;
                dso.ApplyModifiedPropertiesWithoutUndo();
            }

            var sso = new SerializedObject(ssao);
            SetFloat(sso, "m_Settings.Intensity", 0.6f);
            SetFloat(sso, "m_Settings.Radius", 0.3f);
            SetFloat(sso, "m_Settings.DirectLightingStrength", 0.25f);
            sso.ApplyModifiedPropertiesWithoutUndo();
            ssao.SetActive(true);

            EditorUtility.SetDirty(ssao);
            EditorUtility.SetDirty(data);
            data.SetDirty();
        }

        static void SetFloat(SerializedObject so, string path, float v)
        {
            var p = so.FindProperty(path);
            if (p != null && p.propertyType == SerializedPropertyType.Float) p.floatValue = v;
        }

        // ------------------------------------------------------------------ post fx profiles

        struct MoodLook
        {
            public float bloom, exposure, contrast, saturation, temperature, tint, vignette;
            public Color filter;
        }

        static MoodLook LookFor(string mood)
        {
            switch (mood)
            {
                case "sunset":
                    return new MoodLook { bloom = 0.8f, exposure = 0.05f, contrast = 14f, saturation = 10f, temperature = 18f, tint = 4f, vignette = 0.2f, filter = new Color(1f, 0.93f, 0.86f) };
                case "golden":
                    return new MoodLook { bloom = 0.7f, exposure = 0.1f, contrast = 13f, saturation = 10f, temperature = 12f, tint = 2f, vignette = 0.18f, filter = new Color(1f, 0.96f, 0.88f) };
                case "noon":
                    return new MoodLook { bloom = 0.5f, exposure = 0.05f, contrast = 12f, saturation = 6f, temperature = 0f, tint = 0f, vignette = 0.15f, filter = new Color(0.98f, 0.99f, 1f) };
                default: // park
                    return new MoodLook { bloom = 0.6f, exposure = 0.1f, contrast = 11f, saturation = 12f, temperature = 4f, tint = 0f, vignette = 0.16f, filter = new Color(1f, 0.99f, 0.96f) };
            }
        }

        static string ProfilePath(string mood) => PostFXDir + "/PostFX_" + mood + ".asset";

        static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            int slash = path.LastIndexOf('/');
            string parent = path.Substring(0, slash);
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, path.Substring(slash + 1));
        }

        static T GetOrAdd<T>(VolumeProfile profile) where T : VolumeComponent
        {
            if (!profile.TryGet<T>(out var comp) || comp == null)
                comp = profile.Add<T>(true);
            comp.active = true;
            if (!AssetDatabase.IsSubAsset(comp))
            {
                comp.hideFlags = HideFlags.HideInInspector | HideFlags.HideInHierarchy;
                AssetDatabase.AddObjectToAsset(comp, profile);
            }
            return comp;
        }

        static VolumeProfile BuildProfile(string mood)
        {
            EnsureFolder(PostFXDir);
            string path = ProfilePath(mood);
            var profile = AssetDatabase.LoadAssetAtPath<VolumeProfile>(path);
            if (profile == null)
            {
                profile = ScriptableObject.CreateInstance<VolumeProfile>();
                profile.name = "PostFX_" + mood;
                AssetDatabase.CreateAsset(profile, path);
            }
            // Drop dangling entries (deleted sub-assets) so TryGet/Add never hit a null component.
            profile.components.RemoveAll(c => c == null);

            var look = LookFor(mood);

            var tm = GetOrAdd<Tonemapping>(profile);
            tm.mode.Override(TonemappingMode.ACES);

            var bloom = GetOrAdd<Bloom>(profile);
            bloom.threshold.Override(0.95f);
            bloom.intensity.Override(look.bloom);
            bloom.scatter.Override(0.7f);
            bloom.highQualityFiltering.Override(false);

            var ca = GetOrAdd<ColorAdjustments>(profile);
            ca.postExposure.Override(look.exposure);
            ca.contrast.Override(look.contrast);
            ca.saturation.Override(look.saturation);
            ca.colorFilter.Override(look.filter);

            var wb = GetOrAdd<WhiteBalance>(profile);
            wb.temperature.Override(look.temperature);
            wb.tint.Override(look.tint);

            var vg = GetOrAdd<Vignette>(profile);
            vg.intensity.Override(look.vignette);
            vg.smoothness.Override(0.4f);

            foreach (var c in profile.components) if (c != null) EditorUtility.SetDirty(c);
            EditorUtility.SetDirty(profile);
            return profile;
        }

        // ------------------------------------------------------------------ scene

        public static void ApplyToScene(string mood, Vector3 probeCenter, Vector3 probeSize)
        {
            if (string.IsNullOrEmpty(mood)) mood = "park";
            mood = mood.ToLowerInvariant();

            VolumeProfile profile = AssetDatabase.LoadAssetAtPath<VolumeProfile>(ProfilePath(mood));
            if (profile == null)
            {
                try { profile = BuildProfile(mood); AssetDatabase.SaveAssets(); }
                catch (System.Exception e) { Debug.LogWarning("[GraphicsSetup] Could not build profile '" + mood + "': " + e.Message); }
            }

            // Global volume
            var volGo = GameObject.Find("Global Volume");
            if (volGo == null) volGo = new GameObject("Global Volume");
            var vol = volGo.GetComponent<Volume>();
            if (vol == null) vol = volGo.AddComponent<Volume>();
            vol.isGlobal = true;
            vol.priority = 1f;
            vol.weight = 1f;
            vol.sharedProfile = profile;
            if (volGo.GetComponent<PlatformGraphics>() == null) volGo.AddComponent<PlatformGraphics>();

            // Reflection probe
            var probeGo = GameObject.Find("Reflection Probe");
            if (probeGo == null) probeGo = new GameObject("Reflection Probe");
            probeGo.transform.position = probeCenter;
            var probe = probeGo.GetComponent<ReflectionProbe>();
            if (probe == null) probe = probeGo.AddComponent<ReflectionProbe>();
            // Baked by LightingBaker (Lightmapping.Bake): free at runtime, so it stays on for Quest too.
            probe.mode = ReflectionProbeMode.Baked;
            probe.refreshMode = ReflectionProbeRefreshMode.OnAwake;
            probe.timeSlicingMode = ReflectionProbeTimeSlicingMode.NoTimeSlicing;
            probe.size = probeSize;
            probe.center = Vector3.zero;
            probe.resolution = 128;
            probe.boxProjection = false;
            probe.importance = 1;
            probe.intensity = 1f;
            probe.clearFlags = ReflectionProbeClearFlags.Skybox;
            probe.hdr = true;

            // Cameras: post-processing on, no post AA (MSAA handles VR).
            var cams = Object.FindObjectsByType<Camera>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            foreach (var cam in cams)
            {
                var data = cam.GetComponent<UniversalAdditionalCameraData>();
                if (data == null) data = cam.gameObject.AddComponent<UniversalAdditionalCameraData>();
                data.renderPostProcessing = true;
                data.antialiasing = AntialiasingMode.None;
                EditorUtility.SetDirty(data);
                // XR rig cameras are usually prefab instances: record the overrides or they are lost on save.
                if (PrefabUtility.IsPartOfPrefabInstance(data))
                    PrefabUtility.RecordPrefabInstancePropertyModifications(data);
            }

            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;
            RenderSettings.reflectionIntensity = 1f;

            Scene scene = SceneManager.GetActiveScene();
            if (scene.IsValid()) EditorSceneManager.MarkSceneDirty(scene);
        }
    }
}
