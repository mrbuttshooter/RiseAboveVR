using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Moves along a closed loop of points forever (cars, pedestrians, clouds).</summary>
    public class LoopMover : MonoBehaviour
    {
        public Vector3[] points;
        public float speed = 6f;
        public float startOffset;

        float distance;
        float total;
        float[] cumulative;

        void Start()
        {
            if (points == null || points.Length < 2) { enabled = false; return; }
            cumulative = new float[points.Length + 1];
            for (int i = 0; i < points.Length; i++)
            {
                cumulative[i] = total;
                total += Vector3.Distance(points[i], points[(i + 1) % points.Length]);
            }
            cumulative[points.Length] = total;
            distance = startOffset * total;
        }

        void Update()
        {
            distance = (distance + speed * Time.deltaTime) % total;
            for (int i = 0; i < points.Length; i++)
            {
                if (distance <= cumulative[i + 1])
                {
                    Vector3 a = points[i], b = points[(i + 1) % points.Length];
                    float seg = cumulative[i + 1] - cumulative[i];
                    float t = seg > 0f ? (distance - cumulative[i]) / seg : 0f;
                    transform.position = Vector3.Lerp(a, b, t);
                    Vector3 dir = b - a;
                    if (dir.sqrMagnitude > 0.001f) transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(dir), Time.deltaTime * 6f);
                    break;
                }
            }
        }
    }
}
