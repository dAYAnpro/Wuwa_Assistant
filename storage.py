import json
import os
import hashlib
from datetime import datetime

class EchoStorage:
    def __init__(self, json_path="echoes.json"):
        self.json_path = json_path
        self.seen_hashes = set()
        self.echoes = []
        self._load_existing()

    def _generate_fingerprint(self, echo_data) -> str:
        """Create a unique MD5 hash for an echo to prevent duplicate entries."""
        parts = [
            echo_data.get("name", ""),
            str(echo_data.get("cost", "")),
            str(echo_data.get("level", "")),
            str(echo_data.get("sonata", ""))
        ]
        for m in echo_data.get("main_stats", []):
            if isinstance(m, dict):
                parts.append(f"{m.get('stat')}:{m.get('value')}")
            else:
                parts.append(str(m))
        # Sort substats so order doesn't affect hash
        sub_list = []
        for s in echo_data.get("sub_stats", []):
            if isinstance(s, dict):
                sub_list.append(f"{s.get('stat')}:{s.get('value')}")
            else:
                sub_list.append(str(s))
        parts.extend(sorted(sub_list))
        return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()

    def _load_existing(self):
        """Safely load existing JSON without crashing on empty or corrupted files."""
        self.seen_hashes.clear()
        self.echoes = []
        if os.path.exists(self.json_path) and os.path.getsize(self.json_path) > 0:
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    self.echoes = json.load(f)
                    for item in self.echoes:
                        fp = item.get("_fingerprint") or self._generate_fingerprint(item)
                        self.seen_hashes.add(fp)
            except Exception as e:
                print(f"[!] Warning: Could not read existing {self.json_path}: {e}")
                self.echoes = []

    def format_echo_record(self, echo_data) -> dict:
        """Format the parsed data into a clean, collision-free JSON object."""
        main_stats_dict = {}
        for m in echo_data.get("main_stats", []):
            if isinstance(m, dict):
                main_stats_dict[m["stat"]] = m["value"]

        sub_stats_dict = {}
        for s in echo_data.get("sub_stats", []):
            if isinstance(s, dict):
                sub_stats_dict[s["stat"]] = s["value"]

        record = {
            "id": len(self.echoes) + 1,
            "name": echo_data.get("name", "Unknown"),
            "cost": echo_data.get("cost", 0),
            "level": echo_data.get("level", 0),
            "sonata": echo_data.get("sonata", "Unknown"),
            "main_stats": main_stats_dict,
            "sub_stats": sub_stats_dict,
            "crit_value": {
                "substats_cv": echo_data.get("substats_cv", 0.0),
                "total_cv": echo_data.get("total_cv", 0.0)
            },
            "raw_values": {
                "main_stats": echo_data.get("main_stats", []),
                "sub_stats": echo_data.get("sub_stats", [])
            },
            "_fingerprint": self._generate_fingerprint(echo_data),
            "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return record

    def add_echo(self, echo_data, min_level=1) -> tuple[bool, str]:
        """
        Add echo to JSON file.
        Returns: (success: bool, status_reason: str)
          - (True, "saved")
          - (False, "level_skipped")
          - (False, "duplicate")
        """
        if echo_data.get("level", 0) < min_level:
            return False, "level_skipped"

        fp = self._generate_fingerprint(echo_data)
        if fp in self.seen_hashes:
            return False, "duplicate"

        self.seen_hashes.add(fp)
        record = self.format_echo_record(echo_data)
        self.echoes.append(record)

        # Atomic file write
        temp_file = f"{self.json_path}.tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.echoes, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, self.json_path)
        except Exception:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(self.echoes, f, indent=2, ensure_ascii=False)

        return True, "saved"

    def clear_all(self):
        """Reset storage and empty the JSON file."""
        self.seen_hashes.clear()
        self.echoes.clear()
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

    def count(self) -> int:
        return len(self.echoes)
