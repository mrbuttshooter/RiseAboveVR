using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Remembers where the player should reappear after a slip or after leaving the safe room.</summary>
    public static class CheckpointSystem
    {
        static Vector3 position;
        static Vector3 forward = Vector3.forward;

        public static Vector3 Position => position;
        public static Vector3 Forward => forward;
        public static string Label { get; private set; } = "Start";

        public static void Set(Transform point, string label)
        {
            position = point.position;
            forward = point.forward;
            Label = label;
        }

        public static void RespawnPlayer()
        {
            if (PlayerRig.Instance != null) PlayerRig.Instance.TeleportTo(position, forward);
        }
    }
}
