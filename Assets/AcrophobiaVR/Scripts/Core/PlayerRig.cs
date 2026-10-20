using Unity.XR.CoreUtils;
using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit.Locomotion;

namespace AcrophobiaVR
{
    /// <summary>
    /// Thin wrapper around the XR Origin: where the head is, teleporting the player to a point
    /// (respawn / safe room) and freezing locomotion while riding the lift.
    /// </summary>
    [DefaultExecutionOrder(-100)]
    public class PlayerRig : MonoBehaviour
    {
        public static PlayerRig Instance { get; private set; }

        XROrigin origin;
        CharacterController characterController;
        LocomotionProvider[] providers;

        public Transform Head
        {
            get
            {
                if (origin != null && origin.Camera != null) return origin.Camera.transform;
                return Camera.main != null ? Camera.main.transform : transform;
            }
        }

        public Transform Root => origin != null ? origin.transform : transform;

        public Transform LeftHand { get; private set; }
        public Transform RightHand { get; private set; }

        /// <summary>True when running without a headset (keyboard and mouse).</summary>
        public bool IsDesktop { get; set; }

        /// <summary>Height of the floor the player is standing on (rig origin height).</summary>
        public float FeetY => Root.position.y;

        void Awake()
        {
            Instance = this;
            origin = GetComponent<XROrigin>();
            if (origin == null) origin = FindFirstObjectByType<XROrigin>();
            if (origin != null)
            {
                characterController = origin.GetComponentInChildren<CharacterController>();
                providers = origin.GetComponentsInChildren<LocomotionProvider>(true);
                foreach (var t in origin.GetComponentsInChildren<Transform>(true))
                {
                    string n = t.name.ToLowerInvariant();
                    if (!n.Contains("controller") || n.Contains("stabilized") || n.Contains("teleport")) continue;
                    if (LeftHand == null && n.Contains("left")) LeftHand = t;
                    if (RightHand == null && n.Contains("right")) RightHand = t;
                }
            }
        }

        /// <summary>Moves the rig so the feet are at the given position, facing the given direction.</summary>
        public void TeleportTo(Vector3 feetPosition, Vector3 forward)
        {
            var root = Root;
            var head = Head;
            bool ccWasEnabled = characterController != null && characterController.enabled;
            if (ccWasEnabled) characterController.enabled = false;

            Vector3 headForward = Vector3.ProjectOnPlane(head.forward, Vector3.up);
            Vector3 wantedForward = Vector3.ProjectOnPlane(forward, Vector3.up);
            if (headForward.sqrMagnitude > 0.001f && wantedForward.sqrMagnitude > 0.001f)
            {
                float angle = Vector3.SignedAngle(headForward, wantedForward, Vector3.up);
                root.RotateAround(head.position, Vector3.up, angle);
            }

            Vector3 headOffset = head.position - root.position;
            headOffset.y = 0f;
            root.position = feetPosition - headOffset;

            Physics.SyncTransforms();
            if (ccWasEnabled) characterController.enabled = true;
            if (IsDesktop)
            {
                var desktop = root.GetComponent<DesktopRig>();
                if (desktop != null) desktop.FaceDirection(forward);
            }
        }

        public void TeleportTo(Transform point) => TeleportTo(point.position, point.forward);

        /// <summary>Moves the whole rig by a world-space offset (used by moving platforms).</summary>
        public void MoveBy(Vector3 delta)
        {
            if (characterController != null && characterController.enabled) characterController.Move(delta);
            else Root.position += delta;
        }

        public CharacterController Body => characterController;

        /// <summary>Disables walking, teleporting, turning and gravity (e.g. while the lift is moving).</summary>
        public void SetLocomotionEnabled(bool enabled)
        {
            // In desktop mode the XR locomotion stays off; DesktopRig moves the player itself.
            if (providers != null && !IsDesktop)
                foreach (var p in providers)
                    if (p != null) p.enabled = enabled;
            if (characterController != null) characterController.enabled = enabled;
            Physics.SyncTransforms();
        }

        /// <summary>
        /// Race rules for VR locomotion: no teleporting or grab-moving across gaps, one jump (no double jump),
        /// a running pace. Desktop mode has its own controls (DesktopRig).
        /// </summary>
        public void ConfigureForRunning()
        {
            if (origin == null) return;
            foreach (var tp in origin.GetComponentsInChildren<UnityEngine.XR.Interaction.Toolkit.Locomotion.Teleportation.TeleportationProvider>(true)) tp.enabled = false;
            foreach (var gm in origin.GetComponentsInChildren<UnityEngine.XR.Interaction.Toolkit.Locomotion.Movement.GrabMoveProvider>(true)) gm.enabled = false;
            foreach (var gm in origin.GetComponentsInChildren<UnityEngine.XR.Interaction.Toolkit.Locomotion.Movement.TwoHandedGrabMoveProvider>(true)) gm.enabled = false;
            foreach (var t in origin.GetComponentsInChildren<Transform>(true))
                if (t.name.Contains("Teleport Interactor")) t.gameObject.SetActive(false);
            foreach (var j in origin.GetComponentsInChildren<UnityEngine.XR.Interaction.Toolkit.Locomotion.Jump.JumpProvider>(true))
            {
                j.jumpHeight = JumpHeight;
                j.unlimitedInAirJumps = false;
                j.inAirJumpCount = 0;
            }
            foreach (var m in origin.GetComponentsInChildren<UnityEngine.XR.Interaction.Toolkit.Locomotion.Movement.ContinuousMoveProvider>(true))
                m.moveSpeed = RunSpeed;
        }

        /// <summary>Jump apex height (m) for VR and desktop.</summary>
        public const float JumpHeight = 1.05f;
        /// <summary>VR stick speed (m/s); desktop walks at this and sprints faster.</summary>
        public const float RunSpeed = 3.4f;

        /// <summary>The collider the player is standing on (null when airborne).</summary>
        public Collider GroundCollider()
        {
            Vector3 feet = Root.position;
            if (characterController != null && characterController.enabled)
            {
                Vector3 c = characterController.transform.TransformPoint(characterController.center);
                feet = new Vector3(c.x, Root.position.y, c.z);
            }
            else
            {
                feet = new Vector3(Head.position.x, Root.position.y, Head.position.z);
            }
            return Physics.SphereCast(feet + Vector3.up * 0.4f, 0.15f, Vector3.down, out RaycastHit hit, 0.55f, ~0, QueryTriggerInteraction.Ignore) ? hit.collider : null;
        }

        /// <summary>Point roughly in front of the eyes, used to place floating panels.</summary>
        public Vector3 PointInFront(float distance, float heightOffset = 0f)
        {
            var head = Head;
            Vector3 fwd = Vector3.ProjectOnPlane(head.forward, Vector3.up);
            if (fwd.sqrMagnitude < 0.001f) fwd = Vector3.ProjectOnPlane(head.up, Vector3.up);
            return head.position + fwd.normalized * distance + Vector3.up * heightOffset;
        }

        /// <summary>Places and rotates a world-space panel so it faces the player.</summary>
        public void PlaceInFront(Transform panel, float distance = 1.4f, float heightOffset = -0.1f)
        {
            panel.position = PointInFront(distance, heightOffset);
            Vector3 look = panel.position - Head.position;
            look.y = 0f;
            if (look.sqrMagnitude > 0.0001f) panel.rotation = Quaternion.LookRotation(look);
        }
    }
}
