using System;
using UnityEngine;
using UnityEngine.InputSystem;

namespace AcrophobiaVR
{
    /// <summary>
    /// 0-10 "Subjective Units of Distress" (SUDS) rating, the standard self-report scale used in
    /// exposure therapy. Shown before and after every level; values are logged to CSV.
    /// Desktop shortcut: number keys 0-9.
    /// </summary>
    public class RatingPanel : MonoBehaviour
    {
        Action<int> onRated;
        bool done;

        static readonly string[] Words =
        {
            "Totally calm", "", "Relaxed", "", "A bit nervous", "Uneasy", "", "Anxious", "", "Very anxious", "Panic"
        };

        public static RatingPanel Show(string title, string question, Action<int> onRated)
        {
            var go = new GameObject("RatingPanel");
            var p = go.AddComponent<RatingPanel>();
            p.onRated = onRated;
            p.Build(title, question);
            return p;
        }

        void Build(string title, string question)
        {
            var canvas = UIFactory.CreateWorldCanvas("Canvas", new Vector2(1300, 640), 0.001f, transform);
            var root = canvas.transform;
            UIFactory.FullPanel(root, UIFactory.PanelColor);
            UIFactory.Label(root, title, 56, new Vector2(0, 240), new Vector2(1240, 80), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);
            UIFactory.Label(root, question, 36, new Vector2(0, 150), new Vector2(1200, 100));

            for (int i = 0; i <= 10; i++)
            {
                int value = i;
                Color c = Color.Lerp(UIFactory.Calm, new Color(0.95f, 0.35f, 0.35f), i / 10f);
                float x = (i - 5) * 112f;
                UIFactory.Button(root, i.ToString(), new Vector2(x, 0), new Vector2(100, 120), c * 0.85f, () => Choose(value), 48);
                if (!string.IsNullOrEmpty(Words[i]))
                    UIFactory.Label(root, Words[i], 22, new Vector2(x, -95), new Vector2(150, 60), TextAnchor.UpperCenter, new Color(1, 1, 1, 0.75f));
            }
            UIFactory.Label(root, "Point and pull the trigger (or click) on a number. Be honest - there is no wrong answer.",
                26, new Vector2(0, -220), new Vector2(1200, 60), TextAnchor.MiddleCenter, new Color(1, 1, 1, 0.6f));

            if (PlayerRig.Instance != null) PlayerRig.Instance.PlaceInFront(transform, 1.6f, -0.1f);
            ProceduralAudio.PlayChime(0.4f);
        }

        void Update()
        {
            var kb = Keyboard.current;
            if (kb == null) return;
            for (int i = 0; i <= 9; i++)
            {
                // Input System orders Digit1..Digit9 then Digit0, so map explicitly.
                var key = kb[i == 0 ? Key.Digit0 : (Key)((int)Key.Digit1 + i - 1)];
                if (key != null && key.wasPressedThisFrame)
                {
                    Choose(i);
                    return;
                }
            }
        }

        void Choose(int value)
        {
            if (done) return;
            done = true;
            Destroy(gameObject);
            onRated?.Invoke(value);
        }
    }
}