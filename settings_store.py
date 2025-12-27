import json
import os

class SettingsStore:
    def __init__(self, file_path='settings.json'):
        self.file_path = file_path
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return {}
        return {}

    def get_user_settings(self, user_id):
        uid = str(user_id)
        if uid not in self.data:
            self.data[uid] = {
                'filters': {'brightness': 0.05, 'contrast': 0.0, 'saturation': 0.0, 'zoom': 0.0, 'speed': 0.0},
                'copies_count': 1, 'batch_size': 1, 'current_batch_count': 0
            }
        return self.data[uid]

    def save_user_settings(self, user_id, settings):
        self.data[str(user_id)] = settings
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def update_filter(self, user_id, param, value):
        settings = self.get_user_settings(user_id)
        settings['filters'][param] = value
        self.save_user_settings(user_id, settings)
