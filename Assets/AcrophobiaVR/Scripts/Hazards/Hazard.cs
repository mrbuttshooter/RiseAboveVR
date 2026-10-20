using System.Collections.Generic;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Base for obstacles that move or change during a run. Hazards only run while the level is live and are put
    /// back to their start state after a respawn (<see cref="ResetAll"/>), so every attempt is the same challenge.
    /// </summary>
    public abstract class Hazard : MonoBehaviour
    {
        static readonly List<Hazard> all = new List<Hazard>();

        protected virtual void OnEnable() => all.Add(this);
        protected virtual void OnDisable() => all.Remove(this);

        public static void ResetAll()
        {
            foreach (var h in all.ToArray()) if (h != null) h.ResetHazard();
        }

        /// <summary>Back to the start state (called after the player respawns).</summary>
        public virtual void ResetHazard() { }

        /// <summary>The level clock is running and the player is in control.</summary>
        protected static bool Live
        {
            get
            {
                var lc = LevelController.Instance;
                return lc == null || (lc.Started && !lc.Finished && !lc.IsRespawning);
            }
        }

        /// <summary>Hazards move only once the countdown is over (or always, outside a level).</summary>
        protected static bool Running
        {
            get
            {
                var lc = LevelController.Instance;
                return lc == null || (lc.Started && !lc.Finished);
            }
        }

        /// <summary>Roughly the middle of the player's body.</summary>
        protected static Vector3 PlayerChest
        {
            get
            {
                var rig = PlayerRig.Instance;
                if (rig == null) return Vector3.one * 99999f;
                Vector3 h = rig.Head.position;
                return new Vector3(h.x, Mathf.Lerp(rig.FeetY, h.y, 0.55f), h.z);
            }
        }

        /// <summary>Knocks the player sideways off the course and costs a life.</summary>
        protected static void KnockPlayer(Vector3 push, string reason = "hit")
        {
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            if (rig == null || lc == null || lc.IsRespawning || lc.Finished) return;
            push.y = 0f;
            rig.MoveBy(push.normalized * 0.9f + Vector3.up * 0.2f);
            ProceduralAudio.PlayClunk();
            Haptics.Strong();
            lc.Slip(reason);
        }
    }
}
