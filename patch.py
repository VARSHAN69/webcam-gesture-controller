import sys
import ctypes

def apply_msvcrt_patch():
    """
    Monkeypatches ctypes.CDLL to resolve 'free' function lookup from msvcrt.dll on Windows.
    This resolves a known compatibility issue in MediaPipe under newer Python versions (3.12, 3.13, 3.14) 
    where the C++ runtime shared library does not explicitly export 'free', causing:
    'AttributeError: function 'free' not found'.
    """
    if sys.platform == 'win32':
        # Cache original __getattr__ lookup
        original_getattr = ctypes.CDLL.__getattr__

        def patched_getattr(self, name):
            try:
                return original_getattr(self, name)
            except AttributeError as e:
                # If 'free' is not found, redirect to Microsoft C Runtime Library
                if name == 'free':
                    try:
                        return ctypes.cdll.msvcrt.free
                    except Exception:
                        pass
                raise e

        # Apply the patch to ctypes.CDLL class dynamically
        ctypes.CDLL.__getattr__ = patched_getattr

# Run patch instantly on import
apply_msvcrt_patch()
