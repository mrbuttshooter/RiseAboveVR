using System.Collections;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace AcrophobiaVR
{
    /// <summary>
    /// Full-view fade to a soft colour. Uses a Screen Space - Camera canvas placed just in front of
    /// the headset camera, which renders correctly in both eyes. Fades in automatically on scene load.
    /// </summary>
    public class ScreenFader : MonoBehaviour
    {
        public static ScreenFader Instance { get; private set; }

        static readonly Color FadeColor = new Color(0.08f, 0.12f, 0.16f, 1f);

        Canvas canvas;
        CanvasGroup group;
        Coroutine running;

        public bool IsFading { get; private set; }

        void Awake()
        {
            Instance = this;

            var go = new GameObject("FadeCanvas", typeof(RectTransform));
            go.transform.SetParent(transform, false);
            canvas = go.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceCamera;
            canvas.sortingOrder = short.MaxValue;
            canvas.planeDistance = 0.12f;
            group = go.AddComponent<CanvasGroup>();
            group.blocksRaycasts = false;
            group.interactable = false;

            var img = new GameObject("Fade", typeof(RectTransform)).AddComponent<Image>();
            img.transform.SetParent(go.transform, false);
            img.color = FadeColor;
            img.raycastTarget = false;
            var rt = img.rectTransform;
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = new Vector2(-500, -500);
            rt.offsetMax = new Vector2(500, 500);

            group.alpha = 1f;
            SceneManager.sceneLoaded += OnSceneLoaded;
        }

        void OnDestroy() => SceneManager.sceneLoaded -= OnSceneLoaded;

        void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            AttachToCamera();
            group.alpha = 1f;
            StartFade(0f, 1.2f);
        }

        void LateUpdate()
        {
            if (canvas.worldCamera == null || !canvas.worldCamera.isActiveAndEnabled) AttachToCamera();
        }

        void AttachToCamera()
        {
            var cam = Camera.main;
            if (cam == null) return;
            canvas.worldCamera = cam;
            canvas.planeDistance = Mathf.Max(cam.nearClipPlane + 0.02f, 0.12f);
        }

        public IEnumerator FadeOut(float duration = 0.6f) => FadeTo(1f, duration);

        public IEnumerator FadeIn(float duration = 0.6f) => FadeTo(0f, duration);

        void StartFade(float target, float duration)
        {
            if (running != null) StopCoroutine(running);
            running = StartCoroutine(FadeTo(target, duration));
        }

        IEnumerator FadeTo(float target, float duration)
        {
            IsFading = true;
            float start = group.alpha;
            float t = 0f;
            while (t < duration)
            {
                t += Time.unscaledDeltaTime;
                group.alpha = Mathf.Lerp(start, target, Mathf.SmoothStep(0f, 1f, t / duration));
                yield return null;
            }
            group.alpha = target;
            IsFading = false;
        }
    }
}
