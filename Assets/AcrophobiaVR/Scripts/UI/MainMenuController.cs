using UnityEngine;
using UnityEngine.UI;

namespace AcrophobiaVR
{
    /// <summary>
    /// The park hub: title, level cards (play / locked / stars / best time), exposure mode picker,
    /// trophy wall with the anxiety graph, and help. Walking through the portals also starts levels.
    /// </summary>
    public class MainMenuController : MonoBehaviour
    {
        public static bool MenuOpen { get; private set; }

        public Transform menuPoint;
        public Transform trophyPoint;
        public Transform helpPoint;

        readonly Button[] modeButtons = new Button[3];
        Text modeText;

        void Start()
        {
            SafeRoomFlagsReset();
            BuildMenu();
            if (trophyPoint != null) AnxietyGraph.Create(trophyPoint);
            if (helpPoint != null) BuildHelp();
            Invoke(nameof(Welcome), 1.5f);
        }

        static void SafeRoomFlagsReset() => AmbientAudio.SetMeadow(false);

        void Welcome()
        {
            int total = ProgressStore.TotalStars();
            if (total == 0)
                Companion.Say("Hi, I'm Pip! I'll be with you the whole way up. Pick a level - we start low and go higher, step by step.", 7f);
            else
                Companion.Say("Welcome back! You have " + total + " of 9 stars. Ready to rise a little higher?", 5f);
        }

        void BuildMenu()
        {
            MenuOpen = true;
            var canvas = UIFactory.CreateWorldCanvas("MainMenu", new Vector2(1800, 1150), 0.0014f);
            canvas.transform.SetPositionAndRotation(menuPoint.position, menuPoint.rotation);
            var root = canvas.transform;
            UIFactory.FullPanel(root, UIFactory.PanelColor);
            UIFactory.Label(root, "RISE ABOVE", 110, new Vector2(0, 480), new Vector2(1700, 130), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);
            UIFactory.Label(root, "A VR journey to overcome the fear of heights - one step at a time", 38, new Vector2(0, 395), new Vector2(1700, 60), TextAnchor.MiddleCenter, new Color(1, 1, 1, 0.8f));

            for (int i = 0; i < GameManager.LevelScenes.Length; i++)
                BuildLevelCard(root, i, new Vector2((i - 1) * 580, 90));

            UIFactory.Label(root, "Exposure mode", 40, new Vector2(-560, -235), new Vector2(500, 60), TextAnchor.MiddleLeft, UIFactory.Accent, FontStyle.Bold);
            string[] names = { "Gentle", "Standard", "Brave" };
            for (int m = 0; m < 3; m++)
            {
                int mode = m;
                modeButtons[m] = UIFactory.Button(root, names[m], new Vector2(-470 + m * 260, -315), new Vector2(240, 90), UIFactory.ButtonColor, () => SetMode((ExposureMode)mode), 36);
            }
            modeText = UIFactory.Label(root, "", 30, new Vector2(-210, -405), new Vector2(1200, 60), TextAnchor.MiddleLeft, new Color(1, 1, 1, 0.8f));
            RefreshMode();

            UIFactory.Button(root, "Calm Meadow tip", new Vector2(420, -315), new Vector2(320, 90), UIFactory.ButtonColor,
                () => Companion.Say("Feeling too much at any time? Press X on the left controller, or Esc on the keyboard, to go straight to the Calm Meadow.", 7f), 30);
            UIFactory.Button(root, "Reset progress", new Vector2(760, -315), new Vector2(300, 90), new Color(0.45f, 0.2f, 0.2f), ConfirmReset, 30);
            UIFactory.Button(root, "Quit", new Vector2(760, -440), new Vector2(300, 80), new Color(0.3f, 0.3f, 0.35f), () => GameManager.Instance.Quit(), 30);
            UIFactory.Label(root, "Session log: " + SessionLogger.FilePath, 20, new Vector2(-150, -520), new Vector2(1450, 40), TextAnchor.MiddleLeft, new Color(1, 1, 1, 0.4f));
        }

        void BuildLevelCard(Transform root, int i, Vector2 pos)
        {
            bool unlocked = GameManager.Instance.IsUnlocked(i);
            var card = UIFactory.Panel(root, unlocked ? new Color(0.12f, 0.2f, 0.3f, 1f) : new Color(0.12f, 0.12f, 0.15f, 1f), pos, new Vector2(540, 500));
            var t = card.transform;
            float[] heights = { 6f, 25f, 150f };
            UIFactory.Label(t, GameManager.LevelTitles[i].Replace(" - ", "\n"), 40, new Vector2(0, 175), new Vector2(500, 110), TextAnchor.MiddleCenter, Color.white, FontStyle.Bold);
            UIFactory.Label(t, heights[i] + " m up", 34, new Vector2(0, 100), new Vector2(500, 50), TextAnchor.MiddleCenter, UIFactory.Warn);
            UIFactory.Label(t, GameManager.LevelDescriptions[i], 26, new Vector2(0, 15), new Vector2(480, 120), TextAnchor.MiddleCenter, new Color(1, 1, 1, 0.8f));
            var stars = UIFactory.Label(t, "<color=#FFD84D>" + UIFactory.Stars(ProgressStore.GetStars(i)) + "</color>", 54, new Vector2(0, -85), new Vector2(500, 70));
            stars.supportRichText = true;
            float best = ProgressStore.GetBestTime(i);
            UIFactory.Label(t, best > 0 ? "Best time " + LevelController.FormatTime(best) : " ", 26, new Vector2(0, -135), new Vector2(500, 40), TextAnchor.MiddleCenter, new Color(1, 1, 1, 0.6f));
            var b = UIFactory.Button(t, unlocked ? "Play" : "Locked", new Vector2(0, -200), new Vector2(300, 80),
                unlocked ? UIFactory.Calm * 0.75f : new Color(0.3f, 0.3f, 0.3f), unlocked ? () => GameManager.Instance.LoadLevel(i) : (UnityEngine.Events.UnityAction)null, 38);
            b.interactable = unlocked;
        }

        void SetMode(ExposureMode mode)
        {
            ExposureSettings.Mode = mode;
            RefreshMode();
            Companion.Say(ExposureSettings.Describe(mode), 4f);
        }

        void RefreshMode()
        {
            var mode = ExposureSettings.Mode;
            for (int m = 0; m < 3; m++)
                modeButtons[m].GetComponent<Image>().color = m == (int)mode ? UIFactory.Calm * 0.8f : UIFactory.ButtonColor;
            modeText.text = ExposureSettings.Describe(mode);
        }

        void ConfirmReset()
        {
            Dialog.Show("Reset progress?", "This locks levels 2 and 3 again and clears stars and the anxiety history.\n(The CSV session log is kept.)",
                new Dialog.Choice("Reset", () =>
                {
                    GameManager.Instance.ResetProgress();
                    ProgressStore.ResetAll();
                    GameManager.Instance.LoadMenu();
                }, new Color(0.5f, 0.2f, 0.2f)),
                new Dialog.Choice("Cancel", null));
        }

        void BuildHelp()
        {
            var canvas = UIFactory.CreateWorldCanvas("Help", new Vector2(1000, 900), 0.0014f);
            canvas.transform.SetPositionAndRotation(helpPoint.position, helpPoint.rotation);
            var root = canvas.transform;
            UIFactory.FullPanel(root, UIFactory.PanelColor);
            UIFactory.Label(root, "How to play", 56, new Vector2(0, 380), new Vector2(950, 80), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);
            UIFactory.Label(root,
                "<b>VR controls</b>\n" +
                "Left stick: walk    Right stick: turn / teleport\n" +
                "Grip: grab things and ladder rungs\n" +
                "Trigger: press UI buttons\n" +
                "X button: Calm Meadow (safe place) - anytime\n" +
                "Crouch for real to resist wind gusts!\n\n" +
                "<b>Desktop controls</b>\n" +
                "WASD walk, mouse look, Shift careful steps\n" +
                "Left click use/grab, right click pour\n" +
                "C crouch, Space climb, Esc Calm Meadow, Tab cursor\n\n" +
                "<b>Stars</b>: finish  +  no slips  +  all courage stars",
                30, new Vector2(0, -40), new Vector2(920, 700), TextAnchor.UpperLeft).supportRichText = true;
        }

        void OnDestroy() => MenuOpen = false;
    }
}