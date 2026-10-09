using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Detects a real fall: the player is well below their last checkpoint AND dropping fast. Climbing or
    /// walking back down to a lower floor never counts; going over an edge always does (it costs a life).
    /// </summary>
    public class FallGuard : MonoBehaviour
    {
        public float dropTolerance = 1.6f;
        public float fallSpeed = 3f;   // m/s downwards; after 1.6 m of free fall you're already doing ~5.6

        float lastFeet;
        bool hasLast;

        void Update()
        {
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            if (rig == null || lc == null || lc.IsRespawning || SafeRoom.InSafeRoom || MovingPlatform.AnyRiding)
            {
                hasLast = false;
                return;
            }
            float feet = rig.FeetY;
            float vy = hasLast ? (feet - lastFeet) / Mathf.Max(Time.deltaTime, 0.0001f) : 0f;
            lastFeet = feet;
            hasLast = true;
            if (feet < CheckpointSystem.Position.y - dropTolerance && vy < -fallSpeed)
                lc.Slip("fall");
        }
    }
}