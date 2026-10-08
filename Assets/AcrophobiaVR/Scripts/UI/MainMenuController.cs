using UnityEngine;
using UnityEngine.UI;

namespace AcrophobiaVR
{
    /// <summary>
    /// The park hub: title, level cards (play / locked / stars / best time), exposure mode picker,
    /// trophy wall with the anxiety graph, and help. Walking through the portals also starts levels.
    /// Text is deliberately large and short so it stays readable in a headset and on a laptop screen.
    /// </summary>
    public class MainMenuController : MonoBehaviour
    {
        public static bool MenuOpen { get; private set; }

        public Transform menuPoint;
        public Transform trophyPoint;
        public Transform helpPoint;

        static readonly Color Dim = new Color(1f, 1f, 1f, 0.85f);

        readonly Button[] modeButtons = new Button[3];
        TMPro.TMP_Text modeText;
        TMPro.TMP_Text volumeText;

        void Start()
        {
            AmbientAudio.SetMeadow(false);
            BuildMenu();
            if (trophyPoint != null) AnxietyGraph.Create(trophyPoint);
            if (helpPoint != null) BuildHelp();
            Invoke(nameof(Welcome), 1.5f);
        }

        void Welcome()
        {
            int total = ProgressStore.TotalStars();
            if (total == 0)
                Companion.Say("Hi, I'm Pip! I'll be with you the whole way up. Start with Level 1 - we go higher step by step.", 7f);
            else
                Companion.Say("Welcome back! You have " + total + " of 9 stars. Ready to rise a little higher?", 5f);
        }

        void BuildMenu()
        {
            MenuOpen = true;
            var canvas = UIFactory.CreateWorldCanvas("MainMenu", new Vector2(1700, 1120), 0.0015f);
            canvas.transform.SetPositionAndRotation(menuPoint.position, menuPoint.rotation);
            var root = canvas.transform;
            UIFactory.FullPanel(root, new Color(0.06f, 0.1f, 0.16f, 0.95f));
            UIFactory.Label(root, "RISE ABOVE", 130, new Vector2(0, 470), new Vector2(1650, 150), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);
            UIFactory.Label(root, "Overcome the fear of heights - one step at a time", 46, new Vector2(0, 375), new Vector2(1650, 64), TextAnchor.MiddleCenter, Dim);

            for (int i = 0; i < GameManager.LevelScenes.Length; i++)
                BuildLevelCard(root, i, new Vector2((i - 1) * 555, 70));

            UIFactory.Label(root, "Exposure:", 46, new Vector2(-670, -300), new Vector2(300, 70), TextAnchor.MiddleLeft, UIFactory.Accent, FontStyle.Bold);
            string[] names = { "Gentle", "Standard", "Brave" };
            for (int m = 0; m < 3; m++)
            {
                int mode = m;
                modeButtons[m] = UIFactory.Button(root, names[m], new Vector2(-330 + m * 250, -300), new Vector2(235, 92), UIFactory.ButtonColor, () => SetMode((ExposureMode)mode), 42);
            }
            modeText = UIFactory.Label(root, "", 36, new Vector2(-200, -395), new Vector2(1200, 60), TextAnchor.MiddleLeft, Dim);
            RefreshMode();

            UIFactory.Button(root, "Reset", new Vector2(520, -300), new Vector2(220, 92), new Color(0.5f, 0.22f, 0.22f), ConfirmReset, 40);
            UIFactory.Button(root, "Quit", new Vector2(740, -300), new Vector2(180, 92), new Color(0.32f, 0.32f, 0.38f), () => GameManager.Instance.Quit(), 40);

            // Master volume (right side of the mode-description row; that text ends at x = 400).
            // 34 pt bold "Volume" is ~137 px wide; NoWrap so TMP never splits the word inside the 140 px box.
            var volumeLabel = UIFactory.Label(root, "Volume", 34, new Vector2(475, -395), new Vector2(140, 70), TextAnchor.MiddleLeft, UIFactory.Accent, FontStyle.Bold);
            volumeLabel.textWrappingMode = TMPro.TextWrappingModes.NoWrap;
            UIFactory.Button(root, "-", new Vector2(582, -395), new Vector2(70, 70), UIFactory.ButtonColor, () => ChangeVolume(-0.1f), 44);
            volumeText = UIFactory.Label(root, "", 36, new Vector2(667, -395), new Vector2(100, 70), TextAnchor.MiddleCenter, Color.white, FontStyle.Bold);
            volumeText.textWrappingMode = TMPro.TextWrappingModes.NoWrap;
            UIFactory.Button(root, "+", new Vector2(752, -395), new Vector2(70, 70), UIFactory.ButtonColor, () => ChangeVolume(0.1f), 44);
            RefreshVolume();

            UIFactory.Label(root, "Feeling too much? Press X (or Esc) anytime for the Calm Meadow.", 34, new Vector2(0, -490), new Vector2(1650, 56), TextAnchor.MiddleCenter, UIFactory.Calm);
        }

        void BuildLevelCard(Transform root, int i, Vector2 pos)
        {
            bool unlocked = GameManager.Instance.IsUnlocked(i);
            var card = UIFactory.Panel(root, unlocked ? new Color(0.13f, 0.23f, 0.35f, 1f) : new Color(0.13f, 0.13f, 0.16f, 1f), pos, new Vector2(525, 520));
            var t = card.transform;
            string[] names = { "The Balcony", "Construction Site", "The Skyscraper" };
            string[] heights = { "6 m", "25 m", "150 m" };
            UIFactory.Label(t, "LEVEL " + (i + 1), 38, new Vector2(0, 205), new Vector2(500, 56), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);
            UIFactory.Label(t, names[i], 50, new Vector2(0, 145), new Vector2(510, 70), TextAnchor.MiddleCenter, Color.white, FontStyle.Bold);
            UIFactory.Label(t, heights[i] + " high", 44, new Vector2(0, 80), new Vector2(500, 60), TextAnchor.MiddleCenter, UIFactory.Warn, FontStyle.Bold);
            UIFactory.Label(t, GameManager.LevelDescriptions[i], 32, new Vector2(0, 0), new Vector2(480, 100), TextAnchor.MiddleCenter, Dim);
            UIFactory.StarRow(t, ProgressStore.GetStars(i), 3, new Vector2(0, -85), 58f);
            float best = ProgressStore.GetBestTime(i);
            UIFactory.Label(t, best > 0 ? "Best " + LevelController.FormatTime(best) : " ", 30, new Vector2(0, -140), new Vector2(500, 44), TextAnchor.MiddleCenter, Dim);
            var b = UIFactory.Button(t, unlocked ? "PLAY" : "LOCKED", new Vector2(0, -205), new Vector2(320, 90),
                unlocked ? UIFactory.Calm * 0.8f : new Color(0.32f, 0.32f, 0.32f), unlocked ? () => GameManager.Instance.LoadLevel(i) : (UnityEngine.Events.UnityAction)null, 46);
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
                modeButtons[m].GetComponent<Image>().color = m == (int)mode ? UIFactory.Calm * 0.85f : UIFactory.ButtonColor;
            modeText.text = ExposureSettings.Describe(mode);
        }

        // UIFactory.Button already plays ProceduralAudio.PlayClick on press, so no extra click here.
        void ChangeVolume(float delta)
        {
            // Round to whole tenths so repeated presses land exactly on 0%, 10% ... 100%.
            float v = Mathf.Round((AudioSettingsStore.MasterVolume + delta) * 10f) / 10f;
            AudioSettingsStore.MasterVolume = Mathf.Clamp01(v);
            RefreshVolume();
        }

        void RefreshVolume()
        {
            if (volumeText != null)
                volumeText.text = Mathf.RoundToInt(AudioSettingsStore.MasterVolume * 100f) + "%";
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
            var canvas = UIFactory.CreateWorldCanvas("Help", new Vector2(1000, 1000), 0.0015f);
            canvas.transform.SetPositionAndRotation(helpPoint.position, helpPoint.rotation);
            var root = canvas.transform;
            UIFactory.FullPanel(root, new Color(0.06f, 0.1f, 0.16f, 0.95f));
            UIFactory.Label(root, "HOW TO PLAY", 64, new Vector2(0, 430), new Vector2(950, 90), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);
            var body = UIFactory.Label(root,
                "<b><color=#5CC8FA>VR</color></b>\n" +
                "Left stick - walk\n" +
                "Right stick - turn / teleport\n" +
                "Grip - grab, climb\n" +
                "Trigger - press buttons\n" +
                "Wind gust? Crouch down!\n\n" +
                "<b><color=#5CC8FA>Keyboard + mouse</color></b>\n" +
                "WASD - walk,  Mouse - look\n" +
                "Click - use / grab\n" +
                "C - crouch,  Space - climb\n\n" +
                "<b><color=#FFD84D>Stars:</color></b> finish + no slips + all courage stars",
                38, new Vector2(0, -50), new Vector2(920, 820), TextAnchor.UpperLeft);
            body.richText = true;
        }

        void OnDestroy() => MenuOpen = false;
    }
}