import os
import time
import threading
import logging

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

class ScreenshotHandler:
    def __init__(self, config, get_system_name_cb=None, log_callback=None, trace_callback=None):
        self.config = config
        self.get_system_name_cb = get_system_name_cb
        self.log_callback = log_callback
        self.trace_callback = trace_callback
        self.is_running = True
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False

    def worker(self):
        while self.is_running:
            if self.config.get("screenshots_enabled", False):
                if not PIL_AVAILABLE:
                    logging.error("Pillow library not found. Screenshot conversion disabled.")
                    time.sleep(60)
                    continue

                path = self.config.get("screenshots_path")
                if path and os.path.exists(path):
                    self.process_folder(path)
            
            time.sleep(2)

    def process_folder(self, folder_path):
        t0 = time.perf_counter()
        try:
            files = [f for f in os.listdir(folder_path) if f.lower().endswith(".bmp")]
            max_per_cycle = int(self.config.get("screenshot_max_convert_per_cycle", 2) or 2)
            if max_per_cycle < 1:
                max_per_cycle = 1
            converted = 0
            
            for filename in files:
                if not self.is_running: break
                if converted >= max_per_cycle:
                    break
                
                bmp_path = os.path.join(folder_path, filename)
                
                system_name = "Unknown"
                if self.get_system_name_cb:
                    system_name = self.get_system_name_cb()
                
                if system_name == "---": system_name = "Unknown"
                
                safe_sys_name = "".join([c for c in system_name if c.isalnum() or c in " -_()"]).strip()
                if not safe_sys_name: safe_sys_name = "Unknown"

                try:
                    mtime = os.path.getmtime(bmp_path)
                    ts_str = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(mtime))
                except:
                    ts_str = time.strftime("%Y-%m-%d_%H-%M-%S")

                new_filename = f"{safe_sys_name}_{ts_str}.png"
                
                # Handle duplicates
                counter = 1
                base_name = os.path.splitext(new_filename)[0]
                while os.path.exists(os.path.join(folder_path, new_filename)):
                    new_filename = f"{base_name}_{counter}.png"
                    counter += 1

                png_path = os.path.join(folder_path, new_filename)
                
                try:
                    # Check if file is locked or still writing by attempting to open
                    with Image.open(bmp_path) as img:
                        img.save(png_path, "PNG")
                    
                    if os.path.exists(png_path):
                        os.remove(bmp_path)
                        converted += 1
                        logging.info(f"📸 Converted screenshot: {filename} -> {new_filename}")
                        if self.log_callback:
                            self.log_callback(f"📸 SCREENSHOT SAVED: {new_filename}")
                        
                except (PermissionError, OSError):
                    # File likely locked by game or still writing
                    pass
                except Exception as e:
                    logging.error(f"Error converting {filename}: {e}")
                    
        except Exception as e:
            logging.error(f"Error scanning screenshot folder: {e}")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if callable(self.trace_callback):
            try:
                self.trace_callback("screenshot.process_folder", elapsed_ms)
            except Exception:
                pass
        if elapsed_ms >= 40.0:
            msg = f"PERF SPIKE [screenshot.process_folder] {elapsed_ms:.1f} ms"
            logging.warning(msg)
            if self.log_callback:
                self.log_callback(msg)
