import patch
import sys
import argparse
from controller import GestureController, WINDOWS_VOLUME_SUPPORT

def main():
    parser = argparse.ArgumentParser(
        description="👁️ Webcam Gesture Controller (Computer Vision + System Orchestrator)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        "--camera", "-c",
        type=int,
        default=0,
        help="Index of the webcam to connect to (default: 0)."
    )
    
    parser.add_argument(
        "--sensitivity", "-s",
        type=float,
        default=1.0,
        help="Mouse sensitivity multiplier (default: 1.0)."
    )
    
    parser.add_argument(
        "--no-volume",
        action="store_true",
        help="Explicitly disable Windows PyCaw master volume binding."
    )
    
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("      👁️  WEBCAM GESTURE CONTROLLER (COMPUTER VISION) 👁️")
    print("=" * 60)
    print(f"  * Webcam Device Index    : {args.camera}")
    print(f"  * Speed/Sensitivity Multiplier : {args.sensitivity}x")
    print(f"  * Windows volume tracking: {'ENABLED' if WINDOWS_VOLUME_SUPPORT and not args.no_volume else 'DISABLED (Fallback)'}")
    print("=" * 60)

    try:
        # Create and run controller
        controller = GestureController(
            camera_idx=args.camera,
            sensitivity=args.sensitivity
        )
        
        # Override volume if explicitly disabled via flag
        if args.no_volume:
            controller.volume_control = None
            
        controller.run()
        
    except KeyboardInterrupt:
        print("\n[System] Keyboard interrupt detected. Shutting down gesture controller...")
    except Exception as e:
        print(f"\n[Fatal Error] Application encountered an unexpected failure: {e}", file=sys.stderr)
    finally:
        print("\n[System] Resources released cleanly. Goodbye!\n")

if __name__ == "__main__":
    main()
