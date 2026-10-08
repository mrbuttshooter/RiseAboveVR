using UnityEngine;
using UnityEngine.Events;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace AcrophobiaVR
{
    /// <summary>A big physical button: poke/select it in VR, click it on desktop.</summary>
    public class PressButton : MonoBehaviour, IDesktopUsable
    {
        public string hint = "Press the button";
        public Transform cap;
        public UnityEvent onPressed = new UnityEvent();
        bool pressed;

        void Start()
        {
            var i = GetComponent<XRBaseInteractable>();
            if (i != null) i.selectEntered.AddListener(_ => Press());
        }

        public string DesktopHint => pressed ? "" : "Click: " + hint;
        public void DesktopUse() => Press();

        public void Press()
        {
            if (pressed) return;
            pressed = true;
            ProceduralAudio.PlayClunk();
            if (cap != null) cap.localPosition += Vector3.down * 0.03f;
            onPressed.Invoke();
        }
    }
}