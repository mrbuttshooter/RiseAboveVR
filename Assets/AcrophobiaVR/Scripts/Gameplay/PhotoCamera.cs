using System;
using System.Collections;
using System.Globalization;
using System.IO;
using Unity.XR.CoreUtils;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace AcrophobiaVR
{
    /// <summary>
    /// "Brave Photos": a camera the player always carries (B on the right Quest controller, F on keyboard).
    /// Photos are rendered by a hidden helper camera into a 960x540 texture and saved as JPGs in
    /// <see cref="PhotoDir"/>. A photo taken high up (more than 5 m of air below the feet) or while
    /// scared counts as a brave photo - a playful reason to stop at the edge and look around, which
    /// is exactly the exposure behaviour the therapy wants to encourage.
    /// Installs itself on the player rig in every scene; no scene setup needed.
    /// </summary>
    public class PhotoCamera : MonoBehaviour
    {
        const string BraveKey = "acro_brave_photos";
        const int PhotoWidth = 960;
        const int PhotoHeight = 540;
        const float CooldownSeconds = 1f;
        const float ThumbSeconds = 2.5f;
        const float BraveDrop = 5f;
        const float BraveFear = 0.4f;
        const float FlashSeconds = 0.35f;
        const float FlashAlpha = 0.8f;

        static bool tipShown;
        static AudioClip shutterClip;
        static readonly RaycastHit[] Hits = new RaycastHit[16];
        static readonly WaitForEndOfFrame EndOfFrame = new WaitForEndOfFrame();
        static readonly WaitForSeconds HalfSecond = new WaitForSeconds(0.5f);

        InputAction snapAction;
        Camera helper;
        AudioSource shutterSource;
        Canvas flashCanvas;
        CanvasGroup flashGroup;
        Canvas thumbCanvas;
        RectTransform thumbFrame;
        RawImage thumbImage;
        TMPro.TMP_Text thumbLabel;
        Texture2D thumbTexture;
        Coroutine flashRoutine;
        Coroutine thumbRoutine;
        float nextAllowed;
        bool busy;

        // ------------------------------------------------------------------ public API

        /// <summary>Folder the photos are saved in (Application.persistentDataPath/Photos).</summary>
        public static string PhotoDir => Application.persistentDataPath + "/Photos";

        /// <summary>Total brave photos ever taken (PlayerPrefs "acro_brave_photos").</summary>
        public static int BravePhotoCount => PlayerPrefs.GetInt(BraveKey, 0);

        /// <summary>Full paths of the newest photos, newest first. Empty if there are none.</summary>
        public static string[] RecentPhotos(int max)
        {
            if (max <= 0) return new string[0];
            try
            {
                string dir = PhotoDir;
                if (!Directory.Exists(dir)) return new string[0];
                string[] files = Directory.GetFiles(dir, "*.jpg");
                if (files.Length == 0) return files;
                var keys = new long[files.Length];
                for (int i = 0; i < files.Length; i++) keys[i] = -File.GetLastWriteTimeUtc(files[i]).Ticks; // negative -> newest first
                Array.Sort(keys, files);
                if (files.Length <= max) return files;
                var result = new string[max];
                Array.Copy(files, result, max);
                return result;
            }
            catch (Exception e)
            {
                Debug.LogWarning("[PhotoCamera] Could not list photos: " + e.Message);
                return new string[0];
            }
        }

        // ------------------------------------------------------------------ self-install

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Install()
        {
            tipShown = false;
            SceneManager.sceneLoaded -= OnSceneLoaded;
            SceneManager.sceneLoaded += OnSceneLoaded;
        }

        static void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            try
            {
                GameObject host = null;
                var rig = PlayerRig.Instance;
                if (rig != null)
                {
                    host = rig.gameObject;
                }
                else
                {
                    var origin = FindFirstObjectByType<XROrigin>();
                    if (origin != null)
                    {
                        var originRig = origin.GetComponentInChildren<PlayerRig>(true);
                        host = originRig != null ? originRig.gameObject : origin.gameObject;
                    }
                }
                if (host != null && host.GetComponent<PhotoCamera>() == null) host.AddComponent<PhotoCamera>();
            }
            catch (Exception e)
            {
                Debug.LogWarning("[PhotoCamera] Install failed: " + e.Message);
            }
        }

        // ------------------------------------------------------------------ lifecycle

        void Awake()
        {
            snapAction = new InputAction("BravePhoto", InputActionType.Button);
            snapAction.AddBinding("<XRController>{RightHand}/secondaryButton");
            snapAction.AddBinding("<Keyboard>/f");
            snapAction.performed += OnSnapPerformed;

            shutterSource = gameObject.AddComponent<AudioSource>();
            shutterSource.playOnAwake = false;
            shutterSource.loop = false;
            shutterSource.spatialBlend = 0f;
            shutterSource.bypassListenerEffects = true;
            if (shutterClip == null) shutterClip = MakeShutter();
        }

        void OnEnable()
        {
            if (snapAction != null) snapAction.Enable();
        }

        void OnDisable()
        {
            if (snapAction != null) snapAction.Disable();
            busy = false;
            // Coroutines die with the component: never leave a half-faded white flash or a stuck thumbnail behind.
            flashRoutine = null;
            thumbRoutine = null;
            if (flashGroup != null) flashGroup.alpha = 0f;
            if (flashCanvas != null) flashCanvas.enabled = false;
            // Component toggle only: SetActive on a child is refused while the rig itself is being (de)activated.
            if (thumbCanvas != null) thumbCanvas.enabled = false;
            if (thumbFrame != null) thumbFrame.localScale = Vector3.one;
        }

        void OnDestroy()
        {
            if (snapAction != null)
            {
                snapAction.performed -= OnSnapPerformed;
                snapAction.Disable();
                snapAction.Dispose();
                snapAction = null;
            }
            if (thumbTexture != null) Destroy(thumbTexture);
            thumbTexture = null;
        }

        void Start()
        {
            if (!tipShown && LevelController.Instance != null) StartCoroutine(TipRoutine());
        }

        IEnumerator TipRoutine()
        {
            yield return new WaitForSeconds(20f);
            while (Dialog.AnyOpen || FearSystem.Panicking || SafeRoom.InSafeRoom) yield return HalfSecond;
            if (tipShown || LevelController.Instance == null) yield break;
            tipShown = true;
            bool desktop = PlayerRig.Instance != null && PlayerRig.Instance.IsDesktop;
            Companion.Say("Tip: press " + (desktop ? "F" : "B") + " to take a photo. Brave photos from high up count double for courage!", 6f);
        }

        // ------------------------------------------------------------------ snapping

        void OnSnapPerformed(InputAction.CallbackContext ctx) => TrySnap();

        /// <summary>Takes a photo now if allowed (not in a dialog, not in the Calm Meadow, not cooling down).</summary>
        public void TrySnap()
        {
            if (busy || !isActiveAndEnabled || Time.unscaledTime < nextAllowed) return;
            if (Dialog.AnyOpen || SafeRoom.InSafeRoom) return;
            var lc = LevelController.Instance;
            if (lc != null && lc.IsRespawning) return;
            if (Camera.main == null) return;
            nextAllowed = Time.unscaledTime + CooldownSeconds;
            StartCoroutine(SnapRoutine());
        }

        IEnumerator SnapRoutine()
        {
            busy = true;
            yield return EndOfFrame;

            Camera source = Camera.main;
            Texture2D tex = source != null ? Capture(source) : null;
            busy = false;
            if (tex == null) yield break;

            bool brave = IsBraveSpot();
            string scene = SceneManager.GetActiveScene().name;

            // Instant feedback in the capture frame...
            PlayShutter();
            Haptics.Light();
            Flash();
            ShowThumbnail(tex, brave);

            // ...and the expensive JPG encode on the next frame so the cost is spread out.
            yield return null;
            if (tex != null) Save(tex, scene);

            if (brave)
            {
                int n = PlayerPrefs.GetInt(BraveKey, 0) + 1;
                PlayerPrefs.SetInt(BraveKey, n);
                PlayerPrefs.Save();
                HeadHud.Instance.ShowMessage("Brave photo! (" + n + ")", 2.5f);
                if (n >= 5) Achievements.Unlock("photographer");
            }
            else
            {
                HeadHud.Instance.ShowMessage("Photo saved", 2.5f);
            }
            SessionLogger.Log(scene, "photo", brave ? "brave" : "normal");
        }

        void EnsureHelper()
        {
            if (helper != null) return;
            var go = new GameObject("BravePhotoCamera");
            go.transform.SetParent(transform, false);
            helper = go.AddComponent<Camera>();
            helper.enabled = false;                       // renders only when asked
            helper.stereoTargetEye = StereoTargetEyeMask.None;
            helper.allowHDR = false;
            helper.allowMSAA = false;
            helper.depth = -100f;
        }

        /// <summary>Renders the current view through the helper camera and reads it back. Never touches the XR camera's target.</summary>
        Texture2D Capture(Camera source)
        {
            EnsureHelper();

            // Keep the previous floating thumbnail out of the new photo.
            bool thumbWasActive = thumbCanvas != null && thumbCanvas.gameObject.activeSelf;
            if (thumbWasActive) thumbCanvas.gameObject.SetActive(false);

            Transform st = source.transform;
            helper.transform.SetPositionAndRotation(st.position, st.rotation);
            helper.cullingMask = source.cullingMask;
            helper.clearFlags = source.clearFlags;
            helper.backgroundColor = source.backgroundColor;
            helper.nearClipPlane = source.nearClipPlane;
            helper.farClipPlane = source.farClipPlane;
            helper.fieldOfView = 70f;
            helper.aspect = PhotoWidth / (float)PhotoHeight;

            RenderTexture rt = RenderTexture.GetTemporary(PhotoWidth, PhotoHeight, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Default);
            RenderTexture previousActive = RenderTexture.active;
            Texture2D tex = null;
            try
            {
                helper.targetTexture = rt;
                helper.Render();
                RenderTexture.active = rt;
                tex = new Texture2D(PhotoWidth, PhotoHeight, TextureFormat.RGB24, false);
                tex.name = "BravePhoto";
                tex.wrapMode = TextureWrapMode.Clamp;
                tex.ReadPixels(new Rect(0, 0, PhotoWidth, PhotoHeight), 0, 0, false);
                tex.Apply(false, false);
            }
            catch (Exception e)
            {
                Debug.LogWarning("[PhotoCamera] Capture failed: " + e.Message);
                if (tex != null) Destroy(tex);
                tex = null;
            }
            finally
            {
                helper.targetTexture = null;
                RenderTexture.active = previousActive;
                RenderTexture.ReleaseTemporary(rt);
                if (thumbWasActive && thumbCanvas != null) thumbCanvas.gameObject.SetActive(true);
            }
            return tex;
        }

        static void Save(Texture2D tex, string scene)
        {
            try
            {
                // Copy the pixels on the main thread (Unity API), then JPG-encode + write on a worker thread:
                // encoding 960x540 takes tens of ms on a Quest CPU, which would otherwise drop VR frames.
                byte[] raw = tex.GetRawTextureData();
                UnityEngine.Experimental.Rendering.GraphicsFormat format = tex.graphicsFormat;
                uint w = (uint)tex.width, h = (uint)tex.height;
                string dir = PhotoDir;   // Application.persistentDataPath must be read on the main thread
                string baseName = SafeName(scene) + "_" + DateTime.Now.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture);
                System.Threading.Tasks.Task.Run(() => EncodeAndWrite(raw, format, w, h, dir, baseName));
            }
            catch (Exception e)
            {
                Debug.LogWarning("[PhotoCamera] Could not save photo: " + e.Message);
            }
        }

        /// <summary>Worker thread: ImageConversion.EncodeArrayToJPG is thread-safe (no Texture2D access here).</summary>
        static void EncodeAndWrite(byte[] raw, UnityEngine.Experimental.Rendering.GraphicsFormat format, uint w, uint h, string dir, string baseName)
        {
            try
            {
                byte[] jpg = ImageConversion.EncodeArrayToJPG(raw, format, w, h, 0, 85);
                Directory.CreateDirectory(dir);
                string path = dir + "/" + baseName + ".jpg";
                for (int i = 2; File.Exists(path) && i < 100; i++) path = dir + "/" + baseName + "_" + i + ".jpg";
                File.WriteAllBytes(path, jpg);
            }
            catch (Exception e)
            {
                Debug.LogWarning("[PhotoCamera] Could not save photo: " + e.Message);
            }
        }

        static string SafeName(string s)
        {
            if (string.IsNullOrEmpty(s)) return "Scene";
            foreach (char c in Path.GetInvalidFileNameChars()) s = s.Replace(c, '_');
            return s.Replace(' ', '_');
        }

        // ------------------------------------------------------------------ brave check

        /// <summary>True when more than 5 m of air is below the player's feet, or the player is noticeably scared.</summary>
        static bool IsBraveSpot()
        {
            if (FearSystem.Fear > BraveFear) return true;
            var rig = PlayerRig.Instance;
            Transform head = rig != null ? rig.Head : (Camera.main != null ? Camera.main.transform : null);
            if (head == null) return false;

            Vector3 h = head.position;
            float eye = rig != null ? Mathf.Max(0f, h.y - rig.FeetY) : 1.6f;
            Transform root = rig != null ? rig.Root : null;

            int n = Physics.RaycastNonAlloc(h, Vector3.down, Hits, 500f, ~0, QueryTriggerInteraction.Ignore);
            float drop = 500f;
            for (int i = 0; i < n; i++)
            {
                var c = Hits[i].collider;
                if (c == null || Hits[i].distance >= drop) continue;
                if (root != null && c.transform.IsChildOf(root)) continue;   // the player's own body
                if (SeeThrough(c)) continue;                                   // glass floors still count as height
                drop = Hits[i].distance;
            }
            return drop - eye > BraveDrop;
        }

        static bool SeeThrough(Collider c)
        {
            if (c.GetComponentInParent<CrackingGlass>() != null) return true;
            var r = c.GetComponent<Renderer>();
            return r != null && r.sharedMaterial != null && r.sharedMaterial.renderQueue >= 3000;
        }

        // ------------------------------------------------------------------ feedback

        void PlayShutter()
        {
            if (shutterClip == null) shutterClip = MakeShutter();
            if (shutterSource != null) shutterSource.PlayOneShot(shutterClip, 0.9f);
        }

        void Flash()
        {
            EnsureFlash();
            var cam = Camera.main;
            flashCanvas.worldCamera = cam;
            if (cam != null) flashCanvas.planeDistance = Mathf.Max(cam.nearClipPlane + 0.02f, 0.15f); // never behind the near clip
            if (flashRoutine != null) StopCoroutine(flashRoutine);
            flashRoutine = StartCoroutine(FlashRoutine());
        }

        IEnumerator FlashRoutine()
        {
            flashCanvas.enabled = true;
            float t = 0f;
            while (t < FlashSeconds)
            {
                flashGroup.alpha = Mathf.Lerp(FlashAlpha, 0f, t / FlashSeconds);
                t += Time.unscaledDeltaTime;
                yield return null;
            }
            flashGroup.alpha = 0f;
            flashCanvas.enabled = false;
            flashRoutine = null;
        }

        void EnsureFlash()
        {
            if (flashCanvas != null) return;
            var go = new GameObject("PhotoFlash", typeof(RectTransform));
            go.transform.SetParent(transform, false);
            flashCanvas = go.AddComponent<Canvas>();
            flashCanvas.renderMode = RenderMode.ScreenSpaceCamera;
            flashCanvas.worldCamera = Camera.main;
            flashCanvas.planeDistance = 0.15f;
            flashCanvas.sortingOrder = short.MaxValue - 5;
            flashGroup = go.AddComponent<CanvasGroup>();
            flashGroup.blocksRaycasts = false;
            flashGroup.interactable = false;
            flashGroup.alpha = 0f;

            var img = new GameObject("White", typeof(RectTransform)).AddComponent<Image>();
            img.transform.SetParent(go.transform, false);
            img.color = Color.white;
            img.raycastTarget = false;
            var rt = img.rectTransform;
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = new Vector2(-150, -150);
            rt.offsetMax = new Vector2(150, 150);
            flashCanvas.enabled = false;
        }

        void EnsureThumbnail()
        {
            if (thumbCanvas != null) return;
            thumbCanvas = UIFactory.CreateWorldCanvas("PhotoThumbnail", new Vector2(390, 260), 0.001f, transform);
            thumbCanvas.sortingOrder = 45;
            foreach (var r in thumbCanvas.GetComponents<UnityEngine.EventSystems.BaseRaycaster>()) r.enabled = false;

            var frame = UIFactory.FullPanel(thumbCanvas.transform, new Color(0.96f, 0.95f, 0.9f, 0.97f));
            frame.raycastTarget = false;
            thumbFrame = frame.rectTransform;

            thumbImage = new GameObject("Photo", typeof(RectTransform)).AddComponent<RawImage>();
            thumbImage.transform.SetParent(thumbFrame, false);
            thumbImage.raycastTarget = false;
            thumbImage.rectTransform.anchoredPosition = new Vector2(0, 16);
            thumbImage.rectTransform.sizeDelta = new Vector2(350, 197);

            thumbLabel = UIFactory.Label(thumbFrame, "", 26, new Vector2(0, -106), new Vector2(370, 36),
                TextAnchor.MiddleCenter, new Color(0.15f, 0.17f, 0.2f), FontStyle.Bold);
            thumbCanvas.gameObject.SetActive(false);
        }

        void ShowThumbnail(Texture2D tex, bool brave)
        {
            EnsureThumbnail();
            if (thumbTexture != null && thumbTexture != tex) Destroy(thumbTexture);
            thumbTexture = tex;
            thumbImage.texture = tex;
            thumbLabel.text = brave ? "BRAVE PHOTO" : "Photo saved";
            thumbLabel.color = brave ? new Color(0.78f, 0.55f, 0.05f) : new Color(0.15f, 0.17f, 0.2f);

            thumbCanvas.gameObject.SetActive(true);
            thumbCanvas.enabled = true;
            var rig = PlayerRig.Instance;
            if (rig != null)
            {
                rig.PlaceInFront(thumbCanvas.transform, 0.75f, -0.2f);
            }
            else if (Camera.main != null)
            {
                Transform cam = Camera.main.transform;
                thumbCanvas.transform.position = cam.position + cam.forward * 0.75f - Vector3.up * 0.2f;
                thumbCanvas.transform.rotation = Quaternion.LookRotation(thumbCanvas.transform.position - cam.position);
            }

            if (thumbRoutine != null) StopCoroutine(thumbRoutine);
            thumbRoutine = StartCoroutine(ThumbnailRoutine());
        }

        IEnumerator ThumbnailRoutine()
        {
            // Little "pop" in, hold, shrink away.
            float t = 0f;
            while (t < 0.15f)
            {
                float k = t / 0.15f;
                thumbFrame.localScale = Vector3.one * Mathf.Lerp(0.6f, 1f, 1f - (1f - k) * (1f - k));
                t += Time.unscaledDeltaTime;
                yield return null;
            }
            thumbFrame.localScale = Vector3.one;

            float hold = ThumbSeconds - 0.15f - 0.2f;
            t = 0f;
            while (t < hold)
            {
                t += Time.unscaledDeltaTime;
                yield return null;
            }

            t = 0f;
            while (t < 0.2f)
            {
                thumbFrame.localScale = Vector3.one * Mathf.Lerp(1f, 0.01f, t / 0.2f);
                t += Time.unscaledDeltaTime;
                yield return null;
            }

            thumbCanvas.gameObject.SetActive(false);
            thumbFrame.localScale = Vector3.one;
            thumbImage.texture = null;
            if (thumbTexture != null) Destroy(thumbTexture);
            thumbTexture = null;
            thumbRoutine = null;
        }

        // ------------------------------------------------------------------ procedural audio

        /// <summary>A short mechanical double-click with a soft body thunk.</summary>
        static AudioClip MakeShutter()
        {
            const int rate = 44100;
            int n = (int)(rate * 0.16f);
            var data = new float[n];
            var rng = new System.Random(1234);
            for (int i = 0; i < n; i++)
            {
                float t = i / (float)rate;
                float noise = (float)(rng.NextDouble() * 2.0 - 1.0);
                float click1 = noise * Mathf.Exp(-t * 170f);
                float t2 = t - 0.07f;
                float click2 = t2 > 0f ? noise * Mathf.Exp(-t2 * 130f) * 0.75f : 0f;
                float thunk = Mathf.Sin(2f * Mathf.PI * 170f * t) * Mathf.Exp(-t * 55f) * 0.35f;
                data[i] = Mathf.Clamp((click1 + click2) * 0.55f + thunk, -1f, 1f);
            }
            var clip = AudioClip.Create("shutter", n, 1, rate, false);
            clip.SetData(data, 0);
            return clip;
        }
    }
}
