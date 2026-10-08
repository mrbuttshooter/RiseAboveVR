using System.Collections.Generic;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Balance challenge on narrow planks/beams. A balance meter fills when your head drifts off the
    /// centre line, and during wind gusts unless you crouch. Full meter = slip (back to checkpoint).
    /// The beam visibly wobbles with your balance. The camera itself is never moved (no nausea).
    /// </summary>
    public class BalanceBeam : MonoBehaviour
    {
        static readonly List<BalanceBeam> All = new List<BalanceBeam>();

        [Header("Shape")]
        public Transform start;
        public Transform end;
        public float walkableHalfWidth = 0.25f;
        public float heightAbove = 2.6f;
        public Transform wobbleVisual;

        [Header("Difficulty")]
        public float driftFillRate = 0.9f;
        public float recoverRate = 0.6f;
        public bool gusts;
        public Vector2 gustInterval = new Vector2(9f, 15f);
        public float gustWarning = 2.5f;
        public float gustDuration = 3f;
        public float gustFillRate = 0.55f;

        float meter;
        float nextGust;
        float gustStart = -100f;
        bool warned;
        ParticleSystem gustParticles;
        bool playerOn;

        public static void ResetAll()
        {
            foreach (var b in All) b.meter = 0f;
        }

        void OnEnable() => All.Add(this);
        void OnDisable() => All.Remove(this);

        void Start()
        {
            ScheduleGust();
            if (gusts) gustParticles = Effects.CreateWindStreaks(transform);
        }

        void ScheduleGust() => nextGust = Time.time + Random.Range(gustInterval.x, gustInterval.y);

        float ModeScale
        {
            get
            {
                switch (ExposureSettings.Mode)
                {
                    case ExposureMode.Gentle: return 0.55f;
                    case ExposureMode.Brave: return 1.35f;
                    default: return 1f;
                }
            }
        }

        void Update()
        {
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            if (rig == null || lc == null || start == null || end == null) return;

            Vector3 head = rig.Head.position;
            Vector3 a = start.position, b = end.position;
            Vector3 ab = b - a;
            Vector3 abFlat = new Vector3(ab.x, 0f, ab.z);
            Vector3 ah = head - a;
            float t = Vector3.Dot(new Vector3(ah.x, 0f, ah.z), abFlat) / abFlat.sqrMagnitude;
            Vector3 closest = a + ab * Mathf.Clamp01(t);
            Vector3 side = head - closest;
            float lateral = new Vector2(side.x, side.z).magnitude;
            float above = head.y - closest.y;

            playerOn = t > 0f && t < 1f && above > 0f && above < heightAbove && lateral < walkableHalfWidth + 0.6f;
            bool active = playerOn && lc.Started && !lc.IsRespawning && !SafeRoom.InSafeRoom;

            // Wind gusts
            bool gustNow = false;
            if (gusts && lc.Started)
            {
                if (!warned && Time.time > nextGust - gustWarning)
                {
                    warned = true;
                    ProceduralAudio.PlayWhoosh(0.35f);
                    if (playerOn) HeadHud.Instance.ShowMessage("Gust incoming - crouch down!", gustWarning);
                }
                if (Time.time > nextGust)
                {
                    gustStart = Time.time;
                    ProceduralAudio.PlayWhoosh(1f);
                    if (gustParticles != null) gustParticles.Play();
                    ScheduleGust();
                    warned = false;
                }
                gustNow = Time.time - gustStart < gustDuration;
                AmbientAudio.GustBoost = gustNow ? 1f : 0f;
            }

            if (active)
            {
                float safe = walkableHalfWidth * (ExposureSettings.Mode == ExposureMode.Gentle ? 0.9f : 0.6f);
                float fill = 0f;
                if (lateral > safe) fill += driftFillRate * ModeScale * Mathf.Clamp01((lateral - safe) / walkableHalfWidth + 0.3f);
                if (gustNow && !lc.IsCrouching) fill += gustFillRate * ModeScale;

                if (fill > 0f) meter += fill * Time.deltaTime;
                else meter -= recoverRate * Time.deltaTime;
                meter = Mathf.Clamp01(meter);

                if (meter > 0.05f)
                    HeadHud.Instance.ShowProgress(meter, gustNow && !lc.IsCrouching ? "Crouch! Hold on!" : "Balance - step back to the centre",
                        Color.Lerp(UIFactory.Warn, new Color(1f, 0.3f, 0.3f), meter));

                if (meter >= 1f)
                {
                    meter = 0f;
                    lc.Slip(gustNow ? "gust" : "balance");
                }
            }
            else
            {
                meter = Mathf.MoveTowards(meter, 0f, recoverRate * Time.deltaTime);
            }

            if (wobbleVisual != null)
            {
                float wobble = (playerOn ? meter * 6f : 0f) + (gustNow ? 2.5f : 0f);
                float angle = Mathf.Sin(Time.time * 5f) * wobble + Mathf.Sin(Time.time * 1.3f) * 0.3f;
                wobbleVisual.localRotation = Quaternion.Euler(0f, 0f, angle);
            }
        }

        void OnDrawGizmos()
        {
            if (start == null || end == null) return;
            Gizmos.color = Color.yellow;
            Gizmos.DrawLine(start.position, end.position);
        }
    }
}