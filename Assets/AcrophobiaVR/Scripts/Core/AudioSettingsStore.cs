using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Persistent master volume (0..1) stored in PlayerPrefs and applied through AudioListener.volume.
    /// </summary>
    public static class AudioSettingsStore
    {
        const string Key = "acro_master_volume";
        const float DefaultVolume = 0.9f;

        static bool loaded;
        static float volume = DefaultVolume;

        public static float MasterVolume
        {
            get
            {
                Load();
                return volume;
            }
            set
            {
                float v = float.IsNaN(value) ? DefaultVolume : Mathf.Clamp01(value); // Clamp01 passes NaN through
                loaded = true;
                volume = v;
                PlayerPrefs.SetFloat(Key, v);
                PlayerPrefs.Save();
                AudioListener.volume = v;
            }
        }

        /// <summary>Applies the saved master volume to the AudioListener.</summary>
        public static void Apply()
        {
            Load();
            AudioListener.volume = volume;
        }

        static void Load()
        {
            if (loaded) return;
            loaded = true;
            float v = PlayerPrefs.GetFloat(Key, DefaultVolume);
            volume = float.IsNaN(v) ? DefaultVolume : Mathf.Clamp01(v);
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Init()
        {
            loaded = false; // re-read prefs (static state may survive when domain reload is disabled)
            Apply();
        }
    }
}
