using System.Collections;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Pigeons roosting on a ledge burst out right next to you when you get close - a clatter of wings,
    /// a jolt of fear and a moment where you really want to grab something. Re-arms after you leave.
    /// </summary>
    public class StartleBirds : MonoBehaviour
    {
        public float triggerRadius = 1.4f;
        public int count = 7;
        public Vector3 fleeDirection = Vector3.back;   // the flock's general escape direction (world)
        public Material bodyMaterial;
        public Material wingMaterial;

        bool fired;
        float rearmAt;
        GameObject[] perched;

        void Start()
        {
            // A few birds sit on the ledge so the player can see them coming.
            perched = new GameObject[3];
            for (int i = 0; i < perched.Length; i++)
            {
                // Sitting in a row along the ledge (the object's forward), wings folded.
                perched[i] = MakeBird(transform.position + transform.forward * (i - 1) * 0.32f + Vector3.up * 0.07f,
                    transform.rotation * Quaternion.Euler(0f, -90f + (i - 1) * 25f, 0f)); // face the street
                foreach (var w in new[] { "WingL", "WingR" })
                {
                    var wing = perched[i].transform.Find(w);
                    wing.localRotation = Quaternion.Euler(0f, 0f, w == "WingL" ? 80f : -80f);
                    wing.localScale = new Vector3(0.6f, 1f, 1.2f);
                }
            }
        }

        void Update()
        {
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            if (rig == null || lc == null || !lc.Started) return;
            float d2 = (rig.Head.position - transform.position).sqrMagnitude;
            if (fired)
            {
                if (Time.time > rearmAt && d2 > 36f)
                {
                    fired = false;
                    foreach (var p in perched) if (p != null) p.SetActive(true);
                }
                return;
            }
            if (d2 > triggerRadius * triggerRadius) return;
            fired = true;
            rearmAt = Time.time + 20f;
            StartCoroutine(Burst(rig));
        }

        IEnumerator Burst(PlayerRig rig)
        {
            foreach (var p in perched) if (p != null) p.SetActive(false);
            ProceduralAudio.PlayFlutterAt(transform.position);
            ProceduralAudio.PlayChirpAt(transform.position + Vector3.up * 0.3f);
            Haptics.Medium();
            FearSystem.Spike(0.35f);

            var birds = new GameObject[count];
            var vel = new Vector3[count];
            var wings = new Transform[count * 2];
            Vector3 flee = fleeDirection.normalized;
            for (int i = 0; i < count; i++)
            {
                Vector3 start = transform.position + Random.insideUnitSphere * 0.3f + Vector3.up * 0.1f;
                birds[i] = MakeBird(start, Quaternion.identity);
                wings[i * 2] = birds[i].transform.Find("WingL");
                wings[i * 2 + 1] = birds[i].transform.Find("WingR");
                // Most flap away from the wall, a couple straight past the player's face.
                Vector3 toHead = (rig.Head.position - start).normalized;
                Vector3 v = (i < 2 ? toHead + Vector3.up * 0.6f : flee + Random.insideUnitSphere * 0.6f + Vector3.up * Random.Range(0.4f, 1f));
                vel[i] = v.normalized * Random.Range(3f, 5f);
            }

            for (float t = 0f; t < 3.5f; t += Time.deltaTime)
            {
                for (int i = 0; i < count; i++)
                {
                    if (birds[i] == null) continue;
                    vel[i] += Vector3.up * 1.2f * Time.deltaTime;
                    birds[i].transform.position += vel[i] * Time.deltaTime;
                    birds[i].transform.rotation = Quaternion.LookRotation(vel[i]);
                    float flap = Mathf.Sin((t + i * 0.13f) * 40f) * 55f;
                    if (wings[i * 2] != null) wings[i * 2].localRotation = Quaternion.Euler(0f, 0f, flap);
                    if (wings[i * 2 + 1] != null) wings[i * 2 + 1].localRotation = Quaternion.Euler(0f, 0f, -flap);
                }
                if (t < 0.05f) ProceduralAudio.PlayFlutterAt(transform.position + flee);
                yield return null;
            }
            foreach (var b in birds) if (b != null) Destroy(b);
        }

        GameObject MakeBird(Vector3 pos, Quaternion rot)
        {
            var root = new GameObject("Pigeon");
            root.transform.SetPositionAndRotation(pos, rot);
            root.transform.SetParent(transform, true);
            Part(PrimitiveType.Sphere, "Body", root.transform, Vector3.zero, new Vector3(0.14f, 0.12f, 0.22f), bodyMaterial);
            Part(PrimitiveType.Sphere, "Head", root.transform, new Vector3(0f, 0.07f, 0.11f), new Vector3(0.08f, 0.08f, 0.08f), bodyMaterial);
            var wl = new GameObject("WingL").transform;
            wl.SetParent(root.transform, false);
            wl.localPosition = new Vector3(-0.05f, 0.03f, 0f);
            Part(PrimitiveType.Cube, "Feathers", wl, new Vector3(-0.1f, 0f, 0f), new Vector3(0.2f, 0.015f, 0.12f), wingMaterial);
            var wr = new GameObject("WingR").transform;
            wr.SetParent(root.transform, false);
            wr.localPosition = new Vector3(0.05f, 0.03f, 0f);
            Part(PrimitiveType.Cube, "Feathers", wr, new Vector3(0.1f, 0f, 0f), new Vector3(0.2f, 0.015f, 0.12f), wingMaterial);
            return root;
        }

        static void Part(PrimitiveType type, string name, Transform parent, Vector3 pos, Vector3 scale, Material mat)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            Destroy(go.GetComponent<Collider>());
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localScale = scale;
            if (mat != null) go.GetComponent<Renderer>().sharedMaterial = mat;
        }
    }
}
