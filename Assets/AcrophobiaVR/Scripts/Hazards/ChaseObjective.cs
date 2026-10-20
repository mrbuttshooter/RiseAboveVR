using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Chase a runaway (Kiwi the parrot) across the course: she waits on a perch until you get close, then flies
    /// off to the next one. At the last perch she's cornered - touch her to catch her.
    /// </summary>
    public class ChaseObjective : Objective
    {
        public Transform target;
        public Transform[] perches;
        public float fleeRadius = 3.2f;
        public float catchRadius = 1.3f;
        public float flightSeconds = 1.8f;
        public float arcHeight = 3f;
        [Tooltip("Catching the runaway ends the level (no separate goal zone).")]
        public bool finishOnCatch = true;
        [TextArea] public string[] tauntLines =
        {
            "Squawk! Too slow!",
            "Kiwi's laughing at you. Jump!",
            "She's heading for the next roof!",
            "Nearly! Don't let her get away!",
        };

        int perch;
        bool flying;
        float flyT;
        Vector3 flyFrom, flyTo;
        Quaternion flyRot;

        public override string ProgressSuffix => IsComplete || perches == null ? "" : "  (" + perch + "/" + (perches.Length - 1) + ")";

        void Start()
        {
            if (target != null && perches != null && perches.Length > 0)
                target.SetPositionAndRotation(perches[0].position, perches[0].rotation);
        }

        void Update()
        {
            if (target == null || perches == null || perches.Length == 0 || IsComplete) return;
            if (flying)
            {
                flyT += Time.deltaTime / flightSeconds;
                float k = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(flyT));
                Vector3 p = Vector3.Lerp(flyFrom, flyTo, k) + Vector3.up * Mathf.Sin(k * Mathf.PI) * arcHeight;
                Vector3 vel = p - target.position;
                target.position = p;
                vel.y = 0f;
                if (vel.sqrMagnitude > 1e-5f) target.rotation = Quaternion.Slerp(target.rotation, Quaternion.LookRotation(vel), Time.deltaTime * 10f);
                if (flyT >= 1f)
                {
                    flying = false;
                    target.rotation = flyRot;
                }
                return;
            }
            if (!IsActive) return;
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            if (rig == null || (lc != null && lc.IsRespawning)) return;
            float d = Vector3.Distance(rig.Head.position, target.position);
            bool last = perch >= perches.Length - 1;
            if (last)
            {
                // She sits at your feet: catch on horizontal distance (or a VR hand on her).
                Vector3 flat = rig.Head.position - target.position;
                float vertical = flat.y;
                flat.y = 0f;
                bool handOn = false;
                foreach (var hand in new[] { rig.LeftHand, rig.RightHand })
                    if (hand != null && Vector3.Distance(hand.position, target.position) < 0.45f) handOn = true;
                if ((flat.magnitude < catchRadius && vertical > -0.5f && vertical < 2.4f) || handOn)
                {
                    ProceduralAudio.PlayChirpAt(target.position);
                    Haptics.Strong();
                    Achievements.Unlock("kiwi_caught");
                    target.gameObject.SetActive(false);
                    Complete();
                    if (finishOnCatch && lc != null) lc.TryFinish();
                }
            }
            else if (d < fleeRadius)
            {
                perch++;
                flyFrom = target.position;
                flyTo = perches[perch].position;
                flyRot = perches[perch].rotation;
                flyT = 0f;
                flying = true;
                ProceduralAudio.PlayChirpAt(target.position);
                ProceduralAudio.PlayFlutterAt(target.position);
                if (tauntLines != null && tauntLines.Length > 0 && Random.value < 0.6f)
                    Companion.Say(tauntLines[Random.Range(0, tauntLines.Length)], 2f);
            }
        }
    }
}
