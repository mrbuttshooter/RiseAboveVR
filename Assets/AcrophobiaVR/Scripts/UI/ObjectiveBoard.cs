using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace AcrophobiaVR
{
    /// <summary>World-space checklist of the level's tasks, courage stars and slips.</summary>
    public class ObjectiveBoard : MonoBehaviour
    {
        readonly List<TMPro.TMP_Text> lines = new List<TMPro.TMP_Text>();
        readonly List<Image> icons = new List<Image>();
        TMPro.TMP_Text header;
        TMPro.TMP_Text stats;
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
                icons.Add(UIFactory.CircleImage(root, new Color(1f, 1f, 1f, 0.25f), new Vector2(-335, h / 2 - 130 - i * 70), 30));
                var t = UIFactory.Label(root, "", 32, new Vector2(35, h / 2 - 130 - i * 70), new Vector2(640, 64), TextAnchor.MiddleLeft);
                lines.Add(t);
            }
            stats = UIFactory.Label(root, "", 30, new Vector2(0, -h / 2 + 45), new Vector2(720, 60), TextAnchor.MiddleCenter, UIFactory.Gold);
            Refresh();
        }

        void Update() => Refresh();

        void Refresh()
        {
            // After an editor hot reload the UI lists come back empty while the objectives survive: skip, don't spam.
            if (objectives == null || lines.Count < objectives.Length || icons.Count < objectives.Length || stats == null) return;
            for (int i = 0; i < objectives.Length; i++)
            {
                var o = objectives[i];
                lines[i].text = o.IsComplete ? "<s><color=#FFFFFF88>" + o.Description + "</color></s>" : o.Description + o.ProgressSuffix;
                icons[i].color = o.IsComplete ? UIFactory.Calm : new Color(1f, 1f, 1f, 0.25f);
            }
            var lc = LevelController.Instance;
            if (lc != null)
                stats.text = "Courage stars " + CourageStar.Collected + "/" + CourageStar.Total + "     Slips " + lc.Slips;
        }
    }
}