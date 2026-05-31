import cv2

# ==========================================
# Camera & Frame Settings
# ==========================================
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
TARGET_FPS = 30

# ==========================================
# Screen Resolution & Active Tracking Zone
# ==========================================
# To make cursor control comfortable, only hands inside a central box 
# in the camera frame will map to the entire screen.
# Coordinates are normalized (0.0 to 1.0)
ACTIVE_ZONE_LEFT = 0.15
ACTIVE_ZONE_RIGHT = 0.85
ACTIVE_ZONE_TOP = 0.15
ACTIVE_ZONE_BOTTOM = 0.70

# ==========================================
# Cursor Smoothing & Performance
# ==========================================
# Exponential Moving Average smoothing factor. Smaller = smoother but slight lag.
# Larger = faster but potentially more jitter.
EMA_ALPHA = 0.22

# PyAutoGUI settings
MOUSE_DRAG_SPEED = 0.0  # Instantaneous movement to avoid queue build-up
PYAUTOGUI_PAUSE = 0.001  # Tiny pause to let OS process events

# ==========================================
# Gesture Thresholds & Timing (Scale-Invariant)
# ==========================================
# Distances will be normalized by palm length (distance between wrist [0] and middle finger MCP [9])
PINCH_CLICK_THRESHOLD = 0.22       # Distance between index tip (4) and thumb tip (8)
PINCH_RIGHT_CLICK_THRESHOLD = 0.22 # Distance between middle tip (4) and thumb tip (12)
PAUSE_GESTURE_TIME = 2.0           # Seconds of steady open hand to pause/resume controller
DOUBLE_CLICK_WINDOW = 0.35         # Seconds to detect rapid double pinches
HOTKEY_COOLDOWN = 1.2              # Cooldown period (seconds) for keyboard bindings

# Mouse Acceleration Curve Settings
ACCEL_SPEED_MIN = 3.0              # Speed threshold (pixels/frame) below which sensitivity is halved
ACCEL_SPEED_MAX = 28.0             # Speed threshold above which sensitivity is doubled
ACCEL_MIN_MULTIPLIER = 0.5         # Slow movement dampener for high-accuracy targeting
ACCEL_MAX_MULTIPLIER = 2.2         # Fast sweep multiplier for swift navigation

# ==========================================
# Neon UI Styling (BGR Color Space)
# ==========================================
# Pure neon colors for the premium HUD visual experience
COLOR_CYAN = (255, 243, 0)      # Cyan-blue glow
COLOR_NEON_GREEN = (50, 255, 0) # Electric neon green
COLOR_MAGENTA = (203, 0, 255)   # Hot pink / Magenta
COLOR_RED = (46, 46, 255)       # Cyberpunk red
COLOR_DARK_GRAY = (40, 40, 40)  # Clean panel backing
COLOR_WHITE = (255, 255, 255)

FONT_HUD = cv2.FONT_HERSHEY_SIMPLEX
HUD_LINE_THICKNESS = 2
HUD_GLOW_THICKNESS = 4
