using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Pip - a little glowing bird-drone that floats beside the player, gives instructions and
    /// encouragement, and reacts to what happens. Speaks through subtitles plus a chirp.
    /// </summary>
    public class Companion : MonoBehaviour
    {
        public static Companion Instance { get; private set; }

        public static readonly string[] SlipLines =
        {
            "Oof! Down you go - that's a heart gone. Back to the checkpoint!",
            "The ground says hi! Shake it off and try again.",
            "Whoa! Eyes on where you want to go, not on the drop.",
            "Splat-free landing, thanks to me. Careful - hearts don't grow on trees!",
        };

        public static readonly string[] ReturnLines =
        {
            "Welcome back! Let's finish this.",
            "Ready again? I'm right here with you.",
            "Recharged? Back to the heights!",
        };

        public static readonly string[] EncourageLines =
        {
            "Nice moves up here!",
            "Courage stars hide at the scariest spots - have you found them all?",
            "If I shout 'gust', crouch! Trust me on this one.",
            "Heart racing? Look up at the sky for a second - it helps.",
        };

        public Transform body;
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
        }

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
            if (Instance != null) ProceduralAudio.PlayChirpAt(Instance.transform.position);
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
            // During a panic wave Pip climbs above the player's head, glowing, so their gaze follows it up to the sky.
            if (FearSystem.Panicking)
                target = head.position + flatFwd * 1.1f + Vector3.up * (1.6f + Mathf.Sin(Time.time * 3f) * 0.1f);
            // Pip only drops in to talk (or help in a panic), then flies off out of sight.
            bool wanted = Time.time < visibleUntil || FearSystem.Panicking;
            if (!wanted)
                target = head.position + Vector3.up * 4.5f - flatFwd * 2f + right * 3f;
            SetShown(wanted || (transform.position - head.position).sqrMagnitude < 3.6f * 3.6f);
            transform.position = Vector3.SmoothDamp(transform.position, target, ref velocity, 0.45f);
            Vector3 look = head.position - transform.position;
            if (look.sqrMagnitude > 0.001f)
                transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(look), Time.deltaTime * 4f);

            float flap = Mathf.Sin(Time.time * 18f) * 35f;
            if (leftWing != null) leftWing.localRotation = Quaternion.Euler(0f, 0f, flap);
            if (rightWing != null) rightWing.localRotation = Quaternion.Euler(0f, 0f, -flap);

            pulse = Mathf.MoveTowards(pulse, 0f, Time.deltaTime * 1.5f);
            if (body != null) body.localScale = bodyBaseScale * (1f + pulse * 0.25f);
            if (glow != null) glow.intensity = 1.2f + pulse * 2f;

            if (Time.time > nextIdleLine && LevelController.Instance != null && LevelController.Instance.Started && !SafeRoom.InSafeRoom)
            {
                nextIdleLine = Time.time + Random.Range(140f, 220f);
                SayRandom(EncourageLines);
            }
        }
    }
}