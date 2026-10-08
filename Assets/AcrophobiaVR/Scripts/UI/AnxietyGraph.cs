using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Trophy wall: for each level, before (orange) and after (green) anxiety bars for the last attempts.
    /// Makes the effect of repeated exposure visible - ideal for the project presentation.
    /// </summary>
    public static class AnxietyGraph
    {
        static readonly Color BeforeColor = new Color(1f, 0.55f, 0.3f);
        static readonly Color AfterColor = new Color(0.45f, 0.85f, 0.6f);

        public static void Create(Transform point)
        {
            var canvas = UIFactory.CreateWorldCanvas("TrophyWall", new Vector2(1500, 900), 0.0014f);
            canvas.transform.SetPositionAndRotation(point.position, point.rotation);
            var root = canvas.transform;
            UIFactory.FullPanel(root, UIFactory.PanelColor);
            UIFactory.Label(root, "Trophy wall - your anxiety over time", 52, new Vector2(0, 390), new Vector2(1450, 80), TextAnchor.MiddleCenter, UIFactory.Gold, FontStyle.Bold);
            var legend = UIFactory.Label(root, "<color=#FF8C4D>Orange = before the level</color>     <color=#73D999>Green = after</color>     (0 calm, 10 panic)", 28, new Vector2(0, 330), new Vector2(1400, 50));
            legend.richText = true;

            const float chartH = 420f;
            for (int level = 0; level < GameManager.LevelScenes.Length; level++)
            {
                float cx = (level - 1) * 480f;
                UIFactory.Panel(root, new Color(1, 1, 1, 0.05f), new Vector2(cx, 60), new Vector2(440, chartH + 40), false);
                UIFactory.Label(root, GameManager.LevelTitles[level].Split('-')[1].Trim(), 32, new Vector2(cx, -200), new Vector2(440, 50), TextAnchor.MiddleCenter, Color.white, FontStyle.Bold);
                var history = ProgressStore.GetHistory(level);
                if (history.Count == 0)
                {
                    UIFactory.Label(root, "No attempts yet", 28, new Vector2(cx, 60), new Vector2(400, 50), TextAnchor.MiddleCenter, new Color(1, 1, 1, 0.5f));
                    continue;
                }
                int n = Mathf.Min(history.Count, 6);
                int startIdx = history.Count - n;
                float slot = 400f / n;
                for (int k = 0; k < n; k++)
                {
                    var h = history[startIdx + k];
                    float x = cx - 200f + slot * (k + 0.5f);
                    Bar(root, x - slot * 0.18f, h.Before, BeforeColor, slot * 0.32f, chartH);
                    Bar(root, x + slot * 0.18f, h.After, AfterColor, slot * 0.32f, chartH);
                    UIFactory.Label(root, "#" + (startIdx + k + 1), 20, new Vector2(x, -160), new Vector2(slot, 30), TextAnchor.MiddleCenter, new Color(1, 1, 1, 0.5f));
                }
                var last = history[history.Count - 1];
                int drop = last.Before - last.After;
                UIFactory.Label(root, drop > 0 ? "Last time: -" + drop + " points" : (drop == 0 ? "Last time: steady" : "Last time: +" + (-drop)), 26,
                    new Vector2(cx, -245), new Vector2(440, 40), TextAnchor.MiddleCenter, drop > 0 ? AfterColor : new Color(1, 1, 1, 0.6f));
            }
            UIFactory.Label(root, "Total stars: " + ProgressStore.TotalStars() + " / 9", 40, new Vector2(0, -340), new Vector2(1400, 60), TextAnchor.MiddleCenter, UIFactory.Gold, FontStyle.Bold);
        }

        static void Bar(Transform root, float x, int value, Color color, float width, float chartH)
        {
            float h = Mathf.Max(6f, chartH * value / 10f);
            var img = UIFactory.Panel(root, color, new Vector2(x, -140 + h / 2f), new Vector2(width, h), false);
            img.raycastTarget = false;
            UIFactory.Label(root, value.ToString(), 22, new Vector2(x, -140 + h + 16), new Vector2(60, 30));
        }
    }
}