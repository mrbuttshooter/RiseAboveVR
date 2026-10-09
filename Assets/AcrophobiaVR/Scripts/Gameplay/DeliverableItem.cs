using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Desktop handling for a deliverable: pick up, carry in front of you, use near the target.</summary>
    public class DeliverableItem : MonoBehaviour, IDesktopUsable
    {
        public DeliverObjective owner;
        bool held;

        public string DesktopHint
        {
            get
            {
                if (!held) return "Click to pick up";
                return owner != null && owner.PlayerNearTarget() ? "Click to place it here" : "Carry it to the marked spot";
            }
        }

        public void DesktopUse()
        {
            if (owner == null || owner.IsComplete) return;
            if (!held)
            {
                SetHeld(true);
            }
            else if (owner.PlayerNearTarget())
            {
                SetHeld(false);
                owner.Deliver();
            }
        }

        void SetHeld(bool on)
        {
            held = on;
            var rb = GetComponent<Rigidbody>();
            if (on && rb != null) rb.isKinematic = true;
            // While carried it must not shove the player's capsule or block the crosshair (same fix as the watering can).
            foreach (var c in GetComponentsInChildren<Collider>(true)) c.enabled = !on;
        }

        void Start()
        {
            var rig = PlayerRig.Instance;
            if (rig == null || rig.Body == null) return;
            foreach (var c in GetComponentsInChildren<Collider>(true)) Physics.IgnoreCollision(c, rig.Body, true);
        }

        void LateUpdate()
        {
            if (!held || PlayerRig.Instance == null) return;
            if (owner == null || owner.IsComplete)
            {
                SetHeld(false);
                return;
            }
            var head = PlayerRig.Instance.Head;
            Vector3 flat = Vector3.ProjectOnPlane(head.forward, Vector3.up);
            if (flat.sqrMagnitude < 0.001f) flat = head.up;
            transform.position = head.position + head.forward * 0.7f - head.up * 0.25f + head.right * 0.22f;
            transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(flat), Time.deltaTime * 10f);
        }
    }
}