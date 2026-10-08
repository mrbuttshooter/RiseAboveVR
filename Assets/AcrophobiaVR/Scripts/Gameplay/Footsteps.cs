using System;
using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace AcrophobiaVR
{
    /// <summary>
    /// Surface-aware footsteps for both VR (room-scale walking + smooth locomotion) and desktop.
    /// Tracks how far the head travels horizontally and plays a positional step on the surface under
    /// the player every stride. Planks high above the ground occasionally creak.
    /// Added at runtime to the PlayerRig GameObject.
    /// </summary>
    public class Footsteps : MonoBehaviour
    {
        public float stride = 0.65f;
        public float crouchStride = 0.45f;
        public float volume = 0.5f;
        public float teleportThreshold = 1.5f;
        [Range(0f, 1f)] public float highPlankCreakChance = 0.25f;
        public float highPlankDrop = 8f;

        static readonly string[] WoodKeys = { "Plank", "Deck", "Wood", "Bench", "Tile" };
        static readonly string[] MetalKeys = { "Grate", "Steel", "Metal", "Scaffold", "Rail", "Beam", "IBeam", "Crane", "Lift" };
        static readonly string[] GrassKeys = { "Grass", "Meadow" };
        static readonly RaycastHit[] Hits = new RaycastHit[8];

        PlayerRig trackedRig;
        Vector3 lastPos;
        Vector3 anchor;
        bool hasLast;
        bool leftFoot;

        void Awake()
        {
            // Idempotent runtime dressing: only one Footsteps per GameObject.
            if (GetComponent<Footsteps>() != this) Destroy(this);
        }

        void OnEnable() => hasLast = false;

        void Update()
        {
            if (Time.deltaTime <= 0f) return;
            var rig = PlayerRig.Instance;
            Transform head = rig != null ? rig.Head : null;
            if (head == null) { hasLast = false; return; }

            Vector3 p = head.position;
            if (!hasLast || rig != trackedRig)
            {
                trackedRig = rig;
                ResetTo(p);
                return;
            }

            Vector3 frame = p - lastPos;
            frame.y = 0f;
            lastPos = p;

            var lc = LevelController.Instance;
            bool ignore = (lc != null && lc.IsRespawning) || MovingPlatform.AnyRiding || frame.magnitude > teleportThreshold;
            if (ignore) { anchor = p; return; }

            bool crouching = lc != null && lc.IsCrouching;
            float s = crouching ? crouchStride : stride;
            Vector3 moved = p - anchor;
            moved.y = 0f;
            if (moved.sqrMagnitude < s * s) return;

            anchor = p;
            Step(rig, p, moved, crouching);
        }

        void ResetTo(Vector3 p)
        {
            lastPos = p;
            anchor = p;
            hasLast = true;
        }

        void Step(PlayerRig rig, Vector3 headPos, Vector3 moveDir, bool crouching)
        {
            if (!FindGround(rig, headPos, out RaycastHit hit)) return;

            StepSurface surface = Classify(hit.collider);

            // Alternate left/right foot slightly to the side of the walking line, with a tiny level change.
            leftFoot = !leftFoot;
            Vector3 fwd = moveDir.sqrMagnitude > 1e-6f ? moveDir.normalized : Vector3.forward;
            Vector3 sideways = Vector3.Cross(Vector3.up, fwd);
            Vector3 footPos = hit.point + sideways * (leftFoot ? -0.11f : 0.11f);
            float vol = volume * (leftFoot ? 1f : 0.92f) * (crouching ? 0.7f : 1f);
            ProceduralAudio.PlayFootstep(surface, footPos, vol);

            if (surface == StepSurface.Wood && UnityEngine.Random.value < highPlankCreakChance && IsHighAbove(hit.point, headPos))
                ProceduralAudio.PlayCreakAt(hit.point, 0.3f);
        }

        bool FindGround(PlayerRig rig, Vector3 origin, out RaycastHit best)
        {
            best = default;
            int n = Physics.RaycastNonAlloc(origin, Vector3.down, Hits, 3f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
            Transform root = rig.Root;
            float bestDist = float.MaxValue;
            bool found = false;
            for (int i = 0; i < n; i++)
            {
                var h = Hits[i];
                var c = h.collider;
                if (c == null || h.distance >= bestDist) continue;
                if (c is CharacterController) continue;
                Transform t = c.transform;
                if (root != null && t.IsChildOf(root)) continue;
                if (t.IsChildOf(rig.transform)) continue;
                if (c.GetComponentInParent<XRBaseInteractable>() != null) continue; // held / grabbable items
                bestDist = h.distance;
                best = h;
                found = true;
            }
            return found;
        }

        bool IsHighAbove(Vector3 plankPoint, Vector3 headPos)
        {
            Vector3 below = plankPoint + Vector3.down * 0.25f;
            float groundY;
            if (Physics.Raycast(below, Vector3.down, out RaycastHit g, 300f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore)) groundY = g.point.y;
            else groundY = below.y - 300f;
            return headPos.y - groundY > highPlankDrop;
        }

        static StepSurface Classify(Collider c)
        {
            if (c.GetComponentInParent<CrackingGlass>() != null) return StepSurface.Glass;

            GameObject go = c.gameObject;
            string goName = go.name;
            string parentName = go.transform.parent != null ? go.transform.parent.name : string.Empty;
            string matName = string.Empty;
            var rend = go.GetComponent<Renderer>();
            if (rend != null && rend.sharedMaterial != null) matName = rend.sharedMaterial.name;

            if (Has(goName, "Glass") || Has(matName, "Glass")) return StepSurface.Glass;

            if (go.GetComponentInParent<CrumblingTile>() != null)
            {
                bool woodTile = HasAny(goName, matName, parentName, "Plank") || HasAny(goName, matName, parentName, "Wood");
                return woodTile ? StepSurface.Wood : StepSurface.Concrete;
            }

            if (MatchAny(goName, matName, parentName, WoodKeys)) return StepSurface.Wood;
            if (MatchAny(goName, matName, parentName, MetalKeys)) return StepSurface.Metal;
            if (MatchAny(goName, matName, parentName, GrassKeys)) return StepSurface.Grass;
            return StepSurface.Concrete;
        }

        static bool MatchAny(string a, string b, string c, string[] keys)
        {
            for (int i = 0; i < keys.Length; i++)
                if (HasAny(a, b, c, keys[i])) return true;
            return false;
        }

        static bool HasAny(string a, string b, string c, string key) => Has(a, key) || Has(b, key) || Has(c, key);

        static bool Has(string s, string key) =>
            !string.IsNullOrEmpty(s) && s.IndexOf(key, StringComparison.OrdinalIgnoreCase) >= 0;
    }
}
