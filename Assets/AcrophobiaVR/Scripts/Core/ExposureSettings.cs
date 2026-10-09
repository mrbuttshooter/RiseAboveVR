using System;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace AcrophobiaVR
{
    /// <summary>
    /// Graded-exposure intensity. Mirrors how a therapist would adjust exposure:
    /// Gentle adds safety glass, extra rails and fog that hides the drop; Brave removes helpers.
    /// </summary>
    public enum ExposureMode
    {
        Gentle = 0,
        Standard = 1,
        Brave = 2,
    }

    public static class ExposureSettings
    {
        const string Key = "acro_exposure_mode";

        public static event Action<ExposureMode> Changed;

        public static ExposureMode Mode
        {
            get => (ExposureMode)Mathf.Clamp(PlayerPrefs.GetInt(Key, (int)ExposureMode.Standard), 0, 2);
            set
            {
                if (value == Mode) return;
                PlayerPrefs.SetInt(Key, (int)value);
                PlayerPrefs.Save();
                SessionLogger.Log(SceneManager.GetActiveScene().name, "exposure_mode", value.ToString());
                Changed?.Invoke(value);
            }
        }

        /// <summary>Player-facing difficulty name (the enum keeps its original names for saves and logs).</summary>
        public static string DisplayName(ExposureMode mode)
        {
            switch (mode)
            {
                case ExposureMode.Gentle: return "Easy";
                case ExposureMode.Brave: return "Hard";
                default: return "Normal";
            }
        }

        public static string Describe(ExposureMode mode)
        {
            switch (mode)
            {
                case ExposureMode.Gentle: return "Easy: railings, safety glass and soft fog hide the drop.";
                case ExposureMode.Brave: return "Hard: no railings, narrower paths, crystal-clear air, stronger wind.";
                default: return "Normal: no railings - one wrong step and you fall. 3 lives.";
            }
        }

        const string TrackKey = "acro_track_anxiety";

        /// <summary>Optional "anxiety tracking" (0-10 rating before and after each level, for research/demo). Off by default.</summary>
        public static bool TrackAnxiety
        {
            get => PlayerPrefs.GetInt(TrackKey, 0) == 1;
            set
            {
                PlayerPrefs.SetInt(TrackKey, value ? 1 : 0);
                PlayerPrefs.Save();
            }
        }

        /// <summary>Fog density used to soften the view of the ground far below.</summary>
        public static float FogDensity(ExposureMode mode)
        {
            switch (mode)
            {
                case ExposureMode.Gentle: return 0.02f;
                case ExposureMode.Brave: return 0.0012f;
                default: return 0.004f;
            }
        }

        public static float WindMultiplier(ExposureMode mode)
        {
            switch (mode)
            {
                case ExposureMode.Gentle: return 0.5f;
                case ExposureMode.Brave: return 1.4f;
                default: return 1f;
            }
        }
    }
}
