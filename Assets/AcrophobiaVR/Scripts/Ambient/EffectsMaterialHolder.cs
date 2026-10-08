using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>Hands the particle material asset to the Effects helper (keeps its shader in builds).</summary>
    public class EffectsMaterialHolder : MonoBehaviour
    {
        public Material particleMaterial;
        void Awake() => Effects.SetMaterial(particleMaterial);
    }
}