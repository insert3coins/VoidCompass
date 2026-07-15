import json
import os
import math

WAYPOINTS_FILE = "waypoints.json"

class WaypointManager:
    def __init__(self, path=None):
        self.path = path or WAYPOINTS_FILE
        self.waypoints = []
        self.last_error = None
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.waypoints = [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
                self.last_error = None
            except Exception as exc:
                self.last_error = str(exc)
                self.waypoints = []

    def save(self):
        temp_path = self.path + '.tmp'
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.waypoints, f, indent=4)
            os.replace(temp_path, self.path)
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = str(exc)
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
            return False

    def add_waypoint(self, name, coords=None, note=None):
        self.waypoints.append({"name": name, "coords": coords, "note": note})
        self.save()

    def remove_waypoint(self, index):
        if 0 <= index < len(self.waypoints):
            del self.waypoints[index]
            self.save()

    def remove_waypoints(self, indices):
        valid = set()
        for index in indices:
            try:
                index = int(index)
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(self.waypoints):
                valid.add(index)
        valid = sorted(valid, reverse=True)
        for index in valid:
            del self.waypoints[index]
        if valid:
            self.save()
        return len(valid)
    
    def clear(self):
        self.waypoints = []
        self.save()

    def move_up(self, index):
        if index > 0:
            self.waypoints[index], self.waypoints[index-1] = self.waypoints[index-1], self.waypoints[index]
            self.save()
            return True
        return False

    def move_down(self, index):
        if index < len(self.waypoints) - 1:
            self.waypoints[index], self.waypoints[index+1] = self.waypoints[index+1], self.waypoints[index]
            self.save()
            return True
        return False

    def update_coords(self, index, coords):
        if 0 <= index < len(self.waypoints):
            self.waypoints[index]['coords'] = coords
            self.save()
            return True
        return False

    def edit_waypoint(self, index, name, coords=None, note=None):
        if 0 <= index < len(self.waypoints):
            updated = dict(self.waypoints[index])
            updated.update({"name": name, "coords": coords, "note": note})
            self.waypoints[index] = updated
            self.save()
            return True
        return False
            
    def get_distance(self, c1, c2):
        """Calculates distance between two coordinate dicts or lists."""
        # Normalize to dicts if lists are passed
        if isinstance(c1, list) and len(c1) == 3:
            c1 = {'x': c1[0], 'y': c1[1], 'z': c1[2]}
        if isinstance(c2, list) and len(c2) == 3:
            c2 = {'x': c2[0], 'y': c2[1], 'z': c2[2]}

        if c1 and c2:
            return math.sqrt((c1['x']-c2['x'])**2 + (c1['y']-c2['y'])**2 + (c1['z']-c2['z'])**2)
        return 0.0

    def get_next_waypoint(self, current_name):
        current_name = str(current_name or "")
        for i, wp in enumerate(self.waypoints):
            if str(wp.get('name') or '').lower() == current_name.lower():
                for candidate in self.waypoints[i + 1:]:
                    if not candidate.get('visited', False) and candidate.get('name'):
                        return candidate['name']
                return None
        for wp in self.waypoints:
            if not wp.get('visited', False) and wp.get('name'):
                return wp['name']
        return None

    def get_waypoint_index(self, name):
        name = str(name or "")
        for i, wp in enumerate(self.waypoints):
            if str(wp.get('name') or '').lower() == name.lower():
                return i
        return -1
