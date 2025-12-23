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
        return ["-af", f"atempo={f.speed}"]
    return ["-c:a", "copy"]

async def safe_edit(event, text, buttons):
    """Безопасное редактирование сообщений"""
    try:
        await event.edit(text, buttons=buttons)
    except MessageNotModifiedError:
        await event.answer()
    except Exception as e:
        print(f"Edit error: {e}")

# =====================================================
# ГЛАВНОЕ МЕНЮ
# =====================================================

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    keyboard = [
        [Button.text("Изменить битрейт"), Button.text("Отзеркалить")],
        [Button.text("Наложить картинку"), Button.text("🚀 Только фильтры")],
        [Button.text("🎛 Настройки видео")]
    ]
    await event.respond(
        "👋 **Video Uniqueizer Advanced v2.0**\n\n"
        "1. Настрой фильтры в «🎛 Настройки видео»\n"
        "2. Выбери режим обработки\n"
        "3. Пришли видеофайлом",
        buttons=keyboard
    )

# =====================================================
# НАСТРОЙКИ (UI)
# =====================================================

@bot.on(events.NewMessage(pattern="🎛 Настройки видео"))
async def settings_main_menu(event):
    f = settings_store.get_filters(event.sender_id)
    text = (
        "⚙️ **Настройки видео**\n\n"
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

@bot.on(events.CallbackQuery(pattern=b"ui_adv"))
async def advanced_menu(event):
    f = settings_store.get_filters(event.sender_id)
    text = f"🚀 **Advanced настройки**\n\nЗум: {f.zoom}%\nПоворот: {f.rotate}°\nСкорость: {f.speed}x"
    kb = [[Button.inline("🔍 Зум", b"p_zoom"), Button.inline("🔄 Поворот", b"p_rot")],
          [Button.inline("🏃 Скорость", b"p_speed")], [Button.inline("⬅️ Назад", b"back_to_settings")]]
    await safe_edit(event, text, kb)

@bot.on(events.CallbackQuery(pattern=b"p_zoom"))
async def zoom_menu(event):
    f = settings_store.get_filters(event.sender_id)
    kb = [[Button.inline("+1%", b"sz_1"), Button.inline("+2%", b"sz_2"), Button.inline("+5%", b"sz_5")],
          [Button.inline("🔄 Сброс", b"sz_0")], [Button.inline("⬅️ Назад", b"ui_adv")]]
    await safe_edit(event, f"🔍 **Зум**: {f.zoom}%", kb)

@bot.on(events.CallbackQuery(pattern=b"sz_(\\d+)"))
async def set_zoom(event):
    f = settings_store.get_filters(event.sender_id)
    f.zoom = float(event.pattern_match.group(1).decode())
    settings_store.save_filters(event.sender_id, f)
    await event.answer(); await zoom_menu(event)

@bot.on(events.CallbackQuery(pattern=b"p_rot"))
async def rot_menu(event):
    f = settings_store.get_filters(event.sender_id)
    kb = [[Button.inline("-1°", b"sr_-1"), Button.inline("-0.3°", b"sr_-0.3"), Button.inline("+0.3°", b"sr_0.3"), Button.inline("+1°", b"sr_1")],
          [Button.inline("🔄 0°", b"sr_0")], [Button.inline("⬅️ Назад", b"ui_adv")]]
    await safe_edit(event, f"🔄 **Поворот**: {f.rotate}°", kb)

@bot.on(events.CallbackQuery(pattern=b"sr_(.*)"))
async def set_rot(event):
    f = settings_store.get_filters(event.sender_id)
    f.rotate = float(event.pattern_match.group(1).decode())
    settings_store.save_filters(event.sender_id, f)
    await event.answer(); await rot_menu(event)

@bot.on(events.CallbackQuery(pattern=b"p_speed"))
async def speed_menu(event):
    f = settings_store.get_filters(event.sender_id)
    kb = [[Button.inline("0.98x", b"ss_0.98"), Button.inline("1.01x", b"ss_1.01"), Button.inline("1.02x", b"ss_1.02")],
          [Button.inline("🔄 1.0x", b"ss_1.0")], [Button.inline("⬅️ Назад", b"ui_adv")]]
    await safe_edit(event, f"🏃 **Скорость**: {f.speed}x", kb)

@bot.on(events.CallbackQuery(pattern=b"ss_(.*)"))
async def set_speed(event):
    f = settings_store.get_filters(event.sender_id)
    f.speed = float(event.pattern_match.group(1).decode())
    settings_store.save_filters(event.sender_id, f)
    await event.answer(); await speed_menu(event)

@bot.on(events.CallbackQuery(pattern=b"ui_(bright|contrast|sharp|noise)"))
async def param_menu(event):
    p = event.pattern_match.group(1).decode()
    f = settings_store.get_filters(event.sender_id)
    titles = {"bright": "☀️ Яркость", "contrast": "🌓 Контраст", "sharp": "🔪 Резкость", "noise": "🌫 Шум"}
    kb = [[Button.inline("-10%", f"ad_{p}_-10"), Button.inline("-1%", f"ad_{p}_-1"), Button.inline("+1%", f"ad_{p}_1"), Button.inline("+10%", f"ad_{p}_10")],
          [Button.inline("🔄 Сброс", f"ad_{p}_0")], [Button.inline("⬅️ Назад", b"back_to_settings")]]
    await safe_edit(event, f"**{titles[p]}**", kb)

@bot.on(events.CallbackQuery(pattern=b"ad_(.*)_(.*)"))
async def adj_logic(event):
    p = event.pattern_match.group(1).decode(); v = int(event.pattern_match.group(2).decode())
    f = settings_store.get_filters(event.sender_id)
    if v == 0:
        if p == "bright": f.brightness.reset()
        elif p == "contrast": f.contrast.value = 1.0
        elif p == "sharp": f.sharpness.reset()
        elif p == "noise": f.noise.reset()
    else:
        if p == "bright": f.adjust_brightness(v)
        elif p == "contrast": f.adjust_contrast(v)
        elif p == "sharp": f.adjust_sharpness(v)
        elif p == "noise": f.adjust_noise(v)
    settings_store.save_filters(event.sender_id, f); await event.answer(); await param_menu(event)

@bot.on(events.CallbackQuery(pattern=b"ui_grid"))
async def grid_menu(event):
    f = settings_store.get_filters(event.sender_id)
    kb = [[Button.inline("🔄 Вкл/Выкл", b"g_tgl")], [Button.inline("⬅️ Назад", b"back_to_settings")]]
    await safe_edit(event, f"#️⃣ Сетка: {'ВКЛ' if f.grid_enabled else 'ВЫКЛ'}", kb)

@bot.on(events.CallbackQuery(pattern=b"g_tgl"))
async def g_tgl(event):
    f = settings_store.get_filters(event.sender_id); f.toggle_grid()
    settings_store.save_filters(event.sender_id, f); await event.answer(); await grid_menu(event)

@bot.on(events.CallbackQuery(pattern=b"back_to_settings"))
async def nav_s(event): await settings_main_menu(event)

@bot.on(events.CallbackQuery(pattern=b"f_reset_all"))
async def nav_r(event): settings_store.reset_filters(event.sender_id); await event.answer("Сброшено"); await settings_main_menu(event)

@bot.on(events.CallbackQuery(pattern=b"f_save_exit"))
async def nav_sv(event): await event.answer("✅ Сохранено", alert=True)

@bot.on(events.CallbackQuery(pattern=b"f_main_back"))
async def nav_b(event): await event.delete(); await start_handler(event)

# =====================================================
# ОБРАБОТКА (FFMPEG ENGINE)
# =====================================================

@bot.on(events.NewMessage(pattern="(Изменить битрейт|Отзеркалить|Наложить картинку|🚀 Только фильтры)"))
async def set_mode(event):
    user_id = event.sender_id; text = event.pattern_match.group(1)
    m = {"Изменить битрейт": "bitrate", "Отзеркалить": "mirror", "Наложить картинку": "picture", "🚀 Только фильтры": "filters"}
    user_states[user_id] = m[text]
    await event.respond(f"✅ Режим {text} активен. Пришли видео.")

@bot.on(events.NewMessage)
async def process_video(event):
    uid = event.sender_id; state = user_states.get(uid)
    if state and event.media and hasattr(event.media, "document") and "video" in event.media.document.mime_type:
        status = await event.respond("⏳ Обработка видео...")
        path = await event.client.download_media(event.media.document)
        out = f"mod_{uuid.uuid4()}.mp4"
        try:
            vf = get_full_filter_chain(uid, "hflip" if state == "mirror" else None)
            audio = get_audio_args(uid)
            
            # Базовая команда
            cmd = ["ffmpeg", "-y", "-i", path]
            
            if state == "picture":
                f_c = f"[0:v]{vf if vf else 'format=yuv420p'}[v_f]; [v_f][1:v]overlay=W-w-10:H-h-10,format=yuv420p[v]"
                cmd.extend(["-i", picture_path, "-filter_complex", f_c, "-map", "[v]", "-map", "0:a"])
            else:
                cmd.extend(["-vf", vf if vf else "format=yuv420p"])
            
            cmd.extend(audio)
            
            # Параметры качества и плавности
            cmd.extend([
                "-c:v", "libx264", "-crf", "23", "-preset", "veryfast",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                "-vsync", "vfr", "-map_metadata", "-1", out
            ])
            
            if state == "bitrate":
                cap = cv2.VideoCapture(path); fps = cap.get(cv2.CAP_PROP_FPS); frms = cap.get(cv2.CAP_PROP_FRAME_COUNT); cap.release()
                br = int((os.path.getsize(path) * 8 / (frms/fps)) * 0.7) if fps > 0 else 2000000
                cmd.insert(-1, "-b:v"); cmd.insert(-1, str(br))

            subprocess.call(cmd)
            await event.client.send_file(event.chat_id, out, caption="✅ Готово!")
            await status.delete()
        except Exception as e: await event.respond(f"❌ Ошибка: {e}")
        finally:
            if os.path.exists(path): os.remove(path)
            if os.path.exists(out): os.remove(out)

def main():
    print("Бот запущен...")
    bot.run_until_disconnected()

if __name__ == "__main__":
    main()
