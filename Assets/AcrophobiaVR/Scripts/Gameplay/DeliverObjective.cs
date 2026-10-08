using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace AcrophobiaVR
{
    /// <summary>
    /// Carry an item to a spot (plant the flag on top of the crane, launch the fireworks...).
    /// VR: grab and bring it into the target. Desktop: click the item, then click again near the target.
    /// </summary>
    public class DeliverObjective : Objective
    {
        public Transform item;
        public BoxCollider target;
        public Transform snapPoint;

        void Start()
        {
            if (item != null)
            {
                var d = item.GetComponent<DeliverableItem>();
                if (d == null) d = item.gameObject.AddComponent<DeliverableItem>();
                d.owner = this;
            }
        }

        void Update()
        {
            if (!IsActive || IsComplete || item == null || target == null) return;
            Vector3 local = target.transform.InverseTransformPoint(item.position) - target.center;
            Vector3 half = target.size * 0.5f;
            if (Mathf.Abs(local.x) <= half.x && Mathf.Abs(local.y) <= half.y && Mathf.Abs(local.z) <= half.z)
                Deliver();
        }

        public bool PlayerNearTarget()
        {
            var rig = PlayerRig.Instance;
            return rig != null && target != null && Vector3.Distance(rig.Head.position, target.bounds.center) < 2.2f;
        }

        public void Deliver()
        {
            if (IsComplete) return;
            var grab = item.GetComponent<XRGrabInteractable>();
            if (grab != null) grab.enabled = false;
            var rb = item.GetComponent<Rigidbody>();
            if (rb != null) rb.isKinematic = true;
            item.SetParent(null, true);
            Transform snap = snapPoint != null ? snapPoint : target.transform;
            item.SetPositionAndRotation(snap.position, snap.rotation);
            Effects.Sparkle(item.position, UIFactory.Gold);
            Haptics.Medium();
            Complete();
        }
    }
}
