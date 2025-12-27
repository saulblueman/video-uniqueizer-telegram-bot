import random

class VideoFilters:
    def __init__(self, brightness=0.05, contrast=0.05, saturation=0.05, zoom=0.05, speed=0.05):
        self.brightness_range = brightness
        self.contrast_range = contrast
        self.saturation_range = saturation
        self.zoom_range = zoom
        self.speed_range = speed

    def generate_random_state(self):
        """Генерирует случайные значения и формирует список только измененных параметров."""
        def get_rand(max_val, is_offset=True):
            if max_val <= 0: return 0.0 if is_offset else 1.0
            res = random.uniform(-max_val, max_val)
            # Гарантируем минимальное изменение
            while abs(res) < 0.005:
                res = random.uniform(-max_val, max_val)
            return res

        b = get_rand(self.brightness_range, True)
        c = 1.0 + get_rand(self.contrast_range, True)
        s = 1.0 + get_rand(self.saturation_range, True)
        z = 1.0 + abs(get_rand(self.zoom_range, True))
        sp = 1.0 + get_rand(self.speed_range, True)

        vals = {'brightness': b, 'contrast': c, 'saturation': s, 'zoom': z, 'speed': sp}
        
        # Динамическое формирование описания (только измененные параметры)
        parts = []
        if abs(b) > 0.001: 
            parts.append(f"Ярк: {'+' if b>0 else ''}{round(b, 2)}")
        if abs(c - 1.0) > 0.001: 
            parts.append(f"Конт: {round(c, 2)}")
        if abs(s - 1.0) > 0.001: 
            parts.append(f"Насыщ: {round(s, 2)}")
        if abs(z - 1.0) > 0.001: 
            parts.append(f"Зум: {round(z, 2)}x")
        if abs(sp - 1.0) > 0.001: 
            parts.append(f"Скор: {round(sp, 2)}x")
        
        desc = " ".join(parts) if parts else "Без изменений"
        return vals, desc

    def to_dict(self):
        return {k.replace('_range', ''): v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data):
        return cls(**data)
