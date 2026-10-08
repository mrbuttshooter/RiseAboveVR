using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// Shows this object only in the chosen exposure modes - e.g. safety glass and extra rails
    /// in Gentle mode, a missing handrail in Brave mode.
    /// </summary>
    public class ExposureVisual : MonoBehaviour
    {
        public bool gentle = true;
        public bool standard;
        public bool brave;

        void Awake()
        {
            Apply(ExposureSettings.Mode);
            ExposureSettings.Changed += Apply;
        }

        void OnDestroy() => ExposureSettings.Changed -= Apply;

        void Apply(ExposureMode mode)
        {
            bool show = mode == ExposureMode.Gentle ? gentle : (mode == ExposureMode.Brave ? brave : standard);
            gameObject.SetActive(show);
        }
    }
}