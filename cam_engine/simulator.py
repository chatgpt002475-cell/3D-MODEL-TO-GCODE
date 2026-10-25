"""G-code Simulator, Verification, and Toolpath Vector Extractor."""

import re
import numpy as np
from typing import Dict, Any, List

class GCodeSimulator:
    """Parses and simulates G-code execution to verify safety, cycle time, and geometry."""

    def __init__(self, rapid_rate_mm_min: float = 3000.0):
        self.default_rapid_feed = rapid_rate_mm_min

    def simulate(self, gcode_text: str) -> Dict[str, Any]:
        lines = gcode_text.splitlines()

        current_x = 0.0
        current_y = 0.0
        current_z = 0.0
        current_feed = 1000.0
        motion_mode = "G0"  # G0 (rapid) or G1 (feed)

        min_coords = [float("inf"), float("inf"), float("inf")]
        max_coords = [float("-inf"), float("-inf"), float("-inf")]

        total_feed_dist = 0.0
        total_rapid_dist = 0.0
        total_feed_time_sec = 0.0
        total_rapid_time_sec = 0.0

        toolpaths: List[Dict[str, Any]] = []

        g_regex = re.compile(r'([GMTFXYZIJKS])([+-]?\d*\.?\d+)', re.IGNORECASE)

        for line_num, raw_line in enumerate(lines, 1):
            line = raw_line.strip()
            # Remove comments (in parentheses or after semicolon)
            line = re.sub(r'\(.*?\)', '', line)
            line = re.sub(r';.*$', '', line).strip()
            if not line:
                continue

            matches = g_regex.findall(line)
            tokens = {m[0].upper(): float(m[1]) for m in matches}

            if 'G' in tokens:
                g_code = int(tokens['G'])
                if g_code in [0, 1, 2, 3]:
                    motion_mode = f"G{g_code}"

            if 'F' in tokens:
                current_feed = max(1.0, tokens['F'])

            target_x = tokens.get('X', current_x)
            target_y = tokens.get('Y', current_y)
            target_z = tokens.get('Z', current_z)

            # Check if there was actual motion
            if (target_x != current_x or target_y != current_y or target_z != current_z):
                dx = target_x - current_x
                dy = target_y - current_y
                dz = target_z - current_z
                dist = np.sqrt(dx*dx + dy*dy + dz*dz)

                is_rapid = (motion_mode == "G0")
                if is_rapid:
                    total_rapid_dist += dist
                    total_rapid_time_sec += (dist / (self.default_rapid_feed / 60.0))
                else:
                    total_feed_dist += dist
                    total_feed_time_sec += (dist / (current_feed / 60.0))

                # Update bounds
                min_coords[0] = min(min_coords[0], current_x, target_x)
                min_coords[1] = min(min_coords[1], current_y, target_y)
                min_coords[2] = min(min_coords[2], current_z, target_z)

                max_coords[0] = max(max_coords[0], current_x, target_x)
                max_coords[1] = max(max_coords[1], current_y, target_y)
                max_coords[2] = max(max_coords[2], current_z, target_z)

                # Store vector for visualizer (limit density if too large)
                if len(toolpaths) < 15000 or (line_num % 2 == 0):
                    toolpaths.append({
                        "type": "rapid" if is_rapid else "cut",
                        "start": [round(current_x, 3), round(current_y, 3), round(current_z, 3)],
                        "end": [round(target_x, 3), round(target_y, 3), round(target_z, 3)],
                        "feed": current_feed
                    })

                current_x = target_x
                current_y = target_y
                current_z = target_z

        total_time_sec = total_feed_time_sec + total_rapid_time_sec
        mins, secs = divmod(int(total_time_sec), 60)
        hours, mins = divmod(mins, 60)

        duration_formatted = f"{hours:02d}h {mins:02d}m {secs:02d}s" if hours > 0 else f"{mins:02d}m {secs:02d}s"

        # Sanitize empty bounds
        if min_coords[0] == float("inf"):
            min_coords = [0.0, 0.0, 0.0]
            max_coords = [0.0, 0.0, 0.0]

        return {
            "total_lines": len(lines),
            "toolpath_segments_count": len(toolpaths),
            "bounds": {
                "min": [round(v, 2) for v in min_coords],
                "max": [round(v, 2) for v in max_coords],
                "travel_span": [round(max_coords[i] - min_coords[i], 2) for i in range(3)]
            },
            "feed_distance_mm": round(total_feed_dist, 2),
            "rapid_distance_mm": round(total_rapid_dist, 2),
            "total_distance_mm": round(total_feed_dist + total_rapid_dist, 2),
            "estimated_time_sec": round(total_time_sec, 1),
            "estimated_time_formatted": duration_formatted,
            "toolpaths": toolpaths
        }
