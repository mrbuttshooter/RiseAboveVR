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
                held = true;
                var rb = GetComponent<Rigidbody>();
                if (rb != null) rb.isKinematic = true;
            }
            else if (owner.PlayerNearTarget())
            {
                held = false;
                owner.Deliver();
            }
        }

        void Update()
        {
            if (!held || PlayerRig.Instance == null) return;
            var head = PlayerRig.Instance.Head;
            transform.position = Vector3.Lerp(transform.position, head.position + head.forward * 0.7f - head.up * 0.2f + head.right * 0.15f, Time.deltaTime * 12f);
            transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(Vector3.ProjectOnPlane(head.forward, Vector3.up)), Time.deltaTime * 8f);
        }
    }
}