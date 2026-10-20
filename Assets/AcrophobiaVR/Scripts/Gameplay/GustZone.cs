using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Wind gusts that really push you. While your head is inside the zone a gust builds every few seconds:
    /// a rising whoosh and a warning, then a shove (towards the edge, or a random side). Crouch to hold on
    /// (C on desktop, really crouch in VR). With no railings, a gust near the edge can blow you off.
    /// </summary>
    public class GustZone : MonoBehaviour
    {
        public Vector3 size = new Vector3(10f, 4f, 10f);
        public Vector3 pushDirection = Vector3.forward;   // world space
        public bool randomSide;                           // flip the direction at random for each gust
        public float pushSpeed = 1.2f;                    // m/s at the peak of a gust (desktop)
        public float vrScale = 0.55f;                     // a gentler shove in a headset (comfort)
        public Vector2 interval = new Vector2(7f, 12f);
        public float warning = 2f;
        public float duration = 1.6f;

        float nextGust;
        float gustStart = -100f;
        bool warned;
        bool gusting;
        Vector3 dir = Vector3.forward;
        ParticleSystem streaks;

        void Start()
        {
            streaks = Effects.CreateWindStreaks(transform);
            Schedule();
        }

        void Schedule()
        {
            float wind = Mathf.Max(0.3f, Difficulty.Wind);
            nextGust = Time.time + Random.Range(interval.x, interval.y) / wind;
        }

        bool Contains(Vector3 p)
        {
            Vector3 d = Quaternion.Inverse(transform.rotation) * (p - transform.position);
            return Mathf.Abs(d.x) <= size.x * 0.5f && Mathf.Abs(d.y) <= size.y * 0.5f && Mathf.Abs(d.z) <= size.z * 0.5f;
        }

        void Update()
        {
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            bool inside = rig != null && lc != null && lc.Started && !lc.Finished && !lc.IsRespawning && Contains(rig.Head.position);
            if (!inside)
            {
                // Keep the next gust a little way off so stepping in never means an instant shove.
                if (Time.time > nextGust - warning - 1f) Schedule();
                warned = false;
                SetGusting(false);
                return;
            }

            if (!warned && Time.time > nextGust - warning)
            {
                warned = true;
                dir = pushDirection;
                dir.y = 0f;
                dir = dir.normalized * (randomSide && Random.value < 0.5f ? -1f : 1f);
                ProceduralAudio.PlayWhoosh(0.45f);
                HeadHud.Instance.ShowMessage(rig.IsDesktop ? "Gust coming - crouch! (hold C)" : "Gust coming - crouch down!", warning);
            }
            if (Time.time > nextGust)
            {
                gustStart = Time.time;
                warned = false;
                Schedule();
                ProceduralAudio.PlayWhoosh(1f);
                Haptics.Pulse(0.7f, 0.5f);
                if (streaks != null)
                {
                    // The streak emitter blows along its local +X.
                    streaks.transform.SetPositionAndRotation(rig.Head.position, Quaternion.LookRotation(dir) * Quaternion.Euler(0f, -90f, 0f));
                    streaks.Play();
                }
            }

            float t = (Time.time - gustStart) / duration;
            bool gust = t >= 0f && t < 1f;
            SetGusting(gust);
            if (!gust) return;
            float speed = pushSpeed * Mathf.Sin(t * Mathf.PI) * Difficulty.Wind;
            if (!rig.IsDesktop) speed *= vrScale;
            if (lc.IsCrouching) speed *= 0.12f;
            rig.MoveBy(dir * speed * Time.deltaTime);
        }

        void SetGusting(bool on)
        {
            if (gusting == on) return;
            gusting = on;
            AmbientAudio.GustBoost = on ? 1f : 0f;
        }

        void OnDisable() => SetGusting(false);

        void OnDrawGizmosSelected()
        {
            Gizmos.matrix = Matrix4x4.TRS(transform.position, transform.rotation, Vector3.one);
            Gizmos.DrawWireCube(Vector3.zero, size);
        }
    }
}
