using System;
using System.Collections;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace AcrophobiaVR
{
    /// <summary>
    /// Persistent game state: level order, unlock progress and fading scene transitions.
    /// Created automatically before the first scene loads, so no scene needs to contain it.
    /// </summary>
    public class GameManager : MonoBehaviour
    {
        public const string MenuScene = "MainMenu";

        public static readonly string[] LevelScenes =
        {
            "Level1_Balcony",
            "Level2_Construction",
            "Level3_Skyscraper",
        };

        public static readonly string[] LevelTitles =
        {
            "Level 1 - The Cafe",
            "Level 2 - The Construction Site",
            "Level 3 - The Skyscraper Beam",
        };

        public static readonly string[] LevelDescriptions =
        {
            "Walk on glass, rescue a parrot on a ledge, climb to the roof.",
            "Ride an open lift, cross planks, climb the crane.",
            "Cross a beam between towers and rescue a cat.",
        };

        const string UnlockKey = "acro_highest_unlocked";
        const string CompletedKeyPrefix = "acro_completed_";

        public static GameManager Instance { get; private set; }

        bool loading;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Bootstrap()
        {
            if (Instance != null) return;
            var go = new GameObject("[GameManager]");
            go.AddComponent<GameManager>();
            go.AddComponent<ScreenFader>();
            DontDestroyOnLoad(go);
        }

        void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            SessionLogger.Log(SceneManager.GetActiveScene().name, "app_start");
        }

        public int HighestUnlocked => Mathf.Clamp(PlayerPrefs.GetInt(UnlockKey, 0), 0, LevelScenes.Length - 1);

        public bool IsUnlocked(int levelIndex) => levelIndex <= HighestUnlocked;

        public bool IsCompleted(int levelIndex) => PlayerPrefs.GetInt(CompletedKeyPrefix + levelIndex, 0) == 1;

        public static int CurrentLevelIndex => Array.IndexOf(LevelScenes, SceneManager.GetActiveScene().name);

        public void CompleteLevel(int levelIndex)
        {
            PlayerPrefs.SetInt(CompletedKeyPrefix + levelIndex, 1);
            if (levelIndex + 1 > HighestUnlocked)
                PlayerPrefs.SetInt(UnlockKey, Mathf.Min(levelIndex + 1, LevelScenes.Length - 1));
            PlayerPrefs.Save();
        }

        public void ResetProgress()
        {
            PlayerPrefs.DeleteKey(UnlockKey);
            for (int i = 0; i < LevelScenes.Length; i++)
                PlayerPrefs.DeleteKey(CompletedKeyPrefix + i);
            PlayerPrefs.Save();
            SessionLogger.Log(MenuScene, "progress_reset");
        }

        public void LoadLevel(int levelIndex)
        {
            if (levelIndex < 0 || levelIndex >= LevelScenes.Length) return;
            LoadScene(LevelScenes[levelIndex]);
        }

        public void LoadMenu() => LoadScene(MenuScene);

        public void ReloadCurrent() => LoadScene(SceneManager.GetActiveScene().name);

        public void LoadScene(string sceneName)
        {
            if (!loading) StartCoroutine(LoadRoutine(sceneName));
        }

        IEnumerator LoadRoutine(string sceneName)
        {
            loading = true;
            yield return ScreenFader.Instance.FadeOut(0.8f);
            yield return SceneManager.LoadSceneAsync(sceneName);
            loading = false;
        }

        public void Quit()
        {
            SessionLogger.Log(SceneManager.GetActiveScene().name, "app_quit");
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }
    }
}
