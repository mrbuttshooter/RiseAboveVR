using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace AcrophobiaVR
{
    /// <summary>Floating world-space dialog with a title, body text and up to four buttons.</summary>
    public class Dialog : MonoBehaviour
    {
        public struct Choice
        {
            public string Label;
            public Color Color;
            public Action OnChosen;

            public Choice(string label, Action onChosen, Color? color = null)
            {
                Label = label;
                OnChosen = onChosen;
                Color = color ?? UIFactory.ButtonColor;
            }
        }

        static readonly List<Dialog> Open = new List<Dialog>();

        public static bool AnyOpen => Open.Count > 0;

        public static Dialog Show(string title, string body, params Choice[] choices)
        {
            var go = new GameObject("Dialog " + title);
            var d = go.AddComponent<Dialog>();
            d.Build(title, body, choices);
            return d;
        }

        public RectTransform Content { get; private set; }

        void Build(string title, string body, Choice[] choices)
        {
            Open.Add(this);
            var canvas = UIFactory.CreateWorldCanvas("Canvas", new Vector2(1100, 760), 0.001f, transform);
            UIFactory.FullPanel(canvas.transform, UIFactory.PanelColor);
            UIFactory.Panel(canvas.transform, UIFactory.Accent, new Vector2(0, 372), new Vector2(1060, 8));
            UIFactory.Label(canvas.transform, title, 58, new Vector2(0, 290), new Vector2(1020, 90), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);
            var bodyText = UIFactory.Label(canvas.transform, body, 36, new Vector2(0, 60), new Vector2(980, 360), TextAnchor.MiddleCenter);
            bodyText.richText = true;
            Content = (RectTransform)canvas.transform;

            int n = choices.Length;
            float width = n <= 2 ? 440 : (n == 3 ? 320 : 245);
            float spacing = width + 20;
            for (int i = 0; i < n; i++)
            {
                var c = choices[i];
                float x = (i - (n - 1) * 0.5f) * spacing;
                UIFactory.Button(canvas.transform, c.Label, new Vector2(x, -290), new Vector2(width, 110), c.Color, () =>
                {
                    Close();
                    c.OnChosen?.Invoke();
                }, n > 3 ? 30 : 36);
            }

            if (PlayerRig.Instance != null) PlayerRig.Instance.PlaceInFront(transform, 1.6f, -0.15f);
            ProceduralAudio.PlayChime(0.5f);
        }

        public void Close()
        {
            Open.Remove(this);
            Destroy(gameObject);
        }

        void OnDestroy() => Open.Remove(this);
    }
}