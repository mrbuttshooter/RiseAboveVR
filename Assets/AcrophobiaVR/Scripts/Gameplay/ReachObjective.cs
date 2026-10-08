using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Complete by getting your head into a region (top of a ladder, end of a plank...).</summary>
    [RequireComponent(typeof(BoxCollider))]
    public class ReachObjective : Objective
    {
        BoxCollider box;

        void Awake()
        {
            box = GetComponent<BoxCollider>();
            box.isTrigger = true;
            gameObject.layer = 2;
        }

        void Update()
        {
            if (!IsActive || IsComplete || PlayerRig.Instance == null) return;
            Vector3 local = transform.InverseTransformPoint(PlayerRig.Instance.Head.position) - box.center;
            Vector3 half = box.size * 0.5f;
            if (Mathf.Abs(local.x) <= half.x && Mathf.Abs(local.y) <= half.y && Mathf.Abs(local.z) <= half.z)
                Complete();
        }
    }
}