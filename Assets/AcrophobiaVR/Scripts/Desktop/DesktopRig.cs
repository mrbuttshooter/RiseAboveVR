using System.Collections;
using Unity.XR.CoreUtils;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;
using UnityEngine.XR;

namespace AcrophobiaVR
{
    /// <summary>
    /// Keyboard + mouse fallback when no headset is connected, so the whole game can be played and
    /// demonstrated on a normal PC. WASD run, Shift sprint, Space jump (climbs on ladders), C crouch,
    /// left click use/grab, right click pour, Esc pause, Tab free the cursor.
    /// </summary>
    [RequireComponent(typeof(XROrigin))]
    public class DesktopRig : MonoBehaviour
    {
        public static bool ClimbingThisFrame;

        public float walkSpeed = PlayerRig.RunSpeed;
        public float sprintSpeed = 4.6f;
        public float mouseSensitivity = 0.12f;
        public float standingHeight = 1.65f;
        public float crouchHeight = 1.05f;
        public float interactRange = 3.5f;

        XROrigin origin;
        Transform cam;
        CharacterController cc;
        float pitch;
        float yaw;
        float verticalVelocity;
        float lastGroundedTime = -1f;
        float jumpPressedTime = -1f;
        float currentHeight;
        bool active;
        TMPro.TMP_Text crosshairHint;
        Image crosshair;
        bool cursorFree;
        bool manualFree;
        bool wasUiOpen;

        /// <summary>Turns the desktop view (used when a rotating platform carries the player).</summary>
        public void AddYaw(float degrees) => yaw += degrees;

        /// <summary>Faces the desktop view along a direction (teleports, respawns, ladder exits).</summary>
        public void FaceDirection(Vector3 forward)
        {
            forward.y = 0f;
            if (forward.sqrMagnitude < 1e-4f) return;
            yaw = Quaternion.LookRotation(forward).eulerAngles.y;
            pitch = 0f;
        }

        IEnumerator Start()
        {
            origin = GetComponent<XROrigin>();
            // Give the XR runtime a moment to start before deciding.
            yield return new WaitForSeconds(0.75f);
            if (XRSettings.isDeviceActive && !ForceDesktop()) yield break;
            Activate();
        }

        static bool ForceDesktop()
        {
            foreach (var a in System.Environment.GetCommandLineArgs())
                if (a == "-desktop") return true;
            return false;
        }

        void Activate()
        {
            active = true;
            if (PlayerRig.Instance != null) PlayerRig.Instance.IsDesktop = true;
            UIFactory.DesktopMode = true;
            foreach (var gr in FindObjectsByType<GraphicRaycaster>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                var tracked = gr.GetComponent<UnityEngine.XR.Interaction.Toolkit.UI.TrackedDeviceGraphicRaycaster>();
                if (tracked != null && tracked.enabled) gr.enabled = true;
            }
            cam = origin.Camera.transform;

            // Stop the XR tracked pose driver and VR locomotion from fighting the mouse/keyboard.
            foreach (var tpd in cam.GetComponents<UnityEngine.InputSystem.XR.TrackedPoseDriver>()) tpd.enabled = false;
            foreach (var p in GetComponentsInChildren<UnityEngine.XR.Interaction.Toolkit.Locomotion.LocomotionProvider>(true)) p.enabled = false;
            foreach (var t in GetComponentsInChildren<Transform>(true))
            {
                string n = t.name.ToLowerInvariant();
                if (n.Contains("left controller") || n.Contains("right controller")) t.gameObject.SetActive(false);
            }

            cc = GetComponent<CharacterController>();
            if (cc == null) cc = gameObject.AddComponent<CharacterController>();
            cc.enabled = true;
            cc.radius = 0.25f;
            cc.stepOffset = 0.3f;
            cc.skinWidth = 0.02f;

            if (origin.CameraFloorOffsetObject != null) origin.CameraFloorOffsetObject.transform.localPosition = Vector3.zero;
            currentHeight = standingHeight;
            cam.localPosition = new Vector3(0f, currentHeight, 0f);
            cam.localRotation = Quaternion.identity;
            yaw = transform.eulerAngles.y;
            BuildCrosshair();
            SetCursorFree(false);
            HeadHud.Instance.ShowMessage("Desktop: WASD run, Shift sprint, Space jump / climb, C crouch, click to use, Esc pause", 7f);
        }

        void BuildCrosshair()
        {
            var go = new GameObject("DesktopCrosshair", typeof(RectTransform));
            go.transform.SetParent(transform, false);
            var canvas = go.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;
            crosshair = UIFactory.CircleImage(go.transform, new Color(1, 1, 1, 0.8f), Vector2.zero, 10);
            crosshair.rectTransform.anchorMin = crosshair.rectTransform.anchorMax = new Vector2(0.5f, 0.5f);
            crosshairHint = UIFactory.Label(go.transform, "", 22, new Vector2(0, -40), new Vector2(700, 40));
            crosshairHint.rectTransform.anchorMin = crosshairHint.rectTransform.anchorMax = new Vector2(0.5f, 0.5f);
        }

        void SetCursorFree(bool free)
        {
            cursorFree = free;
            Cursor.lockState = free ? CursorLockMode.None : CursorLockMode.Locked;
            Cursor.visible = free;
        }

        void Update()
        {
            if (!active) return;
            var kb = Keyboard.current;
            var mouse = Mouse.current;
            if (kb == null || mouse == null) return;

            // Free the mouse whenever a menu/rating panel is open so it can be clicked.
            bool uiOpen = Dialog.AnyOpen || MainMenuController.MenuOpen;
            if (kb.tabKey.wasPressedThisFrame) manualFree = !manualFree;
            // A panel just appeared at eye level: level the view so the player actually sees it.
            if (uiOpen && !wasUiOpen) pitch = 0f;
            wasUiOpen = uiOpen;
            bool wantFree = uiOpen || manualFree;
            if (wantFree != cursorFree) SetCursorFree(wantFree);
            if (crosshair != null) crosshair.enabled = !cursorFree;

            // Locked cursor: mouse look. Free cursor (menus): hold the right mouse button to look around.
            if (!cursorFree || mouse.rightButton.isPressed)
            {
                Vector2 d = mouse.delta.ReadValue() * mouseSensitivity;
                yaw += d.x;
                pitch = Mathf.Clamp(pitch - d.y, -85f, 85f);
            }

            bool frozen = cc == null || !cc.enabled; // e.g. riding the lift
            transform.rotation = Quaternion.Euler(0f, yaw, 0f);
            cam.localRotation = Quaternion.Euler(pitch, 0f, 0f);

            float targetHeight = kb.cKey.isPressed || kb.leftCtrlKey.isPressed ? crouchHeight : standingHeight;
            currentHeight = Mathf.MoveTowards(currentHeight, targetHeight, Time.deltaTime * 3f);
            cam.localPosition = new Vector3(0f, currentHeight, 0f);

            if (!frozen)
            {
                cc.height = Mathf.Max(0.6f, currentHeight + 0.1f);
                cc.center = new Vector3(0f, cc.height * 0.5f, 0f);
                Vector2 input = Vector2.zero;
                if (kb.wKey.isPressed) input.y += 1;
                if (kb.sKey.isPressed) input.y -= 1;
                if (kb.dKey.isPressed) input.x += 1;
                if (kb.aKey.isPressed) input.x -= 1;
                float speed = kb.leftShiftKey.isPressed ? sprintSpeed : walkSpeed;
                if (targetHeight < standingHeight) speed *= 0.5f;
                Vector3 move = (transform.forward * input.y + transform.right * input.x).normalized * speed;

                // isGrounded flickers on moving platforms (they move the player each frame): also trust a ground probe.
                bool grounded = cc.isGrounded || (verticalVelocity <= 0.5f && PlayerRig.Instance != null && PlayerRig.Instance.GroundCollider() != null);
                if (grounded) lastGroundedTime = Time.time;
                if (kb.spaceKey.wasPressedThisFrame) jumpPressedTime = Time.time;
                if (ClimbingThisFrame) verticalVelocity = 0f;
                else if (Time.time - jumpPressedTime < 0.12f && Time.time - lastGroundedTime < 0.12f && verticalVelocity <= 0f)
                {
                    // Jump (with a little coyote time and input buffering so edge jumps feel fair).
                    verticalVelocity = Mathf.Sqrt(2f * -Physics.gravity.y * PlayerRig.JumpHeight);
                    jumpPressedTime = -1f;
                    lastGroundedTime = -1f;
                    ProceduralAudio.PlayWhoosh(0.25f);
                }
                else if (grounded && verticalVelocity < 0f) verticalVelocity = -1f;
                else verticalVelocity += Physics.gravity.y * Time.deltaTime;
                if (!ClimbingThisFrame) move.y = verticalVelocity;
                cc.Move(move * Time.deltaTime);
            }
            ClimbingThisFrame = false;

            HandleInteraction(mouse);
        }

        void HandleInteraction(Mouse mouse)
        {
            if (cursorFree || crosshairHint == null) return;
            crosshairHint.text = "";
            if (!Physics.Raycast(cam.position, cam.forward, out RaycastHit hit, interactRange, ~0, QueryTriggerInteraction.Ignore)) return;
            var usable = hit.collider.GetComponentInParent<IDesktopUsable>();
            if (usable == null) return;
            crosshairHint.text = usable.DesktopHint;
            if (mouse.leftButton.wasPressedThisFrame) usable.DesktopUse();
        }

        void LateUpdate()
        {
            // Held items that are being carried may block the ray; let a click still reach them.
            if (!active || cursorFree) return;
            var mouse = Mouse.current;
            if (mouse == null || !mouse.leftButton.wasPressedThisFrame) return;
            foreach (var d in FindObjectsByType<DeliverableItem>(FindObjectsSortMode.None))
                if (d.enabled && Vector3.Distance(d.transform.position, cam.position) < 1.2f && d.owner != null && d.owner.PlayerNearTarget())
                    d.DesktopUse();
        }
    }
}