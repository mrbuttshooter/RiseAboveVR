using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace AcrophobiaVR
{
    /// <summary>
    /// Lives on the scene's Global Volume. On PC (desktop / PCVR) everything stays on and
    /// post-processing is re-enabled on the main camera. On Android (standalone Quest) the
    /// expensive extras - post-processing, the global volume and realtime reflection probes -
    /// are switched off to protect frame rate.
    /// </summary>
    [DisallowMultipleComponent]
    public class PlatformGraphics : MonoBehaviour
    {
        static bool IsQuest => Application.platform == RuntimePlatform.Android;

        void Awake()
        {
            if (!IsQuest) return;

            var cams = FindObjectsByType<Camera>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            for (int i = 0; i < cams.Length; i++) SetPost(cams[i], false);

            var vol = GetComponent<Volume>();
            if (vol != null) vol.enabled = false;

            // Only realtime probes cost anything at runtime (they re-render the scene); baked probes are
            // just a cubemap lookup, so they stay on.
            var probes = FindObjectsByType<ReflectionProbe>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            for (int i = 0; i < probes.Length; i++)
                if (probes[i] != null && probes[i].mode == ReflectionProbeMode.Realtime) probes[i].enabled = false;
        }

        void Start()
        {
            // The XR rig camera may be spawned from a prefab after Awake ran.
            var main = Camera.main;
            if (main != null) SetPost(main, !IsQuest);
        }

        static void SetPost(Camera cam, bool on)
        {
            if (cam == null) return;
            var data = cam.GetComponent<UniversalAdditionalCameraData>();
            if (data == null)
            {
                if (!on) return; // nothing to disable
                data = cam.gameObject.AddComponent<UniversalAdditionalCameraData>();
            }
            data.renderPostProcessing = on;
        }
    }
}
