using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Puts an important item (watering can, flag) back if it's dropped off the building.</summary>
    public class ReturnIfLost : MonoBehaviour
    {
        public float maxDrop = 2.5f;
        Vector3 homePos;
        Quaternion homeRot;
        Rigidbody body;

        void Start()
        {
            homePos = transform.position;
            homeRot = transform.rotation;
            body = GetComponent<Rigidbody>();
        }

        void Update()
        {
            if (transform.position.y > homePos.y - maxDrop) return;
            if (body != null)
            {
                body.linearVelocity = Vector3.zero;
                body.angularVelocity = Vector3.zero;
            }
            transform.SetPositionAndRotation(homePos, homeRot);
            Effects.Sparkle(homePos, UIFactory.Accent);
            HeadHud.Instance.ShowMessage("Oops, it fell - Pip brought it back!", 2.5f);
        }
    }
}