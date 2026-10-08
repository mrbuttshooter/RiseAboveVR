using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace AcrophobiaVR
{
    /// <summary>
    /// Grab the can and tilt it to pour. Water that lands on a flower pot makes it bloom.
    /// Desktop: click to pick up, hold the right mouse button to pour, click again to put it down.
    /// </summary>
    public class WateringCan : MonoBehaviour, IDesktopUsable
    {
        public Transform spout;
        public ParticleSystem water;
        public float pourAngle = 65f;

        XRGrabInteractable grab;
        Rigidbody body;
        Collider[] colliders;
        bool desktopHeld;
        bool ignoringBody;
        int lastToggleFrame = -1;
        float nextPourPulse;
        RigidbodyInterpolation savedInterpolation;

        public bool IsPouring { get; private set; }

        void Awake()
        {
            grab = GetComponent<XRGrabInteractable>();
            body = GetComponent<Rigidbody>();
            colliders = GetComponentsInChildren<Collider>(true);
        }

        public string DesktopHint => desktopHeld ? "Hold right mouse to pour, click to put down" : "Click to pick up the watering can";

        public void DesktopUse()
        {
            if (lastToggleFrame == Time.frameCount) return;
            SetDesktopHeld(!desktopHeld);
        }

        void SetDesktopHeld(bool held)
        {
            lastToggleFrame = Time.frameCount;
            desktopHeld = held;
            // While carried the can must not shove the player's body or block the crosshair.
            foreach (var c in colliders) c.enabled = !held;
            if (body != null)
            {
                if (held)
                {
                    savedInterpolation = body.interpolation;
                    body.interpolation = RigidbodyInterpolation.None; // we drive the transform directly
                    body.isKinematic = true;
                }
                else
                {
                    body.isKinematic = false;
                    body.interpolation = savedInterpolation;
                    body.linearVelocity = Vector3.zero;
                    body.angularVelocity = Vector3.zero;
                }
            }
            if (held) Haptics.Light();
        }

        void Update()
        {
            if (!ignoringBody) IgnorePlayerBody();

            if (desktopHeld && lastToggleFrame != Time.frameCount && Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame)
                SetDesktopHeld(false);

            bool held = desktopHeld || (grab != null && grab.isSelected);
            float tilt = Vector3.Angle(transform.up, Vector3.up);
            bool pour = held && tilt > pourAngle;
            if (pour != IsPouring)
            {
                IsPouring = pour;
                if (water != null)
                {
                    if (pour) water.Play();
                    else water.Stop();
                }
            }

            if (IsPouring && spout != null)
            {
                foreach (var hit in Physics.SphereCastAll(spout.position, 0.18f, Vector3.down, 1.6f, ~0, QueryTriggerInteraction.Collide))
                {
                    var pot = hit.collider.GetComponentInParent<FlowerPot>();
                    if (pot != null) pot.Water(Time.deltaTime);
                }
            }

            // Gentle buzz in the hands while pouring (the holding hand is unknown, so both).
            if (IsPouring && Time.time >= nextPourPulse)
            {
                nextPourPulse = Time.time + 0.1f;
                Haptics.Pulse(0.12f, 0.05f);
            }
        }

        void LateUpdate()
        {
            // After the camera has moved this frame, so the can stays glued to the view instead of trailing behind.
            if (!desktopHeld || PlayerRig.Instance == null) return;
            var head = PlayerRig.Instance.Head;
            bool pourInput = Mouse.current != null && Mouse.current.rightButton.isPressed;
            Vector3 flatForward = Vector3.ProjectOnPlane(head.forward, Vector3.up);
            if (flatForward.sqrMagnitude < 0.001f) flatForward = head.up;
            Quaternion rot = Quaternion.LookRotation(flatForward, Vector3.up);
            if (pourInput) rot = rot * Quaternion.Euler(80f, 0f, 0f);
            transform.position = head.position + head.forward * 0.55f + head.right * 0.22f - head.up * 0.25f;
            transform.rotation = Quaternion.Slerp(transform.rotation, rot, Time.deltaTime * 10f);
        }

        /// <summary>The can never collides with the player's own capsule (in VR or on desktop), so carrying it can't jam movement.</summary>
        void IgnorePlayerBody()
        {
            var rig = PlayerRig.Instance;
            if (rig == null || rig.Body == null) return;
            foreach (var c in colliders) Physics.IgnoreCollision(c, rig.Body, true);
            ignoringBody = true;
        }
    }
}
