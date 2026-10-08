using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Spins an object (crane jib, fans, windmills).</summary>
    public class Spinner : MonoBehaviour
    {
        public Vector3 degreesPerSecond = new Vector3(0, 10, 0);
        public bool oscillate;
        public float oscillateAmplitude = 30f;

        Quaternion start;
        void Start() => start = transform.localRotation;

        void Update()
        {
            if (oscillate)
                transform.localRotation = start * Quaternion.Euler(degreesPerSecond.normalized * Mathf.Sin(Time.time * degreesPerSecond.magnitude * 0.02f) * oscillateAmplitude);
            else
                transform.Rotate(degreesPerSecond * Time.deltaTime, Space.Self);
        }
    }
}
