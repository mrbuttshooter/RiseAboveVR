using UnityEngine;
using UnityEngine.SceneManagement;

namespace AcrophobiaVR
{
    /// <summary>
    /// Adds runtime-built extras to the MainMenu park without editing the scene: the Courage Elevator
    /// (free-practice glass lift) and, if the park has none, a FearSystem so heights there feel real too
    /// (tunnel vision / heartbeat / BPM only - panic needs a LevelController). Idempotent and never throws.
    /// </summary>
    public static class ParkExtras
    {
        public const string ParkScene = "MainMenu";
        // To the player's right, clear of the menu, help board, portals and fountain.
        public static readonly Vector3 ElevatorPosition = new Vector3(9f, 0f, -1f);

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Init()
        {
            SceneManager.sceneLoaded -= OnSceneLoaded;
            SceneManager.sceneLoaded += OnSceneLoaded;
        }

        static void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            if (scene.name != ParkScene) return;
            try
            {
                if (Object.FindFirstObjectByType<CourageElevator>() != null) return;

                var go = new GameObject("Courage Elevator");
                if (go.scene != scene && scene.isLoaded) SceneManager.MoveGameObjectToScene(go, scene);
                var park = GameObject.Find("Park");
                if (park != null && park.scene == scene) go.transform.SetParent(park.transform, false);
                // Faces -X: the open gate, call button and sign point back towards the player area.
                go.transform.SetPositionAndRotation(ElevatorPosition, Quaternion.LookRotation(Vector3.left, Vector3.up));
                go.AddComponent<CourageElevator>();

                if (Object.FindFirstObjectByType<FearSystem>() == null) go.AddComponent<FearSystem>();
            }
            catch (System.Exception e)
            {
                Debug.LogWarning("[ParkExtras] " + e.Message);
            }
        }
    }
}
