using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Moves along local-space waypoints (relative to where it starts), looping or ping-ponging, with optional
    /// pauses at each point. Crane-carried beams, the window-washer cradle, a hovering helicopter.
    /// Add a <see cref="Carrier"/> to let the player ride it.
    /// </summary>
    public class PathMover : Hazard
    {
        [Tooltip("Offsets from the start position (the start itself is point 0 and need not be listed).")]
        public Vector3[] points = { Vector3.zero, Vector3.forward * 5f };
        public float speed = 1.5f;
        public bool pingPong = true;
        public float pauseAtPoints = 1f;
        [Tooltip("Smooth start/stop between points.")]
        public bool ease = true;
        public float startDelay = 0f;
        [Tooltip("Ignore difficulty scaling (story objects like the helicopter).")]
        public bool fixedSpeed;

        Vector3 origin;
        int from, to = 1, dir = 1;
        float t, pause, delay;

        void Awake()
        {
            origin = transform.localPosition;
            ResetHazard();
        }

        public override void ResetHazard()
        {
            from = 0; to = Mathf.Min(1, points.Length - 1); dir = 1; t = 0f;
            pause = 0f; delay = startDelay;
            if (points.Length > 0) transform.localPosition = origin + points[0];
        }

        void Update()
        {
            if (!Running || points.Length < 2) return;
            if (delay > 0f) { delay -= Time.deltaTime; return; }
            if (pause > 0f) { pause -= Time.deltaTime; return; }
            Vector3 a = points[from], b = points[to];
            float len = Mathf.Max(0.01f, Vector3.Distance(a, b));
            float s = speed * (fixedSpeed ? 1f : Difficulty.HazardSpeed);
            t = Mathf.Min(1f, t + s * Time.deltaTime / len);
            float k = ease ? Mathf.SmoothStep(0f, 1f, t) : t;
            transform.localPosition = origin + Vector3.Lerp(a, b, k);
            if (t < 1f) return;
            t = 0f;
            pause = pauseAtPoints;
            from = to;
            if (pingPong)
            {
                if (to + dir >= points.Length || to + dir < 0) dir = -dir;
                to += dir;
            }
            else to = (to + 1) % points.Length;
        }
    }
}
