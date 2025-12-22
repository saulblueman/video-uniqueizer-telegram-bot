import os
import subprocess
import uuid
import mimetypes
import cv2
from decouple import config

# Импорты Telethon
from telethon import TelegramClient, events, Button
from telethon.tl.types import ReplyKeyboardMarkup, KeyboardButtonRow, KeyboardButton

# Твои кастомные модули
from filters_manager import VideoFilters, GRID_COLOR_PRESETS, GRID_OPACITY_PRESETS, GRID_SIZE_PRESETS
from settings_store import settings_store

# Загрузка конфигурации
API_ID = config("API_ID", cast=int)
API_HASH = config("API_HASH")
BOT_TOKEN = config("BOT_TOKEN")

# Инициализация бота
bot = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

picture_path = "best_offer.png" # Убедись, что этот файл есть в папке
user_states = {}

# =====================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================

def get_full_filter_chain(user_id, operation_filter=None):
    """
    Собирает цепочку: [Фильтры из настроек] + [Фильтр операции (например, hflip)]
    Возвращает строку для параметра -vf или None
    """
    filters_obj = settings_store.get_filters(user_id)
    # build_ffmpeg_filter() возвращает список строк-фильтров
    user_filters = filters_obj.build_ffmpeg_filter()
    
    if operation_filter:
        user_filters.append(operation_filter)
    
    if not user_filters:
        return None
    
    return ",".join(user_filters)

# =====================================================
# ГЛАВНОЕ МЕНЮ И КОМАНДЫ
# =====================================================

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    keyboard = [
        [Button.text("Изменить битрейт"), Button.text("Отзеркалить")],
        [Button.text("Наложить картинку")],
        [Button.text("🎛 Настройки видео")]
    ]
    await event.respond(
        "👋 Привет! Я бот для уникализации видео.\n\n"
        "Настрой фильтры в меню «🎛 Настройки видео», а затем "
        "выбери режим обработки и пришли видео.",
        buttons=keyboard
    )

@bot.on(events.NewMessage(pattern="/menu"))
async def menu_cmd(event):
    keyboard = ReplyKeyboardMarkup([
        KeyboardButtonRow([KeyboardButton("Изменить битрейт"), KeyboardButton("Отзеркалить")]),
        KeyboardButtonRow([KeyboardButton("Наложить картинку")])
    ], resize=True)
    await event.respond("Выбери действие:", buttons=keyboard)

# =====================================================
# ОБРАБОТЧИКИ НАСТРОЕК (UI)
# =====================================================

@bot.on(events.NewMessage(pattern="🎛 Настройки видео"))
async def settings_main_menu(event):
    user_id = event.sender_id
    f = settings_store.get_filters(user_id)
    
    text = (
        "⚙️ **Настройки фильтров видео**\n\n"
        f"☀️ Яркость: **{f.get_brightness_percent():+.1f}%**\n"
        f"🌓 Контраст: **{f.get_contrast_percent():+.1f}%**\n"
        f"🔪 Резкость: **{f.get_sharpness_percent():.1f}%**\n"
        f"🌫 Шум: **{f.get_noise_percent()}%**\n"
        f"#️⃣ Сетка: **{'✅ Вкл' if f.grid_enabled else '❌ Выкл'}**\n"
    )
    if f.grid_enabled:
        text += f"   └ Цвет: {f.grid_color}, Прозр: {int(f.grid_opacity*100)}%, Разм: {f.grid_width}x{f.grid_height}\n"

    kb = [
        [Button.inline("☀️ Яркость", b"ui_bright"), Button.inline("🌓 Контраст", b"ui_contrast")],
        [Button.inline("🔪 Резкость", b"ui_sharp"), Button.inline("🌫 Шум", b"ui_noise")],
        [Button.inline("#️⃣ Сетка", b"ui_grid")],
        [Button.inline("🔄 Сброс", b"f_reset_all"), Button.inline("💾 Сохранить", b"f_save_exit")],
        [Button.inline("⬅️ Назад", b"f_main_back")]
    ]
    await event.respond(text, buttons=kb)

# Универсальный обработчик для подменю параметров (Яркость, Контраст, Резкость, Шум)
@bot.on(events.CallbackQuery(pattern=b"ui_(bright|contrast|sharp|noise)"))
async def parameter_sub_menu(event):
    param = event.pattern_match.group(1).decode()
    user_id = event.sender_id
    f = settings_store.get_filters(user_id)
    
    titles = {"bright": "☀️ Яркость", "contrast": "🌓 Контраст", "sharp": "🔪 Резкость", "noise": "🌫 Шум"}
    values = {
        "bright": f"{f.get_brightness_percent():+.1f}%",
        "contrast": f"{f.get_contrast_percent():+.1f}%",
        "sharp": f"{f.get_sharpness_percent():.1f}%",
        "noise": f"{f.get_noise_percent()}%"
    }

    text = f"**{titles[param]}**\nТекущее значение: **{values[param]}**"
    
    # Кнопки изменения
    steps = ["-10", "-5", "-1", "+1", "+5", "+10"]
    row1 = [Button.inline(f"{s}%", f"adj_{param}_{s}".encode()) for s in steps[:3]]
    row2 = [Button.inline(f"{s}%", f"adj_{param}_{s}".encode()) for s in steps[3:]]
    
    kb = [row1, row2, [Button.inline("🔄 Сброс", f"adj_{param}_0".encode())], [Button.inline("⬅️ Назад", b"back_to_settings")]]
    await event.edit(text, buttons=kb)

@bot.on(events.CallbackQuery(pattern=b"adj_(.*)_(.*)"))
async def adjust_logic(event):
    param = event.pattern_match.group(1).decode()
    value = int(event.pattern_match.group(2).decode())
    user_id = event.sender_id
    f = settings_store.get_filters(user_id)

    if value == 0:
        if param == "bright": f.brightness.reset()
        elif param == "contrast": f.contrast.value = 1.0
        elif param == "sharp": f.sharpness.reset()
        elif param == "noise": f.noise.reset()
    else:
        if param == "bright": f.adjust_brightness(value)
        elif param == "contrast": f.adjust_contrast(value)
        elif param == "sharp": f.adjust_sharpness(value)
        elif param == "noise": f.adjust_noise(value)
    
    settings_store.save_filters(user_id, f)
    await parameter_sub_menu(event)

# Меню Сетки
@bot.on(events.CallbackQuery(pattern=b"ui_grid"))
async def grid_menu(event):
    user_id = event.sender_id
    f = settings_store.get_filters(user_id)
    status = "✅ Вкл" if f.grid_enabled else "❌ Выкл"
    text = f"#️⃣ **Настройка сетки**\nСтатус: {status}\nЦвет: {f.grid_color}\nПрозрачность: {int(f.grid_opacity*100)}%"
    
    kb = [
        [Button.inline("🔄 Вкл/Выкл", b"g_toggle")],
        [Button.inline("🎨 Цвет", b"g_color_menu"), Button.inline("👁 Прозр.", b"g_opac_menu")],
        [Button.inline("📐 Размер", b"g_size_menu")],
        [Button.inline("⬅️ Назад", b"back_to_settings")]
    ]
    await event.edit(text, buttons=kb)

@bot.on(events.CallbackQuery(pattern=b"g_toggle"))
async def g_toggle(event):
    f = settings_store.get_filters(event.sender_id)
    f.toggle_grid()
    settings_store.save_filters(event.sender_id, f)
    await grid_menu(event)

# Настройка Цвета/Прозрачности/Размера (Пресеты)
@bot.on(events.CallbackQuery(pattern=b"g_(color|opac|size)_menu"))
async def grid_presets(event):
    mode = event.pattern_match.group(1).decode()
    kb = []
    if mode == "color":
        for name, val in GRID_COLOR_PRESETS.items():
            kb.append([Button.inline(name, f"set_gcol_{val}".encode())])
    elif mode == "opac":
        for name, val in GRID_OPACITY_PRESETS.items():
            kb.append([Button.inline(name, f"set_gopc_{val}".encode())])
    elif mode == "size":
        for name, (w, h) in GRID_SIZE_PRESETS.items():
            kb.append([Button.inline(name, f"set_gsiz_{w}_{h}".encode())])
    
    kb.append([Button.inline("⬅️ Назад", b"ui_grid")])
    await event.edit(f"Выберите значение ({mode}):", buttons=kb)

@bot.on(events.CallbackQuery(pattern=b"set_g(col|opc|siz)_(.*)"))
async def set_grid_val(event):
    mode = event.pattern_match.group(1).decode()
    val_raw = event.pattern_match.group(2).decode()
    f = settings_store.get_filters(event.sender_id)
    
    if mode == "col": f.set_grid_color(val_raw)
    elif mode == "opc": f.set_grid_opacity(float(val_raw))
    elif mode == "siz":
        w, h = map(int, val_raw.split("_"))
        f.set_grid_size(w, h)
        
    settings_store.save_filters(event.sender_id, f)
    await grid_menu(event)

# Системные кнопки настроек
@bot.on(events.CallbackQuery(pattern=b"back_to_settings"))
async def back_to_settings(event): await settings_main_menu(event)

@bot.on(events.CallbackQuery(pattern=b"f_reset_all"))
async def f_reset_all(event):
    settings_store.reset_filters(event.sender_id)
    await settings_main_menu(event)

@bot.on(events.CallbackQuery(pattern=b"f_save_exit"))
async def f_save_exit(event):
    await event.answer("✅ Настройки успешно сохранены!", alert=True)

@bot.on(events.CallbackQuery(pattern=b"f_main_back"))
async def f_main_back(event):
    await event.delete()
    # Эмуляция команды старт для возврата основного меню
    await start_handler(event)

# =====================================================
# ОБРАБОТКА ВИДЕО
# =====================================================

@bot.on(events.NewMessage(pattern="(Изменить битрейт|Отзеркалить|Наложить картинку)"))
async def set_state(event):
    user_id = event.sender_id
    state_map = {
        "Изменить битрейт": ("change_bitrate", CHANGE_BITRATE_MESSAGE),
        "Отзеркалить": ("mirror_horizontal", MIRROR_HORIZONTAL_MESSAGE),
        "Наложить картинку": ("add_a_picture", ADD_A_PICTURE_MESSAGE)
    }
    state, msg = state_map[event.pattern_match.group(1)]
    user_states[user_id] = state
    await event.respond(msg)

@bot.on(events.NewMessage)
async def handle_video_arrival(event):
    user_id = event.sender_id
    state = user_states.get(user_id)
    
    if state and event.media and hasattr(event.media, "document"):
        if "video" in event.media.document.mime_type:
            # Скачивание
            status_msg = await event.respond("⏳ Скачиваю и обрабатываю видео...")
            video_path = await event.client.download_media(event.media.document)
            
            try:
                if state == "change_bitrate": await change_bitrate(event, video_path)
                elif state == "mirror_horizontal": await mirror_horizontal(event, video_path)
                elif state == "add_a_picture": await add_a_picture(event, video_path)
                await status_msg.delete()
            except Exception as e:
                await event.respond(f"❌ Ошибка обработки: {e}")
            finally:
                if os.path.exists(video_path): os.remove(video_path)

async def mirror_horizontal(event, video_path):
    out = f"mod_{uuid.uuid4()}.mp4"
    vf = get_full_filter_chain(event.sender_id, "hflip")
    
    cmd = ["ffmpeg", "-y", "-i", video_path]
    if vf: cmd.extend(["-vf", vf])
    cmd.extend(["-map_metadata", "-1", "-c:a", "copy", out])
    
    subprocess.call(cmd)
    await event.client.send_file(event.chat_id, out, caption="✅ Видео отзеркалено + фильтры")
    if os.path.exists(out): os.remove(out)

async def change_bitrate(event, video_path):
    out = f"mod_{uuid.uuid4()}.mp4"
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frames / fps if fps > 0 else 1
    cap.release()
    
    target_bitrate = int((os.path.getsize(video_path) * 8 / duration) * 0.7)
    vf = get_full_filter_chain(event.sender_id)
    
    cmd = ["ffmpeg", "-y", "-i", video_path]
    if vf: cmd.extend(["-vf", vf])
    cmd.extend(["-b:v", str(target_bitrate), "-map_metadata", "-1", out])
    
    subprocess.call(cmd)
    await event.client.send_file(event.chat_id, out, caption="✅ Битрейт изменен + фильтры")
    if os.path.exists(out): os.remove(out)

async def add_a_picture(event, video_path):
    out = f"mod_{uuid.uuid4()}.mp4"
    user_vf = get_full_filter_chain(event.sender_id)
    
    # Сложный фильтр: сначала фильтры пользователя к видео [0:v], потом оверлей
    if user_vf:
        f_comp = f"[0:v]{user_vf}[v_filt]; [v_filt][1:v]overlay=W-w-10:H-h-10[v]"
    else:
        f_comp = "[0:v][1:v]overlay=W-w-10:H-h-10[v]"

    cmd = [
        "ffmpeg", "-y", "-i", video_path, "-i", picture_path,
        "-filter_complex", f_comp,
        "-map", "[v]", "-map", "0:a",
        "-map_metadata", "-1", "-c:v", "libx264", "-c:a", "copy", out
    ]
    
    subprocess.call(cmd)
    await event.client.send_file(event.chat_id, out, caption="✅ Картинка наложена + фильтры")
    if os.path.exists(out): os.remove(out)

# Текстовые константы
MIRROR_HORIZONTAL_MESSAGE = "🪞 Режим: Отзеркаливание. Пришли видео."
CHANGE_BITRATE_MESSAGE = "📉 Режим: Сжатие битрейта. Пришли видео."
ADD_A_PICTURE_MESSAGE = "🖼 Режим: Наложение логотипа. Пришли видео."

def main():
    print("Бот запущен...")
    bot.run_until_disconnected()

if __name__ == "__main__":
    main()
