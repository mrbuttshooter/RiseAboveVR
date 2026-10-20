using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// A zipline between two towers. Reach up and grab the handle (VR: put a hand on it; desktop: click it) and you
    /// slide down the cable, picking up speed, and drop off onto the far landing. The cable sways in the wind and
    /// the handle only comes back after a respawn, so you get one try per life.
    /// </summary>
    public class Zipline : Hazard, IDesktopUsable
    {
        public static bool Riding { get; private set; }

        [Tooltip("Handle (child) that slides along the cable. Its start position is the top of the line.")]
        public Transform handle;
        [Tooltip("World position where the handle stops (bottom of the line).")]
        public Vector3 end;
        public float maxSpeed = 14f;
        public float acceleration = 5f;
        [Tooltip("How far below the handle the player's feet hang.")]
        public float hangDepth = 2.0f;
        public float swayDegrees = 6f;

        Vector3 start;
        float travelled, speed;
        bool riding, used;

        public string DesktopHint => used ? "" : "Click: grab the zipline";

        void Awake()
        {
            if (handle != null) start = handle.position;
        }

        public override void ResetHazard()
        {
            if (riding) Stop(false);
            used = false;
            travelled = 0f;
            speed = 0f;
            if (handle != null) handle.position = start;
        }

        public void DesktopUse()
        {
            if (!used && Live && PlayerNear()) Grab();
        }

        bool PlayerNear()
        {
            var rig = PlayerRig.Instance;
            return rig != null && handle != null && Vector3.Distance(rig.Head.position, handle.position) < 2.2f;
        }

        void Update()
        {
            if (handle == null) return;
            var rig = PlayerRig.Instance;
            if (!riding)
            {
                if (used || !Live || rig == null || rig.IsDesktop) return;
                // VR: a hand on the handle grabs it.
                foreach (var hand in new[] { rig.LeftHand, rig.RightHand })
                    if (hand != null && Vector3.Distance(hand.position, handle.position) < 0.3f) { Grab(); return; }
                return;
            }

            float length = Vector3.Distance(start, end);
            speed = Mathf.Min(maxSpeed, speed + acceleration * Time.deltaTime);
            travelled += speed * Time.deltaTime;
            float k = Mathf.Clamp01(travelled / length);
            // Sag in the middle of the cable, sway from the wind.
            float sag = Mathf.Sin(k * Mathf.PI) * length * 0.04f;
            Vector3 dir = (end - start).normalized;
            Vector3 side = Vector3.Cross(Vector3.up, dir).normalized;
            float sway = Mathf.Sin(Time.time * 1.7f) * swayDegrees * Difficulty.Wind * Mathf.Sin(k * Mathf.PI);
            handle.position = Vector3.Lerp(start, end, k) + Vector3.down * sag + side * Mathf.Tan(sway * Mathf.Deg2Rad) * hangDepth;
            Vector3 feet = handle.position + Vector3.down * hangDepth;
            Vector3 headOffset = rig.Head.position - rig.Root.position;
            headOffset.y = 0f;
            rig.Root.position = feet - headOffset;
            if ((Time.frameCount & 7) == 0) Haptics.Pulse(0.15f + speed / maxSpeed * 0.3f, 0.05f);
            if (k >= 1f) Stop(true);
        }

        void Grab()
        {
            var rig = PlayerRig.Instance;
            if (rig == null) return;
            used = true;
            riding = true;
            Riding = true;
            travelled = 0f;
            speed = 1f;
            rig.SetLocomotionEnabled(false);
            ProceduralAudio.PlayClunk();
            ProceduralAudio.PlayWhoosh(1f);
            Haptics.Medium();
            Companion.Say("Hold on!", 1.5f);
        }

        void Stop(bool arrived)
        {
            riding = false;
            Riding = false;
            var rig = PlayerRig.Instance;
            if (rig != null) rig.SetLocomotionEnabled(true);
            if (arrived)
            {
                ProceduralAudio.PlayClunk();
                Haptics.Strong();
            }
        }

        protected override void OnDisable()
        {
            base.OnDisable();
            if (riding) { Riding = false; riding = false; }
        }
    }
}
