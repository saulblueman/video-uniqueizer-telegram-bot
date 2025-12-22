"""
Хранилище пользовательских настроек фильтров
Поддерживает два режима: in-memory и JSON
"""

import json
import os
from filters_manager import VideoFilters


class SettingsStore:
    """Хранилище настроек пользователей"""
    
    def __init__(self, storage_type='json', json_file='user_settings.json'):
        """
        storage_type: 'memory' или 'json'
        json_file: путь к JSON файлу для хранения
        """
        self.storage_type = storage_type
        self.json_file = json_file
        self.memory_storage = {}  # Для in-memory режима
        
        # Если JSON режим, загрузить данные из файла
        if self.storage_type == 'json':
            self._load_from_json()
    
    def _load_from_json(self):
        """Загрузить данные из JSON файла"""
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Конвертируем в VideoFilters объекты
                    for user_id, settings_dict in data.items():
                        self.memory_storage[int(user_id)] = VideoFilters.from_dict(settings_dict)
            except Exception as e:
                print(f"Ошибка загрузки настроек из JSON: {e}")
                self.memory_storage = {}
    
    def _save_to_json(self):
        """Сохранить данные в JSON файл"""
        if self.storage_type == 'json':
            try:
                # Конвертируем VideoFilters объекты в словари
                data = {
                    str(user_id): filters.to_dict()
                    for user_id, filters in self.memory_storage.items()
                }
                with open(self.json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Ошибка сохранения настроек в JSON: {e}")
    
    def get_filters(self, user_id):
        """
        Получить фильтры для пользователя.
        Если не существуют — создать новые с дефолтными значениями.
        """
        if user_id not in self.memory_storage:
            self.memory_storage[user_id] = VideoFilters()
            if self.storage_type == 'json':
                self._save_to_json()
        return self.memory_storage[user_id]
    
    def save_filters(self, user_id, filters):
        """Сохранить фильтры пользователя"""
        self.memory_storage[user_id] = filters
        if self.storage_type == 'json':
            self._save_to_json()
    
    def reset_filters(self, user_id):
        """Сбросить фильтры пользователя к дефолтным"""
        self.memory_storage[user_id] = VideoFilters()
        if self.storage_type == 'json':
            self._save_to_json()
    
    def delete_user(self, user_id):
        """Удалить настройки пользователя"""
        if user_id in self.memory_storage:
            del self.memory_storage[user_id]
            if self.storage_type == 'json':
                self._save_to_json()


# Глобальный экземпляр хранилища
# По умолчанию используем JSON для persistence между перезапусками
settings_store = SettingsStore(storage_type='json')
