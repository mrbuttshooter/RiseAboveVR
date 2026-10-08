using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Spawns drifting fireflies around this point (Calm Meadow, park).</summary>
    public class FirefliesSpawner : MonoBehaviour
    {
        public float radius = 12f;
        void Start() => Effects.Fireflies(transform.position, radius, transform);
    }
}