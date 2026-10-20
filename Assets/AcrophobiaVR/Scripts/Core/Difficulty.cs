using System;
using UnityEngine;

namespace AcrophobiaVR
{
    public enum DifficultyLevel
    {
        Easy = 0,
        Normal = 1,
        Hard = 2,
    }

    /// <summary>
    /// How hard the runs are: lives, how much time you get, how fast hazards move and how strong the wind is.
    /// Easy also keeps a few railings and safety nets (see <see cref="DifficultyVisual"/>).
    /// </summary>
    public static class Difficulty
    {
        const string Key = "rise_difficulty";

        public static event Action<DifficultyLevel> Changed;

        public static DifficultyLevel Level
        {
            get => (DifficultyLevel)Mathf.Clamp(PlayerPrefs.GetInt(Key, (int)DifficultyLevel.Normal), 0, 2);
            set
            {
                if (value == Level) return;
                PlayerPrefs.SetInt(Key, (int)value);
                PlayerPrefs.Save();
                Changed?.Invoke(value);
            }
        }

        public static string DisplayName(DifficultyLevel level) => level.ToString();

        public static string Describe(DifficultyLevel level)
        {
            switch (level)
            {
                case DifficultyLevel.Easy: return "Easy: 5 lives, extra time, slower hazards, a few railings.";
                case DifficultyLevel.Hard: return "Hard: 2 lives, tight clock, fast hazards, brutal wind. No mercy.";
                default: return "Normal: 3 lives, a fair clock and no railings anywhere.";
            }
        }

        public static int Lives => Level == DifficultyLevel.Easy ? 5 : Level == DifficultyLevel.Hard ? 2 : 3;

        /// <summary>Multiplier on every time limit and medal time.</summary>
        public static float TimeFactor => Level == DifficultyLevel.Easy ? 1.5f : Level == DifficultyLevel.Hard ? 0.82f : 1f;

        /// <summary>Multiplier on the speed of moving / swinging / sweeping hazards.</summary>
        public static float HazardSpeed => Level == DifficultyLevel.Easy ? 0.75f : Level == DifficultyLevel.Hard ? 1.3f : 1f;

        public static float Wind => Level == DifficultyLevel.Easy ? 0.6f : Level == DifficultyLevel.Hard ? 1.4f : 1f;

        /// <summary>Score multiplier.</summary>
        public static float ScoreFactor => Level == DifficultyLevel.Easy ? 0.6f : Level == DifficultyLevel.Hard ? 1.6f : 1f;
    }
}
