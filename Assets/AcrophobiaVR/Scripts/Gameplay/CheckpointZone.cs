using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Saves progress when the player reaches it; optionally triggers a breathing break.</summary>
    public class CheckpointZone : HeadZone
    {
        public string label = "Checkpoint";
        public Transform respawnPoint;
        public bool offerBreathingBreak;
        [TextArea] public string companionLine;

        bool reached;

        protected override void OnHeadEnter()
        {
            if (reached) return;
            reached = true;
            CheckpointSystem.Set(respawnPoint != null ? respawnPoint : transform, label);
            SessionLogger.Log(UnityEngine.SceneManagement.SceneManager.GetActiveScene().name, "checkpoint", label);
            HeadHud.Instance.ShowMessage("Checkpoint reached: " + label, 2.5f);
            ProceduralAudio.PlayChime(1f);
            if (!string.IsNullOrEmpty(companionLine)) Companion.Say(companionLine);
            if (offerBreathingBreak && !BreathingGuide.Active)
                BreathingGuide.Show(2);
        }
    }
}