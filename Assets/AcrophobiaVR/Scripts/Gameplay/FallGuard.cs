using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Detects stepping off a ledge (the rig dropping below the last checkpoint) and gently returns
    /// the player to the checkpoint with a quick fade - no falling animation, no punishment screen.
    /// </summary>
    public class FallGuard : MonoBehaviour
    {
        public float dropTolerance = 1.6f;

        void Update()
        {
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            if (rig == null || lc == null || lc.IsRespawning || SafeRoom.InSafeRoom || MovingPlatform.AnyRiding) return;
            if (rig.FeetY < CheckpointSystem.Position.y - dropTolerance)
                lc.Slip("fall");
        }
    }
}