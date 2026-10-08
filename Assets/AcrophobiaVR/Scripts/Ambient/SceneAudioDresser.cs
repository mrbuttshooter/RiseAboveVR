using UnityEngine;
using UnityEngine.SceneManagement;

namespace AcrophobiaVR
{
    /// <summary>
    /// On every scene load, attaches looping 3D SoundEmitters to known silent scene objects (busker, fountains,
    /// cars, moving platforms, cafe, bird flocks) and Footsteps to the player rig. Idempotent and never throws.
    /// Runs once immediately in sceneLoaded and again one frame later to catch objects created in Start.
    /// </summary>
    public static class SceneAudioDresser
    {
        const int MaxCars = 12;
        const string BuskerChild = "BuskerAudio";
        const string CafeChild = "CafeChatterAudio";
        static readonly Vector3 CafeChatterPos = new Vector3(0f, 7.0f, -0.5f);

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Init()
        {
            SceneManager.sceneLoaded -= OnSceneLoaded;
            SceneManager.sceneLoaded += OnSceneLoaded;
        }

        static void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            Dress();
            DressNextFrame();
        }

        static async void DressNextFrame()
        {
            try
            {
                await Awaitable.NextFrameAsync();
                if (Application.isPlaying) Dress();
            }
            catch (System.Exception e)
            {
                if (!(e is System.OperationCanceledException)) Debug.LogWarning("[SceneAudioDresser] " + e.Message);
            }
        }

        /// <summary>Adds any missing emitters to the currently loaded scene(s). Safe to call repeatedly.</summary>
        public static void Dress()
        {
            Try(DressBusker);
            Try(DressFountains);
            Try(DressCars);
            Try(DressPlatforms);
            Try(DressCafe);
            Try(DressBirds);
            Try(DressConstruction);
            Try(DressFootsteps);
        }

        /// <summary>Level 2: distant hammering, drills, a reversing truck and a generator from the site below.</summary>
        static void DressConstruction()
        {
            var building = GameObject.Find("BuildingA");
            if (building == null || building.transform.Find("ConstructionAmbience") != null) return;
            var go = new GameObject("ConstructionAmbience");
            go.transform.SetParent(building.transform, false);
            go.transform.position = new Vector3(-2f, 2f, 4f);
            Add(go, EmitterKind.Construction);
        }

        static void Try(System.Action step)
        {
            try { step(); }
            catch (System.Exception e) { Debug.LogWarning("[SceneAudioDresser] " + e.Message); }
        }

        static void DressBusker()
        {
            var busker = GameObject.Find("Busker");
            if (busker == null || busker.transform.Find(BuskerChild) != null) return;
            var go = new GameObject(BuskerChild);
            go.transform.SetParent(busker.transform, false);
            go.transform.position = busker.transform.position + Vector3.up * 1f;
            Add(go, EmitterKind.BuskerGuitar);
        }

        static void DressFountains()
        {
            var fountain = GameObject.Find("Fountain");
            if (fountain != null && fountain.name == "Fountain") AddIfMissing(fountain, EmitterKind.Fountain);

            var basin = GameObject.Find("FountainBasin");
            if (basin != null && !HasKindInParents(basin.transform, EmitterKind.Fountain))
                AddIfMissing(basin, EmitterKind.Fountain);
        }

        static void DressCars()
        {
            var movers = Object.FindObjectsByType<LoopMover>(FindObjectsSortMode.None);
            if (movers == null) return;
            int count = 0;
            for (int i = 0; i < movers.Length; i++)
                if (movers[i] != null && Has(movers[i].gameObject, EmitterKind.CarEngine)) count++;

            for (int i = 0; i < movers.Length && count < MaxCars; i++)
            {
                var m = movers[i];
                if (m == null) continue;
                var go = m.gameObject;
                if (go.name.IndexOf("Car", System.StringComparison.Ordinal) < 0) continue;
                if (Has(go, EmitterKind.CarEngine)) continue;
                Add(go, EmitterKind.CarEngine);
                count++;
            }
        }

        static void DressPlatforms()
        {
            var platforms = Object.FindObjectsByType<MovingPlatform>(FindObjectsSortMode.None);
            if (platforms != null)
                for (int i = 0; i < platforms.Length; i++)
                    if (platforms[i] != null) AddIfMissing(platforms[i].gameObject, EmitterKind.Motor);

            var crane = GameObject.Find("Crane");
            if (crane != null && crane.GetComponent<MovingPlatform>() != null) AddIfMissing(crane, EmitterKind.Motor);
        }

        static void DressCafe()
        {
            var cafe = GameObject.Find("SunsetCafe");
            if (cafe == null || cafe.transform.Find(CafeChild) != null) return;
            var go = new GameObject(CafeChild);
            go.transform.SetParent(cafe.transform, false);
            go.transform.position = CafeChatterPos;
            Add(go, EmitterKind.CafeChatter);
        }

        static void DressBirds()
        {
            var flocks = Object.FindObjectsByType<BirdFlock>(FindObjectsSortMode.None);
            if (flocks == null) return;
            for (int i = 0; i < flocks.Length; i++)
                if (flocks[i] != null) AddIfMissing(flocks[i].gameObject, EmitterKind.Birds);
        }

        static void DressFootsteps()
        {
            var rig = PlayerRig.Instance;
            if (rig == null) return;
            if (rig.GetComponent<Footsteps>() == null) rig.gameObject.AddComponent<Footsteps>();
        }

        // ------------------------------------------------------------------ helpers

        static void AddIfMissing(GameObject go, EmitterKind kind)
        {
            if (go == null || Has(go, kind)) return;
            Add(go, kind);
        }

        static void Add(GameObject go, EmitterKind kind)
        {
            if (go == null) return;
            var e = go.AddComponent<SoundEmitter>();
            if (e == null) return;
            e.kind = kind;
            e.volume = 1f;
        }

        static bool Has(GameObject go, EmitterKind kind)
        {
            if (go == null) return false;
            var list = go.GetComponents<SoundEmitter>();
            for (int i = 0; i < list.Length; i++)
                if (list[i] != null && list[i].kind == kind) return true;
            return false;
        }

        static bool HasKindInParents(Transform t, EmitterKind kind)
        {
            for (var p = t; p != null; p = p.parent)
                if (Has(p.gameObject, kind)) return true;
            return false;
        }
    }
}
