using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using static AcrophobiaVR.EditorTools.BuildKit;

namespace AcrophobiaVR.EditorTools
{
    /// <summary>
    /// Builds every scene of "Rise Above" from code: Rise Above > Build All Scenes.
    /// Re-running it regenerates the scenes, so tweak numbers here and rebuild.
    /// </summary>
    public static partial class LevelBuilder
    {
        public const string MenuScenePath = SceneDir + "/MainMenu.unity";

        [MenuItem("Rise Above/Build All Scenes", priority = 0)]
        public static void BuildAll()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            BuildAllNoPrompt();
            EditorSceneManager.OpenScene(MenuScenePath);
            EditorUtility.DisplayDialog("Rise Above", "All 4 scenes were built and added to Build Settings.\n\nOpen MainMenu and press Play.", "Great");
        }

        /// <summary>Batch-mode entry point: -executeMethod AcrophobiaVR.EditorTools.LevelBuilder.BuildAllNoPrompt</summary>
        public static void BuildAllNoPrompt()
        {
            EnsureFolders();
            BuildMenu();
            BuildLevel1();
            BuildLevel2();
            BuildLevel3();
            UpdateBuildSettings();
            AssetDatabase.SaveAssets();
            Debug.Log("[Rise Above] All scenes built.");
        }

        [MenuItem("Rise Above/Build Main Menu (Park)", priority = 20)] static void MenuOnly() { EnsureFolders(); BuildMenu(); UpdateBuildSettings(); }
        [MenuItem("Rise Above/Build Level 1 (Balcony)", priority = 21)] static void L1Only() { EnsureFolders(); BuildLevel1(); UpdateBuildSettings(); }
        [MenuItem("Rise Above/Build Level 2 (Construction)", priority = 22)] static void L2Only() { EnsureFolders(); BuildLevel2(); UpdateBuildSettings(); }
        [MenuItem("Rise Above/Build Level 3 (Skyscraper)", priority = 23)] static void L3Only() { EnsureFolders(); BuildLevel3(); UpdateBuildSettings(); }

        [MenuItem("Rise Above/Open Session Log Folder", priority = 40)]
        static void OpenLogFolder() => EditorUtility.RevealInFinder(Application.persistentDataPath);

        [MenuItem("Rise Above/Reset Saved Progress", priority = 41)]
        static void ResetPrefs()
        {
            PlayerPrefs.DeleteAll();
            Debug.Log("[Rise Above] PlayerPrefs cleared.");
        }

        static void UpdateBuildSettings()
        {
            var paths = new List<string> { MenuScenePath };
            foreach (var name in GameManager.LevelScenes) paths.Add(SceneDir + "/" + name + ".unity");
            EditorBuildSettings.scenes = paths.Where(p => System.IO.File.Exists(p)).Select(p => new EditorBuildSettingsScene(p, true)).ToArray();
        }

        static Scene NewScene()
        {
            return EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        }

        static void Save(Scene scene, string name)
        {
            Lightmapping.giWorkflowMode = Lightmapping.GIWorkflowMode.OnDemand;
            EditorSceneManager.SaveScene(scene, SceneDir + "/" + name + ".unity");
        }

        static void Atmosphere(Material sky, Color fogColor, Color ambient)
        {
            RenderSettings.skybox = sky;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = ambient;
            RenderSettings.ambientEquatorColor = Color.Lerp(ambient, fogColor, 0.5f);
            RenderSettings.ambientGroundColor = ambient * 0.45f;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Exponential;
            RenderSettings.fogColor = fogColor;
            RenderSettings.fogDensity = 0.004f;
        }

        /// <summary>Common objects for every level: rig, controller, Pip, audio, effects, Calm Meadow.</summary>
        static LevelController CommonLevel(int index, string title, Vector3 start, float startYaw, float groundY, float maxHeight, float cityAudio)
        {
            var systems = Group("Systems").transform;

            var holder = Group("Effects", systems).AddComponent<EffectsMaterialHolder>();
            holder.particleMaterial = ParticleMat();

            var audio = Group("Ambience", systems);
            audio.AddComponent<AudioSource>();
            var amb = audio.AddComponent<AmbientAudio>();
            amb.groundY = groundY;
            amb.maxHeight = maxHeight;
            amb.cityLevel = cityAudio;

            var lcGo = Group("LevelController", systems);
            var lc = lcGo.AddComponent<LevelController>();
            lcGo.AddComponent<FallGuard>();
            lc.levelIndex = index;
            lc.levelTitle = title;
            lc.startPoint = Point("StartPoint", lcGo.transform, start, startYaw);

            InstantiateRig(start, startYaw);
            CreatePip(start + Quaternion.Euler(0, startYaw, 0) * new Vector3(0.6f, 1.5f, 1f));
            BuildCalmMeadow(new Vector3(3000f, 0f, 3000f));
            return lc;
        }

        /// <summary>The safe place: a sunny meadow ringed by hedges, with a pond, trees, fireflies and the breathing orb.</summary>
        static void BuildCalmMeadow(Vector3 c)
        {
            var root = Group("Calm Meadow (Safe Room)").transform;
            root.position = c;
            var grass = Mat("MeadowGrass", new Color(0.42f, 0.7f, 0.35f));
            var hedge = Mat("Hedge", new Color(0.2f, 0.45f, 0.22f));
            var trunk = Mat("Trunk", new Color(0.4f, 0.28f, 0.18f));
            var leaves = Mat("Leaves", new Color(0.35f, 0.62f, 0.3f));
            var water = Mat("Pond", new Color(0.35f, 0.65f, 0.85f), 0.95f);
            Cyl("Ground", root, new Vector3(0, -0.5f, 0), 28f, 0.5f, grass);
            for (int i = 0; i < 36; i++)
            {
                float a = i / 36f * Mathf.PI * 2f;
                Cyl("Hedge", root, new Vector3(Mathf.Cos(a) * 24f, 0, Mathf.Sin(a) * 24f), 2.6f, 5f, hedge);
            }
            Cyl("Pond", root, new Vector3(-6, 0.01f, 6), 3.5f, 0.02f, water, false);
            var rng = new System.Random(3);
            for (int i = 0; i < 9; i++)
            {
                float a = (float)rng.NextDouble() * Mathf.PI * 2f;
                float r = 10f + (float)rng.NextDouble() * 9f;
                Tree(root, new Vector3(Mathf.Cos(a) * r, 0, Mathf.Sin(a) * r), 0.9f + (float)rng.NextDouble() * 0.6f, trunk, leaves);
            }
            Color[] flowerColors = { new Color(1f, 0.6f, 0.8f), new Color(1f, 0.95f, 0.4f), new Color(0.7f, 0.6f, 1f), Color.white };
            for (int i = 0; i < 60; i++)
            {
                float a = (float)rng.NextDouble() * Mathf.PI * 2f;
                float r = 3f + (float)rng.NextDouble() * 16f;
                var fm = Mat("Flower" + (i % 4), flowerColors[i % 4]);
                Sphere("Flower", root, new Vector3(Mathf.Cos(a) * r, 0.15f, Mathf.Sin(a) * r), 0.18f, fm);
            }
            var bench = Mat("Bench", new Color(0.55f, 0.38f, 0.25f));
            Box("BenchSeat", root, new Vector3(0, 0.45f, 2.5f), new Vector3(1.8f, 0.08f, 0.5f), bench);
            Box("BenchBack", root, new Vector3(0, 0.8f, 2.75f), new Vector3(1.8f, 0.5f, 0.06f), bench);
            var ff = Group("Fireflies", root);
            ff.transform.localPosition = new Vector3(0, 1.2f, 0);
            ff.AddComponent<FirefliesSpawner>().radius = 14f;

            var safe = Group("SafeRoom", root).AddComponent<SafeRoom>();
            safe.spawnPoint = Point("Spawn", safe.transform, new Vector3(0, 0, -3), 0f);
            safe.panelPoint = PanelPoint("Panel", root, new Vector3(-2.6f, 1.6f, 0.5f), c + new Vector3(0, 1.6f, -3f));
        }

        static void Ground(Transform parent, float size, Material mat, float y = 0f, bool teleport = false)
        {
            Floor("Ground", parent, -size, size, -size, size, y, 1f, mat, teleport);
        }

        // ------------------------------------------------------------------ MAIN MENU (PARK HUB)
        static void BuildMenu()
        {
            var scene = NewScene();
            Atmosphere(Sky("SkyPark", new Color(0.45f, 0.62f, 0.9f), new Color(0.4f, 0.45f, 0.4f), 0.04f, 0.9f, 1.25f), new Color(0.75f, 0.85f, 0.95f), new Color(0.7f, 0.75f, 0.85f));
            RenderSettings.fogDensity = 0.006f;
            Sun(new Vector3(40, -30, 0), new Color(1f, 0.96f, 0.88f), 1.25f);
            var env = Group("Park").transform;
            var grass = Mat("Grass", new Color(0.4f, 0.66f, 0.33f));
            var path = Mat("Path", new Color(0.82f, 0.76f, 0.62f));
            var trunk = Mat("Trunk", new Color(0.4f, 0.28f, 0.18f));
            var leaves = Mat("Leaves", new Color(0.35f, 0.62f, 0.3f));
            var stone = Mat("Stone", new Color(0.75f, 0.75f, 0.78f));
            Ground(env, 150f, grass, 0f, true);
            Box("PathMain", env, new Vector3(0, 0.01f, 5), new Vector3(3, 0.02f, 16), path, false);
            Box("PathCross", env, new Vector3(0, 0.01f, 9), new Vector3(16, 0.02f, 3), path, false);
            var rng = new System.Random(11);
            for (int i = 0; i < 40; i++)
            {
                float a = (float)rng.NextDouble() * Mathf.PI * 2f;
                float r = 14f + (float)rng.NextDouble() * 40f;
                Tree(env, new Vector3(Mathf.Cos(a) * r, 0, Mathf.Sin(a) * r), 1f + (float)rng.NextDouble(), trunk, leaves);
            }
            // Fountain behind the player
            Cyl("FountainBasin", env, new Vector3(0, 0, -6), 2.2f, 0.5f, stone);
            Cyl("FountainWater", env, new Vector3(0, 0.45f, -6), 2f, 0.06f, Mat("Pond", new Color(0.35f, 0.65f, 0.85f), 0.95f), false);
            Cyl("FountainColumn", env, new Vector3(0, 0, -6), 0.3f, 1.6f, stone);

            // Backdrop: the three challenges in the distance - cafe, crane, skyscraper.
            Box("Cafe", env, new Vector3(-30, 11, 70), new Vector3(20, 22, 14), Mat("CafeWall", new Color(0.9f, 0.72f, 0.55f)), false);
            Box("CraneMast", env, new Vector3(0, 20, 80), new Vector3(1.5f, 40, 1.5f), Mat("CraneYellow", new Color(1f, 0.78f, 0.15f), 0.4f, 0.3f), false);
            Box("CraneJib", env, new Vector3(8, 40, 80), new Vector3(30, 1.2f, 1.2f), Mat("CraneYellow", new Color(1f, 0.78f, 0.15f), 0.4f, 0.3f), false);
            Box("Skyscraper", env, new Vector3(40, 75, 110), new Vector3(16, 150, 16), Mat("Glass Tower", new Color(0.45f, 0.6f, 0.75f), 0.85f, 0.4f), false);

            var systems = Group("Systems").transform;
            Group("Effects", systems).AddComponent<EffectsMaterialHolder>().particleMaterial = ParticleMat();
            var audio = Group("Ambience", systems);
            audio.AddComponent<AudioSource>();
            var amb = audio.AddComponent<AmbientAudio>();
            amb.startInMeadow = true;
            amb.cityLevel = 0.1f;

            InstantiateRig(Vector3.zero, 0f);
            CreatePip(new Vector3(0.7f, 1.5f, 1.2f));

            var menu = Group("MainMenu", systems).AddComponent<MainMenuController>();
            Vector3 eye = new Vector3(0, 1.6f, 0);
            menu.menuPoint = PanelPoint("MenuPoint", systems, new Vector3(0, 1.75f, 3.4f), eye);
            menu.trophyPoint = PanelPoint("TrophyPoint", systems, new Vector3(-3.6f, 1.7f, 2f), eye);
            menu.helpPoint = PanelPoint("HelpPoint", systems, new Vector3(3.4f, 1.7f, 2f), eye);
            var ff = Group("Fireflies", env);
            ff.transform.position = new Vector3(0, 1.5f, 4);
            ff.AddComponent<FirefliesSpawner>().radius = 10f;

            // Portals
            var frame = Mat("PortalFrame", new Color(0.9f, 0.9f, 0.95f), 0.6f, 0.2f);
            var glow = Transparent("PortalGlow", new Color(0.4f, 0.85f, 1f, 0.55f), true);
            for (int i = 0; i < 3; i++)
            {
                Vector3 p = new Vector3((i - 1) * 5.5f, 0, 10.5f);
                var portal = Group("Portal " + (i + 1), env).transform;
                portal.position = p;
                Box("PillarL", portal, new Vector3(-1.2f, 1.6f, 0), new Vector3(0.3f, 3.2f, 0.3f), frame);
                Box("PillarR", portal, new Vector3(1.2f, 1.6f, 0), new Vector3(0.3f, 3.2f, 0.3f), frame);
                Box("Lintel", portal, new Vector3(0, 3.35f, 0), new Vector3(2.7f, 0.3f, 0.3f), frame);
                var g = Box("Glow", portal, new Vector3(0, 1.6f, 0), new Vector3(2.1f, 3.1f, 0.05f), glow, false, false);
                var lp = Zone<LevelPortal>("PortalZone", portal, new Vector3(0, 1.3f, 0), new Vector3(2f, 2.8f, 0.6f));
                lp.levelIndex = i;
                lp.glowRenderer = g.GetComponent<Renderer>();
                lp.labelPoint = PanelPoint("Label", portal, new Vector3(0, 4.4f, -0.2f), eye);
            }
            Save(scene, "MainMenu");
        }
    }
}