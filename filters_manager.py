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
        # Яркость: диапазон -1.0 до 1.0 (FFmpeg eq=brightness)
        self.brightness = FilterValue(0.0, -1.0, 1.0)
        
        # Контраст: диапазон 0.1 до 3.0 (FFmpeg eq=contrast)
        self.contrast = FilterValue(1.0, 0.1, 3.0)
        
        # Резкость: диапазон 0.0 до 2.0 (FFmpeg unsharp amount)
        self.sharpness = FilterValue(0.0, 0.0, 2.0)
        
        # Шум: диапазон 0 до 30 (FFmpeg noise)
        self.noise = FilterValue(0, 0, 30)
        
        # Сетка
        self.grid_enabled = False
        self.grid_color = "#030303"  # По умолчанию темный цвет
        self.grid_opacity = 0.15     # 15% прозрачности
        self.grid_width = 21         # Ширина ячейки
        self.grid_height = 46        # Высота ячейки
               self.zoom = 0.0      # % зума (0-10)
        self.rotate = 0.0    # градусы (-5 до 5)
        self.speed = 1.0     # коэффициент скорости (0.9 до 1.1)

       def reset_all(self):
        # ... (сброс старых) ...
        self.zoom = 0.0
        self.rotate = 0.0
        self.speed = 1.0
    
    def adjust_brightness(self, percent):
        """
        Изменить яркость на процент.
        percent: +10 означает +10%, -5 означает -5%
        Внутри хранится как float: +10% => +0.1
        """
        delta = percent / 100.0
        return self.brightness.adjust(delta)
    
    def adjust_contrast(self, percent):
        """
        Изменить контраст на процент.
        percent: +10 означает увеличить на 10%
        Внутри: 1.0 + (percent / 100) => +10% => 1.1
        """
        delta = percent / 100.0
        return self.contrast.adjust(delta)
    
    def adjust_sharpness(self, percent):
        """
        Изменить резкость на процент.
        percent преобразуется в amount для unsharp
        """
        delta = percent / 100.0
        return self.sharpness.adjust(delta)
    
    def adjust_noise(self, percent):
        """
        Изменить уровень шума на процент.
        percent напрямую используется как значение
        """
        return self.noise.adjust(percent)
    
    def toggle_grid(self):
        """Включить/выключить сетку"""
        self.grid_enabled = not self.grid_enabled
        return self.grid_enabled
    
    def set_grid_color(self, color):
        """Установить цвет сетки"""
        self.grid_color = color
    
    def set_grid_opacity(self, opacity):
        """Установить прозрачность сетки (0.01 - 0.5)"""
        self.grid_opacity = max(0.01, min(0.5, opacity))
    
    def set_grid_size(self, width, height):
        """Установить размер ячеек сетки"""
        self.grid_width = width
        self.grid_height = height
    
    def reset_all(self):
        """Сброс всех настроек к значениям по умолчанию"""
        self.brightness.reset()
        self.contrast.value = 1.0
        self.sharpness.reset()
        self.noise.reset()
        self.grid_enabled = False
        self.grid_color = "#030303"
        self.grid_opacity = 0.15
        self.grid_width = 21
        self.grid_height = 46
    
    def get_brightness_percent(self):
        """Получить яркость в процентах"""
        return round(self.brightness.value * 100, 1)
    
    def get_contrast_percent(self):
        """Получить контраст в процентах относительно 1.0"""
        return round((self.contrast.value - 1.0) * 100, 1)
    
    def get_sharpness_percent(self):
        """Получить резкость в процентах"""
        return round(self.sharpness.value * 100, 1)
    
    def get_noise_percent(self):
        """Получить шум в процентах"""
        return int(self.noise.value)
    
  def to_dict(self):
        d = {
            'brightness': self.brightness.value,
            'contrast': self.contrast.value,
            'sharpness': self.sharpness.value,
            'noise': self.noise.value,
            'grid_enabled': self.grid_enabled,
            'grid_color': self.grid_color,
            'grid_opacity': self.grid_opacity,
            'grid_width': self.grid_width,
            'grid_height': self.grid_height,
            # Новое
            'zoom': self.zoom,
            'rotate': self.rotate,
            'speed': self.speed
        }
        return d
    
      @classmethod
    def from_dict(cls, data):
        f = cls()
        f.brightness.value = data.get('brightness', 0.0)
        f.contrast.value = data.get('contrast', 1.0)
        f.sharpness.value = data.get('sharpness', 0.0)
        f.noise.value = data.get('noise', 0)
        f.grid_enabled = data.get('grid_enabled', False)
        # ... остальные старые ...
        f.zoom = data.get('zoom', 0.0)
        f.rotate = data.get('rotate', 0.0)
        f.speed = data.get('speed', 1.0)
        return f

   def build_ffmpeg_filter(self):
        filters = []
        
        # 1. Зум (Scale + Crop)
        if self.zoom > 0:
            z = 1 + (self.zoom / 100)
            filters.append(f"scale=iw*{z}:-1,crop=iw/{z}:ih/{z}")

        # 2. Поворот (с обрезкой, чтобы не было черных углов)
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
        
        # КРИТИЧЕСКИЙ ФИКС: Принудительный формат для плавности воспроизведения
        filters.append("format=yuv420p")
        
        return filters


# Пресеты для удобства пользователя
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
