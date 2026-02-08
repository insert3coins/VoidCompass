import time
import os
import keyboard

FILE = os.path.join(os.path.dirname(__file__), "oracle_waiting.txt")
DELAY_BETWEEN_LINES = 45   # seconds
CHAT_KEY = "2"            # Elite chat open key
STOP_KEY = "esc"          # emergency stop

def load_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def main():
    lines = load_lines(FILE)
    print(f"Loaded {len(lines)} oracle lines.")
    print("Switch to Elite Dangerous.")
    print("Press F8 to start. Press ESC to stop.")

    keyboard.wait("F8")

    for i, line in enumerate(lines, 1):
        if keyboard.is_pressed(STOP_KEY): break

        keyboard.press(CHAT_KEY)
        time.sleep(0.15)
        keyboard.release(CHAT_KEY)
        time.sleep(0.5)             # Wait for chat UI to open
        
        # Type the message instead of pasting (more reliable in games)
        # Prepend '/system ' to force the message to the System channel
        keyboard.write("/system " + line, delay=0.05)
        time.sleep(0.2)
        
        keyboard.press("enter")
        time.sleep(0.15)
        keyboard.release("enter")
        time.sleep(0.5)
        keyboard.press(CHAT_KEY)
        time.sleep(0.15)
        keyboard.release(CHAT_KEY)

        print(f"Sent {i}/{len(lines)}")
        
        # Sleep with interrupt check
        start = time.time()
        while time.time() - start < DELAY_BETWEEN_LINES:
            if keyboard.is_pressed(STOP_KEY):
                print("Broadcast stopped.")
                return
            time.sleep(0.1)

if __name__ == "__main__":
    main()
