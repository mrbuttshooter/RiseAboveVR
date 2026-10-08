using UnityEngine;
using UnityEngine.InputSystem;

namespace AcrophobiaVR
{
    /// <summary>
    /// Ladder. In VR, the rungs use XRI climbing (grab and pull yourself up hand over hand).
    /// In desktop mode, look at the ladder and hold W / Space to climb.
    /// </summary>
    public class Ladder : MonoBehaviour
    {
        public Transform bottom;
        public Transform top;
        public Transform topExit;
        public float climbSpeed = 1.1f;
        public float reach = 0.9f;

        void Update()
        {
            var rig = PlayerRig.Instance;
            if (rig == null || bottom == null || top == null) return;
            if (!rig.IsDesktop) { VrStepOff(rig); return; }
            var kb = Keyboard.current;
            if (kb == null) return;

            Vector3 feet = new Vector3(rig.Head.position.x, rig.FeetY, rig.Head.position.z);
            Vector3 axis = top.position - bottom.position;
            float t = Vector3.Dot(feet - bottom.position, axis.normalized) / axis.magnitude;
            Vector3 onAxis = bottom.position + axis * Mathf.Clamp01(t);
            Vector3 flat = feet - onAxis;
            flat.y = 0f;
            if (flat.magnitude > reach || t < -0.2f || t > 1.05f) return;

            bool climb = kb.spaceKey.isPressed || (kb.wKey.isPressed && Vector3.Dot(rig.Head.forward, (onAxis - rig.Head.position).normalized) > -0.2f);
            DesktopRig.ClimbingThisFrame = climb;
            if (!climb) return;

            HeadHud.Instance.ShowProgress(Mathf.Clamp01(t), "Climbing...");
            rig.MoveBy(Vector3.up * climbSpeed * Time.deltaTime);
            if (t >= 1f && topExit != null) rig.TeleportTo(topExit);
        }

        float stepCooldown;

        /// <summary>When a VR climber's head rises above the top, help them over the lip onto the platform.</summary>
        void VrStepOff(PlayerRig rig)
        {
            if (topExit == null || Time.time < stepCooldown) return;
            Vector3 h = rig.Head.position;
            Vector3 flat = h - top.position;
            flat.y = 0f;
            if (h.y > topExit.position.y + 1.2f && flat.magnitude < 1.2f && rig.FeetY < topExit.position.y - 0.3f)
            {
                stepCooldown = Time.time + 2f;
                rig.TeleportTo(topExit);
                ProceduralAudio.PlayClunk();
            }
        }
    }
}