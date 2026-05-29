import numpy as np

class AdaptiveEMAFilter:
    """
    Adaptive Exponential Moving Average Filter.
    Dynamically scales the smoothing factor alpha based on velocity.
    - Slow movements are heavily smoothed to eliminate jitter for precise target selection.
    - Fast movements use minimal smoothing to prevent lag during rapid swipes.
    """
    def __init__(self, min_alpha=0.08, max_alpha=0.6, speed_threshold=40.0):
        self.min_alpha = min_alpha
        self.max_alpha = max_alpha
        self.speed_threshold = speed_threshold  # Pixel distance threshold for high speed
        self.prev_x = None
        self.prev_y = None

    def filter(self, raw_x, raw_y):
        if self.prev_x is None or self.prev_y is None:
            self.prev_x = raw_x
            self.prev_y = raw_y
            return raw_x, raw_y

        # Calculate distance (velocity proxy) from previous filtered point
        distance = np.hypot(raw_x - self.prev_x, raw_y - self.prev_y)

        # Scale alpha dynamically between min_alpha and max_alpha
        if distance >= self.speed_threshold:
            alpha = self.max_alpha
        else:
            # Linear interpolation between min and max alpha based on distance
            ratio = distance / self.speed_threshold
            alpha = self.min_alpha + (self.max_alpha - self.min_alpha) * ratio

        # Apply EMA formula: S_t = alpha * Y_t + (1 - alpha) * S_{t-1}
        filtered_x = alpha * raw_x + (1 - alpha) * self.prev_x
        filtered_y = alpha * raw_y + (1 - alpha) * self.prev_y

        self.prev_x = filtered_x
        self.prev_y = filtered_y

        return int(filtered_x), int(filtered_y)

    def reset(self):
        """Reset the filter state (e.g. when a hand is lost and re-detected)."""
        self.prev_x = None
        self.prev_y = None
