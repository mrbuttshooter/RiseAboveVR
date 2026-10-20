using System.Collections;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// A plank, slab or skylight that gives way shortly after you land on it: it shakes, creaks, then drops
    /// (or shatters, for glass). Keep moving. Comes back after a respawn.
    /// </summary>
    public class CollapsingPlatform : Hazard
    {
        public float delay = 0.9f;
        [Tooltip("Shatter instead of dropping (glass).")]
        public bool shatter;

        Vector3 homePos;
        Quaternion homeRot;
        Collider[] cols;
        Renderer[] rends;
        Coroutine routine;

        void Awake()
        {
            homePos = transform.position;
            homeRot = transform.rotation;
            cols = GetComponentsInChildren<Collider>();
            rends = GetComponentsInChildren<Renderer>();
        }

        public override void ResetHazard()
        {
            if (routine != null) StopCoroutine(routine);
            routine = null;
            transform.SetPositionAndRotation(homePos, homeRot);
            foreach (var c in cols) if (c != null) c.enabled = true;
            foreach (var r in rends) if (r != null) r.enabled = true;
        }

        bool PlayerOn()
        {
            var rig = PlayerRig.Instance;
            var g = rig != null ? rig.GroundCollider() : null;
            return g != null && g.transform.IsChildOf(transform);
        }

        void Update()
        {
            if (routine != null || !Live) return;
            if (PlayerOn()) routine = StartCoroutine(Collapse());
        }

        IEnumerator Collapse()
        {
            float d = delay / Difficulty.HazardSpeed;
            if (shatter) ProceduralAudio.PlayCrackAt(transform.position);
            else ProceduralAudio.PlayCreakAt(transform.position, 0.9f);
            Haptics.Light();
            for (float t = 0; t < d; t += Time.deltaTime)
            {
                transform.position = homePos + Random.insideUnitSphere * 0.02f * (t / d + 0.2f);
                yield return null;
            }
            foreach (var c in cols) if (c != null) c.enabled = false;
            if (shatter)
            {
                ProceduralAudio.PlayShatterAt(transform.position);
                foreach (var r in rends) if (r != null) r.enabled = false;
                yield break;
            }
            ProceduralAudio.PlayWhoosh(0.4f);
            Vector3 vel = Vector3.zero;
            Vector3 spin = Random.onUnitSphere * 90f;
            for (float t = 0; t < 2.5f; t += Time.deltaTime)
            {
                vel += Physics.gravity * Time.deltaTime;
                transform.position += vel * Time.deltaTime;
                transform.Rotate(spin * Time.deltaTime);
                yield return null;
            }
            foreach (var r in rends) if (r != null) r.enabled = false;
        }
    }
}
