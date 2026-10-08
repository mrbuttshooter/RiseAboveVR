using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace AcrophobiaVR.EditorTools
{
    public enum Surface { Concrete, Asphalt, Pavement, Grass, Dirt, Wood, Metal, Grate, RoofGravel, Tiles, BrickFacade, OfficeFacade, GlassFacade, PlasterFacade }

    public struct TextureSet
    {
        public Texture2D albedo;
        public Texture2D normal;
        public Texture2D emission;
        public Vector2 tileMeters;
    }

    /// <summary>
    /// Editor-only procedural PBR texture generator. Every texture is tileable (custom periodic value / cellular
    /// noise), generated once, saved as PNG under <see cref="Dir"/> and then loaded as an asset.
    /// Albedo of tintable surfaces is kept neutral so one texture serves many _BaseColor tints.
    /// Texture V is "up" on vertical faces (facade floors stack along V).
    /// </summary>
    public static class ProceduralTextures
    {
        public const string Dir = "Assets/AcrophobiaVR/Generated/Textures";

        static readonly Dictionary<Surface, TextureSet> Cache = new Dictionary<Surface, TextureSet>();
        static readonly Color Warm = new Color(1f, 0.82f, 0.55f, 1f);

        enum Kind { Albedo, Normal, Emission }

        // ------------------------------------------------------------------ public API

        public static Vector2 TileMeters(Surface surface)
        {
            switch (surface)
            {
                case Surface.Concrete: return new Vector2(4f, 4f);
                case Surface.Asphalt: return new Vector2(6f, 6f);
                case Surface.Pavement: return new Vector2(2f, 2f);
                case Surface.Grass: return new Vector2(4f, 4f);
                case Surface.Dirt: return new Vector2(5f, 5f);
                case Surface.Wood: return new Vector2(2f, 2f);
                case Surface.Metal: return new Vector2(2f, 2f);
                case Surface.Grate: return new Vector2(1f, 1f);
                case Surface.RoofGravel: return new Vector2(4f, 4f);
                case Surface.Tiles: return new Vector2(2f, 2f);
                case Surface.BrickFacade: return new Vector2(6f, 7f);
                case Surface.OfficeFacade: return new Vector2(8f, 7f);
                case Surface.GlassFacade: return new Vector2(6f, 7f);
                case Surface.PlasterFacade: return new Vector2(6f, 7f);
                default: return new Vector2(4f, 4f);
            }
        }

        public static TextureSet Get(Surface surface)
        {
            bool facade = IsFacade(surface);
            if (Cache.TryGetValue(surface, out TextureSet cached) && cached.albedo != null && cached.normal != null &&
                (!facade || cached.emission != null))
                return cached;

            string aPath = PathFor(surface, "Albedo");
            string nPath = PathFor(surface, "Normal");
            string ePath = facade ? PathFor(surface, "Emission") : null;

            var set = new TextureSet { tileMeters = TileMeters(surface) };
            set.albedo = LoadExisting(aPath, Kind.Albedo, surface);
            set.normal = LoadExisting(nPath, Kind.Normal, surface);
            set.emission = facade ? LoadExisting(ePath, Kind.Emission, surface) : null;

            if (set.albedo == null || set.normal == null || (facade && set.emission == null))
            {
                EnsureFolder();
                Buf buf = Generate(surface);
                if (set.albedo == null)
                    set.albedo = Save(aPath, ToColor32(buf.a, surface == Surface.Grate), buf.n, Kind.Albedo, surface);
                if (set.normal == null)
                    set.normal = Save(nPath, NormalFromHeight(buf.h, buf.n, buf.strength), buf.n, Kind.Normal, surface);
                if (facade && set.emission == null)
                    set.emission = Save(ePath, ToColor32(buf.e, false), buf.n, Kind.Emission, surface);
            }

            Cache[surface] = set;
            return set;
        }

        // ------------------------------------------------------------------ asset IO

        static bool IsFacade(Surface s)
        {
            switch (s)
            {
                case Surface.BrickFacade:
                case Surface.OfficeFacade:
                case Surface.GlassFacade:
                case Surface.PlasterFacade:
                    return true;
                default:
                    return false;
            }
        }

        static string PathFor(Surface s, string suffix) => Dir + "/" + s + "_" + suffix + ".png";

        static string FullPath(string assetPath) =>
            Path.Combine(Path.GetDirectoryName(Application.dataPath), assetPath);

        static void EnsureFolder()
        {
            if (AssetDatabase.IsValidFolder(Dir)) return;
            string[] parts = Dir.Split('/');
            string cur = parts[0]; // "Assets"
            for (int k = 1; k < parts.Length; k++)
            {
                string next = cur + "/" + parts[k];
                if (!AssetDatabase.IsValidFolder(next))
                {
                    // Folder on disk but not yet imported: import it instead of creating "<name> 1".
                    if (Directory.Exists(FullPath(next)))
                        AssetDatabase.ImportAsset(next, ImportAssetOptions.ForceSynchronousImport);
                    if (!AssetDatabase.IsValidFolder(next))
                        AssetDatabase.CreateFolder(cur, parts[k]);
                }
                cur = next;
            }
        }

        static Texture2D LoadExisting(string path, Kind kind, Surface s)
        {
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            if (tex == null)
            {
                if (!File.Exists(FullPath(path))) return null;
                // PNG is on disk but not imported yet: import + configure, never regenerate.
                AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
                Configure(path, kind, s);
                return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            }

            var imp = AssetImporter.GetAtPath(path) as TextureImporter;
            if (imp != null && (imp.wrapMode != TextureWrapMode.Repeat || imp.alphaIsTransparency ||
                                (kind == Kind.Normal) != (imp.textureType == TextureImporterType.NormalMap)))
            {
                Configure(path, kind, s);
                tex = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            }
            return tex;
        }

        static Texture2D Save(string path, Color32[] pixels, int n, Kind kind, Surface s)
        {
            var tex = new Texture2D(n, n, TextureFormat.RGBA32, false);
            tex.SetPixels32(pixels);
            tex.Apply(false);
            byte[] png = tex.EncodeToPNG();
            UnityEngine.Object.DestroyImmediate(tex);

            File.WriteAllBytes(FullPath(path), png);
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate | ImportAssetOptions.ForceSynchronousImport);
            Configure(path, kind, s);

            var loaded = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            if (loaded == null) Debug.LogWarning("[ProceduralTextures] Could not load generated texture " + path);
            return loaded;
        }

        static void Configure(string path, Kind kind, Surface s)
        {
            var imp = AssetImporter.GetAtPath(path) as TextureImporter;
            if (imp == null) return;
            bool cutout = kind == Kind.Albedo && s == Surface.Grate;
            imp.textureType = kind == Kind.Normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
            imp.sRGBTexture = kind != Kind.Normal;
            imp.alphaSource = cutout ? TextureImporterAlphaSource.FromInput : TextureImporterAlphaSource.None;
            // Keep false: true dilates bar colour into alpha=0 pixels, erasing the dark grate holes on opaque materials.
            imp.alphaIsTransparency = false;
            imp.wrapMode = TextureWrapMode.Repeat;
            imp.mipmapEnabled = true;
            imp.anisoLevel = 4;
            imp.filterMode = FilterMode.Trilinear;
            imp.maxTextureSize = 512;
            imp.textureCompression = TextureImporterCompression.Compressed;
            imp.SaveAndReimport();
        }

        static Color32[] ToColor32(Color[] src, bool keepAlpha)
        {
            var o = new Color32[src.Length];
            for (int i = 0; i < src.Length; i++)
            {
                Color c = src[i];
                o[i] = new Color32(B(c.r), B(c.g), B(c.b), keepAlpha ? B(c.a) : (byte)255);
            }
            return o;
        }

        static byte B(float f) => (byte)Mathf.Clamp(Mathf.RoundToInt(f * 255f), 0, 255);

        /// <summary>Tangent-space normal map from a (wrapping) height field via Sobel. V up = +Y (green).</summary>
        static Color32[] NormalFromHeight(float[] h, int n, float strength)
        {
            var o = new Color32[n * n];
            for (int y = 0; y < n; y++)
            {
                int ym = ((y - 1 + n) % n) * n, y0 = y * n, yp = ((y + 1) % n) * n;
                for (int x = 0; x < n; x++)
                {
                    int xm = (x - 1 + n) % n, xp = (x + 1) % n;
                    float tl = h[yp + xm], t = h[yp + x], tr = h[yp + xp];
                    float l = h[y0 + xm], r = h[y0 + xp];
                    float bl = h[ym + xm], bm = h[ym + x], br = h[ym + xp];
                    float dx = (tr + 2f * r + br) - (tl + 2f * l + bl);
                    float dy = (tl + 2f * t + tr) - (bl + 2f * bm + br);
                    Vector3 nv = new Vector3(-dx * strength, -dy * strength, 1f).normalized;
                    o[y0 + x] = new Color32(B(nv.x * 0.5f + 0.5f), B(nv.y * 0.5f + 0.5f), B(nv.z * 0.5f + 0.5f), 255);
                }
            }
            return o;
        }

        // ------------------------------------------------------------------ noise (all periodic => seamless)

        static uint HashU(int x, int y, int seed)
        {
            unchecked
            {
                uint h = (uint)x * 0x8da6b343u ^ (uint)y * 0xd8163841u ^ (uint)seed * 0xcb1ab31fu;
                h ^= h >> 15; h *= 0x2c1b3c6du;
                h ^= h >> 12; h *= 0x297a2d39u;
                h ^= h >> 15;
                return h;
            }
        }

        static float Hash01(int x, int y, int seed) => (HashU(x, y, seed) & 0xFFFFFFu) / 16777215f;

        static int Wrap(int a, int p) { int r = a % p; return r < 0 ? r + p : r; }

        static float Frac(float x) => x - Mathf.Floor(x);

        static float SS(float e0, float e1, float x)
        {
            float t = Mathf.Clamp01((x - e0) / (e1 - e0));
            return t * t * (3f - 2f * t);
        }

        static float ValueNoise(float x, float y, int px, int py, int seed)
        {
            int x0 = Mathf.FloorToInt(x), y0 = Mathf.FloorToInt(y);
            float fx = x - x0, fy = y - y0;
            fx = fx * fx * (3f - 2f * fx);
            fy = fy * fy * (3f - 2f * fy);
            int xa = Wrap(x0, px), xb = Wrap(x0 + 1, px), ya = Wrap(y0, py), yb = Wrap(y0 + 1, py);
            float a = Hash01(xa, ya, seed), b = Hash01(xb, ya, seed);
            float c = Hash01(xa, yb, seed), d = Hash01(xb, yb, seed);
            return Mathf.Lerp(Mathf.Lerp(a, b, fx), Mathf.Lerp(c, d, fx), fy);
        }

        /// <summary>Tileable value noise; px/py = lattice cells per tile along U/V.</summary>
        static float Noise(float u, float v, int px, int py, int seed) => ValueNoise(u * px, v * py, px, py, seed);

        static float Fbm(float u, float v, int px, int py, int octaves, int seed)
        {
            float sum = 0f, amp = 0.5f, norm = 0f;
            for (int o = 0; o < octaves; o++)
            {
                sum += amp * ValueNoise(u * px, v * py, px, py, seed + o * 101);
                norm += amp;
                amp *= 0.5f; px *= 2; py *= 2;
            }
            return sum / norm;
        }

        /// <summary>Tileable cellular noise; distances in cell units.</summary>
        static void Worley(float u, float v, int cells, int seed, out float f1, out float f2, out int id)
        {
            float x = u * cells, y = v * cells;
            int cx = Mathf.FloorToInt(x), cy = Mathf.FloorToInt(y);
            f1 = 9f; f2 = 9f; id = 0;
            for (int oy = -1; oy <= 1; oy++)
            for (int ox = -1; ox <= 1; ox++)
            {
                int gx = cx + ox, gy = cy + oy;
                int wx = Wrap(gx, cells), wy = Wrap(gy, cells);
                float dx = gx + 0.1f + 0.8f * Hash01(wx, wy, seed) - x;
                float dy = gy + 0.1f + 0.8f * Hash01(wx, wy, seed + 7) - y;
                float d = dx * dx + dy * dy;
                if (d < f1) { f2 = f1; f1 = d; id = wx + wy * cells; }
                else if (d < f2) f2 = d;
            }
            f1 = Mathf.Sqrt(f1); f2 = Mathf.Sqrt(f2);
        }

        static Color Grey(float l) => new Color(l, l, l, 1f);

        static float Inside(float x, float y, float x0, float y0, float x1, float y1) =>
            Mathf.Min(Mathf.Min(x - x0, x1 - x), Mathf.Min(y - y0, y1 - y));

        /// <summary>Anti-aliased coverage of a signed distance (positive = inside).</summary>
        static float Cov(float d, float soft) => Mathf.Clamp01(d / soft + 0.5f);

        // ------------------------------------------------------------------ buffers

        sealed class Buf
        {
            public readonly int n;
            public readonly float[] h;
            public readonly Color[] a;
            public readonly Color[] e;
            public float strength = 1f;

            public Buf(int n, bool emissive)
            {
                this.n = n;
                h = new float[n * n];
                a = new Color[n * n];
                e = emissive ? new Color[n * n] : null;
            }
        }

        delegate void PixelFn(int x, int y, float u, float v, int i);

        static void Each(Buf buf, PixelFn fn)
        {
            int n = buf.n;
            float inv = 1f / n;
            for (int y = 0; y < n; y++)
            {
                float v = (y + 0.5f) * inv;
                for (int x = 0; x < n; x++) fn(x, y, (x + 0.5f) * inv, v, y * n + x);
            }
        }

        static Buf Generate(Surface s)
        {
            int res = s == Surface.Grate ? 256 : 512;
            var b = new Buf(res, IsFacade(s));
            switch (s)
            {
                case Surface.Concrete: Concrete(b); break;
                case Surface.Asphalt: Asphalt(b); break;
                case Surface.Pavement: Pavement(b); break;
                case Surface.Grass: Grass(b); break;
                case Surface.Dirt: Dirt(b); break;
                case Surface.Wood: Wood(b); break;
                case Surface.Metal: Metal(b); break;
                case Surface.Grate: Grate(b); break;
                case Surface.RoofGravel: RoofGravel(b); break;
                case Surface.Tiles: Tiles(b); break;
                case Surface.BrickFacade: BrickFacade(b); break;
                case Surface.OfficeFacade: OfficeFacade(b); break;
                case Surface.GlassFacade: GlassFacade(b); break;
                case Surface.PlasterFacade: PlasterFacade(b); break;
            }
            return b;
        }

        // ------------------------------------------------------------------ ground / material surfaces

        static void Concrete(Buf b)
        {
            b.strength = 1.6f;
            Each(b, (x, y, u, v, i) =>
            {
                float low = Fbm(u, v, 3, 3, 3, 11);
                float mid = Fbm(u, v, 16, 16, 3, 12);
                float fine = Noise(u, v, 160, 160, 13);
                float pore = SS(0.80f, 0.93f, Noise(u, v, 224, 224, 14));
                float crack = 1f - SS(0.004f, 0.014f, Mathf.Abs(Fbm(u, v, 5, 5, 4, 15) - 0.5f));
                crack *= SS(0.52f, 0.62f, Fbm(u, v, 2, 2, 2, 16));
                float l = 0.80f + (low - 0.5f) * 0.30f + (mid - 0.5f) * 0.14f + (fine - 0.5f) * 0.08f - pore * 0.16f - crack * 0.16f;
                b.a[i] = new Color(l, l * 0.995f, l * 0.98f, 1f);
                b.h[i] = mid * 0.35f + fine * 0.10f - pore * 0.30f - crack * 0.35f;
            });
        }

        static void Asphalt(Buf b)
        {
            b.strength = 1.4f;
            Each(b, (x, y, u, v, i) =>
            {
                float low = Fbm(u, v, 3, 3, 3, 21);
                float grain = Noise(u, v, 200, 200, 22);
                float px = Hash01(x, y, 23);
                float speck = SS(0.76f, 0.88f, grain);
                float pit = SS(0.22f, 0.10f, grain);
                float cr = 1f - SS(0.003f, 0.010f, Mathf.Abs(Fbm(u, v, 4, 4, 4, 24) - 0.5f));
                cr *= SS(0.50f, 0.60f, Fbm(u, v, 2, 2, 2, 25));
                float patch = SS(0.60f, 0.64f, Fbm(u, v, 3, 3, 3, 26));
                float l = 0.20f + (low - 0.5f) * 0.10f + (px - 0.5f) * 0.05f + speck * 0.16f - pit * 0.05f - patch * 0.05f - cr * 0.11f;
                b.a[i] = new Color(l * 0.98f + speck * 0.02f, l * 0.99f + speck * 0.01f, l * 1.02f, 1f);
                b.h[i] = grain * 0.30f + speck * 0.20f + px * 0.05f - cr * 0.5f + patch * 0.04f;
            });
        }

        static void Pavement(Buf b)
        {
            b.strength = 1.6f;
            Each(b, (x, y, u, v, i) =>
            {
                // 2 x 2 slabs per tile => 1 m slabs, distances in meters
                float sx = u * 2f, sy = v * 2f;
                int ix = Mathf.FloorToInt(sx), iy = Mathf.FloorToInt(sy);
                float fx = sx - ix, fy = sy - iy;
                float d = Mathf.Min(Mathf.Min(fx, 1f - fx), Mathf.Min(fy, 1f - fy));
                float joint = 1f - SS(0.003f, 0.007f, d);
                float bevel = SS(0.004f, 0.018f, d);
                float slab = Hash01(Wrap(ix, 2), Wrap(iy, 2), 31) - 0.5f;
                float grain = Noise(u, v, 180, 180, 32);
                float low = Fbm(u, v, 4, 4, 3, 33);
                float pit = SS(0.84f, 0.95f, Noise(u, v, 300, 300, 34));
                float l = 0.84f + slab * 0.10f + (grain - 0.5f) * 0.10f + (low - 0.5f) * 0.16f - pit * 0.12f - (1f - bevel) * 0.06f;
                l = Mathf.Lerp(l, 0.50f, joint);
                b.a[i] = new Color(l, l, l * 0.985f, 1f);
                b.h[i] = bevel * 0.8f + grain * 0.06f - pit * 0.12f + slab * 0.04f;
            });
        }

        static void Grass(Buf b)
        {
            b.strength = 1.3f;
            Color dark = new Color(0.12f, 0.22f, 0.06f), midG = new Color(0.22f, 0.36f, 0.10f);
            Color lightG = new Color(0.38f, 0.48f, 0.16f), dry = new Color(0.47f, 0.43f, 0.24f), soil = new Color(0.24f, 0.18f, 0.11f);
            Each(b, (x, y, u, v, i) =>
            {
                float low = Fbm(u, v, 3, 3, 3, 41);
                float m = Fbm(u, v, 10, 10, 3, 42);
                float blades = Noise(u, v, 256, 96, 43) * 0.6f + Noise(u, v, 96, 256, 44) * 0.4f;
                float px = Hash01(x, y, 45);
                Color c = Color.Lerp(dark, midG, SS(0.35f, 0.65f, low));
                c = Color.Lerp(c, lightG, SS(0.52f, 0.72f, m) * 0.6f);
                c = Color.Lerp(c, dry, SS(0.58f, 0.70f, Fbm(u, v, 5, 5, 3, 46)) * 0.65f);
                c *= 0.70f + blades * 0.45f + (px - 0.5f) * 0.18f;
                c = Color.Lerp(c, soil, SS(0.30f, 0.15f, blades) * 0.5f);
                c.a = 1f;
                b.a[i] = c;
                b.h[i] = blades * 0.6f + px * 0.12f + m * 0.2f;
            });
        }

        static void Dirt(Buf b)
        {
            b.strength = 1.5f;
            Color dry = new Color(0.50f, 0.40f, 0.28f), wet = new Color(0.31f, 0.23f, 0.15f);
            Color red = new Color(0.47f, 0.33f, 0.22f), stone = new Color(0.56f, 0.53f, 0.48f);
            Each(b, (x, y, u, v, i) =>
            {
                float low = Fbm(u, v, 3, 3, 4, 51);
                float m = Fbm(u, v, 10, 10, 3, 52);
                float fine = Noise(u, v, 200, 200, 53);
                Worley(u, v, 40, 54, out float f1, out float f2, out int id);
                float hasStone = Hash01(id, 3, 55) > 0.55f ? 1f : 0f;
                float rad = 0.18f + 0.14f * Hash01(id, 4, 55);
                float pebble = SS(rad, rad * 0.6f, f1) * hasStone;
                Color c = Color.Lerp(dry, wet, SS(0.42f, 0.62f, low));
                c = Color.Lerp(c, red, SS(0.5f, 0.7f, m) * 0.45f);
                c *= 0.82f + fine * 0.32f;
                Color sc = stone * (0.75f + 0.4f * Hash01(id, 5, 55));
                c = Color.Lerp(c, sc, pebble);
                c.a = 1f;
                b.a[i] = c;
                float dome = Mathf.Clamp01(1f - f1 / rad);
                b.h[i] = m * 0.3f + fine * 0.15f + pebble * (0.25f + 0.35f * Mathf.Sqrt(dome));
            });
        }

        static void Wood(Buf b)
        {
            b.strength = 1.6f;
            const int planks = 14; // planks run along U, stacked along V (0.143 m wide on a 2 m tile)
            Color lightW = new Color(0.64f, 0.46f, 0.29f), darkW = new Color(0.42f, 0.27f, 0.15f), gapC = new Color(0.05f, 0.035f, 0.025f);
            Each(b, (x, y, u, v, i) =>
            {
                float pv = v * planks;
                int row = Mathf.FloorToInt(pv);
                float fy = pv - row;
                row = Wrap(row, planks);
                float j = Hash01(row, 0, 61);                 // staggered butt joints, 2 per row (1 m boards)
                float local = Frac(u - j);
                int seg = local < 0.5f ? 0 : 1;
                float du = Mathf.Min(Mathf.Min(local, 1f - local), Mathf.Abs(local - 0.5f)) * 2f; // meters
                float joint = 1f - SS(0.0015f, 0.004f, du);
                float gapD = Mathf.Min(fy, 1f - fy);
                float gap = 1f - SS(0.02f, 0.045f, gapD);
                float tone = Hash01(row, seg, 62);
                float warp = Fbm(u, v, 4, planks * 2, 2, 63);
                float rings = 0.5f + 0.5f * Mathf.Sin((fy * 3.5f + warp * 2.5f + tone * 7f) * Mathf.PI * 2f);
                rings = rings * rings * rings;
                float fibers = Noise(u, v, 6, 384, 64);
                float low = Fbm(u, v, 2, 2, 2, 65);
                float edge = SS(0.03f, 0.12f, gapD);
                Color c = Color.Lerp(darkW, lightW, tone * 0.7f + 0.15f);
                c *= (0.80f + 0.2f * (1f - rings)) * (0.90f + 0.18f * fibers) * (0.92f + (low - 0.5f) * 0.25f) * (0.85f + 0.15f * edge);
                float g = Mathf.Max(gap, joint);
                c = Color.Lerp(c, gapC, g);
                c.a = 1f;
                b.a[i] = c;
                b.h[i] = (1f - g) * (0.55f + 0.25f * edge) + fibers * 0.05f - rings * 0.03f;
            });
        }

        static void Metal(Buf b)
        {
            b.strength = 0.9f;
            Each(b, (x, y, u, v, i) =>
            {
                float s = Noise(u, v, 3, 384, 71) * 0.6f + Noise(u, v, 8, 192, 72) * 0.4f; // brushed along U
                float low = Fbm(u, v, 3, 3, 3, 73);
                float px = Hash01(x, y, 74);
                float l = 0.80f + (s - 0.5f) * 0.16f + (low - 0.5f) * 0.14f + (px - 0.5f) * 0.03f;
                b.a[i] = new Color(l, l, l * 1.01f, 1f);
                b.h[i] = s * 0.2f + low * 0.1f;
            });
        }

        static void Grate(Buf b)
        {
            b.strength = 1.4f;
            const int cells = 16; // ~6 cm openings on a 1 m tile
            Each(b, (x, y, u, v, i) =>
            {
                float cx = Frac(u * cells), cy = Frac(v * cells);
                float dx = Mathf.Min(cx, 1f - cx), dy = Mathf.Min(cy, 1f - cy);
                float barA = 1f - SS(0.085f, 0.115f, dx); // bearing bars
                float barB = 1f - SS(0.06f, 0.09f, dy);   // cross bars
                float bar = Mathf.Max(barA, barB);
                float grime = Fbm(u, v, 4, 4, 3, 81);
                float px = Hash01(x, y, 82);
                float crown = Mathf.Max(SS(0.06f, 0f, dx) * barA, SS(0.04f, 0f, dy) * barB);
                float l = 0.64f + (grime - 0.5f) * 0.25f + (px - 0.5f) * 0.05f + crown * 0.08f;
                float hole = 0.05f + 0.04f * grime;
                float g = Mathf.Lerp(hole, l, bar);
                b.a[i] = new Color(g, g, g, bar);  // alpha = bars (usable for alpha clipping)
                b.h[i] = Mathf.Max(barA, barB * 0.8f);
            });
        }

        static void RoofGravel(Buf b)
        {
            b.strength = 1.5f;
            Each(b, (x, y, u, v, i) =>
            {
                Worley(u, v, 72, 91, out float f1, out float f2, out int id);
                float tone = Hash01(id, 1, 92);
                float crevice = 1f - SS(0.03f, 0.18f, f2 - f1);
                float dome = Mathf.Clamp01(1f - f1 / 0.75f);
                float px = Hash01(x, y, 93);
                float low = Fbm(u, v, 3, 3, 3, 94);
                float l = 0.66f + tone * 0.30f - crevice * 0.32f + (px - 0.5f) * 0.08f + (low - 0.5f) * 0.12f;
                b.a[i] = new Color(l, l * 0.99f, l * 0.97f, 1f);
                b.h[i] = Mathf.Sqrt(dome) * (1f - crevice * 0.6f) * 0.7f + px * 0.04f;
            });
        }

        static void Tiles(Buf b)
        {
            b.strength = 1.6f;
            const int count = 8; // 25 cm tiles on a 2 m tile
            Each(b, (x, y, u, v, i) =>
            {
                float tx = u * count, ty = v * count;
                int ix = Mathf.FloorToInt(tx), iy = Mathf.FloorToInt(ty);
                float fx = tx - ix, fy = ty - iy;
                float d = Mathf.Min(Mathf.Min(fx, 1f - fx), Mathf.Min(fy, 1f - fy));
                float grout = 1f - SS(0.014f, 0.026f, d);
                float bevel = SS(0.015f, 0.06f, d);
                float tone = Hash01(Wrap(ix, count), Wrap(iy, count), 101);
                float speck = Noise(u, v, 128, 128, 102);
                float grime = Fbm(u, v, 4, 4, 3, 103);
                float l = 0.90f + (tone - 0.5f) * 0.07f + (speck - 0.5f) * 0.05f - (1f - bevel) * 0.04f;
                l = Mathf.Lerp(l, 0.62f + (grime - 0.5f) * 0.2f, grout);
                b.a[i] = new Color(l, l, l, 1f);
                b.h[i] = (1f - grout) * (0.5f + 0.3f * bevel) + speck * 0.02f + (tone - 0.5f) * 0.03f;
            });
        }

        // ------------------------------------------------------------------ facades

        /// <summary>Chooses ~30% of the windows (at least one) to be lit, deterministically.</summary>
        static bool[] PickLit(int count, int seed)
        {
            var keys = new float[count];
            var order = new int[count];
            for (int k = 0; k < count; k++) { keys[k] = Hash01(k, 0, seed); order[k] = k; }
            System.Array.Sort(keys, order);
            int litCount = Mathf.Max(1, Mathf.RoundToInt(count * 0.3f));
            var lit = new bool[count];
            for (int k = 0; k < litCount; k++) lit[order[k]] = true;
            return lit;
        }

        static Color LitColor(int pane, int seed, float gy, float scale)
        {
            float k = scale * (0.65f + 0.35f * Hash01(pane, 9, seed)) * (0.75f + 0.25f * gy);
            return new Color(Warm.r * k, Warm.g * k, Warm.b * k, 1f);
        }

        /// <summary>Dark blue-grey window glass with a sky-reflection gradient.</summary>
        static Color Glass(float gx, float gy, int pane, int seed)
        {
            float ph = Hash01(pane, 11, seed);
            float t = Mathf.Clamp01(gy * 0.85f + (ph - 0.5f) * 0.35f + 0.1f);
            Color c = Color.Lerp(new Color(0.06f, 0.08f, 0.10f), new Color(0.24f, 0.29f, 0.35f), t * t);
            float diag = Frac(gx * 0.5f + gy * 0.9f + ph);
            c += new Color(0.05f, 0.055f, 0.06f, 0f) * SS(0.25f, 0f, Mathf.Abs(diag - 0.5f));
            c.a = 1f;
            return c;
        }

        /// <summary>One glass pane: reflection, optional interior blinds, warm emission when lit.</summary>
        static void Pane(float gx, float gy, float heightM, int pane, bool lit, int seed, out Color albedo, out Color emission)
        {
            Color c = Glass(gx, gy, pane, seed);
            bool blinds = false;
            if (Hash01(pane, 7, seed) < 0.4f)
            {
                float drop = 0.2f + 0.5f * Hash01(pane, 8, seed);
                if (gy > 1f - drop)
                {
                    blinds = true;
                    float slat = 0.5f + 0.5f * Mathf.Sin(gy * heightM / 0.05f * Mathf.PI * 2f);
                    c = Color.Lerp(c, new Color(0.46f, 0.45f, 0.42f) * (0.85f + 0.15f * slat), 0.85f);
                }
            }
            c.a = 1f;
            albedo = c;
            emission = lit ? LitColor(pane, seed, gy, blinds ? 0.8f : 1f) : Color.black;
        }

        /// <summary>A recessed window with light frame, centre mullion and transom. ox/oy are meters inside the opening.</summary>
        static void PaintWindow(float ox, float oy, float w, float h, float frame, float bar, int win, bool lit, int seed,
            float soft, out Color albedo, out Color emission, out float height)
        {
            float fd = Mathf.Min(Mathf.Min(ox, w - ox), Mathf.Min(oy, h - oy));
            float fm = 1f - Cov(fd - frame, soft);
            fm = Mathf.Max(fm, 1f - Cov(Mathf.Abs(ox - w * 0.5f) - bar, soft));
            fm = Mathf.Max(fm, 1f - Cov(Mathf.Abs(oy - h * 0.72f) - bar, soft));
            Pane(ox / w, oy / h, h, win, lit, seed, out Color g, out Color e);
            float shade = 1f - 0.4f * SS(0.22f, 0f, h - oy) - 0.15f * SS(0.12f, 0f, ox); // reveal shadow (head + jamb)
            Color fc = new Color(0.90f, 0.90f, 0.89f, 1f) * shade;
            g *= shade;
            albedo = Color.Lerp(g, fc, fm);
            albedo.a = 1f;
            emission = e * (1f - fm);
            emission.a = 1f;
            height = Mathf.Lerp(0.08f, 0.38f, fm);
        }

        static void BrickFacade(Buf b)
        {
            const float W = 6f, H = 7f;
            const int cols = 2, rows = 2, courses = 90, bricksPerRow = 26;
            const float wx0 = 0.8f, wx1 = 2.2f, wy0 = 0.95f, wy1 = 2.75f;
            float cw = W / cols, ch = H / rows, courseH = H / courses, brickW = W / bricksPerRow;
            float soft = W / b.n;
            bool[] lit = PickLit(cols * rows, 201);
            b.strength = 1.2f;
            Each(b, (x, y, u, v, i) =>
            {
                float mx = u * W, my = v * H;
                int col = Mathf.Min(Mathf.FloorToInt(mx / cw), cols - 1), row = Mathf.Min(Mathf.FloorToInt(my / ch), rows - 1);
                float lx = mx - col * cw, ly = my - row * ch;
                int win = row * cols + col;

                // running-bond brickwork
                int r = Mathf.FloorToInt(my / courseH);
                float fyc = my - r * courseH;
                float bxp = mx + ((r & 1) == 1 ? brickW * 0.5f : 0f);
                int bi = Mathf.FloorToInt(bxp / brickW);
                float fxc = bxp - bi * brickW;
                int bw = Wrap(bi, bricksPerRow), brw = Wrap(r, courses);
                float md = Mathf.Min(Mathf.Min(fxc, brickW - fxc), Mathf.Min(fyc, courseH - fyc));
                float mortar = 1f - Cov(md - 0.007f, soft * 0.6f); // ~1 px joint at 512 px / 7 m so courses stay visible
                float tone = Hash01(bw, brw, 202);
                float burnt = Hash01(bw, brw, 203) < 0.12f ? 1f : 0f;
                float face = Noise(u, v, 160, 180, 204);
                float low = Fbm(u, v, 3, 4, 3, 205);
                float wallL = 0.70f + tone * 0.20f - burnt * 0.14f + (face - 0.5f) * 0.10f + (low - 0.5f) * 0.10f;
                wallL = Mathf.Lerp(wallL, 0.93f + (face - 0.5f) * 0.05f, mortar);
                if (lx > wx0 && lx < wx1 && ly < wy0 - 0.09f) // rain streaks below the sill
                {
                    float fade = SS(wy0 - 1.3f, wy0 - 0.1f, ly) * SS(wx0, wx0 + 0.1f, lx) * SS(wx1, wx1 - 0.1f, lx);
                    wallL *= 1f - fade * SS(0.4f, 0.8f, Noise(u, v, 96, 2, 206)) * 0.18f;
                    wallL *= 1f - 0.25f * SS(0.10f, 0f, (wy0 - 0.09f) - ly); // sill shadow
                }
                Color alb = Grey(wallL);
                Color emi = Color.black;
                float hgt = Mathf.Lerp(0.70f + face * 0.08f, 0.50f, mortar);

                // stone lintel and sill
                float stoneL = 0.90f + (face - 0.5f) * 0.06f;
                float lin = Cov(Inside(lx, ly, wx0 - 0.10f, wy1, wx1 + 0.10f, wy1 + 0.20f), soft);
                alb = Color.Lerp(alb, Grey(stoneL), lin);
                hgt = Mathf.Lerp(hgt, 0.85f, lin);
                float sill = Cov(Inside(lx, ly, wx0 - 0.07f, wy0 - 0.09f, wx1 + 0.07f, wy0 + 0.01f), soft);
                alb = Color.Lerp(alb, Grey(stoneL + 0.03f), sill);
                hgt = Mathf.Lerp(hgt, 1f, sill);

                float open = Cov(Inside(lx, ly, wx0, wy0, wx1, wy1), soft);
                if (open > 0f)
                {
                    PaintWindow(lx - wx0, ly - wy0, wx1 - wx0, wy1 - wy0, 0.07f, 0.03f, win, lit[win], 207, soft,
                        out Color wa, out Color we, out float wh);
                    alb = Color.Lerp(alb, wa, open);
                    emi = we * open;
                    hgt = Mathf.Lerp(hgt, wh, open);
                }
                alb.a = 1f; emi.a = 1f;
                b.a[i] = alb; b.e[i] = emi; b.h[i] = hgt;
            });
        }

        static void OfficeFacade(Buf b)
        {
            const float W = 8f, H = 7f;
            const int cols = 4, rows = 2;
            const float gy0 = 1.0f, gy1 = 3.1f, mull = 0.06f; // ribbon window between horizontal spandrel bands
            float cw = W / cols, ch = H / rows;
            float soft = W / b.n;
            bool[] lit = PickLit(cols * rows, 301);
            b.strength = 1.2f;
            Each(b, (x, y, u, v, i) =>
            {
                float mx = u * W, my = v * H;
                int col = Mathf.Min(Mathf.FloorToInt(mx / cw), cols - 1), row = Mathf.Min(Mathf.FloorToInt(my / ch), rows - 1);
                float lx = mx - col * cw, ly = my - row * ch;
                int win = row * cols + col;
                float face = Noise(u, v, 200, 180, 302);
                float low = Fbm(u, v, 4, 3, 3, 303);

                // spandrel panels (neutral wall area) with panel seams
                float l = 0.84f + (face - 0.5f) * 0.06f + (low - 0.5f) * 0.10f;
                float hgt = 0.65f + face * 0.04f;
                float seamD = Mathf.Min(Mathf.Min(lx, cw - lx), Mathf.Min(Mathf.Min(ly, ch - ly), Mathf.Abs(ly - 0.5f)));
                float seam = 1f - Cov(seamD - 0.006f, soft);
                l = Mathf.Lerp(l, 0.55f, seam);
                hgt = Mathf.Lerp(hgt, 0.45f, seam);
                Color alb = Grey(l);
                Color emi = Color.black;

                float ribbon = Cov(Mathf.Min(ly - gy0, gy1 - ly), soft);
                if (ribbon > 0f)
                {
                    float mullD = Mathf.Min(lx, cw - lx);
                    float bandD = Mathf.Min(ly - gy0, gy1 - ly);
                    float fm = Mathf.Max(1f - Cov(mullD - mull, soft), 1f - Cov(bandD - 0.035f, soft));
                    Pane(lx / cw, (ly - gy0) / (gy1 - gy0), gy1 - gy0, win, lit[win], 304, out Color g, out Color e);
                    g *= 1f - 0.35f * SS(0.3f, 0f, gy1 - ly); // shadow cast by the spandrel above
                    Color wa = Color.Lerp(g, Grey(0.70f + (face - 0.5f) * 0.04f), fm);
                    alb = Color.Lerp(alb, wa, ribbon);
                    emi = e * ((1f - fm) * ribbon);
                    hgt = Mathf.Lerp(hgt, Mathf.Lerp(0.12f, 0.85f, fm), ribbon);
                }
                alb.a = 1f; emi.a = 1f;
                b.a[i] = alb; b.e[i] = emi; b.h[i] = hgt;
            });
        }

        static void GlassFacade(Buf b)
        {
            const float W = 6f, H = 7f;
            const int cols = 4, rows = 2;
            const float spandrelTop = 0.9f;
            float cw = W / cols, ch = H / rows;
            float soft = W / b.n;
            bool[] lit = PickLit(cols * rows, 401);
            b.strength = 1.0f;
            Each(b, (x, y, u, v, i) =>
            {
                float mx = u * W, my = v * H;
                int col = Mathf.Min(Mathf.FloorToInt(mx / cw), cols - 1), row = Mathf.Min(Mathf.FloorToInt(my / ch), rows - 1);
                float lx = mx - col * cw, ly = my - row * ch;
                int win = row * cols + col;
                float refl = Fbm(u, v, 2, 2, 3, 402); // large-scale sky reflection variation

                float mullD = Mathf.Min(lx, cw - lx);
                float floorD = Mathf.Min(ly, ch - ly);
                float transD = Mathf.Abs(ly - spandrelTop);
                float m = Mathf.Max(1f - Cov(mullD - 0.03f, soft),
                    Mathf.Max(1f - Cov(floorD - 0.04f, soft), 1f - Cov(transD - 0.025f, soft)));

                Color alb;
                Color emi = Color.black;
                if (ly < spandrelTop)
                {
                    float st = ly / spandrelTop;
                    alb = Color.Lerp(new Color(0.07f, 0.10f, 0.14f), new Color(0.11f, 0.15f, 0.20f), st);
                    alb *= 0.9f + 0.2f * refl;
                }
                else
                {
                    float gy = (ly - spandrelTop) / (ch - spandrelTop);
                    float ph = Hash01(win, 11, 403);
                    float vt = Mathf.Clamp01(gy * 0.7f + (ph - 0.5f) * 0.25f + (refl - 0.5f) * 0.8f + 0.15f);
                    alb = Color.Lerp(new Color(0.10f, 0.16f, 0.23f), new Color(0.30f, 0.39f, 0.48f), vt);
                    float diag = Frac(lx / cw * 0.4f + gy * 0.8f + ph);
                    alb += new Color(0.04f, 0.05f, 0.06f, 0f) * SS(0.2f, 0f, Mathf.Abs(diag - 0.5f));
                    if (lit[win]) emi = LitColor(win, 404, gy, 0.7f);
                }
                alb = Color.Lerp(alb, new Color(0.40f, 0.43f, 0.46f), m);
                emi *= 1f - m;
                alb.a = 1f; emi.a = 1f;
                b.a[i] = alb; b.e[i] = emi;
                b.h[i] = Mathf.Lerp(0.3f, 0.9f, m);
            });
        }

        static void PlasterFacade(Buf b)
        {
            const float W = 6f, H = 7f;
            const int cols = 2, rows = 2;
            const float wx0 = 0.95f, wx1 = 2.05f, wy0 = 1.0f, wy1 = 2.65f, sur = 0.12f, shutW = 0.55f;
            float cw = W / cols, ch = H / rows;
            float soft = W / b.n;
            bool[] lit = PickLit(cols * rows, 501);
            b.strength = 1.3f;
            Each(b, (x, y, u, v, i) =>
            {
                float mx = u * W, my = v * H;
                int col = Mathf.Min(Mathf.FloorToInt(mx / cw), cols - 1), row = Mathf.Min(Mathf.FloorToInt(my / ch), rows - 1);
                float lx = mx - col * cw, ly = my - row * ch;
                int win = row * cols + col;

                // stucco wall
                float stucco = Noise(u, v, 256, 256, 502);
                float grit = Hash01(x, y, 503);
                float low = Fbm(u, v, 3, 3, 4, 504);
                float l = 0.88f + (stucco - 0.5f) * 0.06f + (grit - 0.5f) * 0.03f + (low - 0.5f) * 0.14f;
                float hgt = 0.6f + stucco * 0.10f + grit * 0.03f;
                if (lx > wx0 - 0.2f && lx < wx1 + 0.2f && ly < wy0 - 0.1f) // dirt streaks under the sill
                {
                    float fade = SS(wy0 - 1.6f, wy0 - 0.1f, ly) * SS(wx0 - 0.2f, wx0, lx) * SS(wx1 + 0.2f, wx1, lx);
                    l -= fade * SS(0.45f, 0.8f, Noise(u, v, 128, 3, 505)) * 0.16f;
                    if (lx > wx0 - sur - 0.06f && lx < wx1 + sur + 0.06f)
                        l *= 1f - 0.3f * SS(0.12f, 0f, (wy0 - 0.11f) - ly); // sill shadow
                }
                l *= 1f - 0.15f * SS(ch - 0.12f, ch, ly); // shadow under the next floor's string course

                // string course at each floor
                float band = Cov(0.18f - ly, soft);
                l = Mathf.Lerp(l, 0.95f + (stucco - 0.5f) * 0.03f, band);
                hgt = Mathf.Lerp(hgt, 0.85f, band);
                Color alb = Grey(l);
                Color emi = Color.black;

                // louvered shutters either side of the window
                float shL = Cov(Inside(lx, ly, wx0 - sur - shutW, wy0, wx0 - sur, wy1), soft);
                float shR = Cov(Inside(lx, ly, wx1 + sur, wy0, wx1 + sur + shutW, wy1), soft);
                float sh = Mathf.Max(shL, shR);
                if (sh > 0f)
                {
                    float sx0 = shL > shR ? wx0 - sur - shutW : wx1 + sur;
                    float slx = lx - sx0, sly = ly - wy0;
                    float edge = Mathf.Min(Mathf.Min(slx, shutW - slx), Mathf.Min(sly, (wy1 - wy0) - sly));
                    float rim = 1f - Cov(edge - 0.045f, soft);
                    float slat = Frac(sly / 0.055f);
                    float sl = Mathf.Lerp(0.50f + 0.18f * slat, 0.62f, rim);
                    alb = Color.Lerp(alb, Grey(sl), sh);
                    hgt = Mathf.Lerp(hgt, Mathf.Lerp(0.72f + slat * 0.15f, 0.95f, rim), sh);
                }

                // window surround and protruding sill
                float surr = Cov(Inside(lx, ly, wx0 - sur, wy0 - 0.02f, wx1 + sur, wy1 + sur), soft);
                alb = Color.Lerp(alb, Grey(0.96f + (stucco - 0.5f) * 0.02f), surr);
                hgt = Mathf.Lerp(hgt, 0.8f, surr);
                float sill = Cov(Inside(lx, ly, wx0 - sur - 0.06f, wy0 - 0.11f, wx1 + sur + 0.06f, wy0), soft);
                alb = Color.Lerp(alb, Grey(0.93f), sill);
                hgt = Mathf.Lerp(hgt, 1f, sill);

                float open = Cov(Inside(lx, ly, wx0, wy0, wx1, wy1), soft);
                if (open > 0f)
                {
                    PaintWindow(lx - wx0, ly - wy0, wx1 - wx0, wy1 - wy0, 0.06f, 0.025f, win, lit[win], 506, soft,
                        out Color wa, out Color we, out float wh);
                    alb = Color.Lerp(alb, wa, open);
                    emi = we * open;
                    hgt = Mathf.Lerp(hgt, wh, open);
                }
                alb.a = 1f; emi.a = 1f;
                b.a[i] = alb; b.e[i] = emi; b.h[i] = hgt;
            });
        }
    }
}
