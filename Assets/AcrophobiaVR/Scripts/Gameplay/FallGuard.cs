using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Detects a real fall in a jumping game: dropping more than <see cref="maxDrop"/> below the last surface you
    /// stood on, or going below the level's kill height (the street, the gap between towers). Jumping down to a
    /// lower roof is fine; missing a jump costs a life.
    /// </summary>
    public class FallGuard : MonoBehaviour
    {
        [Tooltip("World height below which you have definitely fallen off the course.")]
        public float killY = -1000f;
        [Tooltip("Free-fall distance below the last surface you stood on that counts as a fall.")]
        public float maxDrop = 4.5f;

        float lastGroundY;
        bool hasGround;

        void Update()
        {
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            if (rig == null || lc == null || lc.IsRespawning || lc.Finished || MovingPlatform.AnyRiding || Zipline.Riding)
            {
                hasGround = false;
                return;
            }
            float feet = rig.FeetY;
            bool grounded = (rig.Body != null && rig.Body.enabled && rig.Body.isGrounded) || rig.GroundCollider() != null;
            if (grounded || !hasGround)
            {
                lastGroundY = feet;
                hasGround = true;
            }
            if (feet < killY || lastGroundY - feet > maxDrop)
            {
                hasGround = false;
                lc.Slip("fall");
            }
        }
    }
}
