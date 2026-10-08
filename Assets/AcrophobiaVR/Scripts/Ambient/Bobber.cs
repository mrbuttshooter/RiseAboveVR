using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Gentle up/down bob (markers, stars, lanterns).</summary>
    public class Bobber : MonoBehaviour
    {
        public float amplitude = 0.15f;
        public float speed = 1.5f;
        Vector3 start;
        void Start() => start = transform.localPosition;
        void Update() => transform.localPosition = start + Vector3.up * Mathf.Sin(Time.time * speed + start.x) * amplitude;
    }
}
