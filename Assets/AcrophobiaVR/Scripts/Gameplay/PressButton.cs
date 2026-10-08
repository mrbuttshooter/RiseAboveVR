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
        [Tooltip("Rings like a bell (three dings and a swing) instead of clunking.")]
        public bool bell;
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
            Haptics.Medium();
            if (bell) StartCoroutine(Ring());
            else ProceduralAudio.PlayClunkAt(transform.position);
            if (cap != null) cap.localPosition += Vector3.down * 0.03f;
            onPressed.Invoke();
        }

        System.Collections.IEnumerator Ring()
        {
            Quaternion rest = transform.localRotation;
            for (int ding = 0; ding < 3; ding++)
            {
                ProceduralAudio.PlayBellAt(transform.position);
                Haptics.Light();
                for (float t = 0; t < 0.6f; t += Time.deltaTime)
                {
                    transform.localRotation = rest * Quaternion.Euler(Mathf.Sin(t / 0.6f * Mathf.PI * 2f) * 18f * (1f - ding * 0.25f), 0f, 0f);
                    yield return null;
                }
            }
            transform.localRotation = rest;
        }
    }
}