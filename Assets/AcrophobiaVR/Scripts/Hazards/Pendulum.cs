using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Swings about a local axis through this transform (the pivot): hanging signs and crane hooks you jump onto,
    /// a tilting cradle. Children with colliders swing along; add a <see cref="Carrier"/> to ride it.
    /// </summary>
    public class Pendulum : Hazard
    {
        public Vector3 axis = Vector3.forward;
        public float amplitude = 30f;
        public float period = 3f;
        [Range(0f, 1f)] public float phase;
        [Tooltip("Children that stay level while swinging (a board hanging on parallel chains).")]
        public Transform[] keepLevel;

        Quaternion rest;
        Quaternion[] levelRot;
        float clock;

        void Awake()
        {
            rest = transform.localRotation;
            if (keepLevel != null)
            {
                levelRot = new Quaternion[keepLevel.Length];
                for (int i = 0; i < keepLevel.Length; i++) if (keepLevel[i] != null) levelRot[i] = keepLevel[i].rotation;
            }
            ResetHazard();
        }

        void Level()
        {
            if (keepLevel == null || levelRot == null) return;
            for (int i = 0; i < keepLevel.Length; i++) if (keepLevel[i] != null) keepLevel[i].rotation = levelRot[i];
        }

        public override void ResetHazard()
        {
            clock = phase * period;
            transform.localRotation = rest * Quaternion.AngleAxis(Mathf.Sin(clock / period * Mathf.PI * 2f) * amplitude, axis);
            Level();
        }

        void Update()
        {
            if (!Running) return;
            clock += Time.deltaTime * Difficulty.HazardSpeed;
            float angle = Mathf.Sin(clock / Mathf.Max(0.1f, period) * Mathf.PI * 2f) * amplitude;
            transform.localRotation = rest * Quaternion.AngleAxis(angle, axis);
            Level();
        }
    }
}
