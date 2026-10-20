using System.Collections;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Open lift / crane-carried beam. Stand on it for a moment to start. Carries the player along
    /// its waypoints. Can stall part-way (a scripted scare with the companion reassuring you).
    /// </summary>
    public class MovingPlatform : MonoBehaviour
    {
        public Transform[] waypoints;
        public float speed = 1.2f;
        public float boardSeconds = 2f;
        public HeadZoneRide rideZone;
        public int stallAtWaypoint = -1;
        public float stallSeconds = 5f;
        [TextArea] public string stallLine = "Hmm, the lift stopped. That happens - it's perfectly safe. Look around while we wait.";
        [TextArea] public string startLine;
        public Transform swingVisual;
        public float swingDegrees = 0f;
        public CheckpointZone arrivalCheckpoint;
        public Objective requiredObjective;
        [TextArea] public string lockedHint = "Finish the task first";

        float nextLockedHint;

        bool moving;
        bool done;
        float boardTimer;

        public bool IsMoving => moving;

        /// <summary>False while the platform is stalled mid-ride, so the motor falls silent (the silence is part of the scare).</summary>
        public bool MotorRunning => moving && !stalled;

        bool stalled;

        /// <summary>True while any platform is carrying the player (fall detection is paused).</summary>
        public static bool AnyRiding { get; private set; }

        void OnDisable() { if (moving) AnyRiding = false; }

        void Update()
        {
            if (moving || done || rideZone == null) return;
            var lc = LevelController.Instance;
            if (lc == null || !lc.Started) return;
            if (rideZone.PlayerInside && requiredObjective != null && !requiredObjective.IsComplete)
            {
                if (Time.time > nextLockedHint) { HeadHud.Instance.ShowMessage(lockedHint, 3f); nextLockedHint = Time.time + 6f; }
                boardTimer = 0f;
            }
            else if (rideZone.PlayerInside)
            {
                boardTimer += Time.deltaTime;
                HeadHud.Instance.ShowProgress(boardTimer / boardSeconds, "Hold still to start");
                if (boardTimer >= boardSeconds) StartCoroutine(Ride());
            }
            else boardTimer = 0f;

            if (swingVisual != null && swingDegrees > 0f)
                swingVisual.localRotation = Quaternion.Euler(Mathf.Sin(Time.time * 0.9f) * swingDegrees * 0.3f, 0f, 0f);
        }

        IEnumerator Ride()
        {
            moving = true;
            AnyRiding = true;
            var rig = PlayerRig.Instance;
            rig.SetLocomotionEnabled(false);
            ProceduralAudio.PlayClunkAt(transform.position);
            Haptics.Medium();
            if (!string.IsNullOrEmpty(startLine)) Companion.Say(startLine, 5f);
            AmbientAudio.Machinery = 1f;

            for (int i = 1; i < waypoints.Length; i++)
            {
                Vector3 from = transform.position;
                Vector3 to = waypoints[i].position;
                float dist = Vector3.Distance(from, to);
                float dur = dist / speed;
                Vector3 last = from;
                for (float t = 0; t < dur; t += Time.deltaTime)
                {
                    float k = Mathf.SmoothStep(0f, 1f, t / dur);
                    Vector3 p = Vector3.Lerp(from, to, k);
                    Vector3 delta = p - last;
                    transform.position = p;
                    rig.MoveBy(delta);
                    last = p;
                    if (swingVisual != null && swingDegrees > 0f)
                        swingVisual.localRotation = Quaternion.Euler(Mathf.Sin(Time.time * 0.9f) * swingDegrees, 0f, 0f);
                    yield return null;
                }
                Vector3 final = to - last;
                transform.position = to;
                rig.MoveBy(final);

                if (i == stallAtWaypoint)
                {
                    AmbientAudio.Machinery = 0f;
                    stalled = true;
                    ProceduralAudio.PlayClunkAt(transform.position);
                    Haptics.Medium();
                    Companion.Say(stallLine, stallSeconds);
                    SessionLogger.Log(UnityEngine.SceneManagement.SceneManager.GetActiveScene().name, "lift_stall");
                    float s = Difficulty.Level == DifficultyLevel.Easy ? stallSeconds * 0.5f : stallSeconds;
                    for (float t = 0; t < s; t += Time.deltaTime)
                    {
                        // The platform shudders a little (the camera stays still).
                        if (swingVisual != null) swingVisual.localPosition = Random.insideUnitSphere * 0.004f;
                        yield return null;
                    }
                    if (swingVisual != null) swingVisual.localPosition = Vector3.zero;
                    stalled = false;
                    ProceduralAudio.PlayClunkAt(transform.position);
                    Haptics.Medium();
                    Companion.Say("And we're moving again. Well done for staying calm!", 3.5f);
                    AmbientAudio.Machinery = 1f;
                }
            }

            AmbientAudio.Machinery = 0f;
            ProceduralAudio.PlayClunkAt(transform.position);
            Haptics.Medium();
            rig.SetLocomotionEnabled(true);
            moving = false;
            AnyRiding = false;
            done = true;
            if (arrivalCheckpoint != null) CheckpointSystem.Set(arrivalCheckpoint.respawnPoint != null ? arrivalCheckpoint.respawnPoint : arrivalCheckpoint.transform, arrivalCheckpoint.label);
        }
    }
}