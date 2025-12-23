"""
Модуль для управления FFmpeg фильтрами видео
"""

class FilterValue:
    """Базовый класс для значения фильтра"""
    def __init__(self, value, min_val, max_val):
        self.value = self._clamp(value, min_val, max_val)
        self.min_val = min_val
        self.max_val = max_val
    
    def _clamp(self, value, min_val, max_val):
        """Ограничение значения в заданных пределах"""
        return max(min_val, min(max_val, value))
    
    def adjust(self, delta):
        """Изменить значение на дельту"""
        self.value = self._clamp(self.value + delta, self.min_val, self.max_val)
        return self.value
    
    def reset(self):
        """Сброс к значению по умолчанию"""
        self.value = 0
        return self.value


class VideoFilters:
    """Класс для управления всеми фильтрами видео"""
    
    def __init__(self):
        # Стандартные фильтры
        self.brightness = FilterValue(0.0, -1.0, 1.0)
        self.contrast = FilterValue(1.0, 0.1, 3.0)
        self.sharpness = FilterValue(0.0, 0.0, 2.0)
        self.noise = FilterValue(0, 0, 30)
        
        # Сетка
        self.grid_enabled = False
        self.grid_color = "#030303"
        self.grid_opacity = 0.15
        self.grid_width = 21
        self.grid_height = 46

        # Продвинутая уникализация
        self.zoom = 0.0      # % зума (0-10)
        self.rotate = 0.0    # градусы (-5 до 5)
        self.speed = 1.0     # коэффициент скорости (0.9 до 1.1)
    
    def adjust_brightness(self, percent):
        delta = percent / 100.0
        return self.brightness.adjust(delta)
    
    def adjust_contrast(self, percent):
        delta = percent / 100.0
        return self.contrast.adjust(delta)
    
    def adjust_sharpness(self, percent):
        delta = percent / 100.0
        return self.sharpness.adjust(delta)
    
    def adjust_noise(self, percent):
        return self.noise.adjust(percent)
    
    def toggle_grid(self):
        self.grid_enabled = not self.grid_enabled
        return self.grid_enabled
    
    def set_grid_color(self, color):
        self.grid_color = color
    
    def set_grid_opacity(self, opacity):
        self.grid_opacity = max(0.01, min(0.5, opacity))
    
    def set_grid_size(self, width, height):
        self.grid_width = width
        self.grid_height = height
    
    def reset_all(self):
        self.brightness.reset()
        self.contrast.value = 1.0
        self.sharpness.reset()
        self.noise.reset()
        self.grid_enabled = False
        self.grid_color = "#030303"
        self.grid_opacity = 0.15
        self.grid_width = 21
        self.grid_height = 46
        self.zoom = 0.0
        self.rotate = 0.0
        self.speed = 1.0
    
    def get_brightness_percent(self):
        return round(self.brightness.value * 100, 1)
    
    def get_contrast_percent(self):
        return round((self.contrast.value - 1.0) * 100, 1)
    
    def get_sharpness_percent(self):
        return round(self.sharpness.value * 100, 1)
    
    def get_noise_percent(self):
        return int(self.noise.value)
    
    def to_dict(self):
        return {
            'brightness': self.brightness.value,
            'contrast': self.contrast.value,
            'sharpness': self.sharpness.value,
            'noise': self.noise.value,
            'grid_enabled': self.grid_enabled,
            'grid_color': self.grid_color,
            'grid_opacity': self.grid_opacity,
            'grid_width': self.grid_width,
            'grid_height': self.grid_height,
            'zoom': self.zoom,
            'rotate': self.rotate,
            'speed': self.speed
        }
    
    @classmethod
    def from_dict(cls, data):
        filters = cls()
        filters.brightness.value = data.get('brightness', 0.0)
        filters.contrast.value = data.get('contrast', 1.0)
        filters.sharpness.value = data.get('sharpness', 0.0)
        filters.noise.value = data.get('noise', 0)
        filters.grid_enabled = data.get('grid_enabled', False)
        filters.grid_color = data.get('grid_color', '#030303')
        filters.grid_opacity = data.get('grid_opacity', 0.15)
        filters.grid_width = data.get('grid_width', 21)
        filters.grid_height = data.get('grid_height', 46)
        filters.zoom = data.get('zoom', 0.0)
        filters.rotate = data.get('rotate', 0.0)
        filters.speed = data.get('speed', 1.0)
        return filters
    
    def build_ffmpeg_filter(self):
        """Построить строку фильтра для FFmpeg"""
        filters = []
        
        # 1. Зум (Scale + Crop) - должен быть первым
        if self.zoom > 0:
            z = 1 + (self.zoom / 100)
            filters.append(f"scale=iw*{z}:-1,crop=iw/{z}:ih/{z}")

        # 2. Поворот (с билинейной фильтрацией для плавности)
        if abs(self.rotate) > 0.01:
            angle_rad = self.rotate * (3.14159 / 180)
            filters.append(f"rotate={angle_rad:.4f}:bilinear=0")

        # 3. Скорость (Video PTS)
        if abs(self.speed - 1.0) > 0.001:
            filters.append(f"setpts={1/self.speed:.4f}*PTS")

        # 4. Яркость и контраст
        if abs(self.brightness.value) > 0.001 or abs(self.contrast.value - 1.0) > 0.001:
            filters.append(f"eq=brightness={self.brightness.value:.3f}:contrast={self.contrast.value:.3f}")
        
        # 5. Резкость
        if abs(self.sharpness.value) > 0.001:
            filters.append(f"unsharp=5:5:{self.sharpness.value:.3f}")
        
        # 6. Шум
        if self.noise.value > 0:
            filters.append(f"noise=alls={int(self.noise.value)}:allf=t+u")
        
        # 7. Сетка
        if self.grid_enabled:
            filters.append(f"drawgrid=w={self.grid_width}:h={self.grid_height}:t=1:c={self.grid_color}@{self.grid_opacity:.2f}")
        
        # 8. Фикс совместимости (всегда последний)
        filters.append("format=yuv420p")
        
        return filters


# Пресеты
GRID_COLOR_PRESETS = {
    '⚫ Темный': '#030303',
    '⚪ Белый': '#ffffff',
    '🔴 Красный': '#ff0000',
    '🟢 Зеленый': '#00ff00',
    '🔵 Синий': '#0000ff'
}

GRID_OPACITY_PRESETS = {
    '5%': 0.05,
    '10%': 0.10,
    '15%': 0.15,
    '20%': 0.20,
    '30%': 0.30
}

GRID_SIZE_PRESETS = {
    'Мелкая (21x46)': (21, 46),
    'Средняя (30x60)': (30, 60),
    'Крупная (40x80)': (40, 80)
}
