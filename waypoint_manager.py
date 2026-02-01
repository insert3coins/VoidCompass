import json
import os
import math

WAYPOINTS_FILE = "waypoints.json"

class WaypointManager:
    def __init__(self):
        self.waypoints = []
        self.load()

    def load(self):
        if os.path.exists(WAYPOINTS_FILE):
            try:
                with open(WAYPOINTS_FILE, 'r') as f:
                    self.waypoints = json.load(f)
            except:
                self.waypoints = []

    def save(self):
        try:
            with open(WAYPOINTS_FILE, 'w') as f:
                json.dump(self.waypoints, f, indent=4)
        except:
            pass

    def add_waypoint(self, name, coords=None, note=None):
        self.waypoints.append({"name": name, "coords": coords, "note": note})
        self.save()

    def remove_waypoint(self, index):
        if 0 <= index < len(self.waypoints):
            del self.waypoints[index]
            self.save()
    
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
            self.waypoints[index] = {"name": name, "coords": coords, "note": note}
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
        for i, wp in enumerate(self.waypoints):
            if wp['name'].lower() == current_name.lower():
                if i + 1 < len(self.waypoints):
                    return self.waypoints[i+1]['name']
        return None

    def get_waypoint_index(self, name):
        for i, wp in enumerate(self.waypoints):
            if wp['name'].lower() == name.lower():
                return i
        return -1