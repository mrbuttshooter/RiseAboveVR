using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.XR;
using UnityEngine.XR;
using CommonUsages = UnityEngine.InputSystem.CommonUsages;

namespace AcrophobiaVR
{
    /// <summary>
    /// Controller vibration helper. Uses Input System rumble controllers first (OpenXR controller
    /// profiles derive from XRControllerWithRumble) and falls back to the legacy XR input devices.
    /// Safe to call on desktop (does nothing) and never throws.
    /// </summary>
    public static class Haptics
    {
        public static void Light() => Pulse(0.25f, 0.05f);
        public static void Medium() => Pulse(0.5f, 0.1f);
        public static void Strong() => Pulse(0.9f, 0.25f);

        public static void Pulse(float amplitude, float duration, bool left = true, bool right = true)
        {
            if (!left && !right) return;
            amplitude = Mathf.Clamp01(amplitude);
            duration = Mathf.Max(0f, duration);
            if (!(amplitude > 0f) || !(duration > 0f)) return; // also rejects NaN

            bool sent = false;
            try
            {
                var devices = InputSystem.devices;
                for (int i = 0; i < devices.Count; i++)
                {
                    var rumble = devices[i] as XRControllerWithRumble;
                    if (rumble == null || !rumble.added) continue;
                    bool isLeft = false, isRight = false;
                    var usages = rumble.usages;
                    for (int u = 0; u < usages.Count; u++)
                    {
                        if (usages[u] == CommonUsages.LeftHand) isLeft = true;
                        else if (usages[u] == CommonUsages.RightHand) isRight = true;
                    }
                    if ((left && isLeft) || (right && isRight))
                    {
                        rumble.SendImpulse(amplitude, duration);
                        sent = true;
                    }
                }
            }
            catch (System.Exception) { }

            if (sent) return;

            try
            {
                if (left) LegacyImpulse(XRNode.LeftHand, amplitude, duration);
                if (right) LegacyImpulse(XRNode.RightHand, amplitude, duration);
            }
            catch (System.Exception) { }
        }

        static void LegacyImpulse(XRNode node, float amplitude, float duration)
        {
            var device = InputDevices.GetDeviceAtXRNode(node);
            if (device.isValid) device.SendHapticImpulse(0u, amplitude, duration);
        }
    }
}
