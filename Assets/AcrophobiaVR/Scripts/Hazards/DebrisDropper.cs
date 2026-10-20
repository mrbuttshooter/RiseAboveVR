using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Drops debris (steel offcuts) onto an area of the course. A glowing warning circle marks where each piece will
    /// land; half the time it aims at you. Getting hit knocks you off (costs a life).
    /// The area is a box centred on this transform; transform.position.y is the walking surface.
    /// </summary>
    public class DebrisDropper : Hazard
    {
        public Vector3 areaSize = new Vector3(4f, 0f, 10f);
        public float interval = 2.2f;
        public float warning = 0.9f;
        public float dropHeight = 14f;
        public Vector3 debrisSize = new Vector3(0.5f, 0.25f, 1.2f);
        public Material debrisMaterial;
        public Material warningMaterial;

        enum State { Idle, Warn, Fall, Landed }

        float next;
        GameObject marker, piece;
        Vector3 target;
        float fallY, vy;
        State state;
        float stateTime;

        public override void ResetHazard()
        {
            state = State.Idle;
            next = Time.time + interval;
            if (marker != null) marker.SetActive(false);
            if (piece != null) piece.SetActive(false);
        }

        bool PlayerInArea(out Vector3 p)
        {
            p = PlayerChest;
            Vector3 l = transform.InverseTransformPoint(p);
            return Mathf.Abs(l.x) < areaSize.x * 0.5f + 1f && Mathf.Abs(l.z) < areaSize.z * 0.5f + 1f && l.y > -1f && l.y < 4f;
        }

        void Ensure()
        {
            if (marker == null)
            {
                marker = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                marker.name = "DebrisWarning";
                Destroy(marker.GetComponent<Collider>());
                marker.transform.SetParent(transform, false);
                marker.transform.localScale = new Vector3(1.1f, 0.005f, 1.1f);
                if (warningMaterial != null) marker.GetComponent<Renderer>().sharedMaterial = warningMaterial;
                marker.SetActive(false);
            }
            if (piece == null)
            {
                piece = GameObject.CreatePrimitive(PrimitiveType.Cube);
                piece.name = "Debris";
                Destroy(piece.GetComponent<Collider>());
                piece.transform.SetParent(transform, false);
                piece.transform.localScale = debrisSize;
                if (debrisMaterial != null) piece.GetComponent<Renderer>().sharedMaterial = debrisMaterial;
                piece.SetActive(false);
            }
        }

        void Update()
        {
            if (!Running) return;
            Ensure();
            stateTime += Time.deltaTime;
            switch (state)
            {
                case State.Idle:
                {
                    if (Time.time < next || !Live) return;
                    bool aim = PlayerInArea(out Vector3 p) && Random.value < 0.5f;
                    Vector3 local = aim ? transform.InverseTransformPoint(p)
                        : new Vector3(Random.Range(-0.5f, 0.5f) * areaSize.x, 0f, Random.Range(-0.5f, 0.5f) * areaSize.z);
                    local.y = 0f;
                    target = transform.TransformPoint(local);
                    marker.transform.position = target + Vector3.up * 0.02f;
                    marker.SetActive(true);
                    state = State.Warn;
                    stateTime = 0f;
                    break;
                }
                case State.Warn:
                {
                    float pulse = 1f + Mathf.Sin(stateTime * 25f) * 0.1f;
                    marker.transform.localScale = new Vector3(1.1f * pulse, 0.005f, 1.1f * pulse);
                    if (stateTime < warning / Difficulty.HazardSpeed) return;
                    fallY = target.y + dropHeight;
                    vy = 0f;
                    piece.transform.SetPositionAndRotation(new Vector3(target.x, fallY, target.z),
                        Quaternion.Euler(Random.Range(-20f, 20f), Random.Range(0f, 360f), Random.Range(-20f, 20f)));
                    piece.SetActive(true);
                    ProceduralAudio.PlayWhoosh(0.5f);
                    state = State.Fall;
                    stateTime = 0f;
                    break;
                }
                case State.Fall:
                {
                    vy += Physics.gravity.y * 1.3f * Time.deltaTime;
                    fallY += vy * Time.deltaTime;
                    float bottom = target.y + debrisSize.y * 0.5f;
                    if (fallY <= bottom) fallY = bottom;
                    piece.transform.position = new Vector3(target.x, fallY, target.z);
                    // Hit if the piece passes through the player's head / body column.
                    var rig = PlayerRig.Instance;
                    if (rig != null && Live)
                    {
                        Vector3 h = rig.Head.position;
                        Vector2 d = new Vector2(h.x - target.x, h.z - target.z);
                        if (d.magnitude < 0.55f && fallY < h.y + 0.2f && fallY > rig.FeetY + 0.3f)
                            KnockPlayer(new Vector3(d.x, 0f, d.y) + rig.Head.right * 0.3f);
                    }
                    if (fallY <= bottom)
                    {
                        ProceduralAudio.PlayClunkAt(target);
                        marker.SetActive(false);
                        state = State.Landed;
                        stateTime = 0f;
                    }
                    break;
                }
                case State.Landed:
                {
                    if (stateTime < 0.8f) return;
                    piece.SetActive(false);
                    next = Time.time + interval / Difficulty.HazardSpeed * Random.Range(0.7f, 1.3f);
                    state = State.Idle;
                    break;
                }
            }
        }

        void OnDrawGizmosSelected()
        {
            Gizmos.matrix = transform.localToWorldMatrix;
            Gizmos.color = new Color(1f, 0.4f, 0.1f, 0.4f);
            Gizmos.DrawCube(Vector3.zero, new Vector3(areaSize.x, 0.05f, areaSize.z));
        }
    }
}
