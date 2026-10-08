using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace AcrophobiaVR
{
    /// <summary>
    /// Persistent achievements (PlayerPrefs "acro_ach_" + id). Unlocking shows a gold head-locked toast,
    /// plays a fanfare, pulses the controllers and writes an "achievement" row to the session CSV.
    /// Several unlocks at once (e.g. at the end of a level) are queued so every toast is readable.
    /// </summary>
    public static class Achievements
    {
        public struct Def
        {
            public string id;
            public string title;
            public string description;

            public Def(string id, string title, string description)
            {
                this.id = id;
                this.title = title;
                this.description = description;
            }
        }

        const string KeyPrefix = "acro_ach_";
        const float ToastSeconds = 4f;
        const float ToastGap = 3.6f;

        public static readonly Def[] All =
        {
            new Def("first_look", "First Look Down", "Finish a look-down task"),
            new Def("glass_walker", "Glass Walker", "Reach the end of the glass skywalk"),
            new Def("panic_beaten", "Rode the Wave", "Beat a panic wave by looking up"),
            new Def("steady_feet", "Steady Feet", "Finish a level with no slips"),
            new Def("star_collector", "Star Collector", "Collect every courage star in a level"),
            new Def("all_stars", "Rise Above", "Earn all 9 stars"),
            new Def("sky_high", "Sky High", "Complete the skyscraper"),
            new Def("brave_soul", "Brave Soul", "Finish a level in Brave mode"),
            new Def("cat_rescuer", "Cat Rescuer", "Rescue Mittens"),
            new Def("calm_breather", "Calm Breather", "Complete a full breathing exercise"),
            new Def("photographer", "Photographer", "Take 5 brave photos"),
            new Def("elevator_100", "Cloud Walker", "Ride the Courage Elevator to 100 m"),
        };

        /// <summary>Raised after a new achievement is unlocked (argument: id).</summary>
        public static event Action<string> Unlocked;

        static readonly Queue<string> pendingToasts = new Queue<string>();
        static MonoBehaviour toastHost;
        static float lastToastAt = -100f;

        static string Key(string id) => KeyPrefix + id;

        // Resets statics when domain reload is disabled and resumes queued toasts after a scene load
        // (e.g. achievements earned at level end when the player presses "Next level" straight away).
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void Init()
        {
            pendingToasts.Clear();
            toastHost = null;
            lastToastAt = -100f;
            SceneManager.sceneLoaded -= OnSceneLoaded;
            SceneManager.sceneLoaded += OnSceneLoaded;
        }

        static void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            if (pendingToasts.Count == 0 || toastHost != null) return;
            // Short pause so the first resumed toast is not lost in the scene fade-in.
            lastToastAt = Mathf.Max(lastToastAt, Time.realtimeSinceStartup - ToastGap + 1.5f);
            EnsureToastPump();
        }

        public static bool IsUnlocked(string id)
        {
            if (string.IsNullOrEmpty(id)) return false;
            return PlayerPrefs.GetInt(Key(id), 0) == 1;
        }

        public static int UnlockedCount
        {
            get
            {
                int n = 0;
                for (int i = 0; i < All.Length; i++)
                    if (IsUnlocked(All[i].id)) n++;
                return n;
            }
        }

        /// <summary>Idempotent: unlocking an already unlocked achievement does nothing.</summary>
        public static void Unlock(string id)
        {
            if (string.IsNullOrEmpty(id) || IsUnlocked(id)) return;
            int index = IndexOf(id);
            if (index < 0)
            {
                Debug.LogWarning("[Achievements] Unknown achievement id: " + id);
                return;
            }

            PlayerPrefs.SetInt(Key(id), 1);
            PlayerPrefs.Save();
            SessionLogger.Log(SceneManager.GetActiveScene().name, "achievement", id);

            pendingToasts.Enqueue(All[index].title);
            EnsureToastPump();
            Unlocked?.Invoke(id);
        }

        public static void ResetAll()
        {
            for (int i = 0; i < All.Length; i++) PlayerPrefs.DeleteKey(Key(All[i].id));
            PlayerPrefs.Save();
            pendingToasts.Clear();
        }

        static int IndexOf(string id)
        {
            for (int i = 0; i < All.Length; i++)
                if (All[i].id == id) return i;
            return -1;
        }

        /// <summary>
        /// Runs the toast queue on the HeadHud (a scene object). If a scene load destroyed the previous
        /// host, the Unity null check fails and a new pump starts on the new scene's HeadHud.
        /// </summary>
        static void EnsureToastPump()
        {
            if (toastHost != null) return;
            if (!Application.isPlaying) { pendingToasts.Clear(); return; }
            var hud = HeadHud.Instance;
            if (hud == null || !hud.isActiveAndEnabled) return; // StartCoroutine would throw; retried on next unlock / scene load
            toastHost = hud;
            hud.StartCoroutine(PumpToasts());
        }

        static IEnumerator PumpToasts()
        {
            while (pendingToasts.Count > 0)
            {
                // Leave the previous toast on screen long enough to read before replacing it.
                float wait = Mathf.Min(ToastGap, lastToastAt + ToastGap - Time.realtimeSinceStartup);
                if (wait > 0f) yield return new WaitForSecondsRealtime(wait);
                if (pendingToasts.Count == 0) break;

                string title = pendingToasts.Dequeue();
                HeadHud.Instance.ShowMessage("<color=#FFD84D><b>Achievement unlocked</b></color>\n" + title, ToastSeconds);
                ProceduralAudio.PlayFanfare();
                Haptics.Medium();
                lastToastAt = Time.realtimeSinceStartup;
            }
            toastHost = null;
        }
    }
}
