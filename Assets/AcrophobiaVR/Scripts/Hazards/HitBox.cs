using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// A dangerous moving part: touching its colliders with your body knocks you off the course (costs a life).
    /// Standing on top of it is fine (feet are below the "body" check height).
    /// </summary>
    public class HitBox : Hazard
    {
        public float bodyRadius = 0.32f;
        [Tooltip("Push direction in local space; zero = away from this object.")]
        public Vector3 localPush = Vector3.zero;

        Collider[] cols;
        float cooldown;

        void Awake() => cols = GetComponentsInChildren<Collider>();

        void Update()
        {
            if (!Live || cooldown > Time.time || cols == null) return;
            var rig = PlayerRig.Instance;
            if (rig == null) return;
            // Sample the body: shins, chest and head (so a low arm must be jumped and a high one ducked).
            Vector3 h = rig.Head.position;
            float feet = rig.FeetY;
            Vector3[] body = { new Vector3(h.x, feet + 0.25f, h.z), new Vector3(h.x, Mathf.Lerp(feet, h.y, 0.55f), h.z), new Vector3(h.x, h.y - 0.08f, h.z) };
            // Sideways the body is as wide as the character controller (it would shove the CC aside before a thinner
            // check could fire); vertically keep it tight so jumping the low arm / ducking the high one still works.
            float side = rig.Body != null ? Mathf.Max(bodyRadius, rig.Body.radius + 0.06f) : bodyRadius;
            foreach (var c in cols)
            {
                if (c == null || !c.enabled || c.isTrigger) continue;
                foreach (var point in body)
                {
                    Vector3 d = c.ClosestPoint(point) - point;
                    if (Mathf.Abs(d.y) > bodyRadius || d.x * d.x + d.z * d.z > side * side) continue;
                    cooldown = Time.time + 1.5f;
                    Vector3 push = localPush.sqrMagnitude > 0f ? transform.TransformDirection(localPush) : point - c.bounds.center;
                    KnockPlayer(push);
                    return;
                }
            }
        }
    }
}
