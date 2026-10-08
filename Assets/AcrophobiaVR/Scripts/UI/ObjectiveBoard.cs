using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace AcrophobiaVR
{
    /// <summary>World-space checklist of the level's tasks, courage stars and slips.</summary>
    public class ObjectiveBoard : MonoBehaviour
    {
        readonly List<Text> lines = new List<Text>();
        Text header;
        Text stats;
        Objective[] objectives;

        public static ObjectiveBoard Create(string title, Objective[] objectives, Vector3 position, Quaternion rotation)
        {
            var go = new GameObject("ObjectiveBoard");
            go.transform.SetPositionAndRotation(position, rotation);
            var b = go.AddComponent<ObjectiveBoard>();
            b.objectives = objectives;
            b.Build(title);
            return b;
        }

        void Build(string title)
        {
            float h = 220 + objectives.Length * 70;
            var canvas = UIFactory.CreateWorldCanvas("Canvas", new Vector2(760, h), 0.0012f, transform);
            var root = canvas.transform;
            UIFactory.FullPanel(root, UIFactory.PanelColor);
            header = UIFactory.Label(root, title, 44, new Vector2(0, h / 2 - 55), new Vector2(720, 70), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);
            for (int i = 0; i < objectives.Length; i++)
            {
                var t = UIFactory.Label(root, "", 32, new Vector2(10, h / 2 - 130 - i * 70), new Vector2(680, 64), TextAnchor.MiddleLeft);
                t.supportRichText = true;
                lines.Add(t);
            }
            stats = UIFactory.Label(root, "", 30, new Vector2(0, -h / 2 + 45), new Vector2(720, 60), TextAnchor.MiddleCenter, UIFactory.Gold);
            Refresh();
        }

        void Update() => Refresh();

        void Refresh()
        {
            for (int i = 0; i < objectives.Length; i++)
            {
                var o = objectives[i];
                string box = o.IsComplete ? "<color=#7BE0A0>\u2714</color>" : "<color=#FFFFFF66>\u25CB</color>";
                string text = o.IsComplete ? "<color=#FFFFFF88>" + o.Description + "</color>" : o.Description + o.ProgressSuffix;
                lines[i].text = box + "  " + text;
            }
            var lc = LevelController.Instance;
            if (lc != null)
                stats.text = "Courage stars " + CourageStar.Collected + "/" + CourageStar.Total + "     Slips " + lc.Slips;
        }
    }
}