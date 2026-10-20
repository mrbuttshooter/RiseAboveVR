using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Per-level results stored in PlayerPrefs: best medal (0 none, 1 bronze, 2 silver, 3 gold), best time
    /// and best score.
    /// </summary>
    public static class ProgressStore
    {
        static string MedalKey(int level) => "rise_medal_" + level;
        static string TimeKey(int level) => "rise_besttime_" + level;
        static string ScoreKey(int level) => "rise_bestscore_" + level;

        public static int GetMedal(int level) => PlayerPrefs.GetInt(MedalKey(level), 0);
        public static float GetBestTime(int level) => PlayerPrefs.GetFloat(TimeKey(level), 0f);
        public static int GetBestScore(int level) => PlayerPrefs.GetInt(ScoreKey(level), 0);

        /// <summary>Stores a finished run; returns true when the score is a new personal best.</summary>
        public static bool RecordResult(int level, int medal, float seconds, int score)
        {
            if (medal > GetMedal(level)) PlayerPrefs.SetInt(MedalKey(level), medal);
            float best = GetBestTime(level);
            if (best <= 0f || seconds < best) PlayerPrefs.SetFloat(TimeKey(level), seconds);
            bool newBest = score > GetBestScore(level);
            if (newBest) PlayerPrefs.SetInt(ScoreKey(level), score);
            PlayerPrefs.Save();
            return newBest;
        }

        public static int TotalMedals()
        {
            int total = 0;
            for (int i = 0; i < GameManager.LevelScenes.Length; i++) total += GetMedal(i);
            return total;
        }

        public static string MedalName(int medal) => medal >= 3 ? "Gold" : medal == 2 ? "Silver" : medal == 1 ? "Bronze" : "No medal";

        public static Color MedalColor(int medal) =>
            medal >= 3 ? new Color(1f, 0.84f, 0.3f) : medal == 2 ? new Color(0.8f, 0.84f, 0.9f) : medal == 1 ? new Color(0.85f, 0.55f, 0.3f) : new Color(0.6f, 0.6f, 0.6f);

        public static void ResetAll()
        {
            for (int i = 0; i < GameManager.LevelScenes.Length; i++)
            {
                PlayerPrefs.DeleteKey(MedalKey(i));
                PlayerPrefs.DeleteKey(TimeKey(i));
                PlayerPrefs.DeleteKey(ScoreKey(i));
            }
            PlayerPrefs.Save();
        }
    }
}
