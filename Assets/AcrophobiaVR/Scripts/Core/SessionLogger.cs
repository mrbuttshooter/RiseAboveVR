using System;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Appends session events (anxiety ratings, completion times, safe-room use, slips) to a CSV file
    /// in Application.persistentDataPath so results can be analysed for the project report.
    /// Columns: session,timestamp,level,event,value
    /// </summary>
    public static class SessionLogger
    {
        public static readonly string SessionId = DateTime.Now.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture);

        public static string FilePath => Path.Combine(Application.persistentDataPath, "acrophobia_log.csv");

        public static void Log(string level, string evt, string value = "")
        {
            try
            {
                bool newFile = !File.Exists(FilePath);
                using (var w = new StreamWriter(FilePath, append: true))
                {
                    if (newFile) w.WriteLine("session,timestamp,level,event,value");
                    w.WriteLine(string.Join(",",
                        SessionId,
                        DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture),
                        Escape(level),
                        Escape(evt),
                        Escape(value)));
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[SessionLogger] Could not write log: {e.Message}");
            }
            Debug.Log($"[Session] {level} | {evt} | {value}");
        }

        static string Escape(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.IndexOfAny(new[] { ',', '"', '\n' }) >= 0 ? "\"" + s.Replace("\"", "\"\"") + "\"" : s;
        }
    }
}
