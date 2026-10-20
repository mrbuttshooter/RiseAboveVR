using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Level 3 finale: the rope ladder under the rescue helicopter. Get your head (or, in VR, a hand) into the ladder
    /// zone - usually by jumping off the roof edge - and you grab on: the level finishes, you hang from the rung and
    /// the helicopter lifts you away over the city while the fireworks go off.
    /// </summary>
    [DefaultExecutionOrder(1000)]
    [RequireComponent(typeof(BoxCollider))]
    public class HeliLadderCatch : Objective
    {
        [Tooltip("Helicopter root that flies off after the catch (its bobbing PathMover is stopped).")]
        public Transform heli;
        [Tooltip("Local X/Z (in the helicopter's space) of the ladder; Y range of the rungs you can hold.")]
        public Vector3 ladderLocal = new Vector3(-1f, 0f, 0f);
        public Vector2 rungRange = new Vector2(-5.2f, -1.6f);
        public float hangDepth = 1.9f;
        public float handReach = 0.25f;

        BoxCollider box;
        bool caught;
        Vector3 holdLocal;
        float caughtAt;
        Vector3 flyVelocity;

        void Awake()
        {
            box = GetComponent<BoxCollider>();
            box.isTrigger = true;
            gameObject.layer = 2;
        }

        bool Inside(Vector3 world, float pad)
        {
            Vector3 local = transform.InverseTransformPoint(world) - box.center;
            Vector3 half = box.size * 0.5f + Vector3.one * pad;
            return Mathf.Abs(local.x) <= half.x && Mathf.Abs(local.y) <= half.y && Mathf.Abs(local.z) <= half.z;
        }

        void Update()
        {
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            if (caught || !IsActive || IsComplete || rig == null || heli == null) return;
            if (lc != null && (lc.Finished || lc.IsRespawning)) return;
            bool grab = Inside(rig.Head.position, 0f);
            if (!grab && !rig.IsDesktop)
                foreach (var hand in new[] { rig.LeftHand, rig.RightHand })
                    if (hand != null && Inside(hand.position, handReach)) grab = true;
            if (!grab) return;

            // Hold the rung nearest your hands.
            float y = heli.InverseTransformPoint(rig.Head.position + Vector3.up * 0.45f).y;
            holdLocal = new Vector3(ladderLocal.x, Mathf.Clamp(y, rungRange.x, rungRange.y), ladderLocal.z);
            caught = true;
            caughtAt = Time.time;
            var bob = heli.GetComponent<PathMover>();
            if (bob != null) bob.enabled = false;
            ProceduralAudio.PlayClunk();
            Haptics.Strong();
            Complete();
            if (lc != null) lc.TryFinish();
            rig.SetLocomotionEnabled(false);
        }

        void LateUpdate()
        {
            if (!caught || heli == null) return;
            var rig = PlayerRig.Instance;
            if (rig == null) return;
            // A beat to swing, then climb away over the city.
            float t = Time.time - caughtAt;
            if (t > 0.8f)
            {
                flyVelocity = Vector3.MoveTowards(flyVelocity, new Vector3(5f, 3.5f, 0f), 2.5f * Time.deltaTime);
                heli.position += flyVelocity * Time.deltaTime;
            }
            Vector3 hold = heli.TransformPoint(holdLocal);
            Vector3 swing = new Vector3(0f, 0f, Mathf.Sin(t * 2.2f) * 0.25f * Mathf.Exp(-t * 0.4f));
            Vector3 feet = hold + Vector3.down * hangDepth + swing;
            Vector3 headOffset = rig.Head.position - rig.Root.position;
            headOffset.y = 0f;
            rig.Root.position = feet - headOffset;
            if ((Time.frameCount & 15) == 0) Haptics.Pulse(0.2f, 0.05f);
        }
    }
}
