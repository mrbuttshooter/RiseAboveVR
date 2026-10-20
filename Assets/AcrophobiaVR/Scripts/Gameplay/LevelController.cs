using System.Collections;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.SceneManagement;

namespace AcrophobiaVR
{
    /// <summary>
    /// Runs a level as a race against the clock: short intro, 3-2-1-GO, goals, falls cost a life, a hard time
    /// limit (time's up = game over), medal times, score, best results and the summary screen.
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
        public UnityEvent onFinale = new UnityEvent();
        public float finaleSeconds = 0f;

        [Header("Clock (Normal difficulty; scaled by Difficulty.TimeFactor)")]
        public float timeLimit = 240f;
        public float goldTime = 120f;
        public float silverTime = 160f;
        public float bronzeTime = 200f;

        public int MaxLives { get; private set; } = 3;
        public int Slips { get; private set; }
        public int Lives { get; private set; } = 3;
        public bool IsRespawning { get; private set; }
        public bool Started { get; private set; }
        public bool Finished => finished;
        public float ElapsedSeconds => Started ? (finished ? finishSeconds : Time.time - startTime) : 0f;
        public float TimeLimit => timeLimit * Difficulty.TimeFactor;
        public float TimeLeft => Mathf.Max(0f, TimeLimit - ElapsedSeconds);
        public float StandingHeadHeight { get; private set; } = 1.65f;

        public int TasksDone
        {
            get
            {
                int n = 0;
                foreach (var o in objectives) if (o != null && o.IsComplete) n++;
                return n;
            }
        }

        float startTime;
        float finishSeconds;
        bool finished;
        bool warned30;
        bool warned10;
        int lastBeep = -1;

        void Awake()
        {
            Instance = this;
            MaxLives = Lives = Difficulty.Lives;
            if (GetComponent<PauseMenu>() == null) gameObject.AddComponent<PauseMenu>();
        }

        IEnumerator Start()
        {
            CourageStar.Init(FindObjectsByType<CourageStar>(FindObjectsSortMode.None).Length);
            if (startPoint != null) CheckpointSystem.Set(startPoint, "Start");
            SessionLogger.Log(SceneName, "level_loaded", Difficulty.Level.ToString());

            yield return new WaitForSeconds(1.0f);
            if (PlayerRig.Instance != null)
            {
                PlayerRig.Instance.ConfigureForRunning();
                if (startPoint != null) PlayerRig.Instance.TeleportTo(startPoint);
            }
            yield return new WaitForSeconds(0.3f);
            CalibrateHeight();

            if (introLines != null)
                foreach (var line in introLines)
                {
                    Companion.Say(line, 3.6f);
                    yield return new WaitForSeconds(4f);
                }
            yield return Countdown();
            Begin();
        }

        static string SceneName => SceneManager.GetActiveScene().name;

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

        IEnumerator Countdown()
        {
            HeadHud.Instance.ShowMessage(levelTitle + "\nTime limit " + FormatTime(TimeLimit) + "   Gold under " + FormatTime(goldTime * Difficulty.TimeFactor), 2.6f);
            yield return new WaitForSeconds(2.8f);
            foreach (var n in new[] { "3", "2", "1" })
            {
                HeadHud.Instance.ShowMessage(n, 0.6f);
                ProceduralAudio.PlayChime(0.8f);
                Haptics.Light();
                yield return new WaitForSeconds(0.9f);
            }
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
            ProceduralAudio.PlayChime(1.6f);
            HeadHud.Instance.ShowMessage("GO!", 1.2f);
            HeadHud.Instance.ShowLives(Lives, MaxLives, MaxLives + " lives - make them count", 3f);
            SessionLogger.Log(SceneName, "level_start");
        }

        void Update()
        {
            if (!Started) { HeadHud.Instance.SetStatus(null); return; }
            UpdateStatus();
            if (finished || IsRespawning) return;

            float left = TimeLeft;
            if (!warned30 && left <= 30f && TimeLimit > 45f)
            {
                warned30 = true;
                Companion.SayRandom(Companion.HurryLines);
            }
            if (!warned10 && left <= 10f)
            {
                warned10 = true;
                HeadHud.Instance.ShowMessage("10 seconds!", 1.5f);
            }
            int sec = Mathf.CeilToInt(left);
            if (left <= 10f && sec != lastBeep)
            {
                lastBeep = sec;
                ProceduralAudio.PlayChime(1.2f + (10 - sec) * 0.05f);
            }
            if (left <= 0f) TimeUp();
        }

        void UpdateStatus()
        {
            float t = ElapsedSeconds;
            float left = TimeLeft;
            string clockColor = left <= 10f ? "#FF5A5A" : left <= 30f ? "#FFB347" : "#FFFFFF";
            int medal = MedalFor(t);
            string target = medal >= 3 ? "<color=#FFD54D>GOLD pace</color>"
                : medal == 2 ? "<color=#D6DCE6>Silver pace</color>"
                : medal == 1 ? "<color=#D98C4D>Bronze pace</color>" : "<color=#888888>No medal</color>";
            string hearts = "";
            for (int i = 0; i < MaxLives; i++) hearts += i < Lives ? "<color=#FF4D5C>♥</color>" : "<color=#555555>♥</color>";
            string stars = CourageStar.Total > 0 ? "   <color=#FFD54D>Stars " + CourageStar.Collected + "/" + CourageStar.Total + "</color>" : "";
            HeadHud.Instance.SetStatus("<color=" + clockColor + "><b>" + FormatTime(left, true) + "</b></color>   " + target + "   " + hearts + stars);
        }

        /// <summary>Medal earned for a finishing time: 3 gold, 2 silver, 1 bronze, 0 none.</summary>
        public int MedalFor(float seconds)
        {
            float f = Difficulty.TimeFactor;
            if (seconds <= goldTime * f) return 3;
            if (seconds <= silverTime * f) return 2;
            if (seconds <= bronzeTime * f) return 1;
            return 0;
        }

#if UNITY_EDITOR
        /// <summary>Editor course tests: refill lives so one failed check doesn't end the whole test run.</summary>
        public void DevRefillLives() => Lives = MaxLives;
#endif

        public void OnCheckpoint(string label)
        {
            if (Random.value < 0.5f) Companion.SayRandom(Companion.NiceLines);
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

        public bool TryFinish(bool hint = true)
        {
            if (finished || !Started) return false;
            if (!AllObjectivesComplete)
            {
                if (hint)
                    foreach (var o in objectives)
                        if (o != null && !o.IsComplete)
                        {
                            HeadHud.Instance.ShowMessage("Not yet: " + o.Description, 2.5f);
                            break;
                        }
                return false;
            }
            finished = true;
            finishSeconds = Time.time - startTime;
            if (PlayerRig.Instance != null) PlayerRig.Instance.SetLocomotionEnabled(false); // stand still for the celebration
            StartCoroutine(FinishRoutine());
            return true;
        }

        IEnumerator FinishRoutine()
        {
            float seconds = finishSeconds;
            SessionLogger.Log(SceneName, "level_complete_seconds", seconds.ToString("F1", System.Globalization.CultureInfo.InvariantCulture));
            Companion.Say(finishLine, 4f);
            ProceduralAudio.PlayFanfare();
            Haptics.Strong();
            onFinale?.Invoke();
            yield return new WaitForSeconds(Mathf.Max(2.5f, finaleSeconds));
            Complete(seconds);
        }

        /// <summary>Score: time left, lives left, stars, goals; scaled by difficulty.</summary>
        public int ComputeScore(float seconds)
        {
            float left = Mathf.Max(0f, TimeLimit - seconds);
            int score = Mathf.RoundToInt(left * 25f) + Lives * 500 + CourageStar.Collected * 300 + TasksDone * 200 + 1000;
            return Mathf.RoundToInt(score * Difficulty.ScoreFactor);
        }

        void Complete(float seconds)
        {
            int medal = MedalFor(seconds);
            Achievements.Unlock("first_finish");
            if (Slips == 0) Achievements.Unlock("steady_feet");
            if (Lives == 1 && Slips > 0) Achievements.Unlock("last_life");
            if (CourageStar.Total > 0 && CourageStar.Collected == CourageStar.Total) Achievements.Unlock("star_collector");
            if (medal >= 3) Achievements.Unlock("gold_rush");
            if (TimeLimit - seconds < 5f) Achievements.Unlock("photo_finish");
            if (levelIndex == 1) Achievements.Unlock("storm_beater");
            if (levelIndex == 2) Achievements.Unlock("sky_high");
            if (Difficulty.Level == DifficultyLevel.Hard) Achievements.Unlock("brave_soul");

            int score = ComputeScore(seconds);
            float oldBest = ProgressStore.GetBestTime(levelIndex);
            bool newBest = ProgressStore.RecordResult(levelIndex, medal, seconds, score);
            if (ProgressStore.TotalMedals() >= 9) Achievements.Unlock("all_stars");
            GameManager.Instance.CompleteLevel(levelIndex);
            SessionLogger.Log(SceneName, "score", score.ToString());
            ShowSummary(medal, seconds, score, newBest, oldBest);
        }

        void ShowSummary(int medal, float seconds, int score, bool newBest, float oldBest)
        {
            string medalLine = "<size=60><b><color=#" + ColorUtility.ToHtmlStringRGB(ProgressStore.MedalColor(medal)) + ">" +
                               ProgressStore.MedalName(medal).ToUpperInvariant() + "</color></b></size>";
            string next = medal >= 3 ? "Untouchable." : "Next medal: under " + FormatTime(NextMedalTime(medal), true);
            string body =
                "\n" + medalLine + "\n" +
                "<size=46><b>" + score.ToString("N0") + "</b></size> points" + (newBest ? "   <color=#FFD54D><b>NEW BEST!</b></color>" : "") + "\n" +
                "Time " + FormatTime(seconds, true) + (oldBest > 0f ? "   (best " + FormatTime(Mathf.Min(oldBest, seconds), true) + ")" : "") +
                "     Falls " + Slips + "     Lives " + Lives + "/" + MaxLives + "     Stars " + CourageStar.Collected + "/" + CourageStar.Total + "\n\n" + next;

            bool hasNext = levelIndex + 1 < GameManager.LevelScenes.Length;
            if (hasNext)
                Dialog.Show(levelTitle + " complete", body,
                    new Dialog.Choice("Next level", () => GameManager.Instance.LoadLevel(levelIndex + 1), UIFactory.Calm * 0.8f),
                    new Dialog.Choice("Retry for a better time", () => GameManager.Instance.ReloadCurrent()),
                    new Dialog.Choice("Menu", () => GameManager.Instance.LoadMenu()));
            else
                Dialog.Show("You beat the skyline!", body + "\n\nAll three levels done. Now go get gold on Hard.",
                    new Dialog.Choice("Retry for a better time", () => GameManager.Instance.ReloadCurrent(), UIFactory.Calm * 0.8f),
                    new Dialog.Choice("Menu", () => GameManager.Instance.LoadMenu()));
        }

        float NextMedalTime(int medal)
        {
            float f = Difficulty.TimeFactor;
            return (medal == 2 ? goldTime : medal == 1 ? silverTime : bronzeTime) * f;
        }

        public static string FormatTime(float seconds, bool tenths = false)
        {
            seconds = Mathf.Max(0f, seconds);
            int m = Mathf.FloorToInt(seconds / 60f);
            float s = seconds - m * 60;
            return tenths ? m + ":" + s.ToString("00.0", System.Globalization.CultureInfo.InvariantCulture)
                          : m + ":" + Mathf.FloorToInt(s).ToString("00");
        }

        /// <summary>
        /// Player fell (missed a jump, knocked off, glass broke, a plank collapsed). The fall is felt for a moment
        /// before the screen goes dark, costs a life, and returns them to the last checkpoint. The clock keeps running.
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
            Haptics.Strong();
            ProceduralAudio.PlayWhoosh(1f);

            var rig = PlayerRig.Instance;
            if (rig != null && (reason == "balance" || reason == "gust" || reason == "hit"))
            {
                // Knocked or blown off the side - and then you really fall.
                Vector3 side = rig.Head.right * (Random.value < 0.5f ? -1f : 1f);
                side.y = 0f;
                rig.MoveBy(side.normalized * 0.8f);
            }
            yield return new WaitForSeconds(reason == "fall" ? 0.5f : 0.8f);
            yield return ScreenFader.Instance.FadeOut(0.25f);
            CheckpointSystem.RespawnPlayer();
            BalanceBeam.ResetAll();
            Hazard.ResetAll();
            yield return new WaitForSeconds(0.3f);
            yield return ScreenFader.Instance.FadeIn(0.5f);

            if (Lives <= 0)
            {
                GameOver("Out of lives", "You fell " + Slips + " times - the heights win this round.");
                yield break;
            }
            IsRespawning = false;
            HeadHud.Instance.ShowLives(Lives, MaxLives, Lives == 1 ? "LAST LIFE" : Lives + " lives left");
            Companion.SayRandom(Companion.SlipLines);
        }

        void TimeUp()
        {
            Haptics.Strong();
            ProceduralAudio.PlayCrack();
            GameOver("Time's up!", "The clock beat you this time.");
        }

        void GameOver(string title, string reason)
        {
            if (finished) return;
            finished = true;
            IsRespawning = true; // nothing else can happen until the player chooses
            finishSeconds = Time.time - startTime;
            if (PlayerRig.Instance != null) PlayerRig.Instance.SetLocomotionEnabled(false);
            SessionLogger.Log(SceneName, "game_over", title);
            HeadHud.Instance.ShowLives(Lives, MaxLives, title, 4f);
            var d = Dialog.Show(title,
                reason + "\n\nGoals done: " + TasksDone + " / " + objectives.Length + "     Stars: " + CourageStar.Collected + " / " + CourageStar.Total +
                "     Time " + FormatTime(finishSeconds, true) + "\n\nLearn the route, keep moving, commit to every jump.",
                new Dialog.Choice("Try again", () => GameManager.Instance.ReloadCurrent(), UIFactory.Calm * 0.8f),
                new Dialog.Choice("Menu", () => GameManager.Instance.LoadMenu()));
            UIFactory.HeartRow(d.Content, Lives, MaxLives, new Vector2(0, 215), 56f);
        }
    }
}
