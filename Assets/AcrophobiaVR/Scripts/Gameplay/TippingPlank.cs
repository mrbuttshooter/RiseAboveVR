using System.Collections;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// A loose board sticking out over the edge - a see-saw puzzle. Walk past the tipping point without
    /// weighing down the inner end and it creaks, wobbles... and tips you off. Back up during the wobble to
    /// save yourself. Once the counterweight is in place (the stabilizer objective is complete) it holds.
    /// </summary>
    public class TippingPlank : MonoBehaviour
    {
        public Transform pivot;                 // sits on the roof edge; everything that tips is its child
        public Vector3 outward = Vector3.forward;
        public float overhang = 3f;             // how far the board sticks out past the edge
        public float halfWidth = 0.45f;
        public float tipDistance = 0.6f;        // walking further out than this tips an unweighted board
        public float wobbleSeconds = 0.8f;
        public Objective stabilizer;            // e.g. "weigh the board down with the cement bag"
        public string warnLine = "Whoa! The board is see-sawing - back up, quick!";

        Quaternion rest;
        Vector3 axis;
        float wobbleStart = -1f;
        bool tipping;
        float nextCreak;
        Collider[] colliders;

        bool Stable => stabilizer != null && stabilizer.IsComplete;

        void Start()
        {
            rest = pivot.rotation;
            outward.y = 0f;
            outward.Normalize();
            axis = Vector3.Cross(Vector3.up, outward);   // rotating +angle about this tips the outer end down
            colliders = pivot.GetComponentsInChildren<Collider>(true);
        }

        void Update()
        {
            var rig = PlayerRig.Instance;
            var lc = LevelController.Instance;
            if (rig == null || lc == null || tipping) return;

            Vector3 feet = new Vector3(rig.Head.position.x, rig.FeetY, rig.Head.position.z);
            Vector3 rel = feet - pivot.position;
            float along = Vector3.Dot(rel, outward);
            Vector3 lateral = rel - outward * along;
            lateral.y = 0f;
            bool onBoard = along > -1.6f && along < overhang + 0.2f && lateral.magnitude < halfWidth + 0.15f && Mathf.Abs(rel.y) < 0.7f;

            if (Stable)
            {
                if (onBoard && along > 0.5f && Time.time > nextCreak)
                {
                    nextCreak = Time.time + Random.Range(1.5f, 3f);
                    ProceduralAudio.PlayCreakAt(pivot.position, 0.25f);
                }
                return;
            }

            if (onBoard && along > tipDistance && !lc.IsRespawning)
            {
                if (wobbleStart < 0f)
                {
                    wobbleStart = Time.time;
                    ProceduralAudio.PlayCreakAt(pivot.position, 1f);
                    Haptics.Medium();
                    FearSystem.Spike(0.3f);
                    Companion.Say(warnLine, 2.5f);
                }
                float w = Time.time - wobbleStart;
                SetAngle(Mathf.Sin(w * 28f) * 2.5f + w * 7f);
                if (w >= wobbleSeconds) StartCoroutine(TipOver());
            }
            else if (wobbleStart >= 0f)
            {
                // Stepped back in time: the board settles.
                wobbleStart = -1f;
                SetAngle(0f);
                ProceduralAudio.PlayClunkAt(pivot.position);
            }
        }

        void SetAngle(float degrees) => pivot.rotation = Quaternion.AngleAxis(degrees, axis) * rest;

        IEnumerator TipOver()
        {
            tipping = true;
            ProceduralAudio.PlayCreakAt(pivot.position, 1f);
            float start = Time.time - wobbleStart;
            float from = Mathf.Sin(start * 28f) * 2.5f + start * 7f;
            for (float t = 0f; t < 0.4f; t += Time.deltaTime)
            {
                float a = Mathf.Lerp(from, 42f, t / 0.4f);
                SetAngle(a);
                if (a > 14f) foreach (var c in colliders) if (c != null) c.enabled = false;
                yield return null;
            }
            SetAngle(42f);
            ProceduralAudio.PlayClunkAt(pivot.position);
            // The fall itself is real: FallGuard notices the drop and costs a life.
            yield return new WaitForSeconds(3f);
            SetAngle(0f);
            foreach (var c in colliders) if (c != null) c.enabled = true;
            wobbleStart = -1f;
            tipping = false;
        }
    }
}
