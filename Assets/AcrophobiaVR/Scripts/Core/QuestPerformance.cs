using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.XR;

namespace AcrophobiaVR
{
    /// <summary>
    /// Standalone Meta Quest (Android) performance tweaks. Nothing here runs per frame:
    /// work happens once at start-up, once per scene load and when the app resumes.
    /// - Foveated rendering (XRDisplaySubsystem level 1, gaze allowed for eye-tracked headsets).
    /// - Requests a 90 Hz display refresh rate when the headset supports it (Meta Display Utilities feature).
    /// - Switches off shadow casting on small renderers and decorative ones (cloud puffs, feathers, leaves).
    /// - Caps the main camera far clip plane.
    /// Does nothing on Windows / desktop / PCVR or in the Editor.
    /// </summary>
    [DisallowMultipleComponent]
    public class QuestPerformance : MonoBehaviour
    {
        public const float FoveationLevel = 1f;
        public const float PreferredRefreshRate = 90f;
        public const float MaxFarClip = 900f;
        /// <summary>Renderers whose largest bounds extent (half size) is below this lose their shadow.</summary>
        public const float SmallRendererExtent = 0.6f;

        const int DisplayAttempts = 5;
        const float FirstDelay = 0.5f;
        const float RetryDelay = 2f;

        public static QuestPerformance Instance { get; private set; }
        public static bool IsQuest => Application.platform == RuntimePlatform.Android;

        /// <summary>Renderers whose shadow casting was switched off by the last scene pass.</summary>
        public static int LastShadowsDisabled { get; private set; }
        /// <summary>Display refresh rate reported by the headset (0 until known).</summary>
        public static float CurrentRefreshRate { get; private set; }
        public static bool FoveationApplied { get; private set; }

        static readonly List<XRDisplaySubsystem> Displays = new List<XRDisplaySubsystem>();
        static readonly List<GameObject> Roots = new List<GameObject>();
        static readonly List<Renderer> Renderers = new List<Renderer>();

        bool refreshDone;
        Coroutine displayRoutine;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Init()
        {
            if (!IsQuest || Instance != null) return;
            var go = new GameObject("QuestPerformance");
            DontDestroyOnLoad(go);
            Instance = go.AddComponent<QuestPerformance>();
            Debug.Log("[Quest] Performance helper started on " + SystemInfo.deviceModel + " (" + SystemInfo.graphicsDeviceType + ").");
        }

        void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        void OnEnable() => SceneManager.sceneLoaded += OnSceneLoaded;
        void OnDisable() => SceneManager.sceneLoaded -= OnSceneLoaded;

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        void Start()
        {
            // The first scene finished loading before this object existed, so handle it here.
            OptimizeScene(SceneManager.GetActiveScene());
            ScheduleDisplay();
        }

        void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            OptimizeScene(scene);
            ScheduleDisplay();
        }

        void OnApplicationPause(bool paused)
        {
            // Returning from the Quest universal menu / sleep can reset display settings.
            if (paused || !isActiveAndEnabled) return;
            refreshDone = false; // re-check the refresh rate too (cheap: logs "already at" when unchanged)
            ScheduleDisplay();
        }

        void ScheduleDisplay()
        {
            if (displayRoutine != null) StopCoroutine(displayRoutine);
            displayRoutine = StartCoroutine(ApplyDisplayRoutine());
        }

        IEnumerator ApplyDisplayRoutine()
        {
            // Give the OpenXR session a moment to reach the running state after start-up / a scene load.
            yield return new WaitForSecondsRealtime(FirstDelay);
            for (int attempt = 1; attempt <= DisplayAttempts; attempt++)
            {
                var display = FindDisplay();
                if (display != null)
                {
                    ApplyFoveation(display);
                    if (!refreshDone) refreshDone = RequestRefreshRate(display, attempt == DisplayAttempts);
                    if (refreshDone) break;
                }
                else if (attempt == DisplayAttempts)
                {
                    Debug.LogWarning("[Quest] No running XR display subsystem - foveation and refresh rate left at defaults.");
                }
                if (attempt < DisplayAttempts) yield return new WaitForSecondsRealtime(RetryDelay);
            }
            displayRoutine = null;
        }

        // ------------------------------------------------------------------ display

        static XRDisplaySubsystem FindDisplay()
        {
            Displays.Clear();
            SubsystemManager.GetSubsystems(Displays);
            XRDisplaySubsystem found = null;
            for (int i = 0; i < Displays.Count; i++)
            {
                if (Displays[i] != null && Displays[i].running)
                {
                    found = Displays[i];
                    break;
                }
            }
            Displays.Clear();
            return found;
        }

        static void ApplyFoveation(XRDisplaySubsystem display)
        {
            try
            {
                display.foveatedRenderingFlags = XRDisplaySubsystem.FoveatedRenderingFlags.GazeAllowed;
                display.foveatedRenderingLevel = FoveationLevel;
                if (!FoveationApplied)
                    Debug.Log("[Quest] Foveated rendering level " + FoveationLevel.ToString("0.##") + " (gaze allowed).");
                FoveationApplied = true;
            }
            catch (Exception e)
            {
                Debug.LogWarning("[Quest] Foveated rendering not applied: " + e.Message);
            }
        }

        /// <summary>Returns true when nothing more needs to be done (requested, already set or unsupported).</summary>
        static bool RequestRefreshRate(XRDisplaySubsystem display, bool lastAttempt)
        {
            float current;
            if (display.TryGetDisplayRefreshRate(out current)) CurrentRefreshRate = current;

#if UNITY_ANDROID
            try
            {
                var settings = UnityEngine.XR.OpenXR.OpenXRSettings.Instance;
                var feature = settings != null
                    ? settings.GetFeature<UnityEngine.XR.OpenXR.Features.Meta.DisplayUtilitiesFeature>()
                    : null;
                if (feature == null || !feature.enabled)
                {
                    Debug.Log("[Quest] Meta Display Utilities feature not enabled - keeping " + current.ToString("0") + " Hz.");
                    return true;
                }

                Unity.Collections.NativeArray<float> rates = default;
                bool listed = false, supported = false;
                float target = PreferredRefreshRate;
                string all = "";
                try
                {
                    listed = UnityEngine.XR.OpenXR.Features.Meta.MetaOpenXRDisplaySubsystemExtensions
                        .TryGetSupportedDisplayRefreshRates(display, Unity.Collections.Allocator.Temp, out rates);
                    if (listed && rates.IsCreated)
                    {
                        for (int i = 0; i < rates.Length; i++)
                        {
                            all += (i > 0 ? "/" : "") + rates[i].ToString("0");
                            if (Mathf.Abs(rates[i] - PreferredRefreshRate) < 0.5f)
                            {
                                supported = true;
                                target = rates[i];
                            }
                        }
                    }
                }
                finally
                {
                    if (rates.IsCreated) rates.Dispose();
                }

                if (!listed)
                {
                    if (lastAttempt) Debug.LogWarning("[Quest] Could not read supported refresh rates - keeping " + current.ToString("0") + " Hz.");
                    return lastAttempt;
                }
                if (!supported)
                {
                    Debug.Log("[Quest] " + PreferredRefreshRate.ToString("0") + " Hz not offered (" + all + " Hz) - keeping " + current.ToString("0") + " Hz.");
                    return true;
                }
                if (Mathf.Abs(current - target) < 0.5f)
                {
                    Debug.Log("[Quest] Display already at " + current.ToString("0") + " Hz.");
                    return true;
                }

                bool ok = UnityEngine.XR.OpenXR.Features.Meta.MetaOpenXRDisplaySubsystemExtensions
                    .TryRequestDisplayRefreshRate(display, target);
                if (ok)
                {
                    CurrentRefreshRate = target;
                    Debug.Log("[Quest] Requested " + target.ToString("0") + " Hz (was " + current.ToString("0") + " Hz; supported " + all + ").");
                    return true;
                }
                if (lastAttempt) Debug.LogWarning("[Quest] Refresh rate request for " + target.ToString("0") + " Hz was refused - keeping " + current.ToString("0") + " Hz.");
                return lastAttempt;
            }
            catch (Exception e)
            {
                Debug.LogWarning("[Quest] Refresh rate request skipped: " + e.Message);
                return true;
            }
#else
            return true;
#endif
        }

        // ------------------------------------------------------------------ scene

        static void OptimizeScene(Scene scene)
        {
            if (!scene.IsValid() || !scene.isLoaded) return;

            int total = 0, changed = 0;
            Roots.Clear();
            scene.GetRootGameObjects(Roots);
            for (int i = 0; i < Roots.Count; i++)
            {
                if (Roots[i] == null) continue;
                Renderers.Clear();
                Roots[i].GetComponentsInChildren(false, Renderers);
                for (int j = 0; j < Renderers.Count; j++)
                {
                    var r = Renderers[j];
                    if (r == null || !r.enabled) continue;
                    total++;
                    // Keep ShadowsOnly proxies (intentional shadow casters) and renderers already off.
                    var mode = r.shadowCastingMode;
                    if (mode != ShadowCastingMode.On && mode != ShadowCastingMode.TwoSided) continue;
                    if (!ShouldDropShadow(r)) continue;
                    r.shadowCastingMode = ShadowCastingMode.Off;
                    changed++;
                }
            }
            Roots.Clear();
            Renderers.Clear();
            LastShadowsDisabled = changed;

            string farInfo = "n/a (no main camera yet)";
            var cam = Camera.main;
            if (cam != null)
            {
                cam.farClipPlane = Mathf.Min(cam.farClipPlane, MaxFarClip);
                farInfo = cam.farClipPlane.ToString("0") + " m";
            }

            Debug.Log("[Quest] Scene '" + scene.name + "': shadow casting off on " + changed + "/" + total +
                      " renderers (small or decorative); camera far clip " + farInfo + ".");
        }

        static bool ShouldDropShadow(Renderer r)
        {
            Vector3 e = r.bounds.extents;
            if (Mathf.Max(e.x, Mathf.Max(e.y, e.z)) < SmallRendererExtent) return true;

            string n = r.gameObject.name;
            return n.StartsWith("Puff", StringComparison.Ordinal)
                || n.StartsWith("Feather", StringComparison.Ordinal)
                || n.StartsWith("Canopy", StringComparison.Ordinal)
                || n.IndexOf("Leaf", StringComparison.Ordinal) >= 0
                || n.IndexOf("Leaves", StringComparison.Ordinal) >= 0;
        }
    }
}
