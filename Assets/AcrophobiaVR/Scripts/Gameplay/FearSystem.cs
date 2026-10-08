using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using UnityEngine.XR;

namespace AcrophobiaVR
{
    /// <summary>
    /// Simulates what acrophobia feels like from the player's own point of view.
    /// Fear rises when the head is exposed to a drop (sampled around and below the head) and when
    /// the player LOOKS DOWN into the drop. It shows as tunnel vision, draining colour, chromatic
    /// shimmer, a desktop vertigo zoom, a pounding heartbeat (audio + controller haptics) and a BPM
    /// readout. Staying at maximum fear triggers a panic attack: the player must LOOK UP at the sky
    /// to calm down - freezing for too long counts as a slip. Looking up / crouching / breathing
    /// are the coping tools, exactly like in real exposure therapy.
    /// </summary>
    [DefaultExecutionOrder(50)]
    public class FearSystem : MonoBehaviour
    {
        public static FearSystem Instance { get; private set; }

        public static float Fear => Instance != null ? Instance.fear : 0f;
        public static bool Panicking => Instance != null && Instance.panic;
        public static int Bpm => Instance != null ? Mathf.RoundToInt(Instance.bpm) : 70;
        public static int PeakBpm => Instance != null ? Mathf.RoundToInt(Instance.peakBpm) : 70;
        public static int PanicsBeaten => Instance != null ? Instance.panicsBeaten : 0;

        [Header("Tuning")]
        public float fullFearDrop = 60f;      // a drop this deep (m) is maximally scary
        public float riseRate = 0.32f;
        public float fallRate = 0.22f;
        public float lookUpFallRate = 0.75f;
        public float panicThreshold = 0.93f;
        public float panicAfter = 2.5f;       // seconds at the threshold before panic starts
        public float freezeLimit = 9f;        // seconds of panic without looking up -> slip

        float fear;
        float target;
        bool panic;
        float atThreshold;
        float panicStarted;
        float lookUpTimer;
        int panicsBeaten;
        float bpm = 70f;
        float peakBpm = 70f;
        float beatTimer;
        bool tutorialSaid;
        float nextLookUpHint;
        float baseFov = -1f;

        Volume volume;
        Vignette vignette;
        ChromaticAberration aberration;
        ColorAdjustments colour;
        LensDistortion lens;
        CanvasGroup edgeGroup;
        Image edgeImage;
        Canvas edgeCanvas;
        Transform heartPanel;
        Text heartText;
        Image heartIcon;
        AudioSource audioSource;
        AudioClip heartClip;
        AudioClip ringClip;

        static readonly Vector3[] SampleDirs = BuildSampleDirs();

        static Vector3[] BuildSampleDirs()
        {
            var d = new Vector3[8];
            for (int i = 0; i < 8; i++)
            {
                float a = i / 8f * Mathf.PI * 2f;
                d[i] = new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a));
            }
            return d;
        }

        void Awake()
        {
            Instance = this;
            BuildPostFx();
            BuildEdgeOverlay();
            BuildHeartPanel();
            audioSource = gameObject.AddComponent<AudioSource>();
            audioSource.playOnAwake = false;
            audioSource.spatialBlend = 0f;
            heartClip = MakeHeartbeat();
            ringClip = MakeRing();
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            if (volume != null && volume.sharedProfile != null) Destroy(volume.sharedProfile);
        }

        // ------------------------------------------------------------------ setup

        void BuildPostFx()
        {
            var go = new GameObject("Fear Volume");
            go.transform.SetParent(transform, false);
            volume = go.AddComponent<Volume>();
            volume.isGlobal = true;
            volume.priority = 50f;
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            vignette = profile.Add<Vignette>(true);
            vignette.intensity.Override(0f);
            vignette.smoothness.Override(0.5f);
            vignette.color.Override(Color.black);
            aberration = profile.Add<ChromaticAberration>(true);
            aberration.intensity.Override(0f);
            colour = profile.Add<ColorAdjustments>(true);
            colour.saturation.Override(0f);
            colour.postExposure.Override(0f);
            lens = profile.Add<LensDistortion>(true);
            lens.intensity.Override(0f);
            volume.sharedProfile = profile;
        }

        /// <summary>Cheap tunnel-vision overlay that works everywhere (including Quest, where post-processing is off).</summary>
        void BuildEdgeOverlay()
        {
            var go = new GameObject("FearEdges", typeof(RectTransform));
            go.transform.SetParent(transform, false);
            edgeCanvas = go.AddComponent<Canvas>();
            edgeCanvas.renderMode = RenderMode.ScreenSpaceCamera;
            edgeCanvas.sortingOrder = short.MaxValue - 10;
            edgeCanvas.planeDistance = 0.16f;
            edgeGroup = go.AddComponent<CanvasGroup>();
            edgeGroup.blocksRaycasts = false;
            edgeGroup.interactable = false;
            edgeGroup.alpha = 0f;

            const int size = 256;
            var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
            for (int y = 0; y < size; y++)
            for (int x = 0; x < size; x++)
            {
                float dx = (x + 0.5f) / size * 2f - 1f, dy = (y + 0.5f) / size * 2f - 1f;
                float d = Mathf.Sqrt(dx * dx + dy * dy);
                float a = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.35f, 1.05f, d));
                tex.SetPixel(x, y, new Color(0f, 0f, 0f, a));
            }
            tex.Apply();
            edgeImage = new GameObject("Edges", typeof(RectTransform)).AddComponent<Image>();
            edgeImage.transform.SetParent(go.transform, false);
            edgeImage.sprite = Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f));
            edgeImage.raycastTarget = false;
            var rt = edgeImage.rectTransform;
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = new Vector2(-150, -150);
            rt.offsetMax = new Vector2(150, 150);
        }

        void BuildHeartPanel()
        {
            var canvas = UIFactory.CreateWorldCanvas("HeartRate", new Vector2(330, 110), 0.0011f, transform);
            foreach (var r in canvas.GetComponents<UnityEngine.EventSystems.BaseRaycaster>()) r.enabled = false;
            heartPanel = canvas.transform;
            UIFactory.FullPanel(heartPanel, new Color(0.05f, 0.07f, 0.1f, 0.75f));
            heartIcon = UIFactory.CircleImage(heartPanel, new Color(1f, 0.35f, 0.4f), new Vector2(-110, 0), 56);
            heartText = UIFactory.Label(heartPanel, "70 BPM", 46, new Vector2(40, 0), new Vector2(230, 90), TextAnchor.MiddleLeft, Color.white, FontStyle.Bold);
        }

        // ------------------------------------------------------------------ simulation

        void Update()
        {
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            if (rig == null) return;
            Transform head = rig.Head;
            float dt = Time.deltaTime;

            bool safe = SafeRoom.InSafeRoom || (lc != null && lc.IsRespawning);
            float pitch = Pitch(head);                     // + looking down, - looking up
            bool lookingUp = pitch < -18f;

            target = safe ? 0f : ComputeTarget(head, rig.FeetY, pitch);
            if (lc != null && !lc.Started) target *= 0.6f;
            if (lc != null && lc.IsCrouching) target *= 0.8f;
            if (BreathingGuide.Active) target *= 0.5f;
            if (lookingUp) target *= 0.15f;
            target *= ModeMultiplier();

            float rate = target > fear ? riseRate : (lookingUp ? lookUpFallRate : fallRate);
            fear = Mathf.MoveTowards(fear, target, rate * dt);

            UpdatePanic(lc, lookingUp, dt);
            UpdateHeart(dt);
            ApplyEffects(rig, head);
            FollowHead(head);

            if (!tutorialSaid && fear > 0.5f && lc != null && lc.Started)
            {
                tutorialSaid = true;
                Companion.Say("Feel that? Your heart is racing - that's the fear talking. When it gets too much, LOOK UP at the sky and breathe. It always passes.", 7f);
            }
        }

        static float Pitch(Transform head)
        {
            // Angle below the horizon in degrees.
            return Mathf.Asin(Mathf.Clamp(-head.forward.y, -1f, 1f)) * Mathf.Rad2Deg;
        }

        float HeightFactor(float drop)
        {
            if (drop <= 2f) return 0f;
            return Mathf.Clamp01(Mathf.Log(1f + (drop - 2f)) / Mathf.Log(1f + fullFearDrop));
        }

        static readonly RaycastHit[] Hits = new RaycastHit[16];

        /// <summary>Glass floors and safety glass don't block the view, so they don't block the fear either.</summary>
        static bool SeeThrough(Collider c)
        {
            if (c.GetComponentInParent<CrackingGlass>() != null) return true;
            var r = c.GetComponent<Renderer>();
            return r != null && r.sharedMaterial != null && r.sharedMaterial.renderQueue >= 3000;
        }

        /// <summary>Nearest opaque hit along a ray (ignores triggers and see-through surfaces).</summary>
        static bool OpaqueRaycast(Vector3 from, Vector3 dir, float max, out float distance, out Vector3 point)
        {
            int n = Physics.RaycastNonAlloc(from, dir, Hits, max, ~0, QueryTriggerInteraction.Ignore);
            distance = max;
            point = from + dir * max;
            bool found = false;
            for (int i = 0; i < n; i++)
            {
                if (Hits[i].distance >= distance || SeeThrough(Hits[i].collider)) continue;
                distance = Hits[i].distance;
                point = Hits[i].point;
                found = true;
            }
            return found;
        }

        static float DropAt(Vector3 from, float max = 400f)
        {
            OpaqueRaycast(from, Vector3.down, max, out float d, out _);
            return d;
        }

        float ComputeTarget(Transform head, float feetY, float pitch)
        {
            Vector3 h = head.position;
            float eye = Mathf.Max(0.8f, h.y - feetY);

            // 1) Exposure: how much empty air surrounds the head (edges, beams, open lifts).
            int exposed = 0;
            float deepest = 0f;
            foreach (var d in SampleDirs)
            {
                float drop = DropAt(h + d * 0.7f) - eye;
                if (drop > 2.5f) { exposed++; deepest = Mathf.Max(deepest, drop); }
            }
            float directlyBelow = DropAt(h) - eye;
            float exposure = exposed / (float)SampleDirs.Length;
            float edgeTerm = HeightFactor(Mathf.Max(deepest, directlyBelow)) * Mathf.Max(exposure * 0.85f, directlyBelow > 2.5f ? 1f : 0f);

            // 2) Looking down into the drop.
            float gazeTerm = 0f;
            if (pitch > 12f)
            {
                float gazeDrop = OpaqueRaycast(h, head.forward, 600f, out _, out Vector3 hitPoint)
                    ? h.y - hitPoint.y - eye
                    : 300f;
                float lookDown = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(12f, 65f, pitch));
                gazeTerm = HeightFactor(gazeDrop) * lookDown;
            }
            return Mathf.Clamp01(Mathf.Max(edgeTerm, gazeTerm * 1.1f));
        }

        static float ModeMultiplier()
        {
            switch (ExposureSettings.Mode)
            {
                case ExposureMode.Gentle: return 0.6f;
                case ExposureMode.Brave: return 1.25f;
                default: return 1f;
            }
        }

        void UpdatePanic(LevelController lc, bool lookingUp, float dt)
        {
            string scene = SceneManager.GetActiveScene().name;
            if (!panic)
            {
                atThreshold = fear >= panicThreshold ? atThreshold + dt : 0f;
                if (atThreshold >= panicAfter && lc != null && lc.Started)
                {
                    panic = true;
                    panicStarted = Time.time;
                    lookUpTimer = 0f;
                    SessionLogger.Log(scene, "panic_start");
                    Companion.Say("Panic wave! LOOK UP at the sky. Slow breath in... and out. You are safe.", 6f);
                    audioSource.PlayOneShot(ringClip, 0.35f);
                }
                return;
            }

            if (Time.time > nextLookUpHint)
            {
                nextLookUpHint = Time.time + 2.2f;
                HeadHud.Instance.ShowMessage("↑  LOOK UP  ↑\nfind the sky and breathe", 2f);
            }
            if (lookingUp) lookUpTimer += dt;

            if (fear < 0.45f)
            {
                panic = false;
                atThreshold = 0f;
                panicsBeaten++;
                SessionLogger.Log(scene, "panic_recovered_seconds", (Time.time - panicStarted).ToString("F1", System.Globalization.CultureInfo.InvariantCulture));
                HeadHud.Instance.ShowMessage("The wave passed. Well done!", 2.5f);
                ProceduralAudio.PlayChime(1.1f);
                Companion.Say("See? You rode the wave and it passed. That's exactly how fear works.", 5f);
            }
            else if (Time.time - panicStarted > freezeLimit && lookUpTimer < 0.5f && lc != null)
            {
                panic = false;
                atThreshold = 0f;
                fear = 0.5f;
                SessionLogger.Log(scene, "panic_froze");
                lc.Slip("froze");
            }
        }

        void UpdateHeart(float dt)
        {
            float targetBpm = 68f + fear * 95f + (panic ? 18f : 0f);
            bpm = Mathf.Lerp(bpm, targetBpm, 1f - Mathf.Exp(-1.5f * dt));
            if (LevelController.Instance != null && LevelController.Instance.Started) peakBpm = Mathf.Max(peakBpm, bpm);

            beatTimer -= dt;
            if (beatTimer <= 0f)
            {
                beatTimer = 60f / bpm;
                float vol = Mathf.Pow(Mathf.InverseLerp(0.15f, 1f, fear), 1.4f) * 0.9f;
                if (vol > 0.02f) audioSource.PlayOneShot(heartClip, vol);
                if (fear > 0.35f) Haptic(Mathf.Lerp(0.15f, 0.7f, fear), 0.07f);
                if (heartIcon != null) heartIcon.rectTransform.localScale = Vector3.one * 1.35f;
            }
            if (heartIcon != null)
                heartIcon.rectTransform.localScale = Vector3.Lerp(heartIcon.rectTransform.localScale, Vector3.one, dt * 8f);
            if (heartText != null)
            {
                heartText.text = Mathf.RoundToInt(bpm) + " BPM";
                heartText.color = Color.Lerp(Color.white, new Color(1f, 0.35f, 0.3f), Mathf.InverseLerp(90f, 150f, bpm));
            }
        }

        static void Haptic(float amplitude, float duration)
        {
            foreach (var node in new[] { XRNode.LeftHand, XRNode.RightHand })
            {
                var device = InputDevices.GetDeviceAtXRNode(node);
                if (device.isValid) device.SendHapticImpulse(0u, amplitude, duration);
            }
        }

        void ApplyEffects(PlayerRig rig, Transform head)
        {
            float f = fear;
            float pulse = 0.5f + 0.5f * Mathf.Sin(Time.time * Mathf.PI * 2f * bpm / 60f);
            bool vr = !rig.IsDesktop && XRSettings.isDeviceActive;

            if (vignette != null)
            {
                vignette.intensity.value = Mathf.Clamp01(0.08f + f * 0.48f + (panic ? 0.12f * pulse : 0f));
                vignette.color.value = panic ? Color.Lerp(Color.black, new Color(0.45f, 0f, 0f), pulse) : Color.black;
                aberration.intensity.value = Mathf.Clamp01(f * f * 0.9f);
                colour.saturation.value = -f * 55f;
                colour.postExposure.value = panic ? 0.25f * pulse : 0f;
                // Lens warp sells vertigo on a monitor but causes nausea in a headset.
                lens.intensity.value = vr ? 0f : -0.28f * f * (0.6f + 0.4f * pulse);
            }

            if (edgeCanvas.worldCamera == null || !edgeCanvas.worldCamera.isActiveAndEnabled) edgeCanvas.worldCamera = Camera.main;
            edgeGroup.alpha = Mathf.Clamp01(Mathf.InverseLerp(0.2f, 1f, f) * 0.85f + (panic ? 0.1f * pulse : 0f));
            edgeImage.color = panic ? Color.Lerp(Color.white, new Color(1f, 0.4f, 0.4f), pulse) : Color.white;

            // Desktop only: a subtle "Vertigo" dolly-zoom on the camera field of view.
            var cam = Camera.main;
            if (cam != null && !vr)
            {
                if (baseFov < 0f) baseFov = cam.fieldOfView;
                cam.fieldOfView = baseFov - f * 9f + Mathf.Sin(Time.time * 1.7f) * f * 1.5f;
            }
        }

        void FollowHead(Transform head)
        {
            if (heartPanel == null) return;
            Vector3 fwd = head.forward;
            Vector3 target = head.position + fwd * 1.2f - head.up * 0.42f + head.right * 0.42f;
            heartPanel.position = Vector3.Lerp(heartPanel.position, target, 1f - Mathf.Exp(-10f * Time.deltaTime));
            heartPanel.rotation = Quaternion.Slerp(heartPanel.rotation, Quaternion.LookRotation(heartPanel.position - head.position, head.up), 1f - Mathf.Exp(-10f * Time.deltaTime));
        }

        /// <summary>A small wave of relief (finishing a task, reaching a checkpoint).</summary>
        public static void Relief(float amount)
        {
            if (Instance != null) Instance.fear = Mathf.Max(0f, Instance.fear - amount);
        }

        // ------------------------------------------------------------------ procedural audio

        static AudioClip MakeHeartbeat()
        {
            const int rate = 44100;
            int n = (int)(rate * 0.45f);
            var data = new float[n];
            for (int i = 0; i < n; i++)
            {
                float t = i / (float)rate;
                float lub = Mathf.Sin(2f * Mathf.PI * 52f * t) * Mathf.Exp(-t * 28f);
                float t2 = t - 0.16f;
                float dub = t2 > 0f ? Mathf.Sin(2f * Mathf.PI * 44f * t2) * Mathf.Exp(-t2 * 32f) * 0.7f : 0f;
                data[i] = Mathf.Clamp((lub + dub) * 0.9f, -1f, 1f);
            }
            var clip = AudioClip.Create("heartbeat", n, 1, rate, false);
            clip.SetData(data, 0);
            return clip;
        }

        static AudioClip MakeRing()
        {
            const int rate = 44100;
            int n = rate * 2;
            var data = new float[n];
            for (int i = 0; i < n; i++)
            {
                float t = i / (float)rate;
                data[i] = Mathf.Sin(2f * Mathf.PI * 5200f * t) * 0.12f * Mathf.Sin(Mathf.PI * t / 2f);
            }
            var clip = AudioClip.Create("ring", n, 1, rate, false);
            clip.SetData(data, 0);
            return clip;
        }
    }
}
