using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.XR.Management;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.XR.Management;
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.OpenXR.Features;
using UnityEngine.XR.OpenXR.Features.Interactions;
using UnityEngine.XR.OpenXR.Features.MetaQuestSupport;

namespace AcrophobiaVR.EditorTools
{
    /// <summary>
    /// One-click Meta Quest (standalone Android) configuration: player settings, OpenXR Android
    /// features, XR loader check and the Android default quality level. Idempotent - safe to run
    /// any number of times. Does not switch the active build target (that reimports every asset);
    /// "Rise Above/Build Quest APK" offers the switch and then builds the APK.
    /// </summary>
    public static class QuestSetup
    {
        public const string CompanyName = "RiseAbove";
        public const string ProductName = "Rise Above VR";
        public const string Version = "1.0";
        public const string PackageId = "com.riseabove.vr";
        public const string PerformancePipelineName = "Performance URP Config";
        public const string ApkPath = "Builds/RiseAboveVR-Quest.apk";

        const string MetaDisplayUtilitiesType = "UnityEngine.XR.OpenXR.Features.Meta.DisplayUtilitiesFeature";
        const string QualitySettingsPath = "ProjectSettings/QualitySettings.asset";
        const string AndroidPlatform = "Android";

        /// <summary>Quest 2 / Pro / 3 / 3S (manifest name, visible name). Quest 1 cannot run Android API 32.</summary>
        static readonly string[,] QuestDevices =
        {
            { "quest2", "Quest 2" }, { "cambria", "Quest Pro" }, { "eureka", "Quest 3" }, { "quest3s", "Quest 3S" }
        };
        const string Quest1Manifest = "quest";

        // ------------------------------------------------------------------ menu

        [MenuItem("Rise Above/Configure for Meta Quest", priority = 60)]
        public static void Apply()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                Debug.LogWarning("[Quest] Exit Play mode first - OpenXR settings cannot be changed while XR is running.");
                return;
            }

            int failed = 0;
            failed += Step("player identity", ApplyIdentity);
            failed += Step("Android player settings", ApplyAndroid);
            failed += Step("OpenXR Android features", ApplyOpenXR);
            failed += Step("XR loader check", CheckLoader);
            failed += Step("Android quality level", ApplyQuality);

            AssetDatabase.SaveAssets();
            Debug.Log("[Quest] Configure for Meta Quest finished" + (failed > 0 ? " with " + failed + " skipped step(s) (see warnings)" : "") +
                      ".\n" + Report());
        }

        [MenuItem("Rise Above/Quest Settings Report", priority = 61)]
        static void LogReport() => Debug.Log(Report());

        [MenuItem("Rise Above/Build Quest APK", priority = 62)]
        public static void BuildApk()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                Debug.LogWarning("[Quest] Exit Play mode before building.");
                return;
            }

            if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
            {
                bool sw = EditorUtility.DisplayDialog("Switch to Android?",
                    "The Quest APK needs the Android build target. Switching reimports all textures and can take several minutes.\n\n" +
                    "After the switch finishes, choose Rise Above > Build Quest APK again.",
                    "Switch to Android", "Cancel");
                if (!sw) return;
                Apply();
                if (!EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android))
                    Debug.LogError("[Quest] Could not switch to Android. Is the Android Build Support module installed (Unity Hub > Installs > Add modules)?");
                else
                    Debug.Log("[Quest] Active build target is now Android. Run Rise Above > Build Quest APK again to build.");
                return;
            }

            Apply();

            var scenes = new List<string>();
            foreach (var s in EditorBuildSettings.scenes)
                if (s != null && s.enabled && !string.IsNullOrEmpty(s.path)) scenes.Add(s.path);
            if (scenes.Count == 0)
            {
                Debug.LogError("[Quest] No enabled scenes in Build Settings - run Rise Above > Build All Scenes first.");
                return;
            }

            string dir = Path.GetDirectoryName(ApkPath);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            EditorUserBuildSettings.buildAppBundle = false;

            var options = new BuildPlayerOptions
            {
                scenes = scenes.ToArray(),
                locationPathName = ApkPath,
                target = BuildTarget.Android,
                targetGroup = BuildTargetGroup.Android,
                options = BuildOptions.None
            };

            BuildReport report = BuildPipeline.BuildPlayer(options);
            var summary = report.summary;
            if (summary.result == BuildResult.Succeeded)
            {
                Debug.Log("[Quest] APK built: " + Path.GetFullPath(ApkPath) + " (" + (summary.totalSize / (1024f * 1024f)).ToString("0.0") +
                          " MB). Install with: adb install -r \"" + Path.GetFullPath(ApkPath) + "\" (or drag it onto SideQuest / Meta Quest Developer Hub).");
                EditorUtility.RevealInFinder(ApkPath);
            }
            else
            {
                Debug.LogError("[Quest] APK build " + summary.result + " with " + summary.totalErrors + " error(s). See the Console above.");
            }
        }

        // ------------------------------------------------------------------ steps

        static int Step(string name, Action action)
        {
            try
            {
                action();
                return 0;
            }
            catch (Exception e)
            {
                Debug.LogWarning("[Quest] Step '" + name + "' skipped: " + e.Message);
                return 1;
            }
        }

        static void Try(string what, Action action)
        {
            try { action(); }
            catch (Exception e) { Debug.LogWarning("[Quest] " + what + " not set: " + e.Message); }
        }

        static void ApplyIdentity()
        {
            // companyName is part of the Windows/Editor PlayerPrefs key and Application.persistentDataPath, so renaming an
            // existing company would orphan saved stars, achievements, photos and the session CSV used for the report.
            // Android uses the package id for both, so Quest builds do not need it changed.
            if (string.IsNullOrWhiteSpace(PlayerSettings.companyName))
                PlayerSettings.companyName = CompanyName;
            else if (PlayerSettings.companyName != CompanyName)
                Debug.Log("[Quest] Company name left as '" + PlayerSettings.companyName + "' so existing desktop save data and session logs stay where they are.");
            PlayerSettings.productName = ProductName;
            PlayerSettings.bundleVersion = Version;
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, PackageId);
            // Keep any higher version code the user set for a store upload.
            if (PlayerSettings.Android.bundleVersionCode < 1) PlayerSettings.Android.bundleVersionCode = 1;
        }

        static void ApplyAndroid()
        {
            Try("IL2CPP scripting backend", () => PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, ScriptingImplementation.IL2CPP));
            Try("ARM64 architecture", () => PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64);
            // Quest 2 / 3 / 3S / Pro all run Android 12L (API 32) or newer.
            Try("min SDK", () => PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel32);
            Try("target SDK", () => PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevelAuto);
            Try("Vulkan graphics API", () =>
            {
                var apis = PlayerSettings.GetGraphicsAPIs(BuildTarget.Android);
                bool vulkanOnly = apis != null && apis.Length == 1 && apis[0] == GraphicsDeviceType.Vulkan;
                if (PlayerSettings.GetUseDefaultGraphicsAPIs(BuildTarget.Android))
                    PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
                if (!vulkanOnly)
                    PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.Vulkan });
            });
            Try("ASTC texture subtarget", () => EditorUserBuildSettings.androidBuildSubtarget = MobileTextureSubtarget.ASTC);
            Try("ASTC texture formats", SetAstcFormats);
            Try("development build off", () => EditorUserBuildSettings.development = false);
            Try("APK output", () => EditorUserBuildSettings.buildAppBundle = false);
            Try("install location", () => PlayerSettings.Android.preferredInstallLocation = AndroidPreferredInstallLocation.Auto);
            Try("landscape-left orientation", () => PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft);
            // Required by the Meta Quest Support feature validation for Unity 6.
            Try("GameActivity entry point", () => PlayerSettings.Android.applicationEntry = AndroidApplicationEntry.GameActivity);
            if (PlayerSettings.colorSpace != ColorSpace.Linear)
                Debug.LogWarning("[Quest] Color space is " + PlayerSettings.colorSpace + " - Linear is recommended (left unchanged; changing it reimports textures).");
        }

        /// <summary>PlayerSettings.Android.textureCompressionFormats via reflection so a signature change can never break compilation.</summary>
        static void SetAstcFormats()
        {
            var prop = typeof(PlayerSettings.Android).GetProperty("textureCompressionFormats", BindingFlags.Public | BindingFlags.Static);
            if (prop == null || !prop.CanWrite || prop.PropertyType != typeof(UnityEditor.TextureCompressionFormat[]))
            {
                Debug.Log("[Quest] PlayerSettings.Android.textureCompressionFormats unavailable - using the ASTC build subtarget only.");
                return;
            }
            prop.SetValue(null, new[] { UnityEditor.TextureCompressionFormat.ASTC });
        }

        static string GetAstcFormats()
        {
            try
            {
                var prop = typeof(PlayerSettings.Android).GetProperty("textureCompressionFormats", BindingFlags.Public | BindingFlags.Static);
                if (prop == null) return "n/a";
                var arr = prop.GetValue(null) as Array;
                if (arr == null) return "n/a";
                var sb = new StringBuilder();
                foreach (var f in arr) sb.Append(sb.Length > 0 ? ", " : "").Append(f);
                return sb.ToString();
            }
            catch (Exception e) { return "n/a (" + e.Message + ")"; }
        }

        static void ApplyOpenXR()
        {
            var s = OpenXRSettings.GetSettingsForBuildTargetGroup(BuildTargetGroup.Android);
            if (s == null)
                throw new InvalidOperationException("No OpenXR settings for Android - tick OpenXR in Project Settings > XR Plug-in Management > Android first.");

            Try("multiview render mode", () => s.renderMode = OpenXRSettings.RenderMode.SinglePassInstanced);
            Try("latency optimization", () => s.latencyOptimization = OpenXRSettings.LatencyOptimization.PrioritizeInputPolling);
            // URP + Unity 6: the SRP foveation API is the one driven by XRDisplaySubsystem.foveatedRenderingLevel (see QuestPerformance).
            Try("SRP foveation API", () => s.foveatedRenderingApi = OpenXRSettings.BackendFovationApi.SRPFoveation);

            var quest = s.GetFeature<MetaQuestFeature>();
            if (quest == null)
            {
                Debug.LogWarning("[Quest] Meta Quest Support feature not found in the Android OpenXR settings.");
            }
            else
            {
                quest.enabled = true;
                Try("Quest target devices", () => EnsureTargetDevices(quest));
                EditorUtility.SetDirty(quest);
            }

            // Controllers: keep whatever Touch profiles are on; make sure at least Oculus Touch is.
            bool touch = IsEnabled(s.GetFeature<OculusTouchControllerProfile>())
                         || IsEnabled(s.GetFeature<MetaQuestTouchPlusControllerProfile>())
                         || IsEnabled(s.GetFeature<MetaQuestTouchProControllerProfile>());
            if (!touch)
            {
                var oculus = s.GetFeature<OculusTouchControllerProfile>();
                if (oculus != null)
                {
                    oculus.enabled = true;
                    EditorUtility.SetDirty(oculus);
                    Debug.Log("[Quest] Enabled the Oculus Touch controller interaction profile.");
                }
                else Debug.LogWarning("[Quest] No Touch controller interaction profile available for Android.");
            }

            var fov = s.GetFeature<FoveatedRenderingFeature>();
            if (fov != null)
            {
                fov.enabled = true;
                EditorUtility.SetDirty(fov);
            }
            else Debug.LogWarning("[Quest] Foveated Rendering feature not found - foveation will be inactive.");

            // Lets QuestPerformance request 90 Hz.
            var display = FindFeature(s, MetaDisplayUtilitiesType);
            if (display != null)
            {
                display.enabled = true;
                EditorUtility.SetDirty(display);
            }
            else Debug.Log("[Quest] Meta Quest Display Utilities feature not found - the headset keeps its default refresh rate.");

            EditorUtility.SetDirty(s);
        }

        static void EnsureTargetDevices(MetaQuestFeature quest)
        {
            int n = QuestDevices.GetLength(0);
            for (int i = 0; i < n; i++) quest.AddTargetDevice(QuestDevices[i, 0], QuestDevices[i, 1], true);

            var so = new SerializedObject(quest);
            var list = so.FindProperty("targetDevices");
            if (list == null || !list.isArray)
            {
                Debug.LogWarning("[Quest] MetaQuestFeature.targetDevices not found - check target devices in the feature's gear menu.");
                return;
            }
            for (int i = 0; i < list.arraySize; i++)
            {
                var el = list.GetArrayElementAtIndex(i);
                var manifest = el.FindPropertyRelative("manifestName");
                var enabled = el.FindPropertyRelative("enabled");
                if (manifest == null || enabled == null) continue;
                if (IsQuestDevice(manifest.stringValue)) enabled.boolValue = true;
                else if (manifest.stringValue == Quest1Manifest) enabled.boolValue = false; // Quest 1 tops out at Android 10
            }
            so.ApplyModifiedPropertiesWithoutUndo();
            // Applying the SerializedObject re-reads targetDevices from serialized data, which resets the
            // [NonSerialized] 'active' flag the manifest writer requires (active && enabled). Mark them active again
            // so a build started right after Apply (Build Quest APK) still lists the Quest devices in the manifest.
            for (int i = 0; i < n; i++) quest.AddTargetDevice(QuestDevices[i, 0], QuestDevices[i, 1], true);
        }

        static bool IsQuestDevice(string manifest)
        {
            for (int i = 0; i < QuestDevices.GetLength(0); i++)
                if (QuestDevices[i, 0] == manifest) return true;
            return false;
        }

        static bool IsEnabled(OpenXRFeature f) => f != null && f.enabled;

        static OpenXRFeature FindFeature(OpenXRSettings s, string fullTypeName)
        {
            foreach (var f in s.GetFeatures())
                if (f != null && f.GetType().FullName == fullTypeName) return f;
            return null;
        }

        static void CheckLoader()
        {
            var general = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(BuildTargetGroup.Android);
            if (general == null)
            {
                Debug.LogWarning("[Quest] No XR settings for Android. Open Project Settings > XR Plug-in Management > Android tab and tick OpenXR.");
                return;
            }
            if (!general.InitManagerOnStart)
                Debug.LogWarning("[Quest] 'Initialize XR on Startup' is off for Android - the app would start without VR. Tick it in XR Plug-in Management > Android.");
            if (!HasOpenXRLoader(general))
                Debug.LogWarning("[Quest] OpenXR is not an active XR loader for Android. Tick OpenXR in XR Plug-in Management > Android.");
        }

        static bool HasOpenXRLoader(XRGeneralSettings general)
        {
            var mgr = general != null ? general.Manager : null;
            if (mgr == null) return false;
            foreach (var l in mgr.activeLoaders)
                if (l is OpenXRLoader) return true;
            return false;
        }

        // ------------------------------------------------------------------ quality

        static void ApplyQuality()
        {
            var names = QualitySettings.names;
            var so = QualityObject();
            var map = so != null ? so.FindProperty("m_PerPlatformDefaultQuality") : null;
            if (map == null || !map.isArray)
            {
                Debug.LogWarning("[Quest] m_PerPlatformDefaultQuality not accessible - set the Android default quality in Project Settings > Quality by hand ('" +
                                 PerformancePipelineName + "' level).");
                return;
            }

            SerializedProperty androidValue = FindPlatformEntry(map);
            int current = androidValue != null ? androidValue.intValue : -1;

            int target = -1;
            if (current >= 0 && current < names.Length && UsesPerformancePipeline(current) && IncludedOnAndroid(current))
                target = current;
            for (int i = names.Length - 1; i >= 0 && target < 0; i--)
                if (UsesPerformancePipeline(i) && IncludedOnAndroid(i)) target = i;

            if (target < 0)
            {
                Debug.LogWarning("[Quest] No quality level uses '" + PerformancePipelineName + "' for Android - Android default left at " + current + ".");
                return;
            }
            if (target == current) return;

            if (androidValue == null)
            {
                int idx = map.arraySize;
                map.InsertArrayElementAtIndex(idx);
                var el = map.GetArrayElementAtIndex(idx);
                var first = el.FindPropertyRelative("first");
                androidValue = el.FindPropertyRelative("second");
                if (first == null || androidValue == null)
                {
                    Debug.LogWarning("[Quest] Could not add an Android entry to the per-platform quality map - set it by hand.");
                    return;
                }
                first.stringValue = AndroidPlatform;
            }
            androidValue.intValue = target;
            so.ApplyModifiedPropertiesWithoutUndo();
            Debug.Log("[Quest] Android default quality level: " + names[target] + " (" + PerformancePipelineName + ").");
        }

        static SerializedObject QualityObject()
        {
            var assets = AssetDatabase.LoadAllAssetsAtPath(QualitySettingsPath);
            return assets != null && assets.Length > 0 && assets[0] != null ? new SerializedObject(assets[0]) : null;
        }

        static SerializedProperty FindPlatformEntry(SerializedProperty map)
        {
            for (int i = 0; i < map.arraySize; i++)
            {
                var el = map.GetArrayElementAtIndex(i);
                var first = el.FindPropertyRelative("first");
                if (first != null && first.propertyType == SerializedPropertyType.String && first.stringValue == AndroidPlatform)
                    return el.FindPropertyRelative("second");
            }
            return null;
        }

        static RenderPipelineAsset PipelineAt(int level) =>
            QualitySettings.GetRenderPipelineAssetAt(level) ?? GraphicsSettings.defaultRenderPipeline;

        static bool UsesPerformancePipeline(int level)
        {
            var rp = PipelineAt(level);
            return rp != null && rp.name == PerformancePipelineName;
        }

        static bool IncludedOnAndroid(int level)
        {
            try { return QualitySettings.IsPlatformIncluded(AndroidPlatform, level); }
            catch { return true; } // older API shape / unknown platform name: assume included
        }

        static string AndroidQualityInfo()
        {
            try
            {
                var so = QualityObject();
                var map = so != null ? so.FindProperty("m_PerPlatformDefaultQuality") : null;
                var v = map != null && map.isArray ? FindPlatformEntry(map) : null;
                if (v == null) return "unknown";
                var names = QualitySettings.names;
                int i = v.intValue;
                if (i < 0 || i >= names.Length) return i.ToString();
                var rp = PipelineAt(i);
                return names[i] + " (" + (rp != null ? rp.name : "built-in") + ")";
            }
            catch (Exception e) { return "unknown (" + e.Message + ")"; }
        }

        // ------------------------------------------------------------------ report

        /// <summary>Multi-line summary of the key Quest build settings.</summary>
        public static string Report()
        {
            var sb = new StringBuilder();
            sb.AppendLine("[Quest] Rise Above - Meta Quest build settings");
            Line(sb, "Active build target", () => EditorUserBuildSettings.activeBuildTarget +
                (EditorUserBuildSettings.activeBuildTarget == BuildTarget.Android ? "" : "  (use Rise Above > Build Quest APK or File > Build Profiles to switch to Android)"));
            Line(sb, "Company / product / version", () => PlayerSettings.companyName + " / " + PlayerSettings.productName + " / " +
                PlayerSettings.bundleVersion + " (code " + PlayerSettings.Android.bundleVersionCode + ")");
            Line(sb, "Package id (Android)", () => PlayerSettings.GetApplicationIdentifier(NamedBuildTarget.Android));
            Line(sb, "Scripting backend", () => PlayerSettings.GetScriptingBackend(NamedBuildTarget.Android).ToString());
            Line(sb, "Architectures", () => PlayerSettings.Android.targetArchitectures.ToString());
            Line(sb, "Min / target SDK", () => PlayerSettings.Android.minSdkVersion + " / " + PlayerSettings.Android.targetSdkVersion);
            Line(sb, "Graphics APIs", () =>
            {
                var apis = PlayerSettings.GetGraphicsAPIs(BuildTarget.Android);
                return (apis != null ? string.Join(", ", apis) : "none") + " (auto: " + PlayerSettings.GetUseDefaultGraphicsAPIs(BuildTarget.Android) + ")";
            });
            Line(sb, "Texture compression", () => EditorUserBuildSettings.androidBuildSubtarget + " (formats: " + GetAstcFormats() + ")");
            Line(sb, "Development build / APK", () => EditorUserBuildSettings.development + " / " + !EditorUserBuildSettings.buildAppBundle);
            Line(sb, "Install / orientation / entry", () => PlayerSettings.Android.preferredInstallLocation + " / " +
                PlayerSettings.defaultInterfaceOrientation + " / " + PlayerSettings.Android.applicationEntry);
            Line(sb, "Color space", () => PlayerSettings.colorSpace.ToString());

            Line(sb, "OpenXR (Android)", () =>
            {
                var s = OpenXRSettings.GetSettingsForBuildTargetGroup(BuildTargetGroup.Android);
                if (s == null) return "no Android OpenXR settings";
                return "render " + s.renderMode + ", latency " + s.latencyOptimization + ", foveation API " + s.foveatedRenderingApi;
            });
            Line(sb, "Meta Quest Support", () =>
            {
                var s = OpenXRSettings.GetSettingsForBuildTargetGroup(BuildTargetGroup.Android);
                var q = s != null ? s.GetFeature<MetaQuestFeature>() : null;
                if (q == null) return "not found";
                return (q.enabled ? "enabled" : "DISABLED") + "; devices: " + TargetDevices(q);
            });
            Line(sb, "Controller profiles", () =>
            {
                var s = OpenXRSettings.GetSettingsForBuildTargetGroup(BuildTargetGroup.Android);
                if (s == null) return "n/a";
                var on = new List<string>();
                if (IsEnabled(s.GetFeature<OculusTouchControllerProfile>())) on.Add("Oculus Touch");
                if (IsEnabled(s.GetFeature<MetaQuestTouchPlusControllerProfile>())) on.Add("Quest Touch Plus");
                if (IsEnabled(s.GetFeature<MetaQuestTouchProControllerProfile>())) on.Add("Quest Touch Pro");
                return on.Count > 0 ? string.Join(", ", on) : "NONE";
            });
            Line(sb, "Foveation / display utilities", () =>
            {
                var s = OpenXRSettings.GetSettingsForBuildTargetGroup(BuildTargetGroup.Android);
                if (s == null) return "n/a";
                var fov = s.GetFeature<FoveatedRenderingFeature>();
                var du = FindFeature(s, MetaDisplayUtilitiesType);
                return (fov == null ? "missing" : fov.enabled ? "on" : "off") + " / " + (du == null ? "missing" : du.enabled ? "on" : "off");
            });
            Line(sb, "XR loader (Android)", () =>
            {
                var g = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(BuildTargetGroup.Android);
                if (g == null) return "NOT CONFIGURED";
                return (HasOpenXRLoader(g) ? "OpenXR" : "OpenXR MISSING") + ", init on startup " + g.InitManagerOnStart;
            });
            Line(sb, "Android default quality", AndroidQualityInfo);
            sb.Append("APK output: ").Append(ApkPath);
            return sb.ToString();
        }

        static string TargetDevices(MetaQuestFeature q)
        {
            var so = new SerializedObject(q);
            var list = so.FindProperty("targetDevices");
            if (list == null || !list.isArray) return "unknown";
            var on = new List<string>();
            for (int i = 0; i < list.arraySize; i++)
            {
                var el = list.GetArrayElementAtIndex(i);
                var name = el.FindPropertyRelative("visibleName");
                var en = el.FindPropertyRelative("enabled");
                if (name != null && en != null && en.boolValue) on.Add(name.stringValue);
            }
            return on.Count > 0 ? string.Join(", ", on) : "NONE";
        }

        static void Line(StringBuilder sb, string label, Func<string> value)
        {
            string v;
            try { v = value(); }
            catch (Exception e) { v = "n/a (" + e.Message + ")"; }
            sb.Append(label).Append(": ").AppendLine(v);
        }
    }
}
