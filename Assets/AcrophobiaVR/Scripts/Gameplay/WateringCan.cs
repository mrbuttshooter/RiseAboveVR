using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace AcrophobiaVR
{
    /// <summary>
    /// Grab the can and tilt it to pour. Water that lands on a flower pot makes it bloom.
    /// Desktop: click to pick up, hold the right mouse button to pour.
    /// </summary>
    public class WateringCan : MonoBehaviour, IDesktopUsable
    {
        public Transform spout;
        public ParticleSystem water;
        public float pourAngle = 65f;

        XRGrabInteractable grab;
        Rigidbody body;
        bool desktopHeld;

        public bool IsPouring { get; private set; }

        void Awake()
        {
            grab = GetComponent<XRGrabInteractable>();
            body = GetComponent<Rigidbody>();
        }

        public string DesktopHint => desktopHeld ? "Hold right mouse to pour, click to drop" : "Click to pick up the watering can";

        public void DesktopUse()
        {
            desktopHeld = !desktopHeld;
            if (body != null) body.isKinematic = desktopHeld;
            if (!desktopHeld) transform.SetParent(null, true);
        }

        void Update()
        {
            if (desktopHeld && PlayerRig.Instance != null)
            {
                var head = PlayerRig.Instance.Head;
                bool pourInput = Mouse.current != null && Mouse.current.rightButton.isPressed;
                Vector3 pos = head.position + head.forward * 0.55f + head.right * 0.22f - head.up * 0.25f;
                Quaternion rot = Quaternion.LookRotation(Vector3.ProjectOnPlane(head.forward, Vector3.up), Vector3.up);
                if (pourInput) rot = rot * Quaternion.Euler(80f, 0f, 0f);
                transform.position = Vector3.Lerp(transform.position, pos, Time.deltaTime * 12f);
                transform.rotation = Quaternion.Slerp(transform.rotation, rot, Time.deltaTime * 8f);
            }

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
        }
    }
}