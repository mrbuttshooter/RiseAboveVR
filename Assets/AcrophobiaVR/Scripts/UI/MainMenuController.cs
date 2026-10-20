using UnityEngine;
using UnityEngine.UI;

namespace AcrophobiaVR
{
    /// <summary>
    /// The hub: title, level cards (play / locked / medal / best time / best score), difficulty picker,
    /// a records wall (medals + achievements), and help. Walking through the portals also starts levels.
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
            if (trophyPoint != null) BuildRecords();
            if (helpPoint != null) BuildHelp();
            Invoke(nameof(Welcome), 1.5f);
        }

        void Welcome()
        {
            int total = ProgressStore.TotalMedals();
            if (total == 0)
                Companion.Say("I'm Pip, your race drone. Three courses, one clock, no railings. Think you can keep up?", 6f);
            else
                Companion.Say("Back for more? " + total + " of 9 medal points so far. Gold on Hard or it does not count!", 5f);
        }

        void BuildMenu()
        {
            MenuOpen = true;
            var canvas = UIFactory.CreateWorldCanvas("MainMenu", new Vector2(1700, 1120), 0.0015f);
            canvas.transform.SetPositionAndRotation(menuPoint.position, menuPoint.rotation);
            var root = canvas.transform;
            UIFactory.FullPanel(root, new Color(0.06f, 0.1f, 0.16f, 0.95f));
            UIFactory.Label(root, "RISE ABOVE", 130, new Vector2(0, 470), new Vector2(1650, 150), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);
            UIFactory.Label(root, "Run. Jump. Don't fall. Beat the clock.", 46, new Vector2(0, 375), new Vector2(1650, 64), TextAnchor.MiddleCenter, Dim);

            for (int i = 0; i < GameManager.LevelScenes.Length; i++)
                BuildLevelCard(root, i, new Vector2((i - 1) * 555, 70));

            UIFactory.Label(root, "Difficulty:", 46, new Vector2(-670, -300), new Vector2(300, 70), TextAnchor.MiddleLeft, UIFactory.Accent, FontStyle.Bold);
            string[] names = { Difficulty.DisplayName(DifficultyLevel.Easy), Difficulty.DisplayName(DifficultyLevel.Normal), Difficulty.DisplayName(DifficultyLevel.Hard) };
            for (int m = 0; m < 3; m++)
            {
                int mode = m;
                modeButtons[m] = UIFactory.Button(root, names[m], new Vector2(-330 + m * 250, -300), new Vector2(235, 92), UIFactory.ButtonColor, () => SetMode((DifficultyLevel)mode), 42);
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

            UIFactory.Label(root, "In a level:  A / Space = jump     crouch = hold on in the wind     Esc / X = pause", 34, new Vector2(0, -490), new Vector2(1650, 56), TextAnchor.MiddleCenter, UIFactory.Calm);
        }

        void BuildLevelCard(Transform root, int i, Vector2 pos)
        {
            bool unlocked = GameManager.Instance.IsUnlocked(i);
            var card = UIFactory.Panel(root, unlocked ? new Color(0.13f, 0.23f, 0.35f, 1f) : new Color(0.13f, 0.13f, 0.16f, 1f), pos, new Vector2(525, 520));
            var t = card.transform;
            string[] names = { "Rooftop Chase", "Crane Rush", "Skyline Gauntlet" };
            string[] heights = { "11-16 m", "6-28 m", "139-150 m" };
            UIFactory.Label(t, "LEVEL " + (i + 1), 38, new Vector2(0, 205), new Vector2(500, 56), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);
            UIFactory.Label(t, names[i], 50, new Vector2(0, 145), new Vector2(510, 70), TextAnchor.MiddleCenter, Color.white, FontStyle.Bold);
            UIFactory.Label(t, heights[i] + " high", 40, new Vector2(0, 88), new Vector2(500, 52), TextAnchor.MiddleCenter, UIFactory.Warn, FontStyle.Bold);
            UIFactory.Label(t, GameManager.LevelDescriptions[i], 28, new Vector2(0, 8), new Vector2(480, 112), TextAnchor.MiddleCenter, Dim);
            int medal = ProgressStore.GetMedal(i);
            UIFactory.Label(t, medal > 0 ? ProgressStore.MedalName(medal).ToUpperInvariant() + " MEDAL" : "No medal yet", 40, new Vector2(0, -85), new Vector2(500, 56),
                TextAnchor.MiddleCenter, ProgressStore.MedalColor(medal), FontStyle.Bold);
            float best = ProgressStore.GetBestTime(i);
            int bestScore = ProgressStore.GetBestScore(i);
            UIFactory.Label(t, best > 0 ? "Best " + LevelController.FormatTime(best, true) + (bestScore > 0 ? "   " + bestScore.ToString("N0") + " pts" : "") : " ", 30, new Vector2(0, -140), new Vector2(500, 44), TextAnchor.MiddleCenter, Dim);
            var b = UIFactory.Button(t, unlocked ? "PLAY" : "LOCKED", new Vector2(0, -205), new Vector2(320, 90),
                unlocked ? UIFactory.Calm * 0.8f : new Color(0.32f, 0.32f, 0.32f), unlocked ? () => GameManager.Instance.LoadLevel(i) : (UnityEngine.Events.UnityAction)null, 46);
            b.interactable = unlocked;
        }

        void BuildRecords()
        {
            var canvas = UIFactory.CreateWorldCanvas("Records", new Vector2(1000, 1000), 0.0015f);
            canvas.transform.SetPositionAndRotation(trophyPoint.position, trophyPoint.rotation);
            var root = canvas.transform;
            UIFactory.FullPanel(root, new Color(0.06f, 0.1f, 0.16f, 0.95f));
            UIFactory.Label(root, "RECORDS", 64, new Vector2(0, 430), new Vector2(950, 90), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);
            var sb = new System.Text.StringBuilder();
            for (int i = 0; i < GameManager.LevelScenes.Length; i++)
            {
                int m = ProgressStore.GetMedal(i);
                float best = ProgressStore.GetBestTime(i);
                sb.Append("<b>" + GameManager.LevelTitles[i] + "</b>\n<color=#" + ColorUtility.ToHtmlStringRGB(ProgressStore.MedalColor(m)) + ">" +
                          ProgressStore.MedalName(m) + "</color>" + (best > 0f ? "   " + LevelController.FormatTime(best, true) : "") + "\n\n");
            }
            sb.Append("<b><color=#FFD84D>Achievements " + Achievements.UnlockedCount + " / " + Achievements.All.Length + "</color></b>\n");
            foreach (var a in Achievements.All)
                sb.Append(Achievements.IsUnlocked(a.id) ? "<color=#8FE3B0>\u2714 " + a.title + "</color>\n" : "<color=#777777>\u2022 " + a.title + "</color>\n");
            var body = UIFactory.Label(root, sb.ToString(), 32, new Vector2(0, -50), new Vector2(920, 820), TextAnchor.UpperLeft);
            body.richText = true;
        }

        void SetMode(DifficultyLevel mode)
        {
            Difficulty.Level = mode;
            RefreshMode();
            Companion.Say(Difficulty.Describe(mode), 4f);
        }

        void RefreshMode()
        {
            var mode = Difficulty.Level;
            for (int m = 0; m < 3; m++)
                modeButtons[m].GetComponent<Image>().color = m == (int)mode ? UIFactory.Calm * 0.85f : UIFactory.ButtonColor;
            modeText.text = Difficulty.Describe(mode);
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
            Dialog.Show("Reset progress?", "This locks levels 2 and 3 again and clears medals, best times and achievements.",
                new Dialog.Choice("Reset", () =>
                {
                    GameManager.Instance.ResetProgress();
                    ProgressStore.ResetAll();
                    Achievements.ResetAll();
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
                "Left stick - run,  Right stick - turn\n" +
                "A - jump (no teleporting!)\n" +
                "Grip - grab, climb, zipline\n" +
                "Gust warning? Crouch!\n\n" +
                "<b><color=#5CC8FA>Keyboard + mouse</color></b>\n" +
                "WASD - run,  Shift - sprint\n" +
                "Space - jump / climb,  C - crouch\n" +
                "Click - use / grab\n\n" +
                "<b><color=#FFD84D>Medals:</color></b> beat the gold / silver / bronze time.\n" +
                "Falls cost lives; time up = game over.",
                38, new Vector2(0, -50), new Vector2(920, 820), TextAnchor.UpperLeft);
            body.richText = true;
        }

        void OnDestroy() => MenuOpen = false;
    }
}