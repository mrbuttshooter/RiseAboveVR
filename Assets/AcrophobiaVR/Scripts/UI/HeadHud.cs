using System.Collections;
using UnityEngine;
using UnityEngine.UI;

namespace AcrophobiaVR
{
    /// <summary>
    /// Head-locked (lazily following) heads-up display: toast messages, a hold/gaze progress ring
    /// and the companion's subtitles. Follows the view smoothly to avoid motion sickness.
    /// </summary>
    public class HeadHud : MonoBehaviour
    {
        static HeadHud instance;

        Canvas canvas;
        Text toast;
        CanvasGroup toastGroup;
        Image ring;
        Image ringBack;
        Text ringLabel;
        Text subtitle;
        CanvasGroup subtitleGroup;
        Coroutine toastRoutine;
        Coroutine subtitleRoutine;
        float ringVisibleUntil;

        public static HeadHud Instance
        {
            get
            {
                if (instance == null) instance = new GameObject("HeadHud").AddComponent<HeadHud>();
                return instance;
            }
        }

        void Awake()
        {
            instance = this;
            canvas = UIFactory.CreateWorldCanvas("HudCanvas", new Vector2(1000, 700), 0.0011f, transform);
            canvas.sortingOrder = 50;
            foreach (var r in canvas.GetComponents<UnityEngine.EventSystems.BaseRaycaster>()) r.enabled = false;
            var root = canvas.transform;

            var toastBg = UIFactory.Panel(root, new Color(0.05f, 0.08f, 0.12f, 0.85f), new Vector2(0, 230), new Vector2(820, 110));
            toastGroup = toastBg.gameObject.AddComponent<CanvasGroup>();
            toast = UIFactory.Label(toastBg.transform, "", 40, Vector2.zero, new Vector2(780, 100));
            toastGroup.alpha = 0f;

            ringBack = UIFactory.CircleImage(root, new Color(0, 0, 0, 0.45f), Vector2.zero, 150);
            ring = UIFactory.Ring(root, UIFactory.Calm, Vector2.zero, 140);
            ringLabel = UIFactory.Label(root, "", 32, new Vector2(0, -115), new Vector2(700, 60));
            SetRingVisible(false);

            var subBg = UIFactory.Panel(root, new Color(0.1f, 0.16f, 0.12f, 0.88f), new Vector2(0, -250), new Vector2(900, 150));
            subtitleGroup = subBg.gameObject.AddComponent<CanvasGroup>();
            subtitle = UIFactory.Label(subBg.transform, "", 36, new Vector2(0, 0), new Vector2(860, 140), TextAnchor.MiddleCenter);
            subtitleGroup.alpha = 0f;
        }

        void LateUpdate()
        {
            var rig = PlayerRig.Instance;
            Transform head = rig != null ? rig.Head : (Camera.main != null ? Camera.main.transform : null);
            if (head == null) return;

            // Lazy follow: position snaps in distance, rotation eases towards the view.
            Vector3 target = head.position + head.forward * 1.3f;
            transform.position = Vector3.Lerp(transform.position, target, 1f - Mathf.Exp(-8f * Time.unscaledDeltaTime));
            Quaternion look = Quaternion.LookRotation(transform.position - head.position, Vector3.up);
            transform.rotation = Quaternion.Slerp(transform.rotation, look, 1f - Mathf.Exp(-8f * Time.unscaledDeltaTime));

            if (Time.unscaledTime > ringVisibleUntil && ring.enabled) SetRingVisible(false);
        }

        void SetRingVisible(bool visible)
        {
            ring.enabled = visible;
            ringBack.enabled = visible;
            ringLabel.enabled = visible;
        }

        /// <summary>Shows hold/gaze progress (0-1). Call every frame while relevant.</summary>
        public void ShowProgress(float progress, string label, Color? color = null)
        {
            SetRingVisible(true);
            ring.fillAmount = Mathf.Clamp01(progress);
            ring.color = color ?? UIFactory.Calm;
            ringLabel.text = label;
            ringVisibleUntil = Time.unscaledTime + 0.15f;
        }

        public void ShowMessage(string message, float seconds = 3f)
        {
            if (toastRoutine != null) StopCoroutine(toastRoutine);
            toastRoutine = StartCoroutine(ShowFor(toastGroup, toast, message, seconds));
        }

        public void ShowSubtitle(string speaker, string line, float seconds)
        {
            if (subtitleRoutine != null) StopCoroutine(subtitleRoutine);
            string text = string.IsNullOrEmpty(speaker) ? line : "<b><color=#8FE3B0>" + speaker + ":</color></b> " + line;
            subtitle.supportRichText = true;
            subtitleRoutine = StartCoroutine(ShowFor(subtitleGroup, subtitle, text, seconds));
        }

        IEnumerator ShowFor(CanvasGroup group, Text label, string message, float seconds)
        {
            label.text = message;
            for (float t = 0; t < 0.25f; t += Time.unscaledDeltaTime)
            {
                group.alpha = t / 0.25f;
                yield return null;
            }
            group.alpha = 1f;
            yield return new WaitForSecondsRealtime(seconds);
            for (float t = 0; t < 0.5f; t += Time.unscaledDeltaTime)
            {
                group.alpha = 1f - t / 0.5f;
                yield return null;
            }
            group.alpha = 0f;
        }
    }
}