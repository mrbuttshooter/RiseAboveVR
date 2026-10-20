using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Makes a moving or rotating object carry the player standing on it (crane beams, swinging signs, the
    /// window-washer cradle, the sweeping jib). Each frame the deepest Carrier under the player's feet moves them
    /// by exactly how much the spot they stand on moved, including turning with it.
    /// </summary>
    [DefaultExecutionOrder(1000)]
    public class Carrier : MonoBehaviour
    {
        Matrix4x4 prev;
        bool hasPrev;

        static int groundFrame = -1;
        static Carrier groundCarrier;

        void Awake()
        {
            // Moving colliders behave best as kinematic rigidbodies.
            var rb = GetComponent<Rigidbody>();
            if (rb == null) rb = gameObject.AddComponent<Rigidbody>();
            rb.isKinematic = true;
            rb.useGravity = false;
            rb.interpolation = RigidbodyInterpolation.None;
        }

        static Carrier CurrentGroundCarrier()
        {
            if (groundFrame == Time.frameCount) return groundCarrier;
            groundFrame = Time.frameCount;
            var rig = PlayerRig.Instance;
            var col = rig != null ? rig.GroundCollider() : null;
            groundCarrier = col != null ? col.GetComponentInParent<Carrier>() : null;
            return groundCarrier;
        }

        void LateUpdate()
        {
            Matrix4x4 now = transform.localToWorldMatrix;
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            bool canCarry = rig != null && (lc == null || !lc.IsRespawning) && !Zipline.Riding;
            if (hasPrev && canCarry && CurrentGroundCarrier() == this)
            {
                Vector3 feet = new Vector3(rig.Head.position.x, rig.FeetY, rig.Head.position.z);
                Vector3 local = prev.inverse.MultiplyPoint3x4(feet);
                Vector3 moved = now.MultiplyPoint3x4(local);
                Vector3 delta = moved - feet;
                if (delta.sqrMagnitude > 1e-8f && delta.sqrMagnitude < 4f) rig.MoveBy(delta);
                // Turn with the platform (yaw only).
                Vector3 f0 = prev.MultiplyVector(Vector3.forward), f1 = now.MultiplyVector(Vector3.forward);
                f0.y = 0f; f1.y = 0f;
                if (f0.sqrMagnitude > 1e-4f && f1.sqrMagnitude > 1e-4f)
                {
                    float yaw = Vector3.SignedAngle(f0, f1, Vector3.up);
                    if (Mathf.Abs(yaw) > 0.01f && Mathf.Abs(yaw) < 20f)
                    {
                        var desktop = rig.IsDesktop ? rig.Root.GetComponent<DesktopRig>() : null;
                        if (desktop != null) desktop.AddYaw(yaw); // DesktopRig owns the desktop yaw
                        else rig.Root.RotateAround(moved, Vector3.up, yaw);
                    }
                }
            }
            prev = now;
            hasPrev = true;
        }
    }
}
