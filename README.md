# Webcam Gesture Controller Walkthrough

Welcome to the upgraded **Webcam Gesture Controller**! This real-time computer vision application tracks up to **two hands concurrently**, mapping intuitive spatial gestures to operating system events (mouse navigation, clicking, double-clicking, scrolling, volume control, and keyboard media shortcuts).

To prevent tracking interference, the application separates controls into distinct **hand-specific profiles**:
1. **Right Hand Profile**: Absolute cursor navigation, single clicks, dragging, and double-clicks.
2. **Left Hand Profile**: Window scrolling, master system volume adjustments, and media/presentation hotkeys.

---

## Workspace Files

* [requirements.txt](file:///C:/Users/Varshan/Documents/antigravity/delightful-nobel/requirements.txt): Third-party libraries (`mediapipe`, `opencv-python`, `pyautogui`, `pycaw`, `numpy`, `comtypes`).
* [config.py](file:///C:/Users/Varshan/Documents/antigravity/delightful-nobel/config.py): Contains active zone bounds, double-click timing windows, hotkey cooldowns, speed-acceleration thresholds, and neon HUD BGR colors.
* [filters.py](file:///C:/Users/Varshan/Documents/antigravity/delightful-nobel/filters.py): Implements the `AdaptiveEMAFilter` that eliminates coordinate tremors.
* [gestures.py](file:///C:/Users/Varshan/Documents/antigravity/delightful-nobel/gestures.py): Geometry engine to classify hand positions (including Fist, Thumbs-up, and OK signs).
* [controller.py](file:///C:/Users/Varshan/Documents/antigravity/delightful-nobel/controller.py): Visualizes dual-hand skeletons, maps Right/Left hand coordinate pipelines, applies mouse acceleration, and executes system triggers.
* [patch.py](file:///C:/Users/Varshan/Documents/antigravity/delightful-nobel/patch.py): Monkeypatch utility ensuring compatibility with Python 3.12+ / 3.13 / 3.14 on Windows.
* [main.py](file:///C:/Users/Varshan/Documents/antigravity/delightful-nobel/main.py): Clean command-line CLI tool.

---

## 🖐️ Hand-Specific Gesture Vocabulary

To ensure scale-invariance, all gesture threshold distances are divided by a reference palm size (the distance from the Wrist [0] to the Middle Knuckle [9]).

### 1. Right Hand Controls (Mirrored as "Left Hand" in feed)
*Handles cursor guidance, clicks, and window dragging.*

| Gesture | Hand Pose | OS Interaction | Cyber-HUD Overlay |
| :--- | :--- | :--- | :--- |
| **Move Cursor** | **Index finger UP**, other fingers closed. | Moves the cursor inside the central active bounds. | Cyan glowing crosshair tracking fingertip. |
| **Left Click / Drag** | **Pinch Thumb + Index tip** (in Cursor Mode). | Left-click down (pinch-hold to drag-and-drop folders/windows). | Expanding Cyan ripple from pinch location. |
| **Right Click** | **Pinch Thumb + Middle tip** (in Cursor Mode). | Triggers system right-click. | Expanding Magenta ripple from pinch location. |
| **Double Click** | **Double Pinch Index + Thumb** within `0.35s`. | Triggers a native OS double-click. | Two rapid Cyan ripples. |

### 2. Left Hand Controls (Mirrored as "Right Hand" in feed)
*Handles scrolling, volume, and presentation shortcuts without displacing your cursor.*

| Gesture | Hand Pose | OS Interaction | Cyber-HUD Overlay |
| :--- | :--- | :--- | :--- |
| **Page Scroll** | **Index & Middle UP & Close**, others closed. | Move hand vertically up/down to scroll active pages. | Dual vertical scroll arrows. |
| **Volume Control** | **Index & Thumb open**, others closed. | Pinch/unpinch distance regulates master system volume. | Pink HUD volume progress bar displaying %. |
| **Play / Pause** | **Fist Gesture** (all fingers and thumb closed). | Presses keyboard `playpause` key (1.2s cooldown). | Medium glowing green ring. |
| **Volume Mute** | **Thumbs Up** (vertical thumb extended, others closed). | Toggles master audio mute state (`volumemute`). | Medium glowing green ring. |
| **Show Desktop** | **OK Sign** (Index + Thumb pinch, other fingers open). | Minimizes all active windows (`Win + D` hotkey). | Medium glowing magenta ring. |

### 3. Safety Lock (Any Hand)
* **Pause / Resume**: Hold a **Fully Open Palm** steady for 2.0 seconds to toggle the controller state. A circular locks progress countdown is drawn on-screen.

---

## Setup & Execution

### 1. Launch the Controller
```powershell
python main.py
```

### 2. Custom Command Line Options
```powershell
# Increase tracking sensitivity multiplier
python main.py --sensitivity 1.5

# Connect to an external camera on index 1
python main.py --camera 1

# Launch with PyCaw audio volume control disabled
python main.py --no-volume
```

---

## Technical Features

* **Absolute Mouse Acceleration**: Cursor speed scales dynamically based on hand movement velocity. At slow speeds, a precision dampener (`0.5x`) activates for pixel-perfect targeting. At high speeds, an acceleration multiplier (`2.2x`) activates, allowing you to traverse your monitor with minor wrist motions.
* **Mirrored Role Handedness**: Because a webcam mirrors your image, a physical Right Hand appears on the left. The software accounts for this, mapping the Right Hand role to mirrored Left labels, ensuring intuitive, natural coordination.
* **Tactile Cooldown Engine**: Media key bindings are armed with a rising-edge toggle and a `1.2` second cooldown. This ensures that forming a Fist pauses a video *once* rather than spamming play/pause event queues.
