using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace AcrophobiaVR
{
    /// <summary>
    /// The Courage Elevator: a free-practice glass lift in the park hub. The player rides it to any
    /// height they choose (0-120 m) with physical UP / STOP / DOWN buttons - self-paced graded exposure.
    /// Everything (glass platform, rails, swing gate, guide masts, beacon, call pedestal, signage and
    /// height readout) is built at runtime from ~32 primitives, so no assets or scene edits are needed.
    /// Quest friendly: no lights, no shadows, no per-frame allocations, text only changes on new values.
    /// </summary>
    public class CourageElevator : MonoBehaviour
    {
        public const float MaxHeight = 120f;
        public const string PrefKey = "acro_elevator_max";

        const float Speed = 1.5f;        // m/s cruise
        const float Accel = 1.2f;        // m/s^2 start / gentle arrival
        const float Brake = 2f;          // m/s^2 when STOP is pressed
        const float MinCrawl = 0.12f;    // m/s final approach to the top / ground
        const float Half = 1.2f;         // half the 2.4 m footprint
        const float FloorTop = 0.06f;    // floor surface above the platform origin
        const float GateHeight = 0.3f;   // gate closes (and blocks) above this height
        const float Headroom = 2.6f;     // head within this much above the floor = riding
        const float MastHeight = 125f;
        const string LevelName = "MainMenu";

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        static readonly int BaseColorId = Shader.PropertyToID("_BaseColor");
        static readonly int ColorId = Shader.PropertyToID("_Color");
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        static readonly float[] Milestones = { 10f, 25f, 50f, 100f };
        static readonly int[] GoalLadder = { 5, 10, 25, 50, 75, 100, 120 };
        static readonly string[] MilestoneLines =
        {
            "Ten metres - about a three-storey building. Breathe.",
            "Twenty-five metres. Look at the park from up here!",
            "Fifty metres! Higher than most trees and houses.",
            "One hundred metres. You're a cloud walker!",
        };

        static readonly string[] StopLines =
        {
            "Nice stop. Feel your feet on the glass - it's holding you. Breathe slowly.",
            "Notice the fear rise... and settle. That's your brain learning you're safe.",
            "Look out at the horizon first, then try a quick peek down. You're in control.",
            "When the nerves drop by about half, you're ready to go a little higher.",
        };

        static readonly string[] StateText =
        {
            "On the ground - press UP",
            "Going up - STOP any time",
            "Going down",
            "Stopped - UP or DOWN",
            "Top reached - press DOWN",
            "Stopping...",
        };

        /// <summary>Highest the player has ever ridden (metres), persisted in PlayerPrefs "acro_elevator_max".</summary>
        public static float BestHeight => PlayerPrefs.GetFloat(PrefKey, 0f);

        /// <summary>Current platform height above the base (metres).</summary>
        public float Height => height;
        public bool IsMoving => dir != 0 || velocity != 0f;
        public bool CarryingPlayer => carrying;

        Transform platform;
        Transform gatePivot;
        Collider gateCollider;
        Renderer beacon;
        TMPro.TMP_Text heightLabel;
        TMPro.TMP_Text stateLabel;
        TMPro.TMP_Text bestLabel;
        TMPro.TMP_Text signBestLabel;
        TMPro.TMP_Text goalLabel;

        readonly List<Material> materials = new List<Material>();
        Material metal, steel, padMat, housingMat, yellowMat, greenMat, redMat, blueMat, goldMat, beaconMat, floorGlass, panelGlass;
        Shader litShader;
        Material template;

        float height;
        float velocity;
        int dir;
        bool carrying;
        bool windOn;
        bool machineryOn;
        bool wasOn;
        bool introSaid;
        bool copingSaid;
        bool ach100;
        float lastLineTime = -100f;
        float best;
        float persistedBest;
        float savedBest;
        float sessionMax;
        float loggedMax;
        float rideMax;
        float bestAtRideStart;
        int lastBand;
        int stopLineIndex;
        readonly bool[] milestoneSaid = new bool[4];
        float nextStopLine;
        float nextGroundHint;
        float nextGuardHint;
        int shownMeters = -1;
        int shownState = -1;
        int shownBest = -1;
        float shownGate = -1f;
        bool beaconOn = true;

        static Mesh cubeMesh;

        // ------------------------------------------------------------------ lifecycle

        void Awake()
        {
            best = BestHeight;
            persistedBest = best;
            savedBest = best;
            bestAtRideStart = best;
            BuildMaterials();
            BuildGeometry();
            BuildSign();
            ApplyHeight();
            RefreshReadout(true);
        }

        void Update()
        {
            var rig = PlayerRig.Instance;
            HandleDesktopClick(rig);

            float dt = Time.deltaTime;
            if (IsMoving && dt > 0f)
            {
                if (!carrying && rig != null) CatchFall(rig); // put back on board; Step then carries them
                Step(rig, dt);
            }
            else IdleChecks(rig);

            UpdateAtmosphere(rig);
            UpdateBeacon();
            RefreshReadout(false);
        }

        void OnApplicationPause(bool paused)
        {
            if (!paused) return;
            SaveBest();
            LogSessionMax();
        }

        void OnDestroy()
        {
            LogSessionMax();
            SaveBest();
            if (machineryOn) AmbientAudio.Machinery = 0f;
            if (carrying)
            {
                carrying = false;
                var rig = PlayerRig.Instance;
                if (rig != null) rig.SetLocomotionEnabled(true);
            }
            for (int i = 0; i < materials.Count; i++)
                if (materials[i] != null) Destroy(materials[i]);
            materials.Clear();
        }

        // ------------------------------------------------------------------ controls

        /// <summary>Called by the physical ElevatorButtons.</summary>
        public void HandleButton(ElevatorButton.ButtonAction action)
        {
            switch (action)
            {
                case ElevatorButton.ButtonAction.Up:
                    if (height >= MaxHeight - 0.01f && !IsMoving) HeadHud.Instance.ShowMessage("This is the top - 120 m. Press DOWN when you're ready.", 3f);
                    else StartMotion(1);
                    break;
                case ElevatorButton.ButtonAction.Down:
                    if (height <= 0.01f && !IsMoving) HeadHud.Instance.ShowMessage("You're already on the ground. Press UP to rise.", 3f);
                    else StartMotion(-1);
                    break;
                case ElevatorButton.ButtonAction.Stop:
                    if (IsMoving) dir = 0; // brake smoothly; OnStopped runs when the speed reaches zero
                    break;
                case ElevatorButton.ButtonAction.Call:
                    if (height <= 0.01f && !IsMoving) HeadHud.Instance.ShowMessage("The lift is here - step inside and press UP.", 3f);
                    else StartMotion(-1);
                    break;
            }
        }

        public void GoUp() => HandleButton(ElevatorButton.ButtonAction.Up);
        public void GoDown() => HandleButton(ElevatorButton.ButtonAction.Down);
        public void Stop() => HandleButton(ElevatorButton.ButtonAction.Stop);

        void StartMotion(int newDir)
        {
            bool wasIdle = !IsMoving;
            dir = newDir;
            if (!wasIdle) return;
            ProceduralAudio.PlayClunkAt(platform.position);
            Haptics.Medium();
            var rig = PlayerRig.Instance;
            if (rig != null && !carrying && IsPlayerOn(rig)) BeginCarry(rig);
        }

        /// <summary>Desktop with a free cursor (the park keeps the cursor free for the menus): click the buttons directly.</summary>
        void HandleDesktopClick(PlayerRig rig)
        {
            if (rig == null || !rig.IsDesktop || Cursor.lockState == CursorLockMode.Locked) return;
            var mouse = UnityEngine.InputSystem.Mouse.current;
            if (mouse == null || !mouse.leftButton.wasPressedThisFrame) return;
            var cam = Camera.main;
            if (cam == null) return;
            Ray ray = cam.ScreenPointToRay(mouse.position.ReadValue());
            if (!Physics.Raycast(ray, out RaycastHit hit, 6f, ~0, QueryTriggerInteraction.Ignore)) return;
            var button = hit.collider.GetComponent<ElevatorButton>();
            if (button != null) button.Press();
        }

        // ------------------------------------------------------------------ motion

        void Step(PlayerRig rig, float dt)
        {
            float prev = height;
            float target = dir * Speed;
            if (dir > 0) target = Mathf.Min(target, Mathf.Max(MinCrawl, Mathf.Sqrt(2f * Accel * (MaxHeight - height))));
            else if (dir < 0) target = Mathf.Max(target, -Mathf.Max(MinCrawl, Mathf.Sqrt(2f * Accel * height)));
            float rate = (Mathf.Abs(target) < Mathf.Abs(velocity) || target * velocity < 0f) ? Brake : Accel;
            velocity = Mathf.MoveTowards(velocity, target, rate * dt);

            // An empty lift coming down never lands on someone standing in the shaft.
            if (!carrying && velocity < 0f && rig != null && HeadUnderPlatform(rig))
            {
                OnStopped();
                if (Time.time > nextGuardHint)
                {
                    nextGuardHint = Time.time + 4f;
                    HeadHud.Instance.ShowMessage("Mind your head! Step out from under the lift, then call it again.", 4f);
                }
                return;
            }

            float next = height + velocity * dt;
            bool arrived = false;
            if (next >= MaxHeight) { next = MaxHeight; arrived = true; }
            else if (next <= 0f) { next = 0f; arrived = true; }

            // Stepped on while it was moving near the ground.
            if (!carrying && rig != null && IsPlayerOn(rig)) BeginCarry(rig);

            float delta = next - height;
            height = next;
            ApplyHeight();
            if (carrying && rig != null && delta != 0f) rig.MoveBy(new Vector3(0f, delta, 0f));

            int band = Mathf.FloorToInt(height / 10f + 0.0001f);
            if (carrying)
            {
                if (band > lastBand && band > 0)
                {
                    ProceduralAudio.PlayChime(1f + band * 0.04f);
                    Haptics.Light();
                }
                TrackRide(prev);
            }
            lastBand = band;
            UpdateMachinery(rig);

            if (arrived) OnStopped();
            else if (dir == 0 && velocity == 0f) OnStopped();
        }

        void BeginCarry(PlayerRig rig)
        {
            carrying = true;
            wasOn = true;
            rig.SetLocomotionEnabled(false);
            if (height < 0.5f)
            {
                // A new ride from the ground (re-read in case progress was reset from the menu).
                best = BestHeight;
                persistedBest = best;
                savedBest = best;
                bestAtRideStart = best;
                rideMax = 0f;
            }
            float floorY = platform.position.y + FloorTop;
            float feet = rig.FeetY;
            if (feet < floorY - 0.05f && feet > floorY - 0.8f) rig.MoveBy(new Vector3(0f, floorY - feet, 0f));
        }

        void TrackRide(float prev)
        {
            if (height > sessionMax) sessionMax = height;
            if (height > rideMax) rideMax = height;
            if (height > best)
            {
                best = height;
                if (best >= persistedBest + 1f || best >= MaxHeight)
                {
                    PlayerPrefs.SetFloat(PrefKey, best);
                    persistedBest = best;
                }
            }

            for (int i = 0; i < Milestones.Length; i++)
            {
                float m = Milestones[i];
                if (milestoneSaid[i] || prev >= m || height < m) continue;
                milestoneSaid[i] = true;
                Say(MilestoneLines[i], 6f);
            }
            // The park has no panic waves, so Pip teaches the coping tool the first time the heart races.
            if (!copingSaid && FearSystem.Fear > 0.55f && Time.time - lastLineTime > 7f)
            {
                copingSaid = true;
                Say("Feel your heart racing? That's normal. Look up at the sky, breathe out slowly - the feeling always passes.", 7f);
            }
            if (!ach100 && height >= 100f)
            {
                ach100 = true;
                Achievements.Unlock("elevator_100");
            }
        }

        void OnStopped()
        {
            velocity = 0f;
            dir = 0;
            if (machineryOn)
            {
                AmbientAudio.Machinery = 0f;
                machineryOn = false;
            }
            ProceduralAudio.PlayClunkAt(platform.position);

            bool rode = carrying;
            if (rode) Haptics.Medium(); // no random buzz when an empty lift arrives far away
            if (carrying)
            {
                carrying = false;
                var rig = PlayerRig.Instance;
                if (rig != null) rig.SetLocomotionEnabled(true);
            }
            SaveBest();

            if (height <= 0.01f)
            {
                if (rode) Landed();
                LogSessionMax();
            }
            else if (rode)
            {
                if (height >= MaxHeight - 0.01f)
                {
                    Say("The very top - 120 metres! Take in the view, breathe, and press DOWN whenever you're ready.", 7f);
                }
                else
                {
                    HeadHud.Instance.ShowMessage("Stopped at " + Mathf.RoundToInt(height).ToString(Inv) + " m - UP or DOWN when you're ready", 3f);
                    if (height > 3f && Time.time > nextStopLine)
                    {
                        nextStopLine = Time.time + 25f;
                        Say(StopLines[stopLineIndex % StopLines.Length], 6f);
                        stopLineIndex++;
                    }
                }
            }
        }

        void Landed()
        {
            if (rideMax >= 2f)
            {
                string h = Mathf.RoundToInt(rideMax).ToString(Inv);
                ProceduralAudio.PlaySuccess();
                if (rideMax > bestAtRideStart + 0.5f) HeadHud.Instance.ShowMessage("New personal best: " + h + " m!", 4f);
                Say("Back on solid ground. You rode up to " + h + " metres - that took real courage!", 6f);
                bestAtRideStart = best;
            }
            rideMax = 0f;
        }

        void SaveBest()
        {
            if (best <= savedBest + 0.001f) return;
            if (best > BestHeight) PlayerPrefs.SetFloat(PrefKey, best);
            PlayerPrefs.Save();
            savedBest = best;
            if (best > persistedBest) persistedBest = best;
        }

        void LogSessionMax()
        {
            if (sessionMax < 1f || sessionMax <= loggedMax + 0.05f) return;
            SessionLogger.Log(LevelName, "elevator_max", sessionMax.ToString("F1", Inv));
            loggedMax = sessionMax;
        }

        void Say(string line, float seconds)
        {
            lastLineTime = Time.time;
            Companion.Say(line, seconds);
        }

        bool IsPlayerOn(PlayerRig rig)
        {
            Vector3 p = platform.InverseTransformPoint(rig.Head.position);
            float above = p.y - FloorTop;
            if (above < 0f || above > Headroom) return false;
            if (Mathf.Abs(p.x) <= Half && Mathf.Abs(p.z) <= Half) return true;
            // VR: leaning over the rail up high. The feet are still on this floor, so the lift must carry the
            // player - otherwise it would leave without them and gravity would drop them to the ground.
            return height > GateHeight && Mathf.Abs(rig.FeetY - (platform.position.y + FloorTop)) < 0.3f
                && Mathf.Abs(p.x) <= Half + 0.6f && Mathf.Abs(p.z) <= Half + 0.6f;
        }

        bool HeadUnderPlatform(PlayerRig rig)
        {
            Vector3 p = platform.InverseTransformPoint(rig.Head.position);
            return Mathf.Abs(p.x) <= Half + 0.15f && Mathf.Abs(p.z) <= Half + 0.15f && p.y < 0f && p.y > -0.6f;
        }

        void ApplyHeight()
        {
            platform.localPosition = new Vector3(0f, height, 0f);
            float open = 1f - Mathf.Clamp01(height / GateHeight);
            if (open != shownGate)
            {
                shownGate = open;
                gatePivot.localRotation = Quaternion.Euler(0f, 90f * open, 0f);
            }
            bool closed = height > GateHeight;
            if (gateCollider != null && gateCollider.enabled != closed) gateCollider.enabled = closed;
        }

        // ------------------------------------------------------------------ ambience and feedback

        void IdleChecks(PlayerRig rig)
        {
            if (rig == null) return;
            if (CatchFall(rig)) return;
            bool on = IsPlayerOn(rig);
            if (on && !wasOn && height < 0.5f && Time.time > nextGroundHint)
            {
                nextGroundHint = Time.time + 12f;
                HeadHud.Instance.ShowMessage("Courage Elevator: UP to rise, STOP to pause, DOWN to come back", 4f);
            }
            wasOn = on;

            if (!introSaid)
            {
                Vector3 d = rig.Head.position - transform.position;
                d.y = 0f;
                if (on || d.sqrMagnitude < 20f)
                {
                    introSaid = true;
                    Say("This is the Courage Elevator - free practice. Step in, press UP, and STOP whenever you like. You're in control.", 7f);
                }
            }
        }

        /// <summary>
        /// Quest room-scale safety net: walking physically through the glass moves the body capsule off the floor
        /// and the rig's gravity would drop the player to the grass (the park has no FallGuard). Put them back on the lift.
        /// </summary>
        bool CatchFall(PlayerRig rig)
        {
            if (height < 1.5f) return false;
            float floorY = platform.position.y + FloorTop;
            float feet = rig.FeetY;
            if (feet > floorY - 0.5f || feet < transform.position.y + 0.3f) return false; // on the lift, or on the ground
            Vector3 p = platform.InverseTransformPoint(rig.Head.position);
            if (Mathf.Abs(p.x) > Half + 3f || Mathf.Abs(p.z) > Half + 3f) return false;
            rig.TeleportTo(platform.TransformPoint(new Vector3(0f, FloorTop, 0f)), rig.Head.forward);
            wasOn = true;
            Haptics.Medium();
            HeadHud.Instance.ShowMessage("Caught you! Stay inside the glass rails - you're safe on the lift.", 4f);
            return true;
        }

        void UpdateAtmosphere(PlayerRig rig)
        {
            // No SafeRoom check: the park has none, and SafeRoom.InSafeRoom stays stale (true) after
            // "Leave level" from the Calm Meadow, which would silence the wind here for the whole visit.
            if (rig == null) return;
            float above = rig.FeetY - transform.position.y;
            if (!windOn && above > 3f)
            {
                windOn = true;
                AmbientAudio.SetMeadow(false);
            }
            else if (windOn && above < 1f)
            {
                windOn = false;
                AmbientAudio.SetMeadow(true);
            }
        }

        void UpdateMachinery(PlayerRig rig)
        {
            float proximity = 1f;
            if (!carrying && rig != null)
                proximity = Mathf.Clamp01(1f - Vector3.Distance(rig.Head.position, platform.position) / 30f);
            AmbientAudio.Machinery = Mathf.Clamp01(Mathf.Abs(velocity) / Speed) * 0.8f * proximity;
            machineryOn = true;
        }

        void UpdateBeacon()
        {
            if (beacon == null) return;
            bool on = Mathf.Repeat(Time.time, 1.5f) < 0.35f;
            if (on == beaconOn) return;
            beaconOn = on;
            beacon.enabled = on;
        }

        /// <summary>Graded-exposure ladder: the next small step above the personal best.</summary>
        static string NextGoalText(float bestSoFar)
        {
            for (int i = 0; i < GoalLadder.Length; i++)
                if (bestSoFar < GoalLadder[i] - 0.5f) return "Next goal: " + GoalLadder[i].ToString(Inv) + " m";
            return "You reached the top - amazing!";
        }

        int StateIndex()
        {
            if (dir > 0) return 1;
            if (dir < 0) return 2;
            if (velocity != 0f) return 5;
            if (height <= 0.01f) return 0;
            if (height >= MaxHeight - 0.01f) return 4;
            return 3;
        }

        void RefreshReadout(bool force)
        {
            int m = Mathf.RoundToInt(height);
            if (force || m != shownMeters)
            {
                shownMeters = m;
                if (heightLabel != null) heightLabel.text = m.ToString(Inv) + " m";
            }
            int s = StateIndex();
            if (force || s != shownState)
            {
                shownState = s;
                if (stateLabel != null) stateLabel.text = StateText[s];
            }
            int b = Mathf.RoundToInt(best);
            if (force || b != shownBest)
            {
                shownBest = b;
                string bs = b.ToString(Inv);
                if (bestLabel != null) bestLabel.text = b > 0 ? "Best: " + bs + " m" : "Best: not set yet";
                if (signBestLabel != null) signBestLabel.text = b > 0 ? "Your best: " + bs + " m" : "How high will you go?";
                if (goalLabel != null) goalLabel.text = NextGoalText(best);
            }
        }

        // ------------------------------------------------------------------ construction

        void BuildMaterials()
        {
            litShader = Shader.Find("Universal Render Pipeline/Lit");
            metal = Lit(new Color(0.78f, 0.8f, 0.84f), 0.75f, 0.55f);
            steel = Lit(new Color(0.32f, 0.34f, 0.38f), 0.6f, 0.4f);
            padMat = Lit(new Color(0.16f, 0.18f, 0.2f), 0f, 0.2f);
            housingMat = Lit(new Color(0.1f, 0.12f, 0.15f), 0.3f, 0.45f);
            yellowMat = Lit(new Color(1f, 0.78f, 0.15f), 0.2f, 0.4f);
            greenMat = Lit(new Color(0.3f, 0.95f, 0.5f), 0f, 0.6f, new Color(0.35f, 1.4f, 0.6f));
            redMat = Lit(new Color(1f, 0.25f, 0.2f), 0f, 0.6f, new Color(1.6f, 0.3f, 0.2f));
            blueMat = Lit(new Color(0.35f, 0.65f, 1f), 0f, 0.6f, new Color(0.4f, 0.9f, 1.8f));
            goldMat = Lit(UIFactory.Gold, 0.2f, 0.6f, new Color(1.5f, 1.2f, 0.35f));
            beaconMat = Lit(new Color(1f, 0.25f, 0.2f), 0f, 0.5f, new Color(4f, 0.7f, 0.5f));
            floorGlass = Glass(new Color(0.7f, 0.9f, 1f, 0.3f));
            panelGlass = Glass(new Color(0.8f, 0.95f, 1f, 0.16f));
        }

        void BuildGeometry()
        {
            // Cube only: CreatePrimitive(Sphere) needs SphereCollider, which no build scene references, so
            // "Strip Engine Code" (IL2CPP / Quest) may remove it and the primitive would fail at runtime.
            if (cubeMesh == null) cubeMesh = PrimitiveMesh(PrimitiveType.Cube);
            Transform root = transform;

            // ---- static shaft: base pad, four guide masts, crown and blinking beacon
            Shape("Base Pad", root, cubeMesh, new Vector3(0f, 0.01f, 0f), new Vector3(2.9f, 0.02f, 2.9f), padMat, false);
            for (int i = 0; i < 4; i++)
            {
                float x = (i & 1) == 0 ? -1.32f : 1.32f;
                float z = (i & 2) == 0 ? -1.32f : 1.32f;
                Shape("Guide Mast", root, cubeMesh, new Vector3(x, MastHeight * 0.5f, z), new Vector3(0.08f, MastHeight, 0.08f), steel, true);
            }
            Shape("Crown", root, cubeMesh, new Vector3(0f, MastHeight + 0.1f, 0f), new Vector3(2.9f, 0.2f, 2.9f), steel, false);
            var beaconGo = Shape("Beacon", root, cubeMesh, new Vector3(0f, MastHeight + 0.6f, 0f), Vector3.one * 0.55f, beaconMat, false);
            beaconGo.transform.localRotation = Quaternion.Euler(45f, 0f, 45f); // diamond-shaped warning light
            beacon = beaconGo.GetComponent<Renderer>();

            // ---- call pedestal beside the gate (brings the lift down if it was left up high)
            Shape("Call Post", root, cubeMesh, new Vector3(-1.95f, 0.5f, 1.5f), new Vector3(0.16f, 1f, 0.16f), metal, true);
            var call = Shape("Call Button", root, cubeMesh, new Vector3(-1.95f, 1.0175f, 1.5f), new Vector3(0.11f, 0.11f, 0.035f), goldMat, true);
            call.transform.localRotation = Quaternion.Euler(90f, 0f, 0f); // +Z (poke direction) points down
            AddButton(call, ElevatorButton.ButtonAction.Call, "Call the lift");
            var callLabel = UIFactory.CreateWorldCanvas("Call Label", new Vector2(320, 90), 0.001f, root);
            callLabel.transform.localPosition = new Vector3(-1.95f, 1.22f, 1.5f);
            callLabel.transform.localRotation = Quaternion.Euler(0f, 180f, 0f);
            DisableRaycasters(callLabel);
            UIFactory.FullPanel(callLabel.transform, UIFactory.PanelColor).raycastTarget = false;
            UIFactory.Label(callLabel.transform, "CALL LIFT", 44, Vector2.zero, new Vector2(300, 80), TextAnchor.MiddleCenter, UIFactory.Gold, FontStyle.Bold);

            // ---- moving platform (kinematic body so its colliders move cheaply)
            platform = new GameObject("Platform").transform;
            platform.SetParent(root, false);
            var body = platform.gameObject.AddComponent<Rigidbody>();
            body.isKinematic = true;
            body.useGravity = false;

            Shape("Glass Floor", platform, cubeMesh, new Vector3(0f, FloorTop * 0.5f, 0f), new Vector3(Half * 2f, FloorTop, Half * 2f), floorGlass, true);
            Shape("Frame", platform, cubeMesh, new Vector3(0f, 0.035f, Half), new Vector3(2.48f, 0.07f, 0.08f), metal, false);
            Shape("Frame", platform, cubeMesh, new Vector3(0f, 0.035f, -Half), new Vector3(2.48f, 0.07f, 0.08f), metal, false);
            Shape("Frame", platform, cubeMesh, new Vector3(Half, 0.035f, 0f), new Vector3(0.08f, 0.07f, 2.32f), metal, false);
            Shape("Frame", platform, cubeMesh, new Vector3(-Half, 0.035f, 0f), new Vector3(0.08f, 0.07f, 2.32f), metal, false);

            const float panelH = 1.05f;
            const float railY = 1.13f;
            float panelY = FloorTop + panelH * 0.5f;
            // Safety-glass balustrade (see-through, so the fear system still "sees" the drop) with metal top rails.
            Shape("Glass Back", platform, cubeMesh, new Vector3(0f, panelY, -Half), new Vector3(2.4f, panelH, 0.03f), panelGlass, true);
            Shape("Glass Left", platform, cubeMesh, new Vector3(-Half, panelY, 0f), new Vector3(0.03f, panelH, 2.4f), panelGlass, true);
            Shape("Glass Right", platform, cubeMesh, new Vector3(Half, panelY, 0f), new Vector3(0.03f, panelH, 2.4f), panelGlass, true);
            Shape("Rail", platform, cubeMesh, new Vector3(0f, railY, -Half), new Vector3(2.46f, 0.05f, 0.05f), metal, false);
            Shape("Rail", platform, cubeMesh, new Vector3(-Half, railY, 0f), new Vector3(0.05f, 0.05f, 2.46f), metal, false);
            Shape("Rail", platform, cubeMesh, new Vector3(Half, railY, 0f), new Vector3(0.05f, 0.05f, 2.46f), metal, false);
            for (int i = 0; i < 4; i++)
            {
                float x = (i & 1) == 0 ? -Half : Half;
                float z = (i & 2) == 0 ? -Half : Half;
                Shape("Post", platform, cubeMesh, new Vector3(x, 0.6f, z), new Vector3(0.06f, 1.1f, 0.06f), metal, false);
            }

            // Swing gate on the front (+Z) side: open at ground level, closes and blocks above 0.3 m.
            gatePivot = new GameObject("Gate").transform;
            gatePivot.SetParent(platform, false);
            gatePivot.localPosition = new Vector3(Half, 0f, Half);
            var gate = Shape("Gate Glass", gatePivot, cubeMesh, new Vector3(-Half, panelY, 0f), new Vector3(2.34f, panelH, 0.03f), panelGlass, true);
            gateCollider = gate.GetComponent<Collider>();
            Shape("Gate Bar", gatePivot, cubeMesh, new Vector3(-Half, railY, 0f), new Vector3(2.34f, 0.05f, 0.05f), yellowMat, false);

            // ---- control lectern on the back rail: UP / STOP / DOWN
            Shape("Control Post", platform, cubeMesh, new Vector3(0.55f, FloorTop + 0.5f, -0.98f), new Vector3(0.07f, 1f, 0.07f), metal, false);
            var controls = new GameObject("Controls").transform;
            controls.SetParent(platform, false);
            controls.localPosition = new Vector3(0.55f, 1.1f, -0.98f);
            controls.localRotation = Quaternion.Euler(30f, 180f, 0f); // +Z into the panel, face tilted up towards the rider
            Shape("Control Plate", controls, cubeMesh, new Vector3(0f, 0f, 0.02f), new Vector3(0.44f, 0.26f, 0.03f), housingMat, false);
            AddButton(Shape("Button Up", controls, cubeMesh, new Vector3(-0.14f, 0.035f, -0.0125f), new Vector3(0.09f, 0.09f, 0.035f), greenMat, true),
                ElevatorButton.ButtonAction.Up, "Go up");
            AddButton(Shape("Button Stop", controls, cubeMesh, new Vector3(0f, 0.035f, -0.0125f), new Vector3(0.09f, 0.09f, 0.035f), redMat, true),
                ElevatorButton.ButtonAction.Stop, "Stop");
            AddButton(Shape("Button Down", controls, cubeMesh, new Vector3(0.14f, 0.035f, -0.0125f), new Vector3(0.09f, 0.09f, 0.035f), blueMat, true),
                ElevatorButton.ButtonAction.Down, "Go down");
            var labels = UIFactory.CreateWorldCanvas("Control Labels", new Vector2(440, 260), 0.001f, controls);
            labels.transform.localPosition = new Vector3(0f, 0f, 0.003f);
            labels.transform.localRotation = Quaternion.identity;
            DisableRaycasters(labels);
            UIFactory.Label(labels.transform, "UP", 30, new Vector2(-140, -78), new Vector2(130, 40), TextAnchor.MiddleCenter, UIFactory.Calm, FontStyle.Bold);
            UIFactory.Label(labels.transform, "STOP", 30, new Vector2(0, -78), new Vector2(130, 40), TextAnchor.MiddleCenter, UIFactory.Warn, FontStyle.Bold);
            UIFactory.Label(labels.transform, "DOWN", 30, new Vector2(140, -78), new Vector2(130, 40), TextAnchor.MiddleCenter, UIFactory.Accent, FontStyle.Bold);

            // ---- height readout above the controls
            Shape("Display", platform, cubeMesh, new Vector3(0.55f, 1.37f, -1.165f), new Vector3(0.62f, 0.46f, 0.03f), housingMat, false);
            var display = UIFactory.CreateWorldCanvas("Elevator Display", new Vector2(580, 420), 0.001f, platform);
            display.transform.localPosition = new Vector3(0.55f, 1.37f, -1.148f);
            display.transform.localRotation = Quaternion.Euler(0f, 180f, 0f);
            DisableRaycasters(display);
            heightLabel = UIFactory.Label(display.transform, "0 m", 120, new Vector2(0, 95), new Vector2(560, 150), TextAnchor.MiddleCenter, Color.white, FontStyle.Bold);
            stateLabel = UIFactory.Label(display.transform, "", 34, new Vector2(0, -15), new Vector2(560, 50), TextAnchor.MiddleCenter, UIFactory.Accent);
            bestLabel = UIFactory.Label(display.transform, "", 36, new Vector2(0, -85), new Vector2(560, 50), TextAnchor.MiddleCenter, UIFactory.Gold, FontStyle.Bold);
            goalLabel = UIFactory.Label(display.transform, "", 30, new Vector2(0, -158), new Vector2(560, 44), TextAnchor.MiddleCenter, UIFactory.Calm);
        }

        void BuildSign()
        {
            // Floats just in front of the shaft (so the rising platform never passes through it), facing the player start.
            var sign = UIFactory.CreateWorldCanvas("Courage Elevator Sign", new Vector2(1500, 420), 0.0012f, transform);
            Vector3 pos = transform.TransformPoint(new Vector3(0f, 3.2f, 1.8f));
            Vector3 face = pos;
            face.y = 0f;
            if (face.sqrMagnitude < 0.01f) face = -transform.forward;
            sign.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(face));
            DisableRaycasters(sign);
            UIFactory.FullPanel(sign.transform, UIFactory.PanelColor).raycastTarget = false;
            UIFactory.Label(sign.transform, "COURAGE ELEVATOR", 110, new Vector2(0, 110), new Vector2(1450, 130), TextAnchor.MiddleCenter, UIFactory.Gold, FontStyle.Bold);
            UIFactory.Label(sign.transform, "Free practice - choose your own height", 56, new Vector2(0, 5), new Vector2(1450, 70), TextAnchor.MiddleCenter, Color.white);
            UIFactory.Label(sign.transform, "Step in, press UP, STOP whenever you like. Up to 120 m.", 40, new Vector2(0, -75), new Vector2(1450, 50), TextAnchor.MiddleCenter, new Color(1f, 1f, 1f, 0.8f));
            signBestLabel = UIFactory.Label(sign.transform, "", 44, new Vector2(0, -150), new Vector2(1450, 56), TextAnchor.MiddleCenter, UIFactory.Calm, FontStyle.Bold);
        }

        void AddButton(GameObject go, ElevatorButton.ButtonAction action, string hint)
        {
            go.AddComponent<ElevatorButton>().Setup(this, action, hint);
        }

        static void DisableRaycasters(Canvas canvas)
        {
            foreach (var r in canvas.GetComponents<UnityEngine.EventSystems.BaseRaycaster>()) r.enabled = false;
        }

        static GameObject Shape(string name, Transform parent, Mesh mesh, Vector3 localPos, Vector3 size, Material mat, bool collider)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localScale = size;
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = mat;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            if (collider)
            {
                var box = go.AddComponent<BoxCollider>();
                box.center = Vector3.zero;
                box.size = Vector3.one;
            }
            return go;
        }

        static Mesh PrimitiveMesh(PrimitiveType type)
        {
            var go = GameObject.CreatePrimitive(type);
            go.SetActive(false);
            var mesh = go.GetComponent<MeshFilter>().sharedMesh;
            Destroy(go);
            return mesh;
        }

        // ------------------------------------------------------------------ materials

        Material NewBase()
        {
            Material m = null;
            if (litShader != null) m = new Material(litShader);
            else
            {
                // Shader.Find can fail if the shader was stripped: clone a material already in the scene.
                if (template == null) template = FindTemplate();
                if (template != null)
                {
                    m = new Material(template);
                    if (m.HasProperty("_BaseMap")) m.SetTexture("_BaseMap", null);
                    if (m.HasProperty("_MainTex")) m.SetTexture("_MainTex", null);
                    if (m.HasProperty("_BumpMap")) m.SetTexture("_BumpMap", null);
                    m.DisableKeyword("_NORMALMAP");
                    m.DisableKeyword("_EMISSION");
                    m.DisableKeyword("_SURFACE_TYPE_TRANSPARENT");
                    m.DisableKeyword("_ALPHAPREMULTIPLY_ON");
                }
            }
            if (m != null) materials.Add(m);
            return m;
        }

        static Material FindTemplate()
        {
            Material any = null;
            var renderers = FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None);
            for (int i = 0; i < renderers.Length; i++)
            {
                var mat = renderers[i].sharedMaterial;
                if (mat == null || mat.shader == null) continue;
                if (any == null) any = mat;
                if (mat.shader.name == "Universal Render Pipeline/Lit" && mat.renderQueue < 2500) return mat;
            }
            return any;
        }

        Material Lit(Color color, float metallic, float smoothness, Color? emission = null)
        {
            var m = NewBase();
            if (m == null) return null;
            SetColor(m, color);
            SetFloat(m, "_Metallic", metallic);
            SetFloat(m, "_Smoothness", smoothness);
            if (emission.HasValue)
            {
                m.EnableKeyword("_EMISSION");
                if (m.HasProperty(EmissionId)) m.SetColor(EmissionId, emission.Value);
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;
            }
            else
            {
                m.DisableKeyword("_EMISSION");
                if (m.HasProperty(EmissionId)) m.SetColor(EmissionId, Color.black);
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.EmissiveIsBlack;
            }
            return m;
        }

        /// <summary>URP Lit transparent (alpha, premultiplied) - same keyword set as the project's FloorGlass so the variant is in the build.</summary>
        Material Glass(Color color)
        {
            var m = NewBase();
            if (m == null) return null;
            SetColor(m, color);
            SetFloat(m, "_Metallic", 0f);
            SetFloat(m, "_Smoothness", 0.9f);
            SetFloat(m, "_Surface", 1f);
            SetFloat(m, "_Blend", 0f);
            SetFloat(m, "_SrcBlend", (float)UnityEngine.Rendering.BlendMode.One);
            SetFloat(m, "_DstBlend", (float)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            SetFloat(m, "_SrcBlendAlpha", (float)UnityEngine.Rendering.BlendMode.One);
            SetFloat(m, "_DstBlendAlpha", (float)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            SetFloat(m, "_ZWrite", 0f);
            m.DisableKeyword("_EMISSION");
            m.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            m.EnableKeyword("_ALPHAPREMULTIPLY_ON");
            m.SetOverrideTag("RenderType", "Transparent");
            m.SetShaderPassEnabled("DepthOnly", false);
            m.SetShaderPassEnabled("ShadowCaster", false);
            m.SetShaderPassEnabled("MotionVectors", false);
            // Render queue >= 3000 also tells FearSystem this surface is see-through.
            m.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
            return m;
        }

        static void SetColor(Material m, Color c)
        {
            if (m.HasProperty(BaseColorId)) m.SetColor(BaseColorId, c);
            if (m.HasProperty(ColorId)) m.SetColor(ColorId, c);
        }

        static void SetFloat(Material m, string property, float value)
        {
            if (m.HasProperty(property)) m.SetFloat(property, value);
        }
    }
}
