# Webcam Gesture Controller

A Python application that uses a standard webcam to track hand gestures in real-time, mapping them to system events such as mouse movement, clicking, scrolling, and volume adjustments. The system uses MediaPipe for hand landmark extraction and OpenCV for a visual HUD feedback loop.

It includes an adaptive smoothing filter to eliminate camera coordinate jitter and uses scale-invariant calculations to ensure gestures work consistently regardless of your distance from the camera.

## Features

* **Adaptive Cursor Smoothing**: Uses an Exponential Moving Average (EMA) filter that adjusts its smoothing coefficient dynamically based on hand speed. Slow movements are heavily filtered to allow precise pixel-level clicking, while fast movements have low latency.
* **Distance-Invariant Calibration**: All gesture thresholds are normalized against the user's palm length (the distance from the wrist to the middle finger knuckle). This calibration prevents coordinate scaling issues when moving closer to or further from the camera.
* **Continuous Click State Machine**: Pinches map directly to mouse button presses and releases (`mouseDown` and `mouseUp`), enabling native dragging, scrollbar sliding, and drop operations.
* **Windows Volume Integration**: Interacts directly with the Windows master audio endpoint via `pycaw` for seamless volume control.
* **Python 3.12+ Compatibility**: Includes a dynamic `ctypes` patch to resolve missing deallocation references in the compiled C++ binaries under newer Python interpreters on Windows.

## How it Works

1. **Webcam Pipeline**: The application grabs the camera frames, mirrors them horizontally for a natural user experience, and converts them to RGB.
2. **Landmark Extraction**: The frame is fed into the MediaPipe HandLandmarker. If a hand is found, the coordinates of its 21 joints are extracted.
3. **Gesture Classification**: The classifier analyzes relative distances between tips and knuckles to determine the active control state (e.g. mouse mode, scroll mode, or volume adjustment).
4. **Coordinate Mapping & Smoothing**: The index finger coordinate is mapped from a central bounding box in the camera view to your monitor's full pixel resolution. The coordinate is passed through the adaptive filter before PyAutoGUI moves the OS cursor.

## Gesture Reference

| Gesture | Hand Pose | Action |
| :--- | :--- | :--- |
| **Move Cursor** | Index finger extended, all other fingers closed. | Moves the cursor inside the screen. |
| **Left Click / Drag** | Pinch index finger and thumb tip together. | Left click (hold to drag-and-drop). |
| **Right Click** | Pinch middle finger and thumb tip together. | Triggers system right-click. |
| **Scroll Page** | Extend index and middle fingers close together. | Move hand up or down to scroll windows. |
| **Adjust Volume** | Extend index and thumb, close other fingers. | Move fingers closer/wider to change volume. |
| **System Pause** | Hold a fully open palm steady for 2 seconds. | Toggles gesture processing on or off. |

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/VARSHAN69/webcam-gesture-controller.git
   cd webcam-gesture-controller
   ```

2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the controller:
   ```bash
   python main.py
   ```

## Configuration and Usage

The controller can be started with command-line arguments to adjust settings:

* **Sensitivity**: Multiply the mouse scroll and cursor speed (default is 1.0):
  ```bash
  python main.py --sensitivity 1.5
  ```
* **Camera Index**: Specify a different camera (default is 0 for built-in webcams):
  ```bash
  python main.py --camera 1
  ```
* **Disable Volume Mixer**: Bypass the Windows audio mixer endpoint:
  ```bash
  python main.py --no-volume
  ```

### Controls

* **Pause / Resume**: Hold your hand fully open for 2 seconds to temporarily lock the controller (useful if you want to use your hands for something else without moving the mouse). Repeat the gesture to unlock.
* **Exit**: Select the active camera window and press **ESC** or **Q** on your keyboard to close the streams and release system resources.
* **Emergency Abort**: If the cursor becomes uncontrollable, violently move your physical mouse or guide the cursor to any of the four corners of your monitor to trigger the PyAutoGUI fail-safe and abort the script.

## Project Structure

* `config.py` — Calibration margins, color settings, and active zone bounds.
* `filters.py` — The velocity-sensitive `AdaptiveEMAFilter` implementation.
* `gestures.py` — Hand geometry parsing and scale-invariant calculations.
* `controller.py` — The core loop, OpenCV HUD rendering, and Windows OS bindings.
* `patch.py` — The ctypes monkeypatch for Python 3.12+ compatibility on Windows.
* `main.py` — CLI entrypoint and exception handler.

## License

This project is licensed under the MIT License.
