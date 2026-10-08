using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// "My Progress" panel opened from the main menu. Reads the session CSV written by SessionLogger,
    /// groups it per session (anxiety before/after per level, peak simulated BPM, panic waves beaten,
    /// slips, Calm Meadow visits, Courage Elevator height, brave photos, achievements) and shows the
    /// last sessions, the achievement grid and totals. "Export report" writes a self-contained HTML
    /// report (inline CSS, no external files) to persistentDataPath for the project write-up.
    /// Everything is computed once when the panel opens - nothing runs per frame.
    /// </summary>
    public class ProgressReport : MonoBehaviour
    {
        /// <summary>Results of one level inside one session (several attempts are merged).</summary>
        public class LevelStats
        {
            public int Level;
            public int Attempts;
            public bool Completed;
            public float BestSeconds;
            public int PeakBpm;
            public int PanicsBeaten;
            public int Slips;
            public int CalmVisits;
            public readonly List<int> Before = new List<int>();
            public readonly List<int> After = new List<int>();

            public bool HasRatings => Before.Count > 0 || After.Count > 0;
        }

        /// <summary>Everything logged under one SessionLogger.SessionId (one app run).</summary>
        public class SessionStats
        {
            public string Id;
            public DateTime Start;
            public bool HasStart;
            public readonly LevelStats[] Levels = new LevelStats[GameManager.LevelScenes.Length];
            public int PeakBpm;
            public int PanicsBeaten;
            public int Slips;
            public int CalmVisits;
            public float ElevatorMax;
            public int Photos;
            public int BravePhotos;
            public readonly List<string> AchievementIds = new List<string>();

            public bool PlayedAnyLevel
            {
                get
                {
                    for (int i = 0; i < Levels.Length; i++)
                        if (Levels[i] != null) return true;
                    return false;
                }
            }

            public bool HasActivity => PlayedAnyLevel || ElevatorMax > 0f || Photos > 0 || AchievementIds.Count > 0;

            public LevelStats GetLevel(int index)
            {
                if (Levels[index] == null) Levels[index] = new LevelStats { Level = index };
                return Levels[index];
            }
        }

        public const string ReportFileName = "RiseAbove_Report.html";
        public static string ReportPath => Path.Combine(Application.persistentDataPath, ReportFileName);

        public static ProgressReport Current { get; private set; }
        public static bool IsOpen => Current != null;

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        static readonly Color Dim = new Color(1f, 1f, 1f, 0.8f);

        // Session table columns (canvas px): Date | Levels | Anxiety | Peak BPM | Panic waves | Slips
        static readonly float[] ColX = { -585f, -380f, -80f, 225f, 450f, 640f };
        static readonly float[] ColW = { 230f, 180f, 420f, 190f, 260f, 120f };

        // ------------------------------------------------------------------ panel

        /// <summary>Opens (or re-opens, refreshed and in front of the player) the progress panel.</summary>
        public static void Show()
        {
            if (Current != null)
            {
                Destroy(Current.gameObject);
                Current = null;
            }
            var go = new GameObject("ProgressReport");
            Current = go.AddComponent<ProgressReport>();
            Current.Build();
        }

        /// <summary>Closes the panel if it is open.</summary>
        public static void Close()
        {
            if (Current == null) return;
            Destroy(Current.gameObject);
            Current = null;
        }

        void OnDestroy()
        {
            if (Current == this) Current = null;
        }

        void Build()
        {
            var sessions = LoadSessions();

            var canvas = UIFactory.CreateWorldCanvas("Canvas", new Vector2(1500, 1050), 0.0015f, transform);
            canvas.sortingOrder = 20; // draws and receives mouse clicks above the main menu behind it
            var root = canvas.transform;
            UIFactory.FullPanel(root, new Color(0.06f, 0.1f, 0.16f, 0.97f));
            UIFactory.Panel(root, UIFactory.Accent, new Vector2(0, 515), new Vector2(1440, 8));
            UIFactory.Label(root, "MY PROGRESS", 80, new Vector2(0, 455), new Vector2(1400, 100), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);

            BuildSessionTable(root, sessions);
            BuildAchievements(root);
            BuildSummary(root);

            UIFactory.Button(root, "Export report", new Vector2(-210, -450), new Vector2(400, 86), UIFactory.Calm * 0.8f, OnExport, 38);
            UIFactory.Button(root, "Close", new Vector2(210, -450), new Vector2(300, 86), new Color(0.32f, 0.32f, 0.38f), Close, 38);

            Place();
            ProceduralAudio.PlayChime(1.2f);
        }

        void Place()
        {
            var rig = PlayerRig.Instance;
            if (rig != null)
            {
                rig.PlaceInFront(transform, 2.0f, 0f);
                return;
            }
            var cam = Camera.main;
            if (cam != null)
            {
                Vector3 fwd = Vector3.ProjectOnPlane(cam.transform.forward, Vector3.up);
                if (fwd.sqrMagnitude < 0.001f) fwd = Vector3.forward;
                fwd.Normalize();
                transform.SetPositionAndRotation(cam.transform.position + fwd * 2.0f, Quaternion.LookRotation(fwd));
            }
            else
            {
                transform.SetPositionAndRotation(new Vector3(0f, 1.6f, 2.0f), Quaternion.identity);
            }
        }

        void BuildSessionTable(Transform root, List<SessionStats> sessions)
        {
            UIFactory.Label(root, "Recent sessions", 40, new Vector2(-350, 392), new Vector2(700, 56), TextAnchor.MiddleLeft, UIFactory.Accent, FontStyle.Bold);
            UIFactory.Label(root, "Levels: <color=#73D999>green</color> = completed     Anxiety: 0 calm, 10 panic", 24,
                new Vector2(350, 392), new Vector2(700, 50), TextAnchor.MiddleRight, Dim);

            string[] headers = { "Date", "Levels", "Anxiety before to after", "Peak BPM", "Panic waves beaten", "Slips" };
            UIFactory.Panel(root, new Color(1f, 1f, 1f, 0.08f), new Vector2(0, 337), new Vector2(1420, 58), false);
            for (int c = 0; c < headers.Length; c++)
                UIFactory.Label(root, headers[c], 24, new Vector2(ColX[c], 337), new Vector2(ColW[c] - 10f, 56), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);

            var active = new List<SessionStats>();
            foreach (var s in sessions)
                if (s.HasActivity) active.Add(s);

            if (active.Count == 0)
            {
                UIFactory.Label(root, "No sessions recorded yet.\nPlay a level and your journey will appear here.", 34,
                    new Vector2(0, 170), new Vector2(1300, 140), TextAnchor.MiddleCenter, Dim);
                return;
            }

            int rows = Mathf.Min(6, active.Count);
            for (int r = 0; r < rows; r++)
            {
                var s = active[active.Count - 1 - r]; // newest first
                float y = 283f - r * 48f;
                if (r % 2 == 1) UIFactory.Panel(root, new Color(1f, 1f, 1f, 0.04f), new Vector2(0, y), new Vector2(1420, 48), false);

                Cell(root, 0, y, FormatDate(s), Color.white);
                Cell(root, 1, y, LevelsCell(s), Color.white);
                Cell(root, 2, y, AnxietyCell(s), Color.white);
                Cell(root, 3, y, s.PeakBpm > 0 ? s.PeakBpm.ToString(Inv) : "-", s.PeakBpm >= 120 ? UIFactory.Warn : Color.white);
                Cell(root, 4, y, s.PlayedAnyLevel ? s.PanicsBeaten.ToString(Inv) : "-", s.PanicsBeaten > 0 ? UIFactory.Calm : Color.white);
                Cell(root, 5, y, s.PlayedAnyLevel ? s.Slips.ToString(Inv) : "-", Color.white);
            }

            if (active.Count > rows)
                UIFactory.Label(root, "+ " + (active.Count - rows) + " older sessions in the exported report", 22,
                    new Vector2(350, 4), new Vector2(700, 26), TextAnchor.MiddleRight, new Color(1f, 1f, 1f, 0.5f));
        }

        static void Cell(Transform root, int col, float y, string text, Color color)
        {
            var t = UIFactory.Label(root, text, 28, new Vector2(ColX[col], y), new Vector2(ColW[col] - 12f, 46), TextAnchor.MiddleCenter, color);
            t.textWrappingMode = TMPro.TextWrappingModes.NoWrap;
            t.enableAutoSizing = true;
            t.fontSizeMin = 16f;
            t.fontSizeMax = 28f;
        }

        void BuildAchievements(Transform root)
        {
            var all = Achievements.All ?? new Achievements.Def[0];
            int unlocked = 0;
            for (int i = 0; i < all.Length; i++)
                if (Achievements.IsUnlocked(all[i].id)) unlocked++;

            UIFactory.Label(root, "Achievements", 40, new Vector2(-350, -40), new Vector2(700, 56), TextAnchor.MiddleLeft, UIFactory.Accent, FontStyle.Bold);
            UIFactory.Label(root, unlocked + " / " + all.Length + " unlocked", 34, new Vector2(350, -40), new Vector2(700, 56), TextAnchor.MiddleRight, UIFactory.Gold, FontStyle.Bold);

            const int perRow = 6;
            const float stepX = 236f, stepY = 118f;
            var darkInk = new Color(0.16f, 0.11f, 0.02f);
            for (int i = 0; i < all.Length; i++)
            {
                var def = all[i];
                bool on = Achievements.IsUnlocked(def.id);
                int col = i % perRow, row = i / perRow;
                var tile = UIFactory.Panel(root, on ? UIFactory.Gold : new Color(1f, 1f, 1f, 0.06f),
                    new Vector2((col - (perRow - 1) * 0.5f) * stepX, -125f - row * stepY), new Vector2(224, 106));
                tile.raycastTarget = false;
                var t = tile.transform;

                var title = UIFactory.Label(t, def.title ?? def.id, 26, new Vector2(0, 22), new Vector2(208, 54), TextAnchor.MiddleCenter,
                    on ? darkInk : new Color(1f, 1f, 1f, 0.45f), FontStyle.Bold);
                title.enableAutoSizing = true;
                title.fontSizeMin = 16f;
                title.fontSizeMax = 26f;

                var desc = UIFactory.Label(t, def.description ?? "", 19, new Vector2(0, -26), new Vector2(208, 48), TextAnchor.MiddleCenter,
                    on ? new Color(darkInk.r, darkInk.g, darkInk.b, 0.85f) : new Color(1f, 1f, 1f, 0.3f));
                desc.enableAutoSizing = true;
                desc.fontSizeMin = 13f;
                desc.fontSizeMax = 19f;
            }
        }

        void BuildSummary(Transform root)
        {
            float best = CourageElevator.BestHeight;
            string text =
                "Stars <color=#FFD84D><b>" + ProgressStore.TotalStars() + " / " + (GameManager.LevelScenes.Length * 3) + "</b></color>" +
                "      Courage Elevator best <color=#FFD84D><b>" + (best > 0f ? best.ToString("0", Inv) + " m" : "not tried") + "</b></color>" +
                "      Brave photos <color=#FFD84D><b>" + PhotoCamera.BravePhotoCount + "</b></color>";
            UIFactory.Label(root, text, 34, new Vector2(0, -350), new Vector2(1440, 60), TextAnchor.MiddleCenter, Color.white);
        }

        void OnExport()
        {
            string path = Export();
            if (path == null)
            {
                HeadHud.Instance.ShowMessage("Could not save the report.", 4f);
                return;
            }
            ProceduralAudio.PlaySuccess();
            HeadHud.Instance.ShowMessage("Report saved:\n" + path, 5f);
#if UNITY_EDITOR || UNITY_STANDALONE_WIN
            Application.OpenURL("file:///" + path.Replace('\\', '/').Replace(" ", "%20"));
#endif
        }

        static string FormatDate(SessionStats s) => s.HasStart ? s.Start.ToString("dd MMM HH:mm", Inv) : s.Id;

        static string LevelsCell(SessionStats s)
        {
            var sb = new StringBuilder();
            for (int i = 0; i < s.Levels.Length; i++)
            {
                var l = s.Levels[i];
                if (l == null) continue;
                if (sb.Length > 0) sb.Append("  ");
                sb.Append(l.Completed ? "<color=#73D999>" : "<color=#FFFFFFA0>").Append(i + 1).Append("</color>");
            }
            return sb.Length > 0 ? sb.ToString() : "<color=#FFFFFFA0>Park</color>";
        }

        static string AnxietyCell(SessionStats s)
        {
            var sb = new StringBuilder();
            for (int i = 0; i < s.Levels.Length; i++)
            {
                var l = s.Levels[i];
                if (l == null || !l.HasRatings) continue;
                if (sb.Length > 0) sb.Append(" / ");
                sb.Append(FormatAvg(l.Before)).Append(" to ").Append(FormatAvg(l.After));
            }
            return sb.Length > 0 ? sb.ToString() : "-";
        }

        static string FormatAvg(List<int> values)
        {
            if (values == null || values.Count == 0) return "-";
            return Average(values).ToString("0.#", Inv);
        }

        static float Average(List<int> values)
        {
            if (values == null || values.Count == 0) return 0f;
            float sum = 0f;
            for (int i = 0; i < values.Count; i++) sum += values[i];
            return sum / values.Count;
        }

        // ------------------------------------------------------------------ CSV

        /// <summary>Parses SessionLogger's CSV into per-session statistics, oldest session first.
        /// Returns an empty list when the log does not exist or cannot be read.</summary>
        public static List<SessionStats> LoadSessions()
        {
            var list = new List<SessionStats>();
            string text;
            try
            {
                string path = SessionLogger.FilePath;
                if (!File.Exists(path)) return list;
                // ReadWrite share: SessionLogger may append while we read.
                using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                using (var reader = new StreamReader(fs, Encoding.UTF8, true))
                    text = reader.ReadToEnd();
            }
            catch (Exception e)
            {
                Debug.LogWarning("[ProgressReport] Could not read session log: " + e.Message);
                return list;
            }
            if (string.IsNullOrEmpty(text)) return list;

            var byId = new Dictionary<string, SessionStats>();
            foreach (var row in ParseCsv(text))
            {
                if (row.Length < 4) continue;
                string id = row[0].Trim();
                if (id.Length == 0 || id == "session") continue; // blank line or header
                if (!byId.TryGetValue(id, out var s))
                {
                    s = new SessionStats { Id = id };
                    if (DateTime.TryParseExact(id, "yyyyMMdd_HHmmss", Inv, DateTimeStyles.None, out var fromId))
                    {
                        s.Start = fromId;
                        s.HasStart = true;
                    }
                    byId[id] = s;
                    list.Add(s);
                }
                if (DateTime.TryParseExact(row[1].Trim(), "yyyy-MM-ddTHH:mm:ss", Inv, DateTimeStyles.None, out var t) &&
                    (!s.HasStart || t < s.Start))
                {
                    s.Start = t;
                    s.HasStart = true;
                }
                try
                {
                    Apply(s, row[2].Trim(), row[3].Trim(), row.Length > 4 ? row[4].Trim() : "");
                }
                catch (Exception e)
                {
                    Debug.LogWarning("[ProgressReport] Skipped malformed row: " + e.Message);
                }
            }
            return list;
        }

        static void Apply(SessionStats s, string scene, string evt, string value)
        {
            int li = Array.IndexOf(GameManager.LevelScenes, scene);
            LevelStats l = null;
            switch (evt)
            {
                case "level_loaded":
                    if (li >= 0) s.GetLevel(li).Attempts++;
                    break;
                case "anxiety_before":
                    if (li >= 0 && TryInt(value, out int before)) s.GetLevel(li).Before.Add(Mathf.Clamp(before, 0, 10));
                    break;
                case "anxiety_after":
                    if (li >= 0 && TryInt(value, out int after)) s.GetLevel(li).After.Add(Mathf.Clamp(after, 0, 10));
                    break;
                case "level_complete_seconds":
                    if (li >= 0)
                    {
                        l = s.GetLevel(li);
                        l.Completed = true;
                        if (TryFloat(value, out float sec) && sec > 0f && (l.BestSeconds <= 0f || sec < l.BestSeconds)) l.BestSeconds = sec;
                    }
                    break;
                case "peak_bpm":
                    if (TryInt(value, out int bpm))
                    {
                        s.PeakBpm = Mathf.Max(s.PeakBpm, bpm);
                        if (li >= 0) { l = s.GetLevel(li); l.PeakBpm = Mathf.Max(l.PeakBpm, bpm); }
                    }
                    break;
                case "panics_beaten":
                    if (TryInt(value, out int beaten) && beaten > 0)
                    {
                        s.PanicsBeaten += beaten;
                        if (li >= 0) s.GetLevel(li).PanicsBeaten += beaten;
                    }
                    break;
                case "slip":
                    s.Slips++;
                    if (li >= 0) s.GetLevel(li).Slips++;
                    break;
                case "calm_meadow_enter":
                    s.CalmVisits++;
                    if (li >= 0) s.GetLevel(li).CalmVisits++;
                    break;
                case "elevator_max":
                    if (TryFloat(value, out float h)) s.ElevatorMax = Mathf.Max(s.ElevatorMax, h);
                    break;
                case "photo":
                    s.Photos++;
                    if (value.IndexOf("brave", StringComparison.OrdinalIgnoreCase) >= 0) s.BravePhotos++;
                    break;
                case "achievement":
                    if (value.Length > 0 && !s.AchievementIds.Contains(value)) s.AchievementIds.Add(value);
                    break;
            }
        }

        /// <summary>RFC-4180 style parser: commas, doubled quotes and line breaks inside quoted fields.</summary>
        static List<string[]> ParseCsv(string text)
        {
            var rows = new List<string[]>();
            var fields = new List<string>();
            var sb = new StringBuilder();
            bool inQuotes = false;
            for (int i = 0; i < text.Length; i++)
            {
                char c = text[i];
                if (inQuotes)
                {
                    if (c == '"')
                    {
                        if (i + 1 < text.Length && text[i + 1] == '"') { sb.Append('"'); i++; }
                        else inQuotes = false;
                    }
                    else if (c != '\r') sb.Append(c);
                }
                else if (c == '"') inQuotes = true;
                else if (c == ',') { fields.Add(sb.ToString()); sb.Length = 0; }
                else if (c == '\n')
                {
                    fields.Add(sb.ToString());
                    sb.Length = 0;
                    rows.Add(fields.ToArray());
                    fields.Clear();
                }
                else if (c != '\r' && c != (char)0xFEFF) sb.Append(c);
            }
            if (sb.Length > 0 || fields.Count > 0)
            {
                fields.Add(sb.ToString());
                rows.Add(fields.ToArray());
            }
            return rows;
        }

        static bool TryInt(string s, out int value)
        {
            if (int.TryParse(s, NumberStyles.Integer, Inv, out value)) return true;
            if (TryFloat(s, out float f)) { value = Mathf.RoundToInt(f); return true; }
            value = 0;
            return false;
        }

        /// <summary>Parses a leading number, tolerating units such as "37.5m".</summary>
        static bool TryFloat(string s, out float value)
        {
            value = 0f;
            if (string.IsNullOrEmpty(s)) return false;
            int end = 0;
            while (end < s.Length && (char.IsDigit(s[end]) || s[end] == '.' || s[end] == '-' || s[end] == '+')) end++;
            return end > 0 && float.TryParse(s.Substring(0, end), NumberStyles.Float, Inv, out value);
        }

        // ------------------------------------------------------------------ HTML export

        /// <summary>Writes the HTML report and returns its full path, or null on failure.</summary>
        public static string Export()
        {
            string path = ReportPath;
            try
            {
                File.WriteAllText(path, BuildHtml(LoadSessions()), new UTF8Encoding(false));
                SessionLogger.Log(GameManager.MenuScene, "report_exported", ReportFileName);
                return path;
            }
            catch (Exception e)
            {
                Debug.LogWarning("[ProgressReport] Export failed: " + e.Message);
                return null;
            }
        }

        static string BuildHtml(List<SessionStats> sessions)
        {
            var active = new List<SessionStats>();
            foreach (var s in sessions)
                if (s.HasActivity) active.Add(s);

            var all = Achievements.All ?? new Achievements.Def[0];
            int unlocked = 0;
            for (int i = 0; i < all.Length; i++)
                if (Achievements.IsUnlocked(all[i].id)) unlocked++;

            int totalPanics = 0, totalCalm = 0, totalSlips = 0, levelsCompleted = 0;
            foreach (var s in active)
            {
                totalPanics += s.PanicsBeaten;
                totalCalm += s.CalmVisits;
                totalSlips += s.Slips;
            }
            for (int i = 0; i < GameManager.LevelScenes.Length; i++)
                if (GameManager.Instance != null ? GameManager.Instance.IsCompleted(i) : ProgressStore.GetStars(i) > 0) levelsCompleted++;
            float elevator = CourageElevator.BestHeight;

            var h = new StringBuilder(16384);
            h.Append("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n");
            h.Append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n");
            h.Append("<title>Rise Above - Progress Report</title>\n<style>\n");
            h.Append(":root{--ink:#1d2733;--muted:#5d6b7a;--line:#dfe5ec;--accent:#2a8fd0;--before:#e8813f;--after:#3aa866;--gold:#d9a722}\n");
            h.Append("*{box-sizing:border-box}\n");
            h.Append("body{margin:0;background:#f4f7fa;color:var(--ink);font:15px/1.5 'Segoe UI',Roboto,Helvetica,Arial,sans-serif}\n");
            h.Append("main{max-width:1040px;margin:0 auto;padding:32px 20px 48px}\n");
            h.Append("header{border-bottom:4px solid var(--accent);margin-bottom:20px;padding-bottom:12px}\n");
            h.Append("h1{margin:0;font-size:30px}h2{font-size:20px;margin:32px 0 12px;color:var(--accent)}h3{margin:0 0 8px;font-size:16px}\n");
            h.Append(".sub{color:var(--muted);margin:4px 0 0}\n");
            h.Append(".cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}\n");
            h.Append(".card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px}\n");
            h.Append(".card b{display:block;font-size:24px}.card span{color:var(--muted);font-size:13px}\n");
            h.Append(".level{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px}\n");
            h.Append(".row{display:grid;grid-template-columns:130px 1fr 1fr;gap:10px;align-items:center;margin:4px 0;font-size:13px}\n");
            h.Append(".track{background:#eef2f6;border-radius:4px;height:20px}\n");
            h.Append(".bar{height:20px;border-radius:4px;color:#fff;font-size:12px;font-weight:600;line-height:20px;padding:0 6px;min-width:24px;text-align:right}\n");
            h.Append(".b{background:var(--before)}.a{background:var(--after)}\n");
            h.Append(".legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin:0 4px -1px 14px}\n");
            h.Append(".avg{margin-top:8px;color:var(--muted);font-size:13px}.good{color:var(--after);font-weight:600}\n");
            h.Append(".scroll{overflow-x:auto}\n");
            h.Append("table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);font-size:13px}\n");
            h.Append("th,td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:#eaf1f7;font-weight:600}\n");
            h.Append(".ach{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}\n");
            h.Append(".ach div{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px;color:var(--muted)}\n");
            h.Append(".ach .on{background:#fff6dc;border-color:var(--gold);color:var(--ink)}.ach b{display:block}\n");
            h.Append(".note{background:#fff;border-left:4px solid var(--accent);padding:12px 16px;border-radius:6px}\n");
            h.Append("footer{margin-top:32px;color:var(--muted);font-size:12px;word-break:break-all}\n");
            h.Append("@media print{body{background:#fff}.card,.level,table{break-inside:avoid}}\n");
            h.Append("</style>\n</head>\n<body>\n<main>\n");

            h.Append("<header><h1>Rise Above - Progress Report</h1><p class=\"sub\">VR graded exposure for the fear of heights. Generated ")
             .Append(Esc(DateTime.Now.ToString("dd MMM yyyy HH:mm", Inv))).Append("</p></header>\n");

            // Totals
            h.Append("<section class=\"cards\">\n");
            Card(h, ProgressStore.TotalStars() + " / " + (GameManager.LevelScenes.Length * 3), "Stars earned");
            Card(h, levelsCompleted + " / " + GameManager.LevelScenes.Length, "Levels completed");
            Card(h, active.Count.ToString(Inv), "Play sessions");
            Card(h, unlocked + " / " + all.Length, "Achievements");
            Card(h, elevator > 0f ? elevator.ToString("0", Inv) + " m" : "-", "Courage Elevator best");
            Card(h, PhotoCamera.BravePhotoCount.ToString(Inv), "Brave photos");
            Card(h, totalPanics.ToString(Inv), "Panic waves beaten");
            Card(h, totalCalm.ToString(Inv), "Calm Meadow visits");
            Card(h, totalSlips.ToString(Inv), "Slips");
            h.Append("</section>\n");

            // Per-level anxiety chart
            h.Append("<h2>Anxiety before and after each level</h2>\n");
            h.Append("<p class=\"legend\">SUDS rating, 0 = calm, 10 = panic.<i style=\"background:var(--before)\"></i>Before the level<i style=\"background:var(--after)\"></i>After the level</p>\n");
            for (int li = 0; li < GameManager.LevelScenes.Length; li++)
            {
                h.Append("<div class=\"level\"><h3>").Append(Esc(GameManager.LevelTitles[li])).Append("</h3>\n");
                var before = new List<int>();
                var after = new List<int>();
                int start = 0, shown = 0, rated = 0;
                foreach (var s in active)
                    if (s.Levels[li] != null && s.Levels[li].HasRatings) rated++;
                start = Mathf.Max(0, rated - 12); // last 12 sessions per level
                int idx = 0;
                foreach (var s in active)
                {
                    var l = s.Levels[li];
                    if (l == null || !l.HasRatings) continue;
                    before.AddRange(l.Before);
                    after.AddRange(l.After);
                    if (idx++ < start) continue;
                    shown++;
                    h.Append("<div class=\"row\"><span>").Append(Esc(FormatDate(s))).Append("</span>");
                    BarHtml(h, l.Before, "b");
                    BarHtml(h, l.After, "a");
                    h.Append("</div>\n");
                }
                if (shown == 0)
                {
                    h.Append("<p class=\"avg\">No ratings recorded yet.</p></div>\n");
                    continue;
                }
                h.Append("<p class=\"avg\">Average ").Append(FormatAvg(before)).Append(" to ").Append(FormatAvg(after));
                if (before.Count > 0 && after.Count > 0)
                {
                    float change = Average(after) - Average(before);
                    h.Append(change < 0f ? " <span class=\"good\">(" : " (")
                     .Append(change.ToString("+0.0;-0.0;0.0", Inv)).Append(" points)").Append(change < 0f ? "</span>" : "");
                }
                h.Append("</p></div>\n");
            }

            // Session table
            h.Append("<h2>Sessions</h2>\n");
            if (active.Count == 0)
            {
                h.Append("<p>No sessions recorded yet.</p>\n");
            }
            else
            {
                h.Append("<div class=\"scroll\"><table>\n<tr><th>Date</th><th>Levels played</th><th>Anxiety before to after</th><th>Best time</th>")
                 .Append("<th>Peak BPM</th><th>Panic waves beaten</th><th>Slips</th><th>Calm Meadow visits</th><th>Elevator max</th><th>Brave photos</th><th>Achievements</th></tr>\n");
                for (int i = active.Count - 1; i >= 0; i--)
                {
                    var s = active[i];
                    var levels = new StringBuilder();
                    var anxiety = new StringBuilder();
                    var times = new StringBuilder();
                    for (int li = 0; li < s.Levels.Length; li++)
                    {
                        var l = s.Levels[li];
                        if (l == null) continue;
                        if (levels.Length > 0) levels.Append("<br>");
                        levels.Append("Level ").Append(li + 1).Append(l.Completed ? " (completed)" : " (not finished)");
                        if (l.HasRatings)
                        {
                            if (anxiety.Length > 0) anxiety.Append("<br>");
                            anxiety.Append("L").Append(li + 1).Append(": ").Append(FormatAvg(l.Before)).Append(" to ").Append(FormatAvg(l.After));
                        }
                        if (l.BestSeconds > 0f)
                        {
                            if (times.Length > 0) times.Append("<br>");
                            times.Append("L").Append(li + 1).Append(": ").Append(Esc(LevelController.FormatTime(l.BestSeconds)));
                        }
                    }
                    var ach = new StringBuilder();
                    foreach (var id in s.AchievementIds)
                    {
                        if (ach.Length > 0) ach.Append(", ");
                        ach.Append(Esc(AchievementTitle(all, id)));
                    }
                    h.Append("<tr><td>").Append(Esc(s.HasStart ? s.Start.ToString("dd MMM yyyy HH:mm", Inv) : s.Id)).Append("</td>")
                     .Append("<td>").Append(levels.Length > 0 ? levels.ToString() : "Park only").Append("</td>")
                     .Append("<td>").Append(anxiety.Length > 0 ? anxiety.ToString() : "-").Append("</td>")
                     .Append("<td>").Append(times.Length > 0 ? times.ToString() : "-").Append("</td>")
                     .Append("<td>").Append(s.PeakBpm > 0 ? s.PeakBpm.ToString(Inv) : "-").Append("</td>")
                     .Append("<td>").Append(s.PanicsBeaten.ToString(Inv)).Append("</td>")
                     .Append("<td>").Append(s.Slips.ToString(Inv)).Append("</td>")
                     .Append("<td>").Append(s.CalmVisits.ToString(Inv)).Append("</td>")
                     .Append("<td>").Append(s.ElevatorMax > 0f ? s.ElevatorMax.ToString("0", Inv) + " m" : "-").Append("</td>")
                     .Append("<td>").Append(s.BravePhotos.ToString(Inv)).Append("</td>")
                     .Append("<td>").Append(ach.Length > 0 ? ach.ToString() : "-").Append("</td></tr>\n");
                }
                h.Append("</table></div>\n");
            }

            // Achievements
            h.Append("<h2>Achievements (").Append(unlocked).Append(" / ").Append(all.Length).Append(" unlocked)</h2>\n<div class=\"ach\">\n");
            for (int i = 0; i < all.Length; i++)
            {
                bool on = Achievements.IsUnlocked(all[i].id);
                h.Append(on ? "<div class=\"on\">" : "<div>")
                 .Append("<b>").Append(Esc(all[i].title ?? all[i].id)).Append(on ? " - unlocked" : " - locked").Append("</b>")
                 .Append(Esc(all[i].description ?? "")).Append("</div>\n");
            }
            h.Append("</div>\n");

            // Methodology
            h.Append("<h2>Methodology</h2>\n<div class=\"note\">\n");
            h.Append("<p><b>Graded exposure.</b> Rise Above follows the principles of graded exposure therapy: the player climbs through three levels of ")
             .Append("increasing height (a 6 m balcony, a 25 m construction site and a 150 m skyscraper beam). Each level unlocks only after the previous one ")
             .Append("is completed, and an exposure mode (Gentle, Standard or Brave) adjusts the intensity. The Calm Meadow is a safe space that can be ")
             .Append("entered at any time; visits are counted as a coping strategy, not as a failure.</p>\n");
            h.Append("<p><b>Self-reported anxiety (SUDS 0-10).</b> Before and after every level the player rates their anxiety on a Subjective Units of ")
             .Append("Distress scale from 0 (completely calm) to 10 (extreme panic). A lower rating after a level suggests within-session habituation; ")
             .Append("lower before-ratings over repeated sessions suggest between-session habituation.</p>\n");
            h.Append("<p><b>Heart rate is simulated.</b> The BPM values and panic waves come from the in-game fear model (exposure to the drop and looking down), ")
             .Append("not from a physiological sensor. They describe in-game events and are indicative only.</p>\n");
            h.Append("<p>This report was produced by a final-year university project prototype. It is not a medical device and does not replace ")
             .Append("professional assessment or treatment.</p>\n</div>\n");

            h.Append("<footer>Source data: ").Append(Esc(SessionLogger.FilePath)).Append("</footer>\n</main>\n</body>\n</html>\n");
            return h.ToString();
        }

        static void Card(StringBuilder h, string value, string label)
        {
            h.Append("<div class=\"card\"><b>").Append(Esc(value)).Append("</b><span>").Append(Esc(label)).Append("</span></div>\n");
        }

        static void BarHtml(StringBuilder h, List<int> values, string cls)
        {
            if (values.Count == 0)
            {
                h.Append("<div class=\"track\"></div>");
                return;
            }
            float v = Mathf.Clamp(Average(values), 0f, 10f);
            h.Append("<div class=\"track\"><div class=\"bar ").Append(cls).Append("\" style=\"width:")
             .Append((v * 10f).ToString("0.#", Inv)).Append("%\">").Append(v.ToString("0.#", Inv)).Append("</div></div>");
        }

        static string AchievementTitle(Achievements.Def[] all, string id)
        {
            for (int i = 0; i < all.Length; i++)
                if (all[i].id == id) return string.IsNullOrEmpty(all[i].title) ? id : all[i].title;
            return id;
        }

        static string Esc(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;").Replace("\"", "&quot;").Replace("'", "&#39;");
        }
    }
}
