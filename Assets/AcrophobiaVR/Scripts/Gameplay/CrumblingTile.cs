using System.Collections;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>A loose tile/plank: shakes when stepped on, then drops away. Keep moving!</summary>
    public class CrumblingTile : MonoBehaviour
    {
        public float delay = 1.3f;
        public float respawnAfter = 4f;

        Vector3 homePos;
        Quaternion homeRot;
        Collider col;
        Renderer rend;
        bool triggered;

        void Awake()
        {
            homePos = transform.position;
            homeRot = transform.rotation;
            col = GetComponent<Collider>();
            rend = GetComponent<Renderer>();
        }

        bool PlayerOnTop()
        {
            var rig = PlayerRig.Instance;
            if (rig == null || col == null) return false;
            Bounds b = col.bounds;
            Vector3 h = rig.Head.position;
            return h.x > b.min.x - 0.05f && h.x < b.max.x + 0.05f && h.z > b.min.z - 0.05f && h.z < b.max.z + 0.05f &&
                   h.y > b.max.y && h.y < b.max.y + 2.5f;
        }

        void Update()
        {
            var lc = LevelController.Instance;
            if (triggered || lc == null || !lc.Started || lc.IsRespawning) return;
            if (PlayerOnTop()) StartCoroutine(Crumble());
        }

        IEnumerator Crumble()
        {
            triggered = true;
            float d = ExposureSettings.Mode == ExposureMode.Gentle ? delay * 1.8f : (ExposureSettings.Mode == ExposureMode.Brave ? delay * 0.75f : delay);
            ProceduralAudio.PlayCrack();
            for (float t = 0; t < d; t += Time.deltaTime)
            {
                transform.position = homePos + Random.insideUnitSphere * 0.015f * (t / d + 0.3f);
                yield return null;
            }
            bool playerWasOn = PlayerOnTop();
            col.enabled = false;
            ProceduralAudio.PlayWhoosh(0.4f);
            Vector3 vel = Vector3.zero;
            Vector3 spin = Random.onUnitSphere * 120f;
            for (float t = 0; t < 2f; t += Time.deltaTime)
            {
                vel += Physics.gravity * Time.deltaTime;
                transform.position += vel * Time.deltaTime;
                transform.Rotate(spin * Time.deltaTime);
                if (playerWasOn && t > 0.15f && LevelController.Instance != null)
                {
                    playerWasOn = false;
                    if (PlayerRig.Instance != null && PlayerRig.Instance.FeetY > CheckpointSystem.Position.y - 0.5f)
                        LevelController.Instance.Slip("tile");
                }
                yield return null;
            }
            if (rend != null) rend.enabled = false;
            yield return new WaitForSeconds(respawnAfter);
            transform.SetPositionAndRotation(homePos, homeRot);
            if (rend != null) rend.enabled = true;
            col.enabled = true;
            triggered = false;
        }
    }
}