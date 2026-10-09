using System.Collections;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// A helicopter that thunders past once when the player reaches a trigger point (e.g. the middle of the rope
    /// bridge). It follows a path, banks into the turns, and while it is close its rotor wash rocks every balance
    /// beam (crouch!) and shakes the controllers. Rotors spin via child Spinners; the sound is a Rotor SoundEmitter.
    /// </summary>
    public class FlyBy : MonoBehaviour
    {
        public Vector3[] path;                  // world points, flown in order
        public float speed = 26f;
        public Vector3 triggerPoint;
        public float triggerRadius = 3f;
        public float washRadius = 30f;
        public string line = "Helicopter! Crouch down and hold on - here comes the downdraft!";

        bool started;
        bool done;

        void Start()
        {
            if (path != null && path.Length > 0) transform.position = path[0];
            SetVisible(false);
        }

        void SetVisible(bool on)
        {
            foreach (Transform c in transform) c.gameObject.SetActive(on);
        }

        void Update()
        {
            if (started || done || path == null || path.Length < 2) return;
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            if (rig == null || lc == null || !lc.Started || lc.IsRespawning) return;
            if ((rig.Head.position - triggerPoint).sqrMagnitude > triggerRadius * triggerRadius) return;
            started = true;
            StartCoroutine(Fly(rig));
        }

        IEnumerator Fly(PlayerRig rig)
        {
            SetVisible(true);
            Companion.Say(line, 4f);
            bool washed = false;
            for (int i = 1; i < path.Length; i++)
            {
                Vector3 a = path[i - 1], b = path[i];
                float len = Vector3.Distance(a, b);
                for (float d = 0f; d < len; d += speed * Time.deltaTime)
                {
                    Vector3 p = Vector3.Lerp(a, b, d / len);
                    Vector3 fwd = (b - a).normalized;
                    // Nose down a little and bank towards the next leg.
                    float bank = 0f;
                    if (i + 1 < path.Length)
                        bank = -Vector3.SignedAngle(fwd, (path[i + 1] - b).normalized, Vector3.up) * 0.25f * Mathf.Clamp01(d / len);
                    transform.SetPositionAndRotation(p, Quaternion.LookRotation(fwd) * Quaternion.Euler(8f, 0f, bank));

                    float dist = Vector3.Distance(p, rig.Head.position);
                    if (dist < washRadius)
                    {
                        BalanceBeam.ExternalGustUntil = Time.time + 0.25f;
                        AmbientAudio.GustBoost = 1f;
                        float k = 1f - dist / washRadius;
                        if (Time.frameCount % 6 == 0) Haptics.Pulse(0.3f + 0.5f * k, 0.08f);
                        if (!washed)
                        {
                            washed = true;
                            FearSystem.Spike(0.35f);
                            ProceduralAudio.PlayWhoosh(1f);
                        }
                    }
                    yield return null;
                }
            }
            AmbientAudio.GustBoost = 0f;
            SetVisible(false);
            done = true;
        }
    }
}
