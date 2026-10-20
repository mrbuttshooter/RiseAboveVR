using System.Collections;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// A glass floor panel that cracks while you stand on it. In Gentle mode it never breaks
    /// (pure exposure); in Standard/Brave it shatters if you linger - keep moving!
    /// </summary>
    [RequireComponent(typeof(BoxCollider))]
    public class CrackingGlass : MonoBehaviour
    {
        public float secondsToBreak = 10f;
        public LineRenderer[] cracks;
        public Renderer panel;

        float damage;
        int lastStage;
        bool broken;
        Renderer rend;
        Collider col;
        BoxCollider box;

        void Awake()
        {
            box = GetComponent<BoxCollider>();
            col = box;
            rend = panel != null ? panel : GetComponent<Renderer>();
            SetCracks(0f);
        }

        bool PlayerOnTop()
        {
            var rig = PlayerRig.Instance;
            if (rig == null) return false;
            Vector3 local = transform.InverseTransformPoint(rig.Head.position);
            Vector3 half = box.size * 0.5f;
            float aboveWorld = rig.Head.position.y - transform.position.y;
            return Mathf.Abs(local.x - box.center.x) <= half.x && Mathf.Abs(local.z - box.center.z) <= half.z && aboveWorld > 0f && aboveWorld < 2.5f;
        }

        void Update()
        {
            var lc = LevelController.Instance;
            if (broken || lc == null || !lc.Started || lc.IsRespawning) return;

            float rate = Difficulty.Level == DifficultyLevel.Hard ? 1.4f : 1f;
            float cap = Difficulty.Level == DifficultyLevel.Easy ? 0.7f : 1f;
            if (PlayerOnTop()) damage = Mathf.Min(cap, damage + Time.deltaTime / secondsToBreak * rate);

            int stage = Mathf.FloorToInt(damage * cracks.Length);
            if (stage > lastStage)
            {
                lastStage = stage;
                ProceduralAudio.PlayCrackAt(transform.position);
                Haptics.Light();
                if (stage == 1) HeadHud.Instance.ShowMessage("The glass is cracking - keep moving!", 2.5f);
            }
            SetCracks(damage);

            if (damage >= 1f) StartCoroutine(Shatter());
        }

        void SetCracks(float amount)
        {
            if (cracks == null) return;
            for (int i = 0; i < cracks.Length; i++)
                if (cracks[i] != null) cracks[i].enabled = amount * cracks.Length > i;
        }

        IEnumerator Shatter()
        {
            broken = true;
            ProceduralAudio.PlayShatterAt(transform.position);
            Haptics.Strong();
            Effects.Shards(transform.position, transform.lossyScale);
            if (rend != null) rend.enabled = false;
            col.enabled = false;
            SetCracks(0f);
            yield return new WaitForSeconds(0.25f);
            if (PlayerOnTop() && LevelController.Instance != null) LevelController.Instance.Slip("glass");
            yield return new WaitForSeconds(3f);
            damage = 0f;
            lastStage = 0;
            if (rend != null) rend.enabled = true;
            col.enabled = true;
            broken = false;
        }
    }
}