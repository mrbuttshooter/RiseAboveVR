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

        public int Slips { get; private set; }
        public bool IsRespawning { get; private set; }
        public bool Started { get; private set; }
        public float StandingHeadHeight { get; private set; } = 1.65f;

        int ratingBefore = -1;
        float startTime;
        bool finished;

        void Awake()
        {
            Instance = this;
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
            RatingPanel.Show(levelTitle, "Before we start: how anxious do you feel right now?\n0 = totally calm, 10 = panic", value =>
            {
                ratingBefore = value;
                SessionLogger.Log(SceneName, "anxiety_before", value.ToString());
                if (value >= 8 && ExposureSettings.Mode != ExposureMode.Gentle)
                {
                    Dialog.Show("Let's take it slower",
                        "That's a high number, and that's okay.\nGentle mode adds safety glass, extra rails and fog so the drop feels less intense.",
                        new Dialog.Choice("Switch to Gentle", () => { ExposureSettings.Mode = ExposureMode.Gentle; Breathe(); }, UIFactory.Calm * 0.8f),
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
            HeadHud.Instance.ShowMessage("Go! Press X / Esc anytime for the Calm Meadow", 4f);
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
            Companion.Say(finishLine, 5f);
            ProceduralAudio.PlayFanfare();
            onFinale?.Invoke();
            yield return new WaitForSeconds(Mathf.Max(2.5f, finaleSeconds));

            RatingPanel.Show("Level complete!", "And now: how anxious do you feel?\n0 = totally calm, 10 = panic", after =>
            {
                SessionLogger.Log(SceneName, "anxiety_after", after.ToString());
                int stars = 1 + (Slips == 0 ? 1 : 0) + (CourageStar.Total == 0 || CourageStar.Collected == CourageStar.Total ? 1 : 0);
                int before = Mathf.Max(0, ratingBefore);
                ProgressStore.RecordResult(levelIndex, stars, seconds, before, after);
                GameManager.Instance.CompleteLevel(levelIndex);
                ShowSummary(stars, seconds, before, after);
            });
        }

        void ShowSummary(int stars, float seconds, int before, int after)
        {
            string change;
            if (after < before) change = "Your anxiety dropped by <b>" + (before - after) + "</b> points. That is exposure therapy working!";
            else if (after == before) change = "Your anxiety stayed level - you handled the height without it growing.";
            else change = "It felt harder this time, and you still finished. That counts. Try Gentle mode or a breathing break next time.";

            string body =
                "<size=70><color=#FFD84D>" + UIFactory.Stars(stars) + "</color></size>\n" +
                "Time " + FormatTime(seconds) + "     Slips " + Slips + "     Courage stars " + CourageStar.Collected + "/" + CourageStar.Total + "\n" +
                "Anxiety " + before + " \u2192 " + after + "\n\n" + change;

            bool hasNext = levelIndex + 1 < GameManager.LevelScenes.Length;
            if (hasNext)
                Dialog.Show(levelTitle + " complete", body,
                    new Dialog.Choice("Next level", () => GameManager.Instance.LoadLevel(levelIndex + 1), UIFactory.Calm * 0.8f),
                    new Dialog.Choice("Replay", () => GameManager.Instance.ReloadCurrent()),
                    new Dialog.Choice("Menu", () => GameManager.Instance.LoadMenu()));
            else
                Dialog.Show("You rose above!", body + "\n\nYou have completed every level.",
                    new Dialog.Choice("Replay", () => GameManager.Instance.ReloadCurrent()),
                    new Dialog.Choice("Back to the park", () => GameManager.Instance.LoadMenu(), UIFactory.Calm * 0.8f));
        }

        public static string FormatTime(float seconds)
        {
            int s = Mathf.RoundToInt(seconds);
            return (s / 60) + ":" + (s % 60).ToString("00");
        }

        /// <summary>Player slipped (fell off, lost balance, glass broke). Gentle fade back to the checkpoint.</summary>
        public void Slip(string reason)
        {
            if (IsRespawning || finished) return;
            StartCoroutine(SlipRoutine(reason));
        }

        IEnumerator SlipRoutine(string reason)
        {
            IsRespawning = true;
            Slips++;
            SessionLogger.Log(SceneName, "slip", reason);
            ProceduralAudio.PlayWhoosh(0.6f);
            yield return ScreenFader.Instance.FadeOut(0.25f);
            CheckpointSystem.RespawnPlayer();
            BalanceBeam.ResetAll();
            yield return new WaitForSeconds(0.4f);
            yield return ScreenFader.Instance.FadeIn(0.8f);
            IsRespawning = false;
            Companion.SayRandom(Companion.SlipLines);
        }
    }
}