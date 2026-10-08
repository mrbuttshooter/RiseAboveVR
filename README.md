# Rise Above - a VR game for overcoming the fear of heights

End-of-year project. A three-level virtual-reality experience built in Unity 6 that uses
**graded exposure** - the technique psychologists use to treat acrophobia (fear of heights) -
wrapped in a friendly, game-like journey with a companion, tasks, stars and a safe place to retreat to.

## The idea

People with acrophobia avoid heights, so the fear never gets a chance to fade. Exposure therapy
does the opposite: the person faces a height that is *a little* scary, stays until the anxiety
drops, then moves a step higher. VR is ideal for this because the height feels real while the
person is actually standing safely on the floor.

Rise Above turns those principles into game design:

| Therapy principle | How the game does it |
|---|---|
| Graded hierarchy (low -> high) | 3 levels: 6 m balcony -> 25-31 m construction site -> 150 m skyscraper. Levels unlock in order. |
| Measuring anxiety (SUDS 0-10) | Before and after every level the player rates their anxiety. Results go to a CSV log and the trophy-wall graph. |
| Approach, don't avoid | Tasks require looking down, leaning over railings, walking on glass, crossing beams. |
| Feeling in control | **Calm Meadow** escape at any moment (X button / Esc) and back to the checkpoint when ready. |
| Adjustable intensity | **Exposure modes**: Gentle (safety glass, extra rails, wider beams, fog hides the drop), Standard, Brave (no helpers, clear air, stronger wind). Game suggests Gentle if the starting rating is 8+. |
| Coping skills | Guided slow breathing (in 4 s, hold 4 s, out 6 s) at the start and at checkpoints. |
| Encouragement | **Pip**, a little glowing bird-drone companion who explains tasks and reassures the player. |
| No punishment | Slipping fades gently back to the last checkpoint - no falling animation. |

## The levels

**Park hub (main menu)** - level portals, exposure-mode picker, trophy wall with before/after anxiety bars, help board.

**Level 1 - Sunset Cafe balcony (6 m)**
- Water three flowers on a shelf *outside* the railing (grab the can, tilt to pour)
- Look down and find the street musician, the fountain and a dog on a walk (hold your gaze)
- Walk the glass skywalk - the glass cracks while you stand on it, so keep moving

**Level 2 - Construction site (25-31 m)**
- Ride an open lift that *stalls halfway* (Pip talks you through it)
- Collect 3 lost tools - one is at the end of a diving-board plank
- Cross a wobbling plank bridge (balance meter), climb a ladder hand-over-hand
- Walk the crane catwalk in the wind and plant the topping-out flag
- Ride a steel beam hanging from the crane across to the next roof

**Level 3 - Skyscraper (150 m)**
- Cross a steel beam between towers while wind gusts hit - crouch to resist
- Run over loose tiles that crumble a moment after you step on them
- Cross a swaying rope bridge, walk a plank to rescue Mittens the cat
- Launch the fireworks finale over the city

**Stars** per level: finish (1) + no slips (1) + all three Courage Stars (1). Courage Stars float at the scariest spots.

## Controls

| | VR (Quest / PC VR) | Desktop (no headset) |
|---|---|---|
| Move | Left stick | WASD (Shift = careful steps) |
| Turn / teleport | Right stick | Mouse |
| Grab / climb | Grip | Left click (Space to climb) |
| Press UI | Trigger | Click |
| Pour watering can | Tilt it | Hold right mouse |
| Crouch (wind) | Really crouch | C |
| Calm Meadow | X (left controller) | Esc |
| Free cursor | - | Tab (hold right mouse to look while free) |

Desktop mode switches on automatically when no headset is detected (or start the build with `-desktop`),
so the whole game can be played and presented on a normal laptop.

## Ready-made builds

| Build | Where | How to run |
|---|---|---|
| Windows (PC, desktop mode or PC VR) | `E:\Unity_project\Builds\Windows\RiseAboveVR.exe` | Double-click. With no headset it starts in desktop mode. With Quest Link / SteamVR running it starts in VR. Add `-desktop` to force desktop mode. |
| Meta Quest (standalone) | `E:\Unity_project\Builds\Quest\RiseAboveVR.apk` | Enable Developer Mode on the Quest, connect by USB, then `adb install -r RiseAboveVR.apk` (or drag it into SideQuest). Find it under *Unknown Sources*. |

Screenshots from the play-test are in the `Screenshots/` folder (good for the report/presentation).

## Running it in Unity

1. Open the folder `RiseAboveVR` with **Unity 6000.3.25f1** (Unity 6 LTS).
2. Menu **Rise Above > Build All Scenes** (already done once - re-run after changing level code).
3. Open `Assets/AcrophobiaVR/Scenes/MainMenu.unity` and press **Play**.

**Meta Quest (standalone):** File > Build Profiles > Android > Switch Platform, connect the Quest (developer mode on), Build And Run.
**PC VR (Quest Link / SteamVR):** Build Profiles > Windows, enable OpenXR in Project Settings > XR Plug-in Management, Build.

## Data for the report

Every session appends to `acrophobia_log.csv` in `Application.persistentDataPath`
(menu **Rise Above > Open Session Log Folder**). Columns: `session,timestamp,level,event,value`.
Events include `anxiety_before`, `anxiety_after`, `level_complete_seconds`, `slip`, `calm_meadow_enter`,
`calm_meadow_exit_seconds`, `checkpoint`, `courage_star`, `objective_complete`, `exposure_mode`, `lift_stall`.
Open it in Excel to chart anxiety before vs after each level across sessions.

## Code map

```
Assets/AcrophobiaVR/
  Scripts/Core       GameManager (levels, unlocks, scene fades), PlayerRig, ExposureSettings, ProgressStore, SessionLogger
  Scripts/Gameplay   LevelController, objectives (look-down, collect, water, deliver, reach, press), hazards
                     (BalanceBeam, CrackingGlass, CrumblingTile, MovingPlatform, Ladder), SafeRoom, Companion, CourageStar
  Scripts/UI         Runtime-built world-space UI: HUD, rating panel, breathing guide, dialogs, menu, trophy graph
  Scripts/Ambient    Procedural audio (all sounds synthesised - no audio files), particles, birds, traffic, fireworks
  Scripts/Desktop    Keyboard + mouse fallback rig
  Editor/            LevelBuilder - generates all 4 scenes from code (Rise Above menu)
```

Everything is built from Unity primitives and synthesised sound - there are no third-party assets.

## Safety note

This is a student project, not a medical device. Anyone with severe acrophobia, epilepsy, motion sickness or
heart conditions should use it only with appropriate support. Play standing in a clear space, or seated.