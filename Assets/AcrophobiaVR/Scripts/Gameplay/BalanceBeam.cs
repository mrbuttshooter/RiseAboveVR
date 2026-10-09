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

        /// <summary>Until this time every beam acts as if a gust is blowing (set by FlyBy rotor wash).</summary>
        public static float ExternalGustUntil;

        [Header("Shape")]
        public Transform start;
        public Transform end;
        public float walkableHalfWidth = 0.25f;
        public float heightAbove = 2.6f;
        public Transform wobbleVisual;

        [Header("Difficulty")]
        public float driftFillRate = 0.6f;
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
        float nextCreak;
        float nextSoftCreak;
        float nextMeterPulse;

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
                    if (playerOn) Haptics.Pulse(0.6f, 0.4f);
                    if (gustParticles != null) gustParticles.Play();
                    ScheduleGust();
                    warned = false;
                }
                gustNow = Time.time - gustStart < gustDuration;
                AmbientAudio.GustBoost = gustNow ? 1f : 0f;
            }
            // Something else is blasting the beam (a helicopter's rotor wash).
            if (Time.time < ExternalGustUntil) gustNow = true;

            if (active)
            {
                // Real heads sway ~10 cm even when standing still, so never make the safe band narrower than 15 cm.
                float safe = Mathf.Max(0.15f, walkableHalfWidth * (ExposureSettings.Mode == ExposureMode.Gentle ? 0.9f : 0.6f));
                float fill = 0f;
                if (lateral > safe) fill += driftFillRate * ModeScale * Mathf.Clamp01((lateral - safe) / walkableHalfWidth + 0.3f);
                if (gustNow && !lc.IsCrouching) fill += gustFillRate * ModeScale;

                if (fill > 0f) meter += fill * Time.deltaTime;
                else meter -= recoverRate * Time.deltaTime;
                meter = Mathf.Clamp01(meter);

                if (meter > 0.05f)
                    HeadHud.Instance.ShowProgress(meter, gustNow && !lc.IsCrouching ? "Crouch! Hold on!" : "Balance - step back to the centre",
                        Color.Lerp(UIFactory.Warn, new Color(1f, 0.3f, 0.3f), meter));

                // The beam creaks under the player: louder and deeper the more they wobble.
                Vector3 underFoot = new Vector3(closest.x, Mathf.Min(closest.y, head.y), closest.z);
                if (meter > 0.15f && Time.time >= nextCreak)
                {
                    nextCreak = Time.time + Random.Range(0.5f, 1.4f);
                    ProceduralAudio.PlayCreakAt(underFoot, meter);
                }
                if (Time.time >= nextSoftCreak)
                {
                    nextSoftCreak = Time.time + Random.Range(3f, 6f);
                    ProceduralAudio.PlayCreakAt(underFoot, 0.15f);
                }
                if (meter > 0.6f && Time.time >= nextMeterPulse)
                {
                    nextMeterPulse = Time.time + 0.4f;
                    Haptics.Light();
                }

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