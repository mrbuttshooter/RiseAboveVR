using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>A flock of birds circling lazily - seen below you from high up.</summary>
    public class BirdFlock : MonoBehaviour
    {
        public int count = 12;
        public float radius = 25f;
        public float speed = 0.25f;
        public Material material;

        Transform[] birds;
        Transform[] wingsL;
        Transform[] wingsR;
        float[] phase;

        void Start()
        {
            birds = new Transform[count];
            wingsL = new Transform[count];
            wingsR = new Transform[count];
            phase = new float[count];
            for (int i = 0; i < count; i++)
            {
                var b = new GameObject("Bird").transform;
                b.SetParent(transform, false);
                birds[i] = b;
                phase[i] = Random.value * Mathf.PI * 2f;
                wingsL[i] = Wing(b, -1);
                wingsR[i] = Wing(b, 1);
                var body = GameObject.CreatePrimitive(PrimitiveType.Capsule);
                Destroy(body.GetComponent<Collider>());
                body.transform.SetParent(b, false);
                body.transform.localScale = new Vector3(0.12f, 0.2f, 0.12f);
                body.transform.localRotation = Quaternion.Euler(90, 0, 0);
                if (material != null) body.GetComponent<Renderer>().sharedMaterial = material;
            }
        }

        Transform Wing(Transform parent, int side)
        {
            var pivot = new GameObject("WingPivot").transform;
            pivot.SetParent(parent, false);
            var w = GameObject.CreatePrimitive(PrimitiveType.Cube);
            Destroy(w.GetComponent<Collider>());
            w.transform.SetParent(pivot, false);
            w.transform.localScale = new Vector3(0.35f, 0.01f, 0.12f);
            w.transform.localPosition = new Vector3(0.18f * side, 0, 0);
            if (material != null) w.GetComponent<Renderer>().sharedMaterial = material;
            return pivot;
        }

        void Update()
        {
            for (int i = 0; i < count; i++)
            {
                float a = Time.time * speed + phase[i];
                float r = radius * (0.7f + 0.3f * Mathf.Sin(phase[i] * 3f));
                Vector3 p = new Vector3(Mathf.Cos(a) * r, Mathf.Sin(a * 2f + phase[i]) * 2f, Mathf.Sin(a) * r);
                Vector3 next = new Vector3(Mathf.Cos(a + 0.05f) * r, Mathf.Sin((a + 0.05f) * 2f + phase[i]) * 2f, Mathf.Sin(a + 0.05f) * r);
                birds[i].localPosition = p;
                birds[i].localRotation = Quaternion.LookRotation(next - p);
                float flap = Mathf.Sin(Time.time * 12f + phase[i]) * 40f;
                wingsL[i].localRotation = Quaternion.Euler(0, 0, -flap);
                wingsR[i].localRotation = Quaternion.Euler(0, 0, flap);
            }
        }
    }
}
