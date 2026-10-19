using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace AcrophobiaVR.EditorTools
{
    /// <summary>
    /// Real CC0 assets from Poly Haven (downloaded into ThirdParty/PolyHaven): PBR texture sets for the
    /// ground / prop surfaces and equirectangular HDRI skyboxes for each scene mood.
    /// Importers are configured once (idempotent: reimport only when a setting actually changes) with
    /// Quest-friendly Android overrides (ASTC). Facade surfaces are not covered (they stay procedural,
    /// because their textures carry windows and lit-window emission).
    /// </summary>
    public static class RealAssets
    {
        public const string PolyHavenDir = BuildKit.Root + "/ThirdParty/PolyHaven";
        public const string TextureDir = PolyHavenDir + "/Textures";
        public const string SkyDir = PolyHavenDir + "/Skies";
        /// <summary>Packed URP metallic/smoothness masks are written here (shared with ProceduralTextures).</summary>
        public const string MaskDir = ProceduralTextures.Dir;

        const int TextureMaxSize = 2048; // PC; Android gets its own 1024 override
        const int SkyMaxSize = 2048;
        const string AndroidPlatform = "Android";

        enum Role { Albedo, Normal, Rough, Mask }

        struct RealSet
        {
            public Texture2D albedo, normal, mask;
        }

        static readonly Dictionary<Surface, RealSet> Cache = new Dictionary<Surface, RealSet>();
        static bool s_Refreshed;

        // ------------------------------------------------------------------ public API

        /// <summary>True for the surfaces that have downloaded Poly Haven textures (all non-facade surfaces).</summary>
        public static bool HasRealTextures(Surface s)
        {
            switch (s)
            {
                case Surface.Asphalt:
                case Surface.Concrete:
                case Surface.Pavement:
                case Surface.Grass:
                case Surface.Dirt:
                case Surface.Wood:
                case Surface.Metal:
                case Surface.Grate:
                case Surface.RoofGravel:
                case Surface.Tiles:
                case Surface.Brick:
                case Surface.Plaster:
                    return true;
                default:
                    return false;
            }
        }

        /// <summary>Real-world size (metres) covered by one repeat of the real texture.</summary>
        public static Vector2 TileMeters(Surface s)
        {
            switch (s)
            {
                case Surface.Asphalt: return new Vector2(4f, 4f);
                case Surface.Concrete: return new Vector2(3f, 3f);
                case Surface.Pavement: return new Vector2(2f, 2f);
                case Surface.Grass: return new Vector2(6f, 6f);
                case Surface.Dirt: return new Vector2(4f, 4f);
                case Surface.Wood: return new Vector2(2f, 2f);
                case Surface.Metal: return new Vector2(2.2f, 2.2f);   // rusty_painted_metal scan
                case Surface.Grate: return new Vector2(1f, 1f);
                case Surface.RoofGravel: return new Vector2(3f, 3f);
                case Surface.Tiles: return new Vector2(2f, 2f);
                case Surface.Brick: return new Vector2(2.5f, 2.5f);   // red_bricks_04 scan
                case Surface.Plaster: return new Vector2(3f, 3f);     // beige_wall_001 scan
                default: return ProceduralTextures.TileMeters(s);
            }
        }

        /// <summary>
        /// Real albedo (sRGB), normal map (OpenGL / +Y, as Unity expects) and a packed URP metallic/smoothness mask
        /// (R = metallic, A = 1 - roughness) for a surface. Returns false (callers fall back to procedural
        /// textures) for facade surfaces, missing files or any import failure.
        /// </summary>
        public static bool TryGetTextures(Surface s, out Texture2D albedo, out Texture2D normal, out Texture2D mask, out Vector2 tileMeters)
        {
            albedo = null;
            normal = null;
            mask = null;
            tileMeters = TileMeters(s);
            if (!HasRealTextures(s)) return false;

            if (Cache.TryGetValue(s, out RealSet cached) && cached.albedo != null && cached.normal != null && cached.mask != null)
            {
                albedo = cached.albedo;
                normal = cached.normal;
                mask = cached.mask;
                return true;
            }

            try
            {
                string aPath = FindSource(TextureDir, "tex_" + s + "_albedo");
                string nPath = FindSource(TextureDir, "tex_" + s + "_normal");
                string rPath = FindSource(TextureDir, "tex_" + s + "_rough");
                if (aPath == null || nPath == null || rPath == null) return false;

                ConfigureTexture(aPath, Role.Albedo);
                ConfigureTexture(nPath, Role.Normal);
                ConfigureTexture(rPath, Role.Rough);

                var a = AssetDatabase.LoadAssetAtPath<Texture2D>(aPath);
                var n = AssetDatabase.LoadAssetAtPath<Texture2D>(nPath);
                var m = GetOrBuildMask(s, rPath);
                if (a == null || n == null || m == null)
                {
                    Debug.LogWarning("[RealAssets] Incomplete texture set for " + s + "; using procedural textures.");
                    return false;
                }

                Cache[s] = new RealSet { albedo = a, normal = n, mask = m };
                albedo = a;
                normal = n;
                mask = m;
                return true;
            }
            catch (System.Exception e)
            {
                Debug.LogWarning("[RealAssets] Could not load real textures for " + s + ": " + e.Message + " (using procedural textures)");
                return false;
            }
        }

        /// <summary>
        /// Panoramic (latitude-longitude) skybox material using the Poly Haven HDRI for a mood
        /// ("park", "sunset", "noon", "golden"), saved as Generated/Materials/HDRISky_&lt;mood&gt;.mat.
        /// Returns null when the HDR file is missing (callers keep the procedural sky).
        /// </summary>
        public static Material SkyFor(string mood)
        {
            if (string.IsNullOrEmpty(mood)) return null;
            try
            {
                string hdrPath = FindSource(SkyDir, "sky_" + mood);
                if (hdrPath == null) return null;
                ConfigureSky(hdrPath);
                var hdr = AssetDatabase.LoadAssetAtPath<Texture2D>(hdrPath);
                if (hdr == null) return null;

                var shader = Shader.Find("Skybox/Panoramic");
                if (shader == null)
                {
                    Debug.LogWarning("[RealAssets] Shader 'Skybox/Panoramic' not found; keeping the procedural sky.");
                    return null;
                }

                string matPath = BuildKit.MatDir + "/HDRISky_" + mood + ".mat";
                var m = AssetDatabase.LoadAssetAtPath<Material>(matPath);
                bool isNew = m == null;
                if (isNew) m = new Material(shader) { name = "HDRISky_" + mood };
                else if (m.shader != shader) m.shader = shader;

                m.SetTexture("_MainTex", hdr);
                m.SetFloat("_Mapping", 1f);      // latitude-longitude layout
                m.SetFloat("_ImageType", 0f);    // 360 degrees
                m.SetFloat("_MirrorOnBack", 0f);
                m.SetFloat("_Layout", 0f);       // no stereo 3D layout
                m.SetFloat("_Exposure", SkyExposure(mood));
                m.SetFloat("_Rotation", 0f);
                m.SetColor("_Tint", new Color(0.5f, 0.5f, 0.5f, 0.5f));
                // Keywords from the shader's KeywordEnum/Toggle drawers are not updated by SetFloat from script.
                m.DisableKeyword("_MAPPING_6_FRAMES_LAYOUT");
                m.EnableKeyword("_MAPPING_LATITUDE_LONGITUDE_LAYOUT");
                m.DisableKeyword("_MIRRORONBACK_ON");

                if (isNew)
                {
                    EnsureFolder(BuildKit.MatDir);
                    AssetDatabase.CreateAsset(m, matPath);
                }
                else
                {
                    EditorUtility.SetDirty(m);
                }
                return m;
            }
            catch (System.Exception e)
            {
                Debug.LogWarning("[RealAssets] Could not create HDRI sky for '" + mood + "': " + e.Message + " (keeping the procedural sky)");
                return null;
            }
        }

        // ------------------------------------------------------------------ sky

        static float SkyExposure(string mood)
        {
            switch (mood)
            {
                // Tuned against the ACES tonemapper + fog so the horizon doesn't wash out to white.
                case "sunset": return 0.75f;
                case "golden": return 0.85f;
                case "park":
                case "noon":
                default: return 0.9f;
            }
        }

        static void ConfigureSky(string path)
        {
            var imp = AssetImporter.GetAtPath(path) as TextureImporter;
            if (imp == null) return;
            bool changed = false;
            if (imp.textureType != TextureImporterType.Default) { imp.textureType = TextureImporterType.Default; changed = true; }
            if (imp.textureShape != TextureImporterShape.Texture2D) { imp.textureShape = TextureImporterShape.Texture2D; changed = true; }
            if (imp.wrapModeU != TextureWrapMode.Repeat) { imp.wrapModeU = TextureWrapMode.Repeat; changed = true; }
            if (imp.wrapModeV != TextureWrapMode.Clamp) { imp.wrapModeV = TextureWrapMode.Clamp; changed = true; }
            // No mips: lat-long sampling with mips shows a seam where U wraps.
            if (imp.mipmapEnabled) { imp.mipmapEnabled = false; changed = true; }
            if (imp.maxTextureSize != SkyMaxSize) { imp.maxTextureSize = SkyMaxSize; changed = true; }
            changed |= SetAndroidOverride(imp, SkyMaxSize, TextureImporterFormat.ASTC_HDR_6x6);
            if (changed) imp.SaveAndReimport();
        }

        // ------------------------------------------------------------------ textures

        static void ConfigureTexture(string path, Role role)
        {
            var imp = AssetImporter.GetAtPath(path) as TextureImporter;
            if (imp == null) return;
            bool changed = false;

            var type = role == Role.Normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
            if (imp.textureType != type) { imp.textureType = type; changed = true; }
            if (imp.textureShape != TextureImporterShape.Texture2D) { imp.textureShape = TextureImporterShape.Texture2D; changed = true; }
            if (role != Role.Normal)
            {
                bool srgb = role == Role.Albedo;
                if (imp.sRGBTexture != srgb) { imp.sRGBTexture = srgb; changed = true; }
            }
            if (role == Role.Mask && imp.alphaSource != TextureImporterAlphaSource.FromInput)
            {
                imp.alphaSource = TextureImporterAlphaSource.FromInput;
                changed = true;
            }
            // True would dilate colour into low-alpha texels (mask alpha is smoothness, not coverage).
            if (imp.alphaIsTransparency) { imp.alphaIsTransparency = false; changed = true; }
            if (imp.wrapModeU != TextureWrapMode.Repeat || imp.wrapModeV != TextureWrapMode.Repeat)
            {
                imp.wrapMode = TextureWrapMode.Repeat;
                changed = true;
            }
            if (!imp.mipmapEnabled) { imp.mipmapEnabled = true; changed = true; }
            if (imp.anisoLevel != 4) { imp.anisoLevel = 4; changed = true; }
            if (imp.filterMode != FilterMode.Trilinear) { imp.filterMode = FilterMode.Trilinear; changed = true; }
            if (imp.maxTextureSize != TextureMaxSize) { imp.maxTextureSize = TextureMaxSize; changed = true; }
            if (imp.textureCompression != TextureImporterCompression.Compressed)
            {
                imp.textureCompression = TextureImporterCompression.Compressed;
                changed = true;
            }
            changed |= SetAndroidOverride(imp, 1024, TextureImporterFormat.ASTC_6x6);
            if (changed) imp.SaveAndReimport();
        }

        /// <summary>Applies the Quest (Android) platform override; returns true if anything changed.</summary>
        static bool SetAndroidOverride(TextureImporter imp, int maxSize, TextureImporterFormat format)
        {
            var ps = imp.GetPlatformTextureSettings(AndroidPlatform);
            if (ps.overridden && ps.maxTextureSize == maxSize && ps.format == format) return false;
            ps.name = AndroidPlatform;
            ps.overridden = true;
            ps.maxTextureSize = maxSize;
            ps.format = format;
            imp.SetPlatformTextureSettings(ps);
            return true;
        }

        static bool IsMetallic(Surface s) => s == Surface.Grate; // Metal is now painted steel (paint + rust are not metallic)

        /// <summary>Loads (building once if missing) Generated/Textures/mask_&lt;Surface&gt;.png.</summary>
        static Texture2D GetOrBuildMask(Surface s, string roughPath)
        {
            string maskPath = MaskDir + "/mask_" + s + ".png";
            EnsureImported(maskPath);
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(maskPath);
            if (tex == null)
            {
                if (!BuildMaskPng(s, roughPath, maskPath)) return null;
                AssetDatabase.ImportAsset(maskPath, ImportAssetOptions.ForceUpdate | ImportAssetOptions.ForceSynchronousImport);
            }
            ConfigureTexture(maskPath, Role.Mask);
            return AssetDatabase.LoadAssetAtPath<Texture2D>(maskPath);
        }

        /// <summary>
        /// Decodes the roughness JPG straight from disk (raw 8-bit values, no importer or colour-space changes)
        /// and writes R = metallic, G = B = 0, A = 1 - roughness as a PNG.
        /// </summary>
        static bool BuildMaskPng(Surface s, string roughPath, string maskPath)
        {
            string roughFull = FullPath(roughPath);
            if (!File.Exists(roughFull)) return false;
            byte[] bytes = File.ReadAllBytes(roughFull);

            var src = new Texture2D(2, 2, TextureFormat.RGBA32, false, true);
            Texture2D dst = null;
            try
            {
                if (!ImageConversion.LoadImage(src, bytes, false))
                {
                    Debug.LogWarning("[RealAssets] Could not decode " + roughPath);
                    return false;
                }
                Color32[] px = src.GetPixels32();
                byte metal = IsMetallic(s) ? (byte)Mathf.RoundToInt(0.85f * 255f) : (byte)0;
                var o = new Color32[px.Length];
                for (int i = 0; i < px.Length; i++)
                    o[i] = new Color32(metal, 0, 0, (byte)(255 - px[i].r));

                dst = new Texture2D(src.width, src.height, TextureFormat.RGBA32, false, true);
                dst.SetPixels32(o);
                dst.Apply(false);
                byte[] png = dst.EncodeToPNG();

                EnsureFolder(MaskDir);
                File.WriteAllBytes(FullPath(maskPath), png);
                return true;
            }
            finally
            {
                Object.DestroyImmediate(src);
                if (dst != null) Object.DestroyImmediate(dst);
            }
        }

        // ------------------------------------------------------------------ asset lookup / import

        /// <summary>
        /// Asset path of the first file in <paramref name="folder"/> named "&lt;key&gt;__*" (e.g. tex_Grass_albedo__aerial_grass_rock_1k.jpg).
        /// Uses AssetDatabase.FindAssets; files copied in while the editor has not refreshed yet are imported on demand.
        /// </summary>
        static string FindSource(string folder, string key)
        {
            string prefix = key + "__";
            if (AssetDatabase.IsValidFolder(folder))
            {
                foreach (string guid in AssetDatabase.FindAssets(key, new[] { folder }))
                {
                    string p = AssetDatabase.GUIDToAssetPath(guid);
                    if (Path.GetFileName(p).StartsWith(prefix, System.StringComparison.OrdinalIgnoreCase) &&
                        AssetDatabase.LoadMainAssetAtPath(p) != null)
                        return p;
                }
            }

            string full = FullPath(folder);
            if (!Directory.Exists(full)) return null;
            string[] files = Directory.GetFiles(full, prefix + "*");
            System.Array.Sort(files, System.StringComparer.OrdinalIgnoreCase);
            foreach (string f in files)
            {
                string ext = Path.GetExtension(f).ToLowerInvariant();
                if (ext != ".jpg" && ext != ".jpeg" && ext != ".png" && ext != ".hdr" && ext != ".exr") continue;
                string p = folder + "/" + Path.GetFileName(f);
                EnsureImported(p);
                if (AssetDatabase.LoadMainAssetAtPath(p) == null && !s_Refreshed)
                {
                    // Per-file import can fail for a folder the AssetDatabase has never seen: one full refresh, once per domain.
                    s_Refreshed = true;
                    AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                }
                if (AssetDatabase.LoadMainAssetAtPath(p) != null) return p;
            }
            return null;
        }

        /// <summary>Imports a file (and any parent folders) that exists on disk but is not in the AssetDatabase yet.</summary>
        static void EnsureImported(string assetPath)
        {
            string dir = Path.GetDirectoryName(assetPath).Replace('\\', '/');
            string[] parts = dir.Split('/');
            string cur = parts[0]; // "Assets"
            for (int k = 1; k < parts.Length; k++)
            {
                cur += "/" + parts[k];
                if (!AssetDatabase.IsValidFolder(cur) && Directory.Exists(FullPath(cur)))
                    AssetDatabase.ImportAsset(cur, ImportAssetOptions.ForceSynchronousImport);
            }
            if (AssetDatabase.LoadMainAssetAtPath(assetPath) == null && File.Exists(FullPath(assetPath)))
                AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceSynchronousImport);
        }

        static void EnsureFolder(string assetFolder)
        {
            if (AssetDatabase.IsValidFolder(assetFolder)) return;
            string[] parts = assetFolder.Split('/');
            string cur = parts[0];
            for (int k = 1; k < parts.Length; k++)
            {
                string next = cur + "/" + parts[k];
                if (!AssetDatabase.IsValidFolder(next))
                {
                    if (Directory.Exists(FullPath(next)))
                        AssetDatabase.ImportAsset(next, ImportAssetOptions.ForceSynchronousImport);
                    if (!AssetDatabase.IsValidFolder(next))
                        AssetDatabase.CreateFolder(cur, parts[k]);
                }
                cur = next;
            }
        }

        static string FullPath(string assetPath) =>
            Path.Combine(Path.GetDirectoryName(Application.dataPath), assetPath);
    }
}
