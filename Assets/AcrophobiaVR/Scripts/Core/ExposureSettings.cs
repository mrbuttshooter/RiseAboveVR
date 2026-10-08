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

        public static string Describe(ExposureMode mode)
        {
            switch (mode)
            {
                case ExposureMode.Gentle: return "Gentle: safety glass, extra handrails and soft fog below.";
                case ExposureMode.Brave: return "Brave: no extra helpers, crystal-clear air, stronger wind.";
                default: return "Standard: normal railings and a clear view of the drop.";
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
