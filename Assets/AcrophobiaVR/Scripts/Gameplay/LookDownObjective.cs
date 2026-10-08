using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// "Spot it" task: keep your gaze on a target far below for a few seconds. This is the core
    /// exposure exercise - deliberately looking down instead of avoiding it.
    /// </summary>
    public class LookDownObjective : Objective
    {
        public Transform target;
        public float holdSeconds = 3.5f;
        public float maxAngle = 9f;
        public float maxViewDistance = 60f;
        public string spotLabel = "Keep looking...";

        float progress;
        Renderer[] highlight;

        public override string ProgressSuffix => progress > 0f && !IsComplete ? "  (" + Mathf.RoundToInt(progress / holdSeconds * 100f) + "%)" : "";

        void Start()
        {
            if (target != null) highlight = target.GetComponentsInChildren<Renderer>();
        }

        void Update()
        {
            if (!IsActive || IsComplete || target == null || PlayerRig.Instance == null) return;
            var head = PlayerRig.Instance.Head;
            Vector3 dir = target.position - head.position;
            bool looking = dir.magnitude < maxViewDistance && Vector3.Angle(head.forward, dir) < maxAngle;

            if (looking)
            {
                progress += Time.deltaTime;
                HeadHud.Instance.ShowProgress(progress / holdSeconds, spotLabel);
                if (progress >= holdSeconds)
                {
                    Complete();
                    if (highlight != null)
                        foreach (var r in highlight) r.material.color = UIFactory.Calm;
                }
            }
            else
            {
                progress = Mathf.Max(0f, progress - Time.deltaTime * 0.5f);
            }
        }
    }
}