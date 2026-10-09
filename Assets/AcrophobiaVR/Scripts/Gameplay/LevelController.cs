using System.Collections;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.SceneManagement;

namespace AcrophobiaVR
{
    /// <summary>
    /// Runs a level: intro with the companion, anxiety rating before, tasks, slips/respawns,
    /// anxiety rating after, star score and the summary screen.
    /// </summary>
    public class LevelController : MonoBehaviour
    {
        public static LevelController Instance { get; private set; }

        public int levelIndex;
        public string levelTitle = "Level";
        public Transform startPoint;
        public Transform boardPoint;
        public Objective[] objectives;
        [TextArea] public string[] introLines;
        [TextArea] public string finishLine = "You did it!";
        public float baseFogDensity = 1f;
        public UnityEvent onFinale = new UnityEvent();
        public float finaleSeconds = 0f;

        public const int MaxLives = 3;
        public int Slips { get; private set; }
        public int Lives { get; private set; } = MaxLives;
        public bool IsRespawning { get; private set; }
        public float ElapsedSeconds => Started ? Time.time - startTime : 0f;

        public int TasksDone
        {
            get
            {
                int n = 0;
                foreach (var o in objectives) if (o != null && o.IsComplete) n++;
                return n;
            }
        }
        public bool Started { get; private set; }
        public float StandingHeadHeight { get; private set; } = 1.65f;

        int ratingBefore = -1;
        float startTime;
        bool finished;

        void Awake()
        {
            Instance = this;
            if (GetComponent<FearSystem>() == null) gameObject.AddComponent<FearSystem>();
            if (GetComponent<PauseMenu>() == null) gameObject.AddComponent<PauseMenu>();
        }

        IEnumerator Start()
        {
            CourageStar.Init(FindObjectsByType<CourageStar>(FindObjectsSortMode.None).Length);
            ApplyFog(ExposureSettings.Mode);
            ExposureSettings.Changed += ApplyFog;
            if (startPoint != null) CheckpointSystem.Set(startPoint, "Start");
            SessionLogger.Log(SceneName, "level_loaded", ExposureSettings.Mode.ToString());

            yield return new WaitForSeconds(1.2f);
            if (PlayerRig.Instance != null && startPoint != null) PlayerRig.Instance.TeleportTo(startPoint);
            yield return new WaitForSeconds(0.3f);
            CalibrateHeight();

            if (introLines != null)
                foreach (var line in introLines)
                {
                    Companion.Say(line, 4.5f);
                    yield return new WaitForSeconds(5f);
                }

            AskBefore();
        }

        void OnDestroy() => ExposureSettings.Changed -= ApplyFog;

        static string SceneName => SceneManager.GetActiveScene().name;

        void ApplyFog(ExposureMode mode)
        {
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Exponential;
            RenderSettings.fogDensity = ExposureSettings.FogDensity(mode) * baseFogDensity;
        }

        public void CalibrateHeight()
        {
            var rig = PlayerRig.Instance;
            if (rig == null) return;
            float h = rig.Head.position.y - rig.FeetY;
            if (h > 1.0f && h < 2.3f) StandingHeadHeight = h;
        }

        /// <summary>True when the head is noticeably lower than standing height (crouching / kneeling).</summary>
        public bool IsCrouching
        {
            get
            {
                var rig = PlayerRig.Instance;
                if (rig == null) return false;
                return rig.Head.position.y - rig.FeetY < StandingHeadHeight * 0.78f;
            }
        }

        void AskBefore()
        {
            if (!ExposureSettings.TrackAnxiety)
            {
                StartCoroutine(CountdownThenBegin());
                return;
            }
            RatingPanel.Show(levelTitle, "Before we start: how anxious do you feel right now?\n0 = totally calm, 10 = panic", value =>
            {
                ratingBefore = value;
                SessionLogger.Log(SceneName, "anxiety_before", value.ToString());
                if (value >= 8 && ExposureSettings.Mode != ExposureMode.Gentle)
                {
                    Dialog.Show("Let's take it slower",
                        "That's a high number, and that's okay.\nEasy mode brings back railings, safety glass and fog so the drop feels less intense.",
                        new Dialog.Choice("Switch to Easy",() => { ExposureSettings.Mode = ExposureMode.Gentle; Breathe(); }, UIFactory.Calm * 0.8f),
                        new Dialog.Choice("Keep current mode", Breathe));
                }
                else if (value >= 5)
                {
                    Breathe();
                }
                else
                {
                    Begin();
                }
            });
        }

        IEnumerator CountdownThenBegin()
        {
            foreach (var n in new[] { "3", "2", "1" })
            {
                HeadHud.Instance.ShowMessage(n, 0.6f);
                ProceduralAudio.PlayChime(0.8f);
                yield return new WaitForSeconds(0.9f);
            }
            ProceduralAudio.PlayChime(1.6f);
            Begin();
        }

        void Breathe()
        {
            Companion.Say("Let's breathe together first. Follow the light.", 4f);
            BreathingGuide.Show(2, Begin);
        }

        void Begin()
        {
            if (Started) return;
            Started = true;
            startTime = Time.time;
            foreach (var o in objectives)
                if (o != null) o.Activate();
            if (boardPoint != null)
                ObjectiveBoard.Create(levelTitle, objectives, boardPoint.position, boardPoint.rotation);
            HeadHud.Instance.ShowMessage("Go! Press Esc (or X) anytime to pause", 4f);
            HeadHud.Instance.ShowLives(Lives, MaxLives, "3 lives - every fall is real", 4f);
            SessionLogger.Log(SceneName, "level_start");
        }

        bool AllObjectivesComplete
        {
            get
            {
                foreach (var o in objectives)
                    if (o != null && !o.IsComplete) return false;
                return true;
            }
        }

        public bool TryFinish()
        {
            if (finished || !Started) return false;
            if (!AllObjectivesComplete)
            {
                int left = 0;
                foreach (var o in objectives) if (o != null && !o.IsComplete) left++;
                HeadHud.Instance.ShowMessage(left + (left == 1 ? " task left" : " tasks left") + " - check the board", 3f);
                return false;
            }
            finished = true;
            StartCoroutine(FinishRoutine());
            return true;
        }

        IEnumerator FinishRoutine()
        {
            float seconds = Time.time - startTime;
            SessionLogger.Log(SceneName, "level_complete_seconds", seconds.ToString("F1", System.Globalization.CultureInfo.InvariantCulture));
            SessionLogger.Log(SceneName, "peak_bpm", FearSystem.PeakBpm.ToString());
            SessionLogger.Log(SceneName, "panics_beaten", FearSystem.PanicsBeaten.ToString());
            Companion.Say(finishLine, 5f);
            ProceduralAudio.PlayFanfare();
            onFinale?.Invoke();
            yield return new WaitForSeconds(Mathf.Max(2.5f, finaleSeconds));

            if (!ExposureSettings.TrackAnxiety)
            {
                Complete(seconds, -1, -1);
                yield break;
            }
            RatingPanel.Show("Level complete!", "And now: how anxious do you feel?\n0 = totally calm, 10 = panic", after =>
            {
                SessionLogger.Log(SceneName, "anxiety_after", after.ToString());
                Complete(seconds, Mathf.Max(0, ratingBefore), after);
            });
        }

        /// <summary>Score: tasks, courage stars, lives left and a time bonus.</summary>
        public int ComputeScore(float seconds)
        {
            int score = TasksDone * 500 + CourageStar.Collected * 250 + Lives * 400 + Mathf.Max(0, Mathf.RoundToInt(2000f - seconds * 4f));
            if (ExposureSettings.Mode == ExposureMode.Brave) score = Mathf.RoundToInt(score * 1.5f);
            else if (ExposureSettings.Mode == ExposureMode.Gentle) score = Mathf.RoundToInt(score * 0.6f);
            return score;
        }

        void Complete(float seconds, int before, int after)
        {
            int stars = 1 + (Slips == 0 ? 1 : 0) + (CourageStar.Total == 0 || CourageStar.Collected == CourageStar.Total ? 1 : 0);
            if (Slips == 0) Achievements.Unlock("steady_feet");
            if (CourageStar.Total > 0 && CourageStar.Collected == CourageStar.Total) Achievements.Unlock("star_collector");
            if (levelIndex == 2) Achievements.Unlock("sky_high");
            if (ExposureSettings.Mode == ExposureMode.Brave) Achievements.Unlock("brave_soul");
            if (FearSystem.PanicsBeaten > 0) Achievements.Unlock("panic_beaten"); // fallback; FearSystem may also unlock it live (idempotent)
            ProgressStore.RecordResult(levelIndex, stars, seconds, Mathf.Max(0, before), Mathf.Max(0, after));
            if (ProgressStore.TotalStars() >= 9) Achievements.Unlock("all_stars");
            GameManager.Instance.CompleteLevel(levelIndex);

            int score = ComputeScore(seconds);
            string bestKey = "acro_best_score_" + levelIndex;
            bool newBest = score > PlayerPrefs.GetInt(bestKey, 0);
            if (newBest)
            {
                PlayerPrefs.SetInt(bestKey, score);
                PlayerPrefs.Save();
            }
            SessionLogger.Log(SceneName, "score", score.ToString());
            ShowSummary(stars, seconds, before, after, score, newBest);
        }

        void ShowSummary(int stars, float seconds, int before, int after, int score, bool newBest)
        {
            string headline = Slips == 0 ? "Flawless - not a single fall!" : (Lives == 1 ? "Phew - that was close! One life left." : "Made it to the top!");
            string body =
                "\n\n<size=56><b>" + score.ToString("N0") + "</b></size> points" + (newBest ? "   <color=#FFD54D><b>NEW BEST!</b></color>" : "") + "\n" +
                "Time " + FormatTime(seconds) + "     Falls " + Slips + "     Lives left " + Lives + "/" + MaxLives + "     Courage stars " + CourageStar.Collected + "/" + CourageStar.Total + "\n" +
                "Peak heart rate " + FearSystem.PeakBpm + " BPM     Panic waves beaten " + FearSystem.PanicsBeaten + "\n\n" + headline;
            if (before >= 0 && after >= 0)
                body += "\nAnxiety " + before + " to " + after + (after < before ? " - it dropped!" : "");

            bool hasNext = levelIndex + 1 < GameManager.LevelScenes.Length;
            Dialog summary;
            if (hasNext)
                summary = Dialog.Show(levelTitle + " complete", body,
                    new Dialog.Choice("Next level", () => GameManager.Instance.LoadLevel(levelIndex + 1), UIFactory.Calm * 0.8f),
                    new Dialog.Choice("Replay", () => GameManager.Instance.ReloadCurrent()),
                    new Dialog.Choice("Menu", () => GameManager.Instance.LoadMenu()));
            else
                summary = Dialog.Show("You rose above!", body + "\n\nYou have completed every level.",
                    new Dialog.Choice("Replay", () => GameManager.Instance.ReloadCurrent()),
                    new Dialog.Choice("Back to the park", () => GameManager.Instance.LoadMenu(), UIFactory.Calm * 0.8f));
            UIFactory.StarRow(summary.Content, stars, 3, new Vector2(0, 215), 64f);
        }

        public static string FormatTime(float seconds)
        {
            int s = Mathf.RoundToInt(seconds);
            return (s / 60) + ":" + (s % 60).ToString("00");
        }

        /// <summary>
        /// Player fell (stepped off, lost balance, glass broke, a tile or plank gave way). The fall is felt for a
        /// moment before the screen goes dark, costs one of the three lives, and returns them to the checkpoint.
        /// </summary>
        public void Slip(string reason)
        {
            if (IsRespawning || finished) return;
            StartCoroutine(SlipRoutine(reason));
        }

        IEnumerator SlipRoutine(string reason)
        {
            IsRespawning = true;
            Slips++;
            Lives = Mathf.Max(0, Lives - 1);
            SessionLogger.Log(SceneName, "slip", reason);
            SessionLogger.Log(SceneName, "lives_left", Lives.ToString());
            Haptics.Strong();
            ProceduralAudio.PlayWhoosh(1f);
            FearSystem.Spike(0.6f);

            var rig = PlayerRig.Instance;
            if (rig != null && (reason == "balance" || reason == "gust"))
            {
                // Losing your balance tips you off the side of the beam - and then you really fall.
                Vector3 side = rig.Head.right * (Random.value < 0.5f ? -1f : 1f);
                side.y = 0f;
                rig.MoveBy(side.normalized * 0.8f);
            }
            // A second of rushing air before the screen goes dark (the fall itself is real physics).
            if (reason != "froze") yield return new WaitForSeconds(reason == "fall" ? 0.55f : 0.85f);
            yield return ScreenFader.Instance.FadeOut(0.3f);
            CheckpointSystem.RespawnPlayer();
            BalanceBeam.ResetAll();
            yield return new WaitForSeconds(0.4f);
            yield return ScreenFader.Instance.FadeIn(0.8f);

            if (Lives <= 0)
            {
                OutOfLives(); // IsRespawning stays true: nothing else can happen until the player chooses
                yield break;
            }
            IsRespawning = false;
            HeadHud.Instance.ShowLives(Lives, MaxLives, Lives == 1 ? "Last life - slow and steady" : Lives + " lives left");
            Companion.SayRandom(Companion.SlipLines);
        }

        void OutOfLives()
        {
            finished = true;
            SessionLogger.Log(SceneName, "out_of_lives");
            HeadHud.Instance.ShowLives(0, MaxLives, "Out of lives", 4f);
            var d = Dialog.Show("Game over",
                "You fell " + MaxLives + " times - the heights win this round.\n\n" +
                "Tasks done: " + TasksDone + " / " + objectives.Length + "     Courage stars: " + CourageStar.Collected + " / " + CourageStar.Total + "\n\n" +
                "Watch your footing, crouch in the wind, and go again!",
                new Dialog.Choice("Try again", () => GameManager.Instance.ReloadCurrent(), UIFactory.Calm * 0.8f),
                new Dialog.Choice("Back to the park", () => GameManager.Instance.LoadMenu()));
            UIFactory.HeartRow(d.Content, 0, MaxLives, new Vector2(0, 215), 64f);
        }
    }
}