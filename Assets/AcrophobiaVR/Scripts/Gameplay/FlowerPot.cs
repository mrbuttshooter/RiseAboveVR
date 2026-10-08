using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>A pot on the balcony ledge. Water it and the flower grows and blooms.</summary>
    public class FlowerPot : MonoBehaviour
    {
        public Transform flower;
        public float waterNeeded = 2f;
        public WaterObjective owner;

        float water;
        bool bloomed;

        void Start()
        {
            if (flower != null) flower.localScale = Vector3.one * 0.2f;
        }

        public void Water(float amount)
        {
            if (bloomed || owner == null || !owner.IsActive) return;
            water += amount;
            float k = Mathf.Clamp01(water / waterNeeded);
            if (flower != null) flower.localScale = Vector3.one * Mathf.Lerp(0.2f, 1f, k);
            HeadHud.Instance.ShowProgress(k, "Watering...", UIFactory.Accent);
            if (water >= waterNeeded)
            {
                bloomed = true;
                Effects.Sparkle(flower != null ? flower.position : transform.position, new Color(1f, 0.5f, 0.8f));
                owner.NotifyBloomed();
            }
        }
    }
}