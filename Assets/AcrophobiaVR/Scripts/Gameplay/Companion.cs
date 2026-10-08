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
            "Whoops! You're safe - back at the checkpoint. Take your time.",
            "That's okay. Every climber slips. Let's try again, slowly.",
            "Deep breath. Eyes on where you want to go, not on the drop.",
            "Back on solid ground. You've got this.",
        };

        public static readonly string[] ReturnLines =
        {
            "Welcome back. Small steps, steady breaths.",
            "Ready again? I'm right here with you.",
            "Taking a break was smart. Let's keep going.",
        };

        public static readonly string[] EncourageLines =
        {
            "You're doing great. Notice your feet on solid ground.",
            "Your body is safe. The fear will rise, and then it will pass.",
            "Slow breath in... and out. Nice.",
            "Look how far you've come!",
        };

        public Transform body;
        public Transform leftWing;
        public Transform rightWing;
        public Light glow;

        Vector3 velocity;
        Vector3 bodyBaseScale = Vector3.one;
        float nextIdleLine;

        void Awake()
        {
            Instance = this;
            if (body != null) bodyBaseScale = body.localScale;
            nextIdleLine = Time.time + 60f;
        }

        public static void Say(string line, float seconds = 5f)
        {
            if (string.IsNullOrEmpty(line)) return;
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
                nextIdleLine = Time.time + Random.Range(70f, 110f);
                SayRandom(EncourageLines);
            }
        }
    }
}