import numpy as np
import time

class GestureClassifier:
    def __init__(self):
        # Tracking state for the pause/resume toggle (steady open palm)
        self.open_palm_start_time = None
        self.last_state = "ACTIVE"  # Can be "ACTIVE" or "PAUSED"

    @staticmethod
    def get_distance(lm1, lm2):
        """Calculate the 3D Euclidean distance between two landmarks."""
        return np.sqrt((lm1.x - lm2.x)**2 + (lm1.y - lm2.y)**2 + (lm1.z - lm2.z)**2)

    @staticmethod
    def get_palm_scale(landmarks):
        """
        Get palm scale reference length.
        We use the distance between Wrist (0) and Middle Knuckle (9) as it is 
        anatomically stable and does not change when fingers bend.
        """
        return GestureClassifier.get_distance(landmarks[0], landmarks[9])

    def classify(self, landmarks, handedness, config):
        """
        Classifies the hand state into an active gesture.
        Returns:
            gesture_name (str): 'CURSOR', 'CLICK_LEFT', 'CLICK_RIGHT', 'SCROLL', 'VOLUME', 'PAUSE_TRIGGER', 'IDLE'
            normalized_value (float): Contextual value (e.g., pinch distance for volume or cursor speed)
        """
        # 1. Calculate Palm Scale
        palm_scale = self.get_palm_scale(landmarks)
        if palm_scale == 0:
            palm_scale = 0.001  # Prevent division by zero

        # 2. Identify finger states (True = open, False = closed)
        # For standard fingers, open if Tip Y is higher (smaller Y value) than PIP Y
        index_open = landmarks[8].y < landmarks[6].y
        middle_open = landmarks[12].y < landmarks[10].y
        ring_open = landmarks[16].y < landmarks[14].y
        pinky_open = landmarks[20].y < landmarks[18].y

        # For the thumb, it moves horizontally.
        # We compare Thumb Tip (4) horizontal position relative to Thumb IP Knuckle (3).
        # We also check the handedness to determine left/right direction.
        is_right_hand = handedness == "Right"
        if is_right_hand:
            # Right hand palm facing camera: Thumb tip is to the left (smaller X) when open
            thumb_open = landmarks[4].x < landmarks[2].x
        else:
            # Left hand palm facing camera: Thumb tip is to the right (larger X) when open
            thumb_open = landmarks[4].x > landmarks[2].x

        # Calculate normalized pinch distances
        thumb_index_dist = self.get_distance(landmarks[4], landmarks[8]) / palm_scale
        thumb_middle_dist = self.get_distance(landmarks[4], landmarks[12]) / palm_scale

        # ==========================================
        # GESTURE 1: Pause / Resume Toggle (Fully Open Palm)
        # ==========================================
        if index_open and middle_open and ring_open and pinky_open and thumb_open:
            # Check if thumb is sufficiently separated from palm to avoid false positive
            thumb_palm_dist = self.get_distance(landmarks[4], landmarks[5]) / palm_scale
            if thumb_palm_dist > 0.4:
                return "PAUSE_TRIGGER", thumb_palm_dist

        # Reset open palm timer if not in fully open state
        self.open_palm_start_time = None

        # ==========================================
        # GESTURE 1.5: Media Key Shortcuts (OK, Fist, Thumbs Up)
        # ==========================================
        # OK Gesture: Index pinches Thumb, but Middle, Ring, and Pinky are fully OPEN.
        if middle_open and ring_open and pinky_open and thumb_index_dist < config.PINCH_CLICK_THRESHOLD:
            return "KEY_OK", thumb_index_dist

        # Fist Gesture: All fingers closed, including thumb.
        if not index_open and not middle_open and not ring_open and not pinky_open and not thumb_open:
            return "KEY_FIST", 0.0

        # Thumbs Up Gesture: Only thumb is open, and is pointing upwards (tip Y < base CMC Y).
        if thumb_open and not index_open and not middle_open and not ring_open and not pinky_open:
            if landmarks[4].y < landmarks[2].y:
                return "KEY_THUMBS_UP", 0.0

        # ==========================================
        # GESTURE 2: Volume Control Mode
        # ==========================================
        # Gesture: Thumb and Index finger are open/extended, while Middle, Ring, Pinky are closed.
        if thumb_open and index_open and not middle_open and not ring_open and not pinky_open:
            # Volume corresponds to the pinch distance between thumb and index tips
            return "VOLUME", thumb_index_dist

        # ==========================================
        # GESTURE 3: Scroll Mode
        # ==========================================
        # Gesture: Index and Middle finger are open and close together, other fingers closed.
        if index_open and middle_open and not ring_open and not pinky_open:
            index_middle_dist = self.get_distance(landmarks[8], landmarks[12]) / palm_scale
            if index_middle_dist < 0.4:  # Fingers are close together
                return "SCROLL", index_middle_dist

        # ==========================================
        # GESTURE 4: Mouse Cursor Control & Clicks
        # ==========================================
        # Gesture: Index finger is open, Ring and Pinky are closed.
        # Middle finger is closed (otherwise it's Scroll mode).
        if index_open and not ring_open and not pinky_open:
            # Check for Left Click: Index tip pinches Thumb tip
            if thumb_index_dist < config.PINCH_CLICK_THRESHOLD:
                return "CLICK_LEFT", thumb_index_dist
            
            # Check for Right Click: Middle tip pinches Thumb tip 
            # (even if middle is slightly uncurling for the pinch)
            if thumb_middle_dist < config.PINCH_RIGHT_CLICK_THRESHOLD:
                return "CLICK_RIGHT", thumb_middle_dist

            # Just cursor movement
            if not middle_open:
                return "CURSOR", thumb_index_dist

        # Default fallback
        return "IDLE", 0.0

    def check_pause_toggle(self, gesture, elapsed_time_fn=time.time):
        """
        Manages the timing logic to toggle between ACTIVE and PAUSED.
        Requires holding an open palm for `PAUSE_GESTURE_TIME` seconds.
        """
        if gesture == "PAUSE_TRIGGER":
            if self.open_palm_start_time is None:
                self.open_palm_start_time = elapsed_time_fn()
                return False, 0.0  # Just started holding
            
            held_duration = elapsed_time_fn() - self.open_palm_start_time
            if held_duration >= 2.0:  # 2 seconds hold
                # Toggle state
                self.last_state = "PAUSED" if self.last_state == "ACTIVE" else "ACTIVE"
                self.open_palm_start_time = None  # Reset after toggle
                return True, held_duration
            return False, held_duration
        else:
            self.open_palm_start_time = None
            return False, 0.0
