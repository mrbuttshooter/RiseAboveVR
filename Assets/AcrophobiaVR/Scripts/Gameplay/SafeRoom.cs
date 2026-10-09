using System.Collections;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;

namespace AcrophobiaVR
{
    /// <summary>
    /// The Calm Meadow: a ground-level pocket world the player can escape to at any moment from the
    /// pause menu (Esc / left X). Pressing Esc / X again returns them to their checkpoint.
    /// Having a guaranteed escape is key to making exposure feel safe.
    /// </summary>
    public class SafeRoom : MonoBehaviour
    {
        public static bool InSafeRoom { get; private set; }
        public static SafeRoom Instance { get; private set; }

        public Transform spawnPoint;
        public Transform panelPoint;

        bool busy;
        float enteredAt;
        GameObject panel;

        void Awake()
        {
            Instance = this;
            InSafeRoom = false;
        }

        void Start()
        {
            if (panelPoint != null) BuildPanel();
            BreathingGuide.CreateStatic(transform, spawnPoint.localPosition + new Vector3(0f, 1.6f, 3f));
        }

        void BuildPanel()
        {
            var canvas = UIFactory.CreateWorldCanvas("MeadowPanel", new Vector2(900, 520), 0.0012f);
            canvas.transform.SetPositionAndRotation(panelPoint.position, panelPoint.rotation);
            panel = canvas.gameObject;
            var root = canvas.transform;
            UIFactory.FullPanel(root, new Color(0.08f, 0.16f, 0.12f, 0.85f));
            UIFactory.Label(root, "Calm Meadow", 60, new Vector2(0, 190), new Vector2(860, 80), TextAnchor.MiddleCenter, UIFactory.Calm, FontStyle.Bold);
            UIFactory.Label(root, "You are safe on solid ground.\nStay as long as you like. Breathe with the light.\nWhen you're ready, go back - you'll return to your last checkpoint.",
                32, new Vector2(0, 40), new Vector2(840, 180));
            UIFactory.Button(root, "I'm ready - go back", new Vector2(-200, -160), new Vector2(380, 100), UIFactory.Calm * 0.75f, Toggle, 32);
            UIFactory.Button(root, "Leave level", new Vector2(220, -160), new Vector2(300, 100), UIFactory.ButtonColor, () =>
            {
                SessionLogger.Log(SceneManager.GetActiveScene().name, "level_abandoned");
                GameManager.Instance.LoadMenu();
            }, 32);
        }

        public void Toggle()
        {
            if (busy || LevelController.Instance == null || LevelController.Instance.IsRespawning) return;
            StartCoroutine(InSafeRoom ? Leave() : Enter());
        }

        IEnumerator Enter()
        {
            busy = true;
            SessionLogger.Log(SceneManager.GetActiveScene().name, "calm_meadow_enter", CheckpointSystem.Label);
            yield return ScreenFader.Instance.FadeOut(0.5f);
            PlayerRig.Instance.TeleportTo(spawnPoint);
            InSafeRoom = true;
            enteredAt = Time.time;
            AmbientAudio.SetMeadow(true);
            yield return ScreenFader.Instance.FadeIn(1f);
            Companion.Say("You're safe here. Nothing to do but breathe. Come back whenever you're ready.", 6f);
            busy = false;
        }

        IEnumerator Leave()
        {
            busy = true;
            SessionLogger.Log(SceneManager.GetActiveScene().name, "calm_meadow_exit_seconds", Mathf.RoundToInt(Time.time - enteredAt).ToString());
            yield return ScreenFader.Instance.FadeOut(0.5f);
            CheckpointSystem.RespawnPlayer();
            InSafeRoom = false;
            AmbientAudio.SetMeadow(false);
            yield return ScreenFader.Instance.FadeIn(1f);
            Companion.SayRandom(Companion.ReturnLines);
            busy = false;
        }
    }
}