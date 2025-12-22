import os
import subprocess
import uuid
import mimetypes
import cv2
from decouple import config

# Импорты Telethon
from telethon import TelegramClient, events, Button
from telethon.tl.types import ReplyKeyboardMarkup, KeyboardButtonRow, KeyboardButton
from telethon.errors import MessageNotModifiedError

# Твои кастомные модули
from filters_manager import VideoFilters, GRID_COLOR_PRESETS, GRID_OPACITY_PRESETS, GRID_SIZE_PRESETS
from settings_store import settings_store

# Загрузка конфигурации
API_ID = config("API_ID", cast=int)
API_HASH = config("API_HASH")
BOT_TOKEN = config("BOT_TOKEN")

# Инициализация бота
bot = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

picture_path = "best_offer.png" 
user_states = {}

# =====================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================

def get_full_filter_chain(user_id, operation_filter=None):
    """Собирает цепочку: [Настройки] + [Операция]"""
    filters_obj = settings_store.get_filters(user_id)
    user_filters = filters_obj.build_ffmpeg_filter()
    
    if operation_filter:
        user_filters.append(operation_filter)
    
    return ",".join(user_filters) if user_filters else None

def get_audio_args(user_id):
    """Возвращает аргументы для аудио на основе скорости"""
    f = settings_store.get_filters(user_id)
    if abs(f.speed - 1.0) > 0.001:
        # atempo поддерживает диапазон 0.5 - 2.0
        return ["-af", f"atempo={f.speed}"]
    return ["-c:a", "copy"]

async def safe_edit(event, text, buttons):
    """Безопасное редактирование сообщения с обработкой дублей"""
    try:
        await event.edit(text, buttons=buttons)
    except MessageNotModifiedError:
        await event.answer("Значение уже применено")
    except Exception as e:
        print(f"Edit error: {e}")

# =====================================================
# ГЛАВНОЕ МЕНЮ И КОМАНДЫ
# =====================================================

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    keyboard = [
        [Button.text("Изменить битрейт"), Button.text("Отзеркалить")],
        [Button.text("Наложить картинку"), Button.text("🚀 Только фильтры")],
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
        KeyboardButtonRow([KeyboardButton("Наложить картинку"), KeyboardButton("🚀 Только фильтры")])
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
        f"🚀 **Advanced:** Зум {f.zoom}%, Поворот {f.rotate}°, Скор. {f.speed}x"
    )

    kb = [
        [Button.inline("☀️ Яркость", b"ui_bright"), Button.inline("🌓 Контраст", b"ui_contrast")],
        [Button.inline("🔪 Резкость", b"ui_sharp"), Button.inline("🌫 Шум", b"ui_noise")],
        [Button.inline("#️⃣ Сетка", b"ui_grid"), Button.inline("🚀 Уникализация+", b"ui_adv")],
        [Button.inline("🔄 Сброс", b"f_reset_all"), Button.inline("💾 Сохранить", b"f_save_exit")],
        [Button.inline("⬅️ Назад", b"f_main_back")]
    ]
    await event.respond(text, buttons=kb)

# --- МЕНЮ ADVANCED ---
@bot.on(events.CallbackQuery(pattern=b"ui_adv"))
async def advanced_menu(event):
    f = settings_store.get_filters(event.sender_id)
    text = (
        "🚀 **Продвинутая уникализация**\n\n"
        f"🔍 Зум: **{f.zoom}%**\n"
        f"🔄 Поворот: **{f.rotate}°**\n"
        f"🏃 Скорость: **{f.speed}x**"
    )
    kb = [
        [Button.inline("🔍 Зум", b"p_zoom"), Button.inline("🔄 Поворот", b"p_rot")],
        [Button.inline("🏃 Скорость", b"p_speed")],
        [Button.inline("⬅️ Назад", b"back_to_settings")]
    ]
    await safe_edit(event, text, kb)

@bot.on(events.CallbackQuery(pattern=b"p_zoom"))
async def zoom_menu(event):
    f = settings_store.get_filters(event.sender_id)
    kb = [[Button.inline("+1%", b"sz_1"), Button.inline("+2%", b"sz_2"), Button.inline("+5%", b"sz_5")],
          [Button.inline("🔄 Сброс", b"sz_0")], [Button.inline("⬅️ Назад", b"ui_adv")]]
    await safe_edit(event, f"🔍 **Зум (обрезка краев)**\nТекущий: {f.zoom}%", kb)

@bot.on(events.CallbackQuery(pattern=b"sz_(\\d+)"))
async def set_zoom(event):
    val = int(event.pattern_match.group(1).decode())
    f = settings_store.get_filters(event.sender_id)
    f.zoom = float(val)
    settings_store.save_filters(event.sender_id, f)
    await event.answer(f"Зум: {val}%")
    await zoom_menu(event)

@bot.on(events.CallbackQuery(pattern=b"p_rot"))
async def rotate_menu(event):
    f = settings_store.get_filters(event.sender_id)
    kb = [[Button.inline("-1°", b"sr_-1"), Button.inline("-0.3°", b"sr_-0.3"), Button.inline("+0.3°", b"sr_0.3"), Button.inline("+1°", b"sr_1")],
          [Button.inline("🔄 0°", b"sr_0")], [Button.inline("⬅️ Назад", b"ui_adv")]]
    await safe_edit(event, f"🔄 **Поворот видео**\nТекущий: {f.rotate}°", kb)

@bot.on(events.CallbackQuery(pattern=b"sr_(.*)"))
async def set_rotate(event):
    val = float(event.pattern_match.group(1).decode())
    f = settings_store.get_filters(event.sender_id)
    f.rotate = val if val != 0 else 0.0
    settings_store.save_filters(event.sender_id, f)
    await event.answer(f"Поворот: {val}°")
    await rotate_menu(event)

@bot.on(events.CallbackQuery(pattern=b"p_speed"))
async def speed_menu(event):
    f = settings_store.get_filters(event.sender_id)
    kb = [[Button.inline("0.95x", b"ss_0.95"), Button.inline("1.01x", b"ss_1.01"), Button.inline("1.05x", b"ss_1.05")],
          [Button.inline("🔄 1.0x", b"ss_1.0")], [Button.inline("⬅️ Назад", b"ui_adv")]]
    await safe_edit(event, f"🏃 **Скорость видео и звука**\nТекущая: {f.speed}x", kb)

@bot.on(events.CallbackQuery(pattern=b"ss_(.*)"))
async def set_speed(event):
    val = float(event.pattern_match.group(1).decode())
    f = settings_store.get_filters(event.sender_id)
    f.speed = val
    settings_store.save_filters(event.sender_id, f)
    await event.answer(f"Скорость: {val}x")
    await speed_menu(event)

# --- ПАРАМЕТРЫ (Яркость, Контраст и др.) ---
@bot.on(events.CallbackQuery(pattern=b"ui_(bright|contrast|sharp|noise)"))
async def parameter_sub_menu(event):
    param = event.pattern_match.group(1).decode()
    f = settings_store.get_filters(event.sender_id)
    titles = {"bright": "☀️ Яркость", "contrast": "🌓 Контраст", "sharp": "🔪 Резкость", "noise": "🌫 Шум"}
    values = {"bright": f"{f.get_brightness_percent():+.1f}%", "contrast": f"{f.get_contrast_percent():+.1f}%",
              "sharp": f"{f.get_sharpness_percent():.1f}%", "noise": f"{f.get_noise_percent()}%"}
    
    steps = ["-10", "-5", "-1", "+1", "+5", "+10"]
    row1 = [Button.inline(f"{s}%", f"adj_{param}_{s}".encode()) for s in steps[:3]]
    row2 = [Button.inline(f"{s}%", f"adj_{param}_{s}".encode()) for s in steps[3:]]
    kb = [row1, row2, [Button.inline("🔄 Сброс", f"adj_{param}_0".encode())], [Button.inline("⬅️ Назад", b"back_to_settings")]]
    await safe_edit(event, f"**{titles[param]}**\nЗначение: **{values[param]}**", kb)

@bot.on(events.CallbackQuery(pattern=b"adj_(.*)_(.*)"))
async def adjust_logic(event):
    param = event.pattern_match.group(1).decode(); value = int(event.pattern_match.group(2).decode())
    f = settings_store.get_filters(event.sender_id)
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
    settings_store.save_filters(event.sender_id, f); await event.answer(); await parameter_sub_menu(event)

# --- СЕТКА ---
@bot.on(events.CallbackQuery(pattern=b"ui_grid"))
async def grid_menu(event):
    f = settings_store.get_filters(event.sender_id)
    text = f"#️⃣ **Сетка**\nСтатус: {'✅ Вкл' if f.grid_enabled else '❌ Выкл'}\nЦвет: {f.grid_color}"
    kb = [[Button.inline("🔄 Вкл/Выкл", b"g_tgl")], [Button.inline("🎨 Цвет", b"g_c_m"), Button.inline("📐 Размер", b"g_s_m")], [Button.inline("⬅️ Назад", b"back_to_settings")]]
    await safe_edit(event, text, kb)

@bot.on(events.CallbackQuery(pattern=b"g_tgl"))
async def g_tgl(event):
    f = settings_store.get_filters(event.sender_id); f.toggle_grid()
    settings_store.save_filters(event.sender_id, f); await event.answer(); await grid_menu(event)

# Навигация
@bot.on(events.CallbackQuery(pattern=b"back_to_settings"))
async def nav_sett(event): await event.answer(); await settings_main_menu(event)

@bot.on(events.CallbackQuery(pattern=b"f_reset_all"))
async def nav_reset(event):
    settings_store.reset_filters(event.sender_id); await event.answer("Настройки сброшены"); await settings_main_menu(event)

@bot.on(events.CallbackQuery(pattern=b"f_save_exit"))
async def nav_save(event): await event.answer("✅ Сохранено", alert=True)

@bot.on(events.CallbackQuery(pattern=b"f_main_back"))
async def nav_back(event): await event.delete(); await start_handler(event)

# =====================================================
# ОБРАБОТКА ВИДЕО
# =====================================================

@bot.on(events.NewMessage(pattern="(Изменить битрейт|Отзеркалить|Наложить картинку|🚀 Только фильтры)"))
async def set_state(event):
    user_id = event.sender_id
    text = event.pattern_match.group(1)
    state_map = {
        "Изменить битрейт": ("change_bitrate", "📉 Режим: Битрейт. Пришли видео."),
        "Отзеркалить": ("mirror_horizontal", "🪞 Режим: Зеркало. Пришли видео."),
        "Наложить картинку": ("add_a_picture", "🖼 Режим: Картинка. Пришли видео."),
        "🚀 Только фильтры": ("only_filters", "🚀 Режим: Фильтры. Пришли видео.")
    }
    state, msg = state_map[text]
    user_states[user_id] = state
    await event.respond(msg)

@bot.on(events.NewMessage)
async def handle_video(event):
    user_id = event.sender_id; state = user_states.get(user_id)
    if state and event.media and hasattr(event.media, "document"):
        if "video" in event.media.document.mime_type:
            status = await event.respond("⏳ Обработка...")
            video_path = await event.client.download_media(event.media.document)
            try:
                if state == "change_bitrate": await change_bitrate(event, video_path)
                elif state == "mirror_horizontal": await mirror_horizontal(event, video_path)
                elif state == "add_a_picture": await add_a_picture(event, video_path)
                elif state == "only_filters": await only_filters_proc(event, video_path)
                await status.delete()
            except Exception as e:
                await event.respond(f"❌ Ошибка: {e}")
            finally:
                if os.path.exists(video_path): os.remove(video_path)

async def mirror_horizontal(event, video_path):
    out = f"mod_{uuid.uuid4()}.mp4"
    vf = get_full_filter_chain(event.sender_id, "hflip")
    audio = get_audio_args(event.sender_id)
    cmd = ["ffmpeg", "-y", "-i", video_path]
    if vf: cmd.extend(["-vf", vf])
    cmd.extend(audio); cmd.extend(["-map_metadata", "-1", out])
    subprocess.call(cmd)
    await event.client.send_file(event.chat_id, out, caption="✅ Зеркало + фильтры")
    if os.path.exists(out): os.remove(out)

async def only_filters_proc(event, video_path):
    out = f"mod_{uuid.uuid4()}.mp4"
    vf = get_full_filter_chain(event.sender_id)
    audio = get_audio_args(event.sender_id)
    cmd = ["ffmpeg", "-y", "-i", video_path]
    if vf: cmd.extend(["-vf", vf])
    cmd.extend(audio); cmd.extend(["-c:v", "libx264", "-crf", "23", "-map_metadata", "-1", out])
    subprocess.call(cmd)
    await event.client.send_file(event.chat_id, out, caption="✅ Уникализация завершена")
    if os.path.exists(out): os.remove(out)

async def change_bitrate(event, video_path):
    out = f"mod_{uuid.uuid4()}.mp4"
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS); frames = cap.get(cv2.CAP_PROP_FRAME_COUNT); cap.release()
    duration = frames / fps if fps > 0 else 1
    target_bitrate = int((os.path.getsize(video_path) * 8 / duration) * 0.7)
    vf = get_full_filter_chain(event.sender_id); audio = get_audio_args(event.sender_id)
    cmd = ["ffmpeg", "-y", "-i", video_path]
    if vf: cmd.extend(["-vf", vf])
    cmd.extend(audio); cmd.extend(["-b:v", str(target_bitrate), "-map_metadata", "-1", out])
    subprocess.call(cmd)
    await event.client.send_file(event.chat_id, out, caption="✅ Сжатие + фильтры")
    if os.path.exists(out): os.remove(out)

async def add_a_picture(event, video_path):
    out = f"mod_{uuid.uuid4()}.mp4"
    user_vf = get_full_filter_chain(event.sender_id); audio = get_audio_args(event.sender_id)
    f_comp = f"[0:v]{user_vf}[v_filt]; [v_filt][1:v]overlay=W-w-10:H-h-10[v]" if user_vf else "[0:v][1:v]overlay=W-w-10:H-h-10[v]"
    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", picture_path, "-filter_complex", f_comp, "-map", "[v]", "-map", "0:a"]
    cmd.extend(audio); cmd.extend(["-map_metadata", "-1", "-c:v", "libx264", out])
    subprocess.call(cmd)
    await event.client.send_file(event.chat_id, out, caption="✅ Лого + фильтры")
    if os.path.exists(out): os.remove(out)

def main():
    print("Бот запущен...")
    bot.run_until_disconnected()

if __name__ == "__main__":
    main()
