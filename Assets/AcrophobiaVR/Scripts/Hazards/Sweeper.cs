using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Keeps rotating about a local axis (the crane jib sweeping over the roof, a spinning ventilation boom).
    /// Combine with <see cref="HitBox"/> on the arm to knock the player off, or <see cref="Carrier"/> to ride it.
    /// </summary>
    public class Sweeper : Hazard
    {
        public Vector3 axis = Vector3.up;
        public float degreesPerSecond = 30f;
        [Tooltip("If > 0, swing back and forth through this angle instead of turning all the way round.")]
        public float sweepAngle = 0f;

        Quaternion rest;
        float clock;

        void Awake()
        {
            rest = transform.localRotation;
        }

        public override void ResetHazard()
        {
            clock = 0f;
            transform.localRotation = rest;
        }

        void Update()
        {
            if (!Running) return;
            clock += Time.deltaTime * Difficulty.HazardSpeed;
            float angle;
            if (sweepAngle > 0f)
            {
                float period = 2f * sweepAngle / Mathf.Max(1f, degreesPerSecond);
                angle = Mathf.Sin(clock / period * Mathf.PI * 2f) * sweepAngle * 0.5f;
            }
            else angle = clock * degreesPerSecond;
            transform.localRotation = rest * Quaternion.AngleAxis(angle, axis);
        }
    }
}
