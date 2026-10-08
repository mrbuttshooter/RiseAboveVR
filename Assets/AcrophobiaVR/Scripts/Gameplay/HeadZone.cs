using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Region test against the player's head position (not physics triggers), so it works the same
    /// for room-scale walking, teleporting, smooth locomotion and desktop mode.
    /// </summary>
    [RequireComponent(typeof(BoxCollider))]
    public abstract class HeadZone : MonoBehaviour
    {
        BoxCollider box;
        bool inside;

        public bool PlayerInside => inside;

        protected virtual void Awake()
        {
            box = GetComponent<BoxCollider>();
            box.isTrigger = true;
            gameObject.layer = 2; // Ignore Raycast: never blocks teleport rays or interaction rays
        }

        protected virtual void Update()
        {
            var rig = PlayerRig.Instance;
            if (rig == null) return;
            bool now = Contains(rig.Head.position);
            if (now && !inside) { inside = true; OnHeadEnter(); }
            else if (!now && inside) { inside = false; OnHeadExit(); }
            if (inside) OnHeadStay();
        }

        public bool Contains(Vector3 world)
        {
            if (box == null) box = GetComponent<BoxCollider>();
            Vector3 local = transform.InverseTransformPoint(world) - box.center;
            Vector3 half = box.size * 0.5f;
            return Mathf.Abs(local.x) <= half.x && Mathf.Abs(local.y) <= half.y && Mathf.Abs(local.z) <= half.z;
        }

        protected virtual void OnHeadEnter() { }
        protected virtual void OnHeadExit() { }
        protected virtual void OnHeadStay() { }

        protected virtual void OnDrawGizmos()
        {
            var b = GetComponent<BoxCollider>();
            if (b == null) return;
            Gizmos.matrix = transform.localToWorldMatrix;
            Gizmos.color = new Color(0.3f, 0.9f, 0.6f, 0.25f);
            Gizmos.DrawCube(b.center, b.size);
        }
    }
}