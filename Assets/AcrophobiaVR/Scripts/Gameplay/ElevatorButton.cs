using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Filtering;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace AcrophobiaVR
{
    /// <summary>
    /// A physical push button on the Courage Elevator. VR: poke it with a finger or select it with a
    /// controller ray (an XRSimpleInteractable + XRPokeFilter are added at runtime). Desktop: click it
    /// (IDesktopUsable with a locked cursor; CourageElevator handles clicks with a free cursor).
    /// The button's local +Z points into its panel, which is the poke direction.
    /// </summary>
    public class ElevatorButton : MonoBehaviour, IDesktopUsable
    {
        public enum ButtonAction { Up, Down, Stop, Call }

        const float Travel = 0.012f;
        const float Cooldown = 0.35f;
        const float AnimSeconds = 0.3f;

        public ButtonAction action;
        public CourageElevator elevator;

        string desktopHint = "Click: Press";
        Vector3 restPosition;
        Vector3 pressDirection = Vector3.forward;
        float pressedAt = -10f;
        bool animating;
        XRBaseInteractable interactable;

        public string DesktopHint => desktopHint;
        public void DesktopUse() => Press();

        /// <summary>Wires the button to its elevator. Call after the transform and collider are in place.</summary>
        public void Setup(CourageElevator owner, ButtonAction buttonAction, string hint)
        {
            elevator = owner;
            action = buttonAction;
            desktopHint = "Click: " + hint;
            restPosition = transform.localPosition;
            pressDirection = transform.localRotation * Vector3.forward;

            if (interactable != null) return;
            interactable = GetComponent<XRBaseInteractable>();
            if (interactable == null) interactable = gameObject.AddComponent<XRSimpleInteractable>();
            interactable.selectEntered.AddListener(OnSelected);
            if (GetComponent<XRPokeFilter>() == null) gameObject.AddComponent<XRPokeFilter>();
        }

        void OnDestroy()
        {
            if (interactable != null) interactable.selectEntered.RemoveListener(OnSelected);
        }

        void OnSelected(SelectEnterEventArgs args) => Press();

        public void Press()
        {
            if (Time.unscaledTime - pressedAt < Cooldown) return;
            pressedAt = Time.unscaledTime;
            animating = true;
            ProceduralAudio.PlayClick();
            Haptics.Light();
            if (elevator != null) elevator.HandleButton(action);
        }

        void Update()
        {
            if (!animating) return;
            float t = (Time.unscaledTime - pressedAt) / AnimSeconds;
            if (t >= 1f)
            {
                transform.localPosition = restPosition;
                animating = false;
                return;
            }
            float depth = t < 0.25f ? t / 0.25f : 1f - (t - 0.25f) / 0.75f;
            transform.localPosition = restPosition + pressDirection * (Travel * depth);
        }
    }
}
