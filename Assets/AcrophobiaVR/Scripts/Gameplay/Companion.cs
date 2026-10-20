using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Pip - a camera drone that races alongside the player and calls the run like an announcer
    /// (hints, taunts, time warnings). Speaks through subtitles plus a chirp.
    /// </summary>
    public class Companion : MonoBehaviour
    {
        public static Companion Instance { get; private set; }

        public static readonly string[] SlipLines =
        {
            "Ouch! That's a life gone. Back to the checkpoint - and faster this time!",
            "Gravity: 1, you: 0. Go again!",
            "That drop was... educational. The clock is still running!",
            "Splat. Get up, the timer doesn't care!",
            "Missed it! Commit to the jump next time.",
        };

        public static readonly string[] ReturnLines =
        {
            "Back on your feet - move it!",
            "Checkpoint! Don't waste it.",
        };

        public static readonly string[] EncourageLines =
        {
            "Faster! The clock is ticking!",
            "Stars are worth points - grab them if you dare.",
            "Gust coming? Crouch, or fly.",
            "Run, jump, don't look down. Or do - it's a long way!",
        };

        public static readonly string[] HurryLines =
        {
            "Thirty seconds left - MOVE!",
            "Half a minute! Sprint!",
        };

        public static readonly string[] NiceLines =
        {
            "Nice jump!",
            "Clean! Keep that pace!",
            "Ooh, smooth.",
            "Show-off. Keep going!",
        };

        public Transform body;
        [Tooltip("Pip is a camera drone: electronic chime instead of a chirp, propeller hum while visible.")]
        public bool drone;
        AudioSource hum;
        public Transform leftWing;
        public Transform rightWing;
        public Light glow;

        Vector3 velocity;
        Vector3 bodyBaseScale = Vector3.one;
        float nextIdleLine;

        float visibleUntil;
        bool shown = true;
        Renderer[] renderers;

        void Awake()
        {
            Instance = this;
            if (body != null) bodyBaseScale = body.localScale;
            nextIdleLine = Time.time + 120f;
            renderers = GetComponentsInChildren<Renderer>(true);
            if (leftWing != null)
            {
                wingRestL = leftWing.localRotation;
                wingAxisL = leftWing.parent.InverseTransformDirection(transform.forward);
            }
            if (rightWing != null)
            {
                wingRestR = rightWing.localRotation;
                wingAxisR = rightWing.parent.InverseTransformDirection(transform.forward);
            }
        }

        Quaternion wingRestL = Quaternion.identity, wingRestR = Quaternion.identity;
        Vector3 wingAxisL = Vector3.forward, wingAxisR = Vector3.forward;

        void Start()
        {
            // Pip waits out of sight until there is something to say.
            var rig = PlayerRig.Instance;
            if (rig != null) transform.position = rig.Head.position + Vector3.up * 5f;
            SetShown(false);
        }

        void SetShown(bool on)
        {
            if (shown == on) return;
            shown = on;
            foreach (var r in renderers) if (r != null) r.enabled = on;
            if (glow != null) glow.enabled = on;
        }

        public static void Say(string line, float seconds = 5f)
        {
            if (string.IsNullOrEmpty(line)) return;
            if (Instance != null) Instance.visibleUntil = Mathf.Max(Instance.visibleUntil, Time.time + seconds + 1.5f);
            HeadHud.Instance.ShowSubtitle("Pip", line, seconds);
            if (Instance != null && Instance.drone) ProceduralAudio.PlayChime(1.7f);
            else if (Instance != null) ProceduralAudio.PlayChirpAt(Instance.transform.position);
            else ProceduralAudio.PlayChirp();
            if (Instance != null) Instance.Pulse();
        }

        public static void SayRandom(string[] lines) => Say(lines[Random.Range(0, lines.Length)]);

        float pulse;

        void Pulse() => pulse = 1f;

        void LateUpdate()
        {
            var rig = PlayerRig.Instance;
            if (rig == null) return;
            var head = rig.Head;

            // Hover to the right of the view, slightly ahead and below eye level.
            Vector3 flatFwd = Vector3.ProjectOnPlane(head.forward, Vector3.up).normalized;
            if (flatFwd.sqrMagnitude < 0.01f) flatFwd = transform.forward;
            Vector3 right = Vector3.Cross(Vector3.up, flatFwd);
            Vector3 target = head.position + flatFwd * 0.9f + right * 0.55f + Vector3.up * (-0.05f + Mathf.Sin(Time.time * 2.1f) * 0.05f);
            // Pip only drops in to call the race, then flies off out of sight.
            bool wanted = Time.time < visibleUntil;
            if (!wanted)
                target = head.position + Vector3.up * 4.5f - flatFwd * 2f + right * 3f;
            SetShown(wanted || (transform.position - head.position).sqrMagnitude < 3.6f * 3.6f);
            if (hum == null && drone) hum = GetComponentInChildren<AudioSource>();
            if (hum != null) hum.mute = !shown;
            transform.position = Vector3.SmoothDamp(transform.position, target, ref velocity, 0.45f);
            Vector3 look = head.position - transform.position;
            if (look.sqrMagnitude > 0.001f)
                transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(look), Time.deltaTime * 4f);

            // Flap each wing about the bird's forward axis, starting from its resting pose (works for the model and the primitive Pip).
            float flap = Mathf.Sin(Time.time * 18f) * 35f;
            if (leftWing != null) leftWing.localRotation = Quaternion.AngleAxis(flap, wingAxisL) * wingRestL;
            if (rightWing != null) rightWing.localRotation = Quaternion.AngleAxis(-flap, wingAxisR) * wingRestR;

            pulse = Mathf.MoveTowards(pulse, 0f, Time.deltaTime * 1.5f);
            if (body != null) body.localScale = bodyBaseScale * (1f + pulse * 0.25f);
            if (glow != null) glow.intensity = 1.2f + pulse * 2f;

            if (Time.time > nextIdleLine && LevelController.Instance != null && LevelController.Instance.Started)
            {
                nextIdleLine = Time.time + Random.Range(140f, 220f);
                SayRandom(EncourageLines);
            }
        }
    }
}