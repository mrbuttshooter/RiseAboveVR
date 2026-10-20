using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Shows this object only on the chosen difficulties - e.g. a railing or safety net that only Easy gets.</summary>
    public class DifficultyVisual : MonoBehaviour
    {
        public bool easy = true;
        public bool normal;
        public bool hard;

        void Awake()
        {
            Apply(Difficulty.Level);
            Difficulty.Changed += Apply;
        }

        void OnDestroy() => Difficulty.Changed -= Apply;

        void Apply(DifficultyLevel level)
        {
            bool show = level == DifficultyLevel.Easy ? easy : (level == DifficultyLevel.Hard ? hard : normal);
            gameObject.SetActive(show);
        }
    }
}
