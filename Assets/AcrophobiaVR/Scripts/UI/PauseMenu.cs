using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;

namespace AcrophobiaVR
{
    /// <summary>
    /// Esc (keyboard), X or the Menu button (left controller) pauses the level: the world freezes and a panel
    /// offers Resume, Calm Meadow, Restart level and Main menu, with your lives, time and tasks.
    /// Inside the Calm Meadow the same button takes you back to your checkpoint.
    /// </summary>
    public class PauseMenu : MonoBehaviour
    {
        static PauseMenu instance;
        public static bool IsOpen => instance != null && instance.dialog != null;

        InputAction toggle;
        Dialog dialog;
        float savedTimeScale = 1f;

        void Awake()
        {
            instance = this;
            toggle = new InputAction("Pause", InputActionType.Button);
            toggle.AddBinding("<Keyboard>/escape");
            toggle.AddBinding("<XRController>{LeftHand}/primaryButton");
            toggle.AddBinding("<XRController>{LeftHand}/menuButton");
            toggle.performed += _ => Toggle();
        }

        void OnEnable() => toggle.Enable();

        void OnDisable()
        {
            toggle.Disable();
            if (Time.timeScale == 0f) Time.timeScale = 1f;
        }

        void OnDestroy()
        {
            toggle.Dispose();
            if (instance == this) instance = null;
        }

        public void Toggle()
        {
            if (dialog != null)
            {
                dialog.Close();
                Resume();
                return;
            }
            if (SafeRoom.InSafeRoom)
            {
                if (SafeRoom.Instance != null) SafeRoom.Instance.Toggle();
                return;
            }
            var lc = LevelController.Instance;
            // Ratings, the summary and the out-of-lives screen take priority over pausing.
            if (lc == null || lc.IsRespawning || Dialog.AnyOpen || RatingPanel.IsOpen) return;
            Open(lc);
        }

        void Open(LevelController lc)
        {
            savedTimeScale = Time.timeScale > 0f ? Time.timeScale : 1f;
            Time.timeScale = 0f;
            string body = lc.Started
                ? "Time " + LevelController.FormatTime(lc.ElapsedSeconds) + "     Tasks " + lc.TasksDone + " / " + lc.objectives.Length
                : "The level hasn't started yet.";
            body += "\nDifficulty: " + ExposureSettings.DisplayName(ExposureSettings.Mode);
            dialog = Dialog.Show("Paused", body,
                new Dialog.Choice("Resume", Resume, UIFactory.Calm * 0.8f),
                new Dialog.Choice("Calm Meadow", () =>
                {
                    Resume();
                    if (SafeRoom.Instance != null) SafeRoom.Instance.Toggle();
                }),
                new Dialog.Choice("Restart level", () =>
                {
                    Resume();
                    SessionLogger.Log(SceneManager.GetActiveScene().name, "level_restarted");
                    GameManager.Instance.ReloadCurrent();
                }),
                new Dialog.Choice("Main menu", () =>
                {
                    Resume();
                    SessionLogger.Log(SceneManager.GetActiveScene().name, "level_abandoned");
                    GameManager.Instance.LoadMenu();
                }));
            UIFactory.HeartRow(dialog.Content, lc.Lives, LevelController.MaxLives, new Vector2(0, 205), 58f);
        }

        void Resume()
        {
            dialog = null; // the dialog closes itself when one of its buttons is chosen
            Time.timeScale = savedTimeScale;
        }
    }
}
