using System;
using System.Collections;
using UnityEngine;
using UnityEngine.UI;

namespace AcrophobiaVR
{
    /// <summary>
    /// Guided slow breathing (inhale 4 s, hold 4 s, exhale 6 s) with a glowing orb that grows and
    /// shrinks. Slow exhale activates the calming parasympathetic response.
    /// </summary>
    public class BreathingGuide : MonoBehaviour
    {
        const float Inhale = 4f, Hold = 4f, Exhale = 6f;

        Image orb;
        Image halo;
        TMPro.TMP_Text phase;
        TMPro.TMP_Text count;
        int cycles;
        bool loopForever;
        Action onDone;

        public static bool Active { get; private set; }

        public static BreathingGuide Show(int cycles, Action onDone = null)
        {
            var go = new GameObject("BreathingGuide");
            var g = go.AddComponent<BreathingGuide>();
            g.cycles = cycles;
            g.onDone = onDone;
            g.Build(true);
            if (PlayerRig.Instance != null) PlayerRig.Instance.PlaceInFront(go.transform, 1.5f, 0f);
            return g;
        }

        /// <summary>A permanent breathing orb placed in the world (used in the Calm Meadow).</summary>
        public static BreathingGuide CreateStatic(Transform parent, Vector3 localPos)
        {
            var go = new GameObject("BreathingOrb");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var g = go.AddComponent<BreathingGuide>();
            g.loopForever = true;
            g.Build(false);
            return g;
        }

        void Build(bool withButton)
        {
            var canvas = UIFactory.CreateWorldCanvas("Canvas", new Vector2(700, 760), 0.001f, transform);
            var root = canvas.transform;
            UIFactory.Label(root, "Breathe with the light", 40, new Vector2(0, 330), new Vector2(680, 60), TextAnchor.MiddleCenter, new Color(1, 1, 1, 0.85f));
            halo = UIFactory.CircleImage(root, new Color(UIFactory.Calm.r, UIFactory.Calm.g, UIFactory.Calm.b, 0.18f), new Vector2(0, 40), 480);
            orb = UIFactory.CircleImage(root, UIFactory.Calm, new Vector2(0, 40), 300);
            phase = UIFactory.Label(root, "", 48, new Vector2(0, 40), new Vector2(600, 80), TextAnchor.MiddleCenter, new Color(0.05f, 0.15f, 0.1f), FontStyle.Bold);
            count = UIFactory.Label(root, "", 34, new Vector2(0, -250), new Vector2(600, 60));
            if (withButton)
                UIFactory.Button(root, "I feel ready", new Vector2(0, -330), new Vector2(360, 80), UIFactory.ButtonColor, Finish, 32);
            StartCoroutine(Run());
        }

        IEnumerator Run()
        {
            Active = !loopForever || Active;
            int done = 0;
            while (loopForever || done < cycles)
            {
                Breath(true, Inhale);
                yield return Phase("Breathe in", Inhale, 0.55f, 1f);
                yield return Phase("Hold", Hold, 1f, 1f);
                Breath(false, Exhale);
                yield return Phase("Breathe out", Exhale, 1f, 0.55f);
                done++;
                if (!loopForever) count.text = done + " / " + cycles;
            }
            // Reached only when every cycle was breathed through (the "I feel ready" button skips straight to Finish).
            if (cycles > 0) Achievements.Unlock("calm_breather");
            Finish();
        }

        /// <summary>
        /// Audible breath cue. A guide opened on demand always breathes; the permanent meadow orb only
        /// breathes while the player is actually in the Calm Meadow and no on-demand guide is playing
        /// (so two breath sounds never overlap).
        /// </summary>
        void Breath(bool inhale, float seconds)
        {
            bool audible = !loopForever || (SafeRoom.InSafeRoom && !Active);
            if (audible) ProceduralAudio.PlayBreath(inhale, seconds);
        }

        IEnumerator Phase(string label, float seconds, float from, float to)
        {
            phase.text = label;
            for (float t = 0; t < seconds; t += Time.deltaTime)
            {
                float k = Mathf.SmoothStep(from, to, t / seconds);
                orb.rectTransform.localScale = Vector3.one * k;
                halo.rectTransform.localScale = Vector3.one * (0.8f + k * 0.4f + Mathf.Sin(Time.time * 2f) * 0.02f);
                if (loopForever) count.text = Mathf.CeilToInt(seconds - t).ToString();
                yield return null;
            }
        }

        void Finish()
        {
            if (loopForever) return;
            Active = false;
            var cb = onDone;
            onDone = null;
            Destroy(gameObject);
            cb?.Invoke();
        }

        void OnDestroy()
        {
            if (!loopForever) Active = false;
        }
    }
}