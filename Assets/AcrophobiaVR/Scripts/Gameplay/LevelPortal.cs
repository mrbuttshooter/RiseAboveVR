using UnityEngine;
using UnityEngine.UI;

namespace AcrophobiaVR
{
    /// <summary>A glowing doorway in the park hub. Walk through it to start that level (if unlocked).</summary>
    public class LevelPortal : HeadZone
    {
        public int levelIndex;
        public Renderer glowRenderer;
        public Transform labelPoint;

        float cooldown;

        void Start()
        {
            bool unlocked = GameManager.Instance.IsUnlocked(levelIndex);
            if (glowRenderer != null)
                glowRenderer.material.color = unlocked ? new Color(0.4f, 0.85f, 1f, 0.55f) : new Color(0.4f, 0.4f, 0.45f, 0.4f);
            if (labelPoint != null)
            {
                var c = UIFactory.CreateWorldCanvas("PortalLabel", new Vector2(700, 300), 0.003f);
                c.transform.SetPositionAndRotation(labelPoint.position, labelPoint.rotation);
                var root = c.transform;
                UIFactory.FullPanel(root, UIFactory.PanelColor);
                UIFactory.Label(root, GameManager.LevelTitles[levelIndex], 46, new Vector2(0, 80), new Vector2(680, 80), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);
                int stars = ProgressStore.GetStars(levelIndex);
                string state = unlocked ? "" : "Locked - finish the previous level first";
                var t = UIFactory.Label(root, state, unlocked ? 64 : 34, new Vector2(0, -10), new Vector2(680, 90));
                t.richText = true;
                if (unlocked) UIFactory.StarRow(root, stars, 3, new Vector2(0, -10), 70f);
                UIFactory.Label(root, unlocked ? "Walk through the portal to begin" : "", 30, new Vector2(0, -100), new Vector2(680, 60), TextAnchor.MiddleCenter, new Color(1, 1, 1, 0.7f));
            }
        }

        protected override void Update()
        {
            base.Update();
            if (glowRenderer != null)
                glowRenderer.transform.localScale = new Vector3(1f, 1f, 1f) * (1f + Mathf.Sin(Time.time * 2f) * 0.02f);
        }

        protected override void OnHeadEnter()
        {
            if (Time.time < cooldown) return;
            cooldown = Time.time + 3f;
            if (GameManager.Instance.IsUnlocked(levelIndex))
            {
                ProceduralAudio.PlayChime(0.8f);
                GameManager.Instance.LoadLevel(levelIndex);
            }
            else
            {
                HeadHud.Instance.ShowMessage("Locked - complete " + GameManager.LevelTitles[levelIndex - 1] + " first", 3f);
            }
        }
    }
}