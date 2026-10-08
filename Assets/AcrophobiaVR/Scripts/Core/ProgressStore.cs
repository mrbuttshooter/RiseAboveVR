using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Per-level results stored in PlayerPrefs: best stars, best time and the history of
    /// before/after anxiety ratings (shown as a graph on the trophy wall).
    /// </summary>
    public static class ProgressStore
    {
        public struct RatingPair
        {
            public int Before;
            public int After;
        }

        const int MaxHistory = 8;

        static string StarsKey(int level) => "acro_stars_" + level;
        static string TimeKey(int level) => "acro_besttime_" + level;
        static string HistoryKey(int level) => "acro_history_" + level;

        public static int GetStars(int level) => PlayerPrefs.GetInt(StarsKey(level), 0);

        public static float GetBestTime(int level) => PlayerPrefs.GetFloat(TimeKey(level), 0f);

        public static void RecordResult(int level, int stars, float seconds, int before, int after)
        {
            if (stars > GetStars(level)) PlayerPrefs.SetInt(StarsKey(level), stars);
            float best = GetBestTime(level);
            if (best <= 0f || seconds < best) PlayerPrefs.SetFloat(TimeKey(level), seconds);

            var history = GetHistory(level);
            history.Add(new RatingPair { Before = before, After = after });
            while (history.Count > MaxHistory) history.RemoveAt(0);
            var parts = new List<string>();
            foreach (var h in history) parts.Add(h.Before + ":" + h.After);
            PlayerPrefs.SetString(HistoryKey(level), string.Join(";", parts));
            PlayerPrefs.Save();
        }

        public static List<RatingPair> GetHistory(int level)
        {
            var list = new List<RatingPair>();
            string raw = PlayerPrefs.GetString(HistoryKey(level), "");
            if (string.IsNullOrEmpty(raw)) return list;
            foreach (var entry in raw.Split(';'))
            {
                var p = entry.Split(':');
                if (p.Length == 2 &&
                    int.TryParse(p[0], NumberStyles.Integer, CultureInfo.InvariantCulture, out int b) &&
                    int.TryParse(p[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out int a))
                    list.Add(new RatingPair { Before = b, After = a });
            }
            return list;
        }

        public static int TotalStars()
        {
            int total = 0;
            for (int i = 0; i < GameManager.LevelScenes.Length; i++) total += GetStars(i);
            return total;
        }

        public static void ResetAll()
        {
            for (int i = 0; i < GameManager.LevelScenes.Length; i++)
            {
                PlayerPrefs.DeleteKey(StarsKey(i));
                PlayerPrefs.DeleteKey(TimeKey(i));
                PlayerPrefs.DeleteKey(HistoryKey(i));
            }
            PlayerPrefs.Save();
        }
    }
}
