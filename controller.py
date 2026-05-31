import patch
import cv2
import time
import numpy as np
import pyautogui
import os
import urllib.request
import mediapipe as mp
import config
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from comtypes import CoInitialize, CoUninitialize

# Disable PyAutoGUI delay and fail-safe safety window margins
pyautogui.FAILSAFE = True  # Move mouse to any corner to abort execution
pyautogui.MINIMUM_DURATION = 0.0
pyautogui.MINIMUM_SLEEP_TIME = 0.001

from config import (
    FRAME_WIDTH, FRAME_HEIGHT, TARGET_FPS,
    ACTIVE_ZONE_LEFT, ACTIVE_ZONE_RIGHT, ACTIVE_ZONE_TOP, ACTIVE_ZONE_BOTTOM,
    COLOR_CYAN, COLOR_NEON_GREEN, COLOR_MAGENTA, COLOR_RED, COLOR_DARK_GRAY, COLOR_WHITE,
    FONT_HUD, HUD_LINE_THICKNESS, HUD_GLOW_THICKNESS
)
from filters import AdaptiveEMAFilter
from gestures import GestureClassifier

# Windows Volume Control Imports
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    WINDOWS_VOLUME_SUPPORT = True
except Exception:
    WINDOWS_VOLUME_SUPPORT = False


class GestureController:
    def __init__(self, camera_idx=0, sensitivity=1.0):
        self.camera_idx = camera_idx
        self.sensitivity = sensitivity
        
        # Initialize filter & classifier
        self.filter = AdaptiveEMAFilter()
        self.classifier = GestureClassifier()
        
        # Screen dimensions
        self.screen_width, self.screen_height = pyautogui.size()
        
        # Mouse click state machine
        self.left_pressed = False
        self.right_pressed = False
        
        # Timing trackers for upgrades
        self.last_left_click_time = 0.0
        self.last_hotkey_time = 0.0
        self.last_hotkey_pressed = None
        
        # Scroll tracking
        self.prev_scroll_y = None
        
        # Automatic download of model if missing
        self.model_path = "hand_landmarker.task"
        if not os.path.exists(self.model_path):
            print("[System] Pre-trained hand landmarker model not found. Downloading...")
            model_url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
            try:
                urllib.request.urlretrieve(model_url, self.model_path)
                print("[System] Model downloaded successfully!")
            except Exception as e:
                print(f"[Error] Failed to download MediaPipe model: {e}")
                raise e

        # Initialize MediaPipe Tasks HandLandmarker with 2 hands support
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=2,
            min_hand_detection_confidence=0.35,
            min_hand_presence_confidence=0.35,
            min_tracking_confidence=0.35,
            running_mode=vision.RunningMode.IMAGE
        )
        self.detector = vision.HandLandmarker.create_from_options(options)
        
        # Initialize PyCaw Audio controls (Windows-only)
        self.volume_control = None
        if WINDOWS_VOLUME_SUPPORT:
            try:
                CoInitialize()  # Initialize COM
                self.volume_control = AudioUtilities.GetSpeakers().EndpointVolume
            except Exception as e:
                print(f"[Warning] Failed to initialize Windows Core Audio interface: {e}")
        
        # Click ripple animation tracking
        self.ripples = []  # list of dicts: {"pos": (x, y), "radius": r, "color": c, "alpha": a}
        
        # FPS Calculation
        self.prev_time = 0
        self.fps = 0.0

    def __del__(self):
        # Release native MediaPipe Tasks resources
        if hasattr(self, 'detector'):
            try:
                self.detector.close()
            except Exception:
                pass
        # Gracefully uninitialize COM
        if WINDOWS_VOLUME_SUPPORT:
            try:
                CoUninitialize()
            except Exception:
                pass

    def run(self):
        # Open webcam capture
        cap = cv2.VideoCapture(self.camera_idx)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        
        if not cap.isOpened():
            print(f"[Error] Could not open camera with index {self.camera_idx}")
            return

        print("\n=== Webcam Gesture Controller Active ===")
        print("  - Cursor Control: Index finger UP (Inside neon active box)")
        print("  - Left Click / Drag: Pinch Index + Thumb")
        print("  - Right Click: Pinch Middle + Thumb")
        print("  - Web Scroll: Index & Middle UP (Move hand UP/DOWN to scroll)")
        print("  - Volume Control: Index & Thumb open (Fold other fingers; pinch/unpinch)")
        print("  - Pause / Resume: Hold fully OPEN PALM steady for 2 seconds")
        print("  - Exit Application: Press 'ESC' or 'Q' on the video window")
        print("=========================================\n")

        self.prev_time = time.time()

        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                print("[Warning] Empty camera frame received. Retrying...")
                continue

            # Calculate FPS
            curr_time = time.time()
            self.fps = 1.0 / (curr_time - self.prev_time) if (curr_time - self.prev_time) > 0 else 0
            self.prev_time = curr_time

            # 1. Flip frame horizontally for natural mirror interaction
            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            # 2. Process Hand landmarks using Tasks API (multi-hand tracking)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = self.detector.detect(mp_image)

            # Draw static HUD framework
            self._draw_hud_base(frame, w, h)

            gesture_for_hud = "IDLE"
            hand_found = False

            if results.hand_landmarks and results.handedness:
                hand_found = True
                
                # Loop through all detected hands (supports up to 2)
                for idx, landmarks in enumerate(results.hand_landmarks):
                    handedness = results.handedness[idx][0].category_name
                    
                    # Classify gesture for this hand
                    gesture, val = self.classifier.classify(landmarks, handedness, config)
                    
                    # Capture gesture label for HUD overlay panel
                    if handedness == "Left": # Right hand takes HUD label precedence
                        gesture_for_hud = gesture
                    elif gesture_for_hud == "IDLE":
                        gesture_for_hud = gesture

                    # Check for system pause toggle (open palm held for 2 seconds)
                    toggled, held_dur = self.classifier.check_pause_toggle(gesture)
                    if toggled:
                        self._release_all_clicks()
                        self.filter.reset()
                        self.prev_scroll_y = None
                        self.last_hotkey_pressed = None
                        self.ripples.append({
                            "pos": (w // 2, h // 2),
                            "radius": 10,
                            "color": COLOR_NEON_GREEN if self.classifier.last_state == "ACTIVE" else COLOR_RED,
                            "max_radius": 150,
                            "thickness": 6
                        })

                    # Visual feedback for pause countdown
                    if gesture == "PAUSE_TRIGGER" and held_dur > 0.1:
                        pct = min(held_dur / 2.0, 1.0)
                        self._draw_countdown(frame, w, h, pct)

                    # If controller is active, perform system controls
                    if self.classifier.last_state == "ACTIVE":
                        # Dual Hand Role Routing:
                        # Mirrored "Left" hand is physical Right Hand (Absolute Cursor Tracking & Clicking)
                        if handedness == "Left":
                            self._execute_right_hand_actions(frame, landmarks, gesture, val, w, h)
                        # Mirrored "Right" hand is physical Left Hand (Scrolling, Volume, & Key Bindings)
                        elif handedness == "Right":
                            self._execute_left_hand_actions(frame, landmarks, gesture, val, w, h)
                    
                    # Render skeletal structure on hand with handedness label
                    self._draw_skeleton(frame, landmarks, handedness)
            else:
                # No hand detected: reset states, damp filters, and hotkeys
                self._release_all_clicks()
                self.filter.reset()
                self.prev_scroll_y = None
                self.classifier.open_palm_start_time = None
                self.last_hotkey_pressed = None

            # Render active ripples and animations
            self._draw_ripples(frame)

            # Render headers and status panels
            self._draw_hud_panels(frame, w, h, hand_found, gesture_for_hud)

            # Show frame
            cv2.imshow("Webcam Gesture Controller (HUD)", frame)

            # Exit criteria
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q') or key == ord('Q'):
                break

        # Release resources
        self._release_all_clicks()
        cap.release()
        cv2.destroyAllWindows()

    def _execute_right_hand_actions(self, frame, landmarks, gesture, val, w, h):
        """Map physical Right Hand (mirrored 'Left') to cursor movement, clicking, and double-clicking."""
        if gesture in ["CURSOR", "CLICK_LEFT", "CLICK_RIGHT"]:
            # Use Index Tip (landmark 8) for cursor positioning
            index_tip = landmarks[8]
            raw_x, raw_y = index_tip.x, index_tip.y

            # Clamp coordinates to Active Tracking Zone
            x_clamped = max(ACTIVE_ZONE_LEFT, min(ACTIVE_ZONE_RIGHT, raw_x))
            y_clamped = max(ACTIVE_ZONE_TOP, min(ACTIVE_ZONE_BOTTOM, raw_y))

            # Scale clamped values to 0.0 - 1.0 relative to active box size
            x_scaled = (x_clamped - ACTIVE_ZONE_LEFT) / (ACTIVE_ZONE_RIGHT - ACTIVE_ZONE_LEFT)
            y_scaled = (y_clamped - ACTIVE_ZONE_TOP) / (ACTIVE_ZONE_BOTTOM - ACTIVE_ZONE_TOP)

            # Scale to actual screen pixels
            screen_x = int(x_scaled * self.screen_width)
            screen_y = int(y_scaled * self.screen_height)

            # Apply MOUSE ACCELERATION
            if self.filter.prev_x is not None and self.filter.prev_y is not None:
                dx = screen_x - self.filter.prev_x
                dy = screen_y - self.filter.prev_y
                velocity = np.hypot(dx, dy)
                
                from config import ACCEL_SPEED_MIN, ACCEL_SPEED_MAX, ACCEL_MIN_MULTIPLIER, ACCEL_MAX_MULTIPLIER
                
                # Dynamic sensitivity based on velocity
                if velocity <= ACCEL_SPEED_MIN:
                    accel_multiplier = ACCEL_MIN_MULTIPLIER
                elif velocity >= ACCEL_SPEED_MAX:
                    accel_multiplier = ACCEL_MAX_MULTIPLIER
                else:
                    ratio = (velocity - ACCEL_SPEED_MIN) / (ACCEL_SPEED_MAX - ACCEL_SPEED_MIN)
                    accel_multiplier = ACCEL_MIN_MULTIPLIER + (ACCEL_MAX_MULTIPLIER - ACCEL_MIN_MULTIPLIER) * ratio
                
                # Apply acceleration scale to raw coordinate displacements
                screen_x = int(self.filter.prev_x + dx * accel_multiplier * self.sensitivity)
                screen_y = int(self.filter.prev_y + dy * accel_multiplier * self.sensitivity)

            # Smooth cursor position using adaptive EMA filter
            smooth_x, smooth_y = self.filter.filter(screen_x, screen_y)

            # Move OS mouse cursor
            try:
                pyautogui.moveTo(smooth_x, smooth_y, duration=0)
            except Exception:
                pass

            # Render tracking crosshair in active camera view
            cam_x = int(x_clamped * w)
            cam_y = int(y_clamped * h)
            self._draw_crosshair(frame, cam_x, cam_y, gesture)

        # Left Click State Machine with DOUBLE-CLICK timing engine
        if gesture == "CLICK_LEFT":
            if not self.left_pressed:
                from config import DOUBLE_CLICK_WINDOW
                curr_time = time.time()
                # If double click timing matches, trigger double click natively
                if curr_time - self.last_left_click_time < DOUBLE_CLICK_WINDOW:
                    try:
                        pyautogui.doubleClick()
                    except Exception:
                        pass
                    self.last_left_click_time = 0.0  # Reset
                else:
                    try:
                        pyautogui.mouseDown()
                    except Exception:
                        pass
                    self.last_left_click_time = curr_time
                self.left_pressed = True
                
                idx_cam_x = int(landmarks[8].x * w)
                idx_cam_y = int(landmarks[8].y * h)
                self.ripples.append({
                    "pos": (idx_cam_x, idx_cam_y),
                    "radius": 5,
                    "color": COLOR_CYAN,
                    "max_radius": 50,
                    "thickness": 3
                })
        else:
            if self.left_pressed:
                try:
                    pyautogui.mouseUp()
                except Exception:
                    pass
                self.left_pressed = False

        # Right Click State Machine
        if gesture == "CLICK_RIGHT":
            if not self.right_pressed:
                try:
                    pyautogui.rightClick()
                except Exception:
                    pass
                self.right_pressed = True
                
                mid_cam_x = int(landmarks[12].x * w)
                mid_cam_y = int(landmarks[12].y * h)
                self.ripples.append({
                    "pos": (mid_cam_x, mid_cam_y),
                    "radius": 5,
                    "color": COLOR_MAGENTA,
                    "max_radius": 60,
                    "thickness": 4
                })
        else:
            self.right_pressed = False

    def _execute_left_hand_actions(self, frame, landmarks, gesture, val, w, h):
        """Map physical Left Hand (mirrored 'Right') to scrolling, volume, and media keyboard hotkeys."""
        
        # 1. SCROLL MODE
        if gesture == "SCROLL":
            avg_y = (landmarks[8].y + landmarks[12].y) / 2.0
            if self.prev_scroll_y is not None:
                dy = avg_y - self.prev_scroll_y
                if abs(dy) > 0.007:
                    scroll_amount = int(-dy * 5000 * self.sensitivity)
                    if scroll_amount != 0:
                        try:
                            pyautogui.scroll(scroll_amount)
                        except Exception:
                            pass
            self.prev_scroll_y = avg_y
            sc_x = int(landmarks[8].x * w)
            sc_y = int(avg_y * h)
            self._draw_scroll_arrows(frame, sc_x, sc_y)
        else:
            self.prev_scroll_y = None

        # 2. VOLUME CONTROL MODE
        if gesture == "VOLUME" and self.volume_control:
            pinch_dist = val
            min_val, max_val = 0.15, 0.65
            normalized = max(0.0, min(1.0, (pinch_dist - min_val) / (max_val - min_val)))
            try:
                self.volume_control.SetMasterVolumeLevelScalar(normalized, None)
            except Exception:
                pass
            vol_pct = int(normalized * 100)
            self._draw_volume_panel(frame, w, h, vol_pct, landmarks)

        # 3. KEYBOARD HOTKEYS & BINDINGS (Fist, Thumbs Up, OK Sign)
        from config import HOTKEY_COOLDOWN
        current_time = time.time()
        
        if gesture in ["KEY_FIST", "KEY_THUMBS_UP", "KEY_OK"]:
            # Check cooldown and ensure it is a new gesture (rising edge) to prevent repeating
            if (current_time - self.last_hotkey_time > HOTKEY_COOLDOWN) and (self.last_hotkey_pressed != gesture):
                if gesture == "KEY_FIST":
                    try:
                        pyautogui.press("playpause")
                        print("[OS Hotkey] Play/Pause media triggered")
                    except Exception:
                        pass
                elif gesture == "KEY_THUMBS_UP":
                    try:
                        pyautogui.press("volumemute")
                        print("[OS Hotkey] Volume Mute toggled")
                    except Exception:
                        pass
                elif gesture == "KEY_OK":
                    try:
                        pyautogui.hotkey("win", "d")
                        print("[OS Hotkey] Show Desktop triggered")
                    except Exception:
                        pass
                
                self.last_hotkey_time = current_time
                self.last_hotkey_pressed = gesture
                
                # Draw high-contrast trigger ring at the wrist
                self.ripples.append({
                    "pos": (int(landmarks[0].x * w), int(landmarks[0].y * h)),
                    "radius": 15,
                    "color": COLOR_MAGENTA if gesture == "KEY_OK" else COLOR_NEON_GREEN,
                    "max_radius": 90,
                    "thickness": 5
                })
        else:
            self.last_hotkey_pressed = None

    def _release_all_clicks(self):
        """Release mouse buttons safely to prevent locking the OS interface."""
        if self.left_pressed:
            try:
                pyautogui.mouseUp()
            except Exception:
                pass
            self.left_pressed = False
        self.right_pressed = False

    # ==========================================
    # HUD Drawing Functions (BGR Color Space)
    # ==========================================
    def _draw_hud_base(self, frame, w, h):
        """Draws the core neon active region bounding frame and corner ticks."""
        # Top-left and Bottom-right coordinates of active zone
        x_min = int(ACTIVE_ZONE_LEFT * w)
        y_min = int(ACTIVE_ZONE_TOP * h)
        x_max = int(ACTIVE_ZONE_RIGHT * w)
        y_max = int(ACTIVE_ZONE_BOTTOM * h)

        # Draw a dim grid backing panel for the active zone
        overlay = frame.copy()
        cv2.rectangle(overlay, (x_min, y_min), (x_max, y_max), COLOR_DARK_GRAY, -1)
        cv2.addWeighted(overlay, 0.08, frame, 0.92, 0, frame)

        # Outer active boundary glow
        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), COLOR_DARK_GRAY, 1)

        # Draw glowing corners (Cyberpunk ticks)
        tick_len = 25
        # Top-Left Corner
        cv2.line(frame, (x_min, y_min), (x_min + tick_len, y_min), COLOR_CYAN, HUD_LINE_THICKNESS)
        cv2.line(frame, (x_min, y_min), (x_min, y_min + tick_len), COLOR_CYAN, HUD_LINE_THICKNESS)
        # Top-Right Corner
        cv2.line(frame, (x_max, y_min), (x_max - tick_len, y_min), COLOR_CYAN, HUD_LINE_THICKNESS)
        cv2.line(frame, (x_max, y_min), (x_max, y_min + tick_len), COLOR_CYAN, HUD_LINE_THICKNESS)
        # Bottom-Left Corner
        cv2.line(frame, (x_min, y_max), (x_min + tick_len, y_max), COLOR_CYAN, HUD_LINE_THICKNESS)
        cv2.line(frame, (x_min, y_max), (x_min, y_max - tick_len), COLOR_CYAN, HUD_LINE_THICKNESS)
        # Bottom-Right Corner
        cv2.line(frame, (x_max, y_max), (x_max - tick_len, y_max), COLOR_CYAN, HUD_LINE_THICKNESS)
        cv2.line(frame, (x_max, y_max), (x_max, y_max - tick_len), COLOR_CYAN, HUD_LINE_THICKNESS)

    def _draw_hud_panels(self, frame, w, h, hand_found, gesture):
        """Draws top system stats bar, active state labels, and performance metrics."""
        
        # 1. Top Panel Strip (Glassmorphic dark strip)
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 40), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Bottom Border for top strip
        cv2.line(frame, (0, 40), (w, 40), COLOR_DARK_GRAY, 1)

        # System Status
        status_text = "SYSTEM: ACTIVE" if self.classifier.last_state == "ACTIVE" else "SYSTEM: PAUSED"
        status_color = COLOR_NEON_GREEN if self.classifier.last_state == "ACTIVE" else COLOR_RED
        
        # Glow for status text
        cv2.putText(frame, status_text, (15, 26), FONT_HUD, 0.6, (0,0,0), 3, cv2.LINE_AA) # shadow
        cv2.putText(frame, status_text, (15, 26), FONT_HUD, 0.6, status_color, 1, cv2.LINE_AA)

        # Mode Indicator
        if self.classifier.last_state == "ACTIVE":
            mode_text = f"MODE: {gesture}" if hand_found else "SEARCHING FOR HAND..."
            mode_color = COLOR_CYAN if hand_found else COLOR_WHITE
        else:
            mode_text = "PAUSED (HOLD PALM TO RESUME)"
            mode_color = COLOR_RED

        cv2.putText(frame, mode_text, (200, 26), FONT_HUD, 0.55, mode_color, 1, cv2.LINE_AA)

        # FPS indicator
        fps_text = f"FPS: {int(self.fps)}"
        cv2.putText(frame, fps_text, (w - 90, 26), FONT_HUD, 0.55, COLOR_NEON_GREEN, 1, cv2.LINE_AA)

        # 2. Bottom Help Strip
        overlay_bottom = frame.copy()
        cv2.rectangle(overlay_bottom, (0, h - 30), (w, h), (15, 15, 15), -1)
        cv2.addWeighted(overlay_bottom, 0.8, frame, 0.2, 0, frame)
        cv2.line(frame, (0, h - 30), (w, h - 30), COLOR_DARK_GRAY, 1)
        
        help_text = "[ESC/Q] Close Window | [Pinch-Hold] Drag-and-Drop | [Open Palm] Lock/Unlock"
        cv2.putText(frame, help_text, (20, h - 10), FONT_HUD, 0.4, COLOR_WHITE, 1, cv2.LINE_AA)

    def _draw_skeleton(self, frame, landmarks, handedness=None):
        """Draws a premium styled cyan neon hand skeleton overlay with glowing joints."""
        h, w, _ = frame.shape
        
        # Define connection indices for hand skeleton
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),      # Thumb
            (0, 5), (5, 6), (6, 7), (7, 8),      # Index
            (9, 10), (10, 11), (11, 12),         # Middle (MCP is connected via palm)
            (13, 14), (14, 15), (15, 16),        # Ring
            (0, 17), (17, 18), (18, 19), (19, 20),# Pinky
            (5, 9), (9, 13), (13, 17)            # Palm knuckles
        ]

        # Draw bone connections
        for start_idx, end_idx in connections:
            pt1 = (int(landmarks[start_idx].x * w), int(landmarks[start_idx].y * h))
            pt2 = (int(landmarks[end_idx].x * w), int(landmarks[end_idx].y * h))
            
            # Subtle glow line underneath bone
            cv2.line(frame, pt1, pt2, COLOR_CYAN, 3)
            # Bone line
            cv2.line(frame, pt1, pt2, COLOR_WHITE, 1)

        # Draw glowing node joints
        for i in range(21):
            cx, cy = int(landmarks[i].x * w), int(landmarks[i].y * h)
            # Differentiate tips
            if i in [4, 8, 12, 16, 20]:
                cv2.circle(frame, (cx, cy), 6, COLOR_MAGENTA, -1)
                cv2.circle(frame, (cx, cy), 8, COLOR_WHITE, 1)
            else:
                cv2.circle(frame, (cx, cy), 4, COLOR_CYAN, -1)
                cv2.circle(frame, (cx, cy), 5, COLOR_WHITE, 1)

        # Draw physical hand label near wrist
        if handedness:
            hand_label = "RIGHT HAND" if handedness == "Left" else "LEFT HAND"
            label_color = COLOR_CYAN if handedness == "Left" else COLOR_MAGENTA
            wx = int(landmarks[0].x * w)
            wy = int(landmarks[0].y * h) + 20
            cv2.putText(frame, hand_label, (wx - 35, wy), FONT_HUD, 0.4, label_color, 1, cv2.LINE_AA)

    def _draw_crosshair(self, frame, cx, cy, gesture):
        """Draws a cybernetic crosshair HUD at the active finger tracking position."""
        size = 12
        color = COLOR_MAGENTA if gesture == "CLICK_LEFT" else COLOR_CYAN
        
        # Glow backer
        cv2.circle(frame, (cx, cy), size, color, HUD_GLOW_THICKNESS)
        cv2.circle(frame, (cx, cy), size, COLOR_WHITE, 1)

        # Center dot
        cv2.circle(frame, (cx, cy), 2, COLOR_WHITE, -1)

        # Dynamic crosshair ticks
        cv2.line(frame, (cx - size - 5, cy), (cx - size, cy), COLOR_WHITE, 1)
        cv2.line(frame, (cx + size, cy), (cx + size + 5, cy), COLOR_WHITE, 1)
        cv2.line(frame, (cx, cy - size - 5), (cx, cy - size), COLOR_WHITE, 1)
        cv2.line(frame, (cx, cy + size), (cx, cy + size + 5), COLOR_WHITE, 1)

    def _draw_scroll_arrows(self, frame, cx, cy):
        """Draws vertical double arrows indicating page scroll mode is active."""
        size = 15
        # Up Arrow
        cv2.line(frame, (cx, cy - size), (cx, cy + size), COLOR_NEON_GREEN, 2)
        cv2.line(frame, (cx - 6, cy - size + 6), (cx, cy - size), COLOR_NEON_GREEN, 2)
        cv2.line(frame, (cx + 6, cy - size + 6), (cx, cy - size), COLOR_NEON_GREEN, 2)
        # Down Arrow
        cv2.line(frame, (cx - 6, cy + size - 6), (cx, cy + size), COLOR_NEON_GREEN, 2)
        cv2.line(frame, (cx + 6, cy + size - 6), (cx, cy + size), COLOR_NEON_GREEN, 2)

    def _draw_volume_panel(self, frame, w, h, percentage, landmarks):
        """Renders an interactive vertical neon-pink HUD panel showing system volume percentage."""
        # Top-right vertical overlay bar coordinates
        bar_x = w - 45
        bar_y_start = 80
        bar_y_end = h - 80
        bar_height = bar_y_end - bar_y_start

        # Draw structural panel boundary (semi-transparent backup panel)
        overlay = frame.copy()
        cv2.rectangle(overlay, (bar_x - 10, bar_y_start - 10), (bar_x + 25, bar_y_end + 10), COLOR_DARK_GRAY, -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # Draw panel outline
        cv2.rectangle(frame, (bar_x - 10, bar_y_start - 10), (bar_x + 25, bar_y_end + 10), COLOR_CYAN, 1)

        # Draw empty bar background
        cv2.rectangle(frame, (bar_x, bar_y_start), (bar_x + 15, bar_y_end), COLOR_DARK_GRAY, -1)

        # Draw filled volume progress based on percentage
        fill_height = int((percentage / 100.0) * bar_height)
        fill_y = bar_y_end - fill_height
        cv2.rectangle(frame, (bar_x, fill_y), (bar_x + 15, bar_y_end), COLOR_MAGENTA, -1)
        cv2.rectangle(frame, (bar_x, fill_y), (bar_x + 15, bar_y_end), COLOR_WHITE, 1)

        # Draw HUD Percentage Indicator Text
        pct_text = f"{percentage}%"
        cv2.putText(frame, pct_text, (bar_x - 5, bar_y_start - 20), FONT_HUD, 0.45, COLOR_WHITE, 1, cv2.LINE_AA)
        cv2.putText(frame, "VOL", (bar_x - 5, bar_y_end + 25), FONT_HUD, 0.45, COLOR_MAGENTA, 1, cv2.LINE_AA)

        # Draw linking guide line between Thumb tip (4) and Index tip (8)
        idx_pt = (int(landmarks[8].x * w), int(landmarks[8].y * h))
        tmb_pt = (int(landmarks[4].x * w), int(landmarks[4].y * h))
        cv2.line(frame, idx_pt, tmb_pt, COLOR_MAGENTA, 2)
        cv2.circle(frame, idx_pt, 6, COLOR_WHITE, -1)
        cv2.circle(frame, tmb_pt, 6, COLOR_WHITE, -1)

    def _draw_countdown(self, frame, w, h, progress_pct):
        """Draws a futuristic countdown timer circle in the center of the HUD."""
        cx, cy = w // 2, h // 2
        radius = 45
        
        # Background glass panel
        overlay = frame.copy()
        cv2.circle(overlay, (cx, cy), radius + 15, (10, 10, 10), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        # Static outer ring
        cv2.circle(frame, (cx, cy), radius, COLOR_DARK_GRAY, 2)

        # Filled progress arc representing pause trigger hold time
        axes = (radius, radius)
        angle = 0
        startAngle = -90
        endAngle = -90 + int(progress_pct * 360)
        
        cv2.ellipse(frame, (cx, cy), axes, angle, startAngle, endAngle, COLOR_NEON_GREEN if self.classifier.last_state == "PAUSED" else COLOR_RED, 4)

        # Center lock/unlock icon character or text
        action_text = "LOCK" if self.classifier.last_state == "ACTIVE" else "UNLK"
        action_color = COLOR_RED if self.classifier.last_state == "ACTIVE" else COLOR_NEON_GREEN
        cv2.putText(frame, action_text, (cx - 16, cy + 5), FONT_HUD, 0.45, action_color, 1, cv2.LINE_AA)

    def _draw_ripples(self, frame):
        """Iterates over active clicks, expanding their size and fading their alpha."""
        active_ripples = []
        for rip in self.ripples:
            rip["radius"] += 4
            # Compute alpha/thickness fade
            pct = 1.0 - (rip["radius"] / rip["max_radius"])
            if pct > 0:
                thickness = max(1, int(rip["thickness"] * pct))
                cv2.circle(frame, rip["pos"], rip["radius"], rip["color"], thickness)
                active_ripples.append(rip)
        self.ripples = active_ripples
