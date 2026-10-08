using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace AcrophobiaVR.EditorTools
{
    /// <summary>
    /// Editor-only mesh helpers. Produces unit cubes whose UVs are pre-scaled so a tiling
    /// texture repeats at a fixed real-world size regardless of the object's scale.
    /// Meshes are intentionally scene-embedded (not saved as assets).
    /// </summary>
    public static class MeshUtil
    {
        static readonly Dictionary<string, Mesh> s_MeshCache = new Dictionary<string, Mesh>();

        /// <summary>Clears the mesh cache. Call at the start of building each scene.</summary>
        public static void ClearCache()
        {
            s_MeshCache.Clear();
        }

        /// <summary>
        /// Centered unit cube (positions in -0.5..0.5) with UVs scaled so that, when the object is
        /// scaled to <paramref name="size"/>, the texture repeats every tileMeters.x horizontally and
        /// tileMeters.y vertically on side faces (v anchored at the bottom, increasing upward).
        /// Top/bottom faces use tileMeters.x on both axes.
        /// </summary>
        public static Mesh TiledCube(Vector3 size, Vector2 tileMeters)
        {
            const float step = 0.05f;
            int kx = Mathf.Max(1, Mathf.RoundToInt(Mathf.Abs(size.x) / step));
            int ky = Mathf.Max(1, Mathf.RoundToInt(Mathf.Abs(size.y) / step));
            int kz = Mathf.Max(1, Mathf.RoundToInt(Mathf.Abs(size.z) / step));
            float tx = Mathf.Max(0.01f, Mathf.Abs(tileMeters.x));
            float ty = Mathf.Max(0.01f, Mathf.Abs(tileMeters.y));
            int ktx = Mathf.RoundToInt(tx * 1000f);
            int kty = Mathf.RoundToInt(ty * 1000f);

            string key = kx + "_" + ky + "_" + kz + "_" + ktx + "_" + kty;
            Mesh cached;
            if (s_MeshCache.TryGetValue(key, out cached) && cached != null) return cached;

            Vector3 s = new Vector3(kx * step, ky * step, kz * step);
            Mesh mesh = Build(s, tx, ty);
            mesh.name = string.Format(CultureInfo.InvariantCulture,
                "TiledCube_{0:0.0#}x{1:0.0#}x{2:0.0#}", s.x, s.y, s.z);
            s_MeshCache[key] = mesh;
            return mesh;
        }

        /// <summary>
        /// Replaces the GameObject's MeshFilter.sharedMesh with a TiledCube sized from its lossyScale.
        /// Existing colliders are left untouched. No-op if there is no MeshFilter.
        /// </summary>
        public static void ApplyTiledUVs(GameObject go, Vector2 tileMeters)
        {
            if (go == null) return;
            MeshFilter mf = go.GetComponent<MeshFilter>();
            if (mf == null) return;
            Vector3 ls = go.transform.lossyScale;
            Vector3 size = new Vector3(Mathf.Abs(ls.x), Mathf.Abs(ls.y), Mathf.Abs(ls.z));
            mf.sharedMesh = TiledCube(size, tileMeters);
        }

        static Mesh Build(Vector3 size, float tileX, float tileY)
        {
            var verts = new List<Vector3>(24);
            var norms = new List<Vector3>(24);
            var uvs = new List<Vector2>(24);
            var tris = new List<int>(36);

            // Side faces: u = viewer's right when looking at the face from outside, v = up.
            AddFace(Vector3.right, Vector3.forward, Vector3.up, size, tileX, tileY, verts, norms, uvs, tris);
            AddFace(Vector3.left, Vector3.back, Vector3.up, size, tileX, tileY, verts, norms, uvs, tris);
            AddFace(Vector3.forward, Vector3.left, Vector3.up, size, tileX, tileY, verts, norms, uvs, tris);
            AddFace(Vector3.back, Vector3.right, Vector3.up, size, tileX, tileY, verts, norms, uvs, tris);
            // Horizontal faces: square tiling with tileX on both axes.
            AddFace(Vector3.up, Vector3.right, Vector3.forward, size, tileX, tileX, verts, norms, uvs, tris);
            AddFace(Vector3.down, Vector3.right, Vector3.back, size, tileX, tileX, verts, norms, uvs, tris);

            var mesh = new Mesh();
            mesh.SetVertices(verts);
            mesh.SetNormals(norms);
            mesh.SetUVs(0, uvs);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateBounds();
            mesh.RecalculateTangents();
            return mesh;
        }

        static void AddFace(Vector3 n, Vector3 uAxis, Vector3 vAxis, Vector3 size, float tileU, float tileV,
            List<Vector3> verts, List<Vector3> norms, List<Vector2> uvs, List<int> tris)
        {
            float uLen = Mathf.Abs(Vector3.Dot(uAxis, size)) / tileU;
            float vLen = Mathf.Abs(Vector3.Dot(vAxis, size)) / tileV;

            int b = verts.Count;
            // Corner order: (0,0) (1,0) (1,1) (0,1) in (s,t); t = 0 is the bottom edge.
            for (int i = 0; i < 4; i++)
            {
                float sCoord = (i == 1 || i == 2) ? 1f : 0f;
                float tCoord = (i >= 2) ? 1f : 0f;
                Vector3 p = n * 0.5f + uAxis * (sCoord - 0.5f) + vAxis * (tCoord - 0.5f);
                verts.Add(p);
                norms.Add(n);
                uvs.Add(new Vector2(sCoord * uLen, tCoord * vLen));
            }

            AddTri(b, b + 1, b + 2, n, verts, tris);
            AddTri(b, b + 2, b + 3, n, verts, tris);
        }

        // Unity front faces: Cross(b - a, c - a) points out of the face (clockwise as seen by the viewer).
        static void AddTri(int a, int b, int c, Vector3 n, List<Vector3> verts, List<int> tris)
        {
            Vector3 cross = Vector3.Cross(verts[b] - verts[a], verts[c] - verts[a]);
            if (Vector3.Dot(cross, n) > 0f)
            {
                tris.Add(a); tris.Add(b); tris.Add(c);
            }
            else
            {
                tris.Add(a); tris.Add(c); tris.Add(b);
            }
        }
    }
}
