using UnityEditor;
using UnityEditor.AssetImporters;
using UnityEngine;

namespace AcrophobiaVR.EditorTools
{
    /// <summary>
    /// Import rules for the realistic model textures (Gemini Argon bakes and Poly Haven scans):
    /// "*_normal" / "*_nor_gl" become normal maps, and sizes are capped so the Quest build stays light.
    /// </summary>
    public class ModelTextureImporter : AssetPostprocessor
    {
        // Run after URP's own material-description converter so these settings win.
        public override int GetPostprocessOrder() => 100;

        void OnPreprocessTexture()
        {
            string p = assetPath.Replace('\\', '/');
            bool ours = p.Contains("/AcrophobiaVR/Models/") || p.Contains("/PolyHaven/Models/");
            if (!ours) return;
            var ti = (TextureImporter)assetImporter;
            string lower = p.ToLowerInvariant();
            if (lower.Contains("_normal") || lower.Contains("_nor_gl"))
            {
                ti.textureType = TextureImporterType.NormalMap;
                ti.sRGBTexture = false;
            }
            // Full detail on PC (desktop / PC VR); the standalone Quest gets a lighter copy of the same texture.
            ti.maxTextureSize = 4096;
            ti.mipmapEnabled = true;
            ti.anisoLevel = 8;
            var android = ti.GetPlatformTextureSettings("Android");
            android.overridden = true;
            android.maxTextureSize = lower.Contains("/bldg") ? 2048 : 1024;
            android.format = TextureImporterFormat.ASTC_6x6;
            ti.SetPlatformTextureSettings(android);
        }

        void OnPreprocessModel()
        {
            string p = assetPath.Replace('\\', '/');
            if (!p.Contains("/AcrophobiaVR/Models/")) return;
            var mi = (ModelImporter)assetImporter;
            // MakeHuman people share one Textures folder: find textures by name anywhere in the project.
            mi.materialSearch = ModelImporterMaterialSearch.Everywhere;
            mi.materialLocation = ModelImporterMaterialLocation.InPrefab;
            mi.importAnimation = false;
            mi.importCameras = false;
            mi.importLights = false;
        }

        /// <summary>
        /// Our models keep their textures in a "Textures" folder next to the FBX (the ten MakeHuman people share
        /// one). Build each URP Lit material straight from the texture file the FBX names, plus its "_normal"
        /// partner; MakeHuman hair, brows and lashes get alpha cutout.
        /// </summary>
        void OnPreprocessMaterialDescription(MaterialDescription description, Material material, AnimationClip[] clips)
        {
            string p = assetPath.Replace('\\', '/');
            if (!p.Contains("/AcrophobiaVR/Models/")) return;
            string texDir = p.Substring(0, p.LastIndexOf('/') + 1) + "Textures/";
            if (!AssetDatabase.IsValidFolder(texDir.TrimEnd('/'))) return;
            bool people = p.Contains("/Models/People/");
            string n = description.materialName.ToLowerInvariant();

            Texture tex = null;
            string texFile = null;
            if (description.TryGetProperty("DiffuseColor", out TexturePropertyDescription td))
            {
                texFile = td.relativePath ?? td.path;
                tex = td.texture != null ? td.texture : LoadModelTexture(texDir, texFile);
            }
            if (tex == null && people) tex = LoadModelTexture(texDir, texFile = TextureNamedInFbx(p, n.Replace("human.", "")));
            if (tex == null) return; // nothing of ours to bind: leave Unity's default material
            material.shader = Shader.Find("Universal Render Pipeline/Lit");
            material.SetTexture("_BaseMap", tex);
            material.SetTexture("_MainTex", tex);
            material.SetColor("_BaseColor", Color.white);

            string normalFile = tex.name.Replace("_albedo", "_normal").Replace("_diffuse", "_normal") + ".png";
            var nor = normalFile != tex.name + ".png" ? LoadModelTexture(texDir, normalFile) : null;
            if (nor != null)
            {
                material.SetTexture("_BumpMap", nor);
                material.EnableKeyword("_NORMALMAP");
            }

            bool cutout = people && (n.Contains("hair") || n.Contains("brow") || n.Contains("lash") || n.Contains("afro") || n.Contains("bob")
                          || n.Contains("ponytail") || n.Contains("braid") || n.Contains("short0"));
            if (cutout)
            {
                material.SetFloat("_Surface", 0f);
                material.SetFloat("_AlphaClip", 1f);
                material.SetFloat("_Cutoff", 0.45f);
                material.SetFloat("_Cull", 0f); // both sides of the hair cards
                material.EnableKeyword("_ALPHATEST_ON");
                material.renderQueue = (int)UnityEngine.Rendering.RenderQueue.AlphaTest;
            }
            material.SetFloat("_Metallic", 0f);
            bool car = p.Contains("/Models/Cars/");
            material.SetFloat("_Smoothness", n.Contains("low-poly") ? 0.85f : people ? 0.3f : car ? 0.55f : 0.2f); // "low-poly" is the eyeball mesh
            Debug.Log("[RA] model material " + description.materialName + " -> " + tex.name + (nor != null ? " +normal" : "") + (cutout ? " cutout" : ""));
        }

        /// <summary>
        /// Some MakeHuman parts don't link their texture to the FBX diffuse slot, but the file name is still
        /// stored in the FBX: pick the stored .png whose name matches the material (eyes are "low-poly").
        /// </summary>
        static string TextureNamedInFbx(string fbxPath, string matKey)
        {
            string text = System.Text.Encoding.ASCII.GetString(System.IO.File.ReadAllBytes(fbxPath));
            string key = matKey == "low-poly" ? "_eye" : matKey.TrimEnd('0', '1', '2', '3', '4', '5', '6', '7', '8', '9');
            string exact = null, loose = null;
            foreach (System.Text.RegularExpressions.Match m in System.Text.RegularExpressions.Regex.Matches(text, @"[A-Za-z0-9_\-]+\.png"))
            {
                string f = m.Value.ToLowerInvariant();
                if (f.Contains(matKey)) exact = m.Value;
                else if (f.Contains(key) && loose == null) loose = m.Value;
            }
            return exact ?? loose ?? matKey + "_diffuse.png";
        }

        Texture2D LoadModelTexture(string texDir, string file)
        {
            if (string.IsNullOrEmpty(file)) return null;
            string path = texDir + System.IO.Path.GetFileName(file.Replace('\\', '/'));
            context.DependsOnSourceAsset(path);
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }
    }
}
