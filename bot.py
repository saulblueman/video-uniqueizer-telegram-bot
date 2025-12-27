import os
import uuid
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient, events, Button
from filters_manager import VideoFilters
from settings_store import SettingsStore

load_dotenv()
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
store = SettingsStore()

async def run_ffmpeg(input_path, output_path, rnd):
    vf = (f"eq=brightness={rnd['brightness']}:contrast={rnd['contrast']}:saturation={rnd['saturation']},"
          f"scale={rnd['zoom']}*iw:-1,crop=iw/{rnd['zoom']}:ih/{rnd['zoom']},setpts={1/rnd['speed']}*PTS")
    cmd = ['ffmpeg', '-y', '-i', input_path, '-vf', vf, '-pix_fmt', 'yuv420p', '-movflags', '+faststart', 
           '-vsync', 'vfr', '-map_metadata', '-1', '-c:v', 'libx264', '-crf', '23', output_path]
    p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await p.communicate()
    return p.returncode == 0

def get_dashboard(user_id, title="⚙️ Настройки"):
    s = store.get_user_settings(user_id)
    f = s['filters']
    buttons = [
        [Button.inline(f"Яркость: ±{int(f['brightness']*100)}%", b"e_brightness")],
        [Button.inline(f"Контраст: ±{int(f['contrast']*100)}%", b"e_contrast")],
        [Button.inline(f"Насыщ.: ±{int(f['saturation']*100)}%", b"e_saturation")],
        [Button.inline(f"Зум: {int(f['zoom']*100)}%", b"e_zoom")],
        [Button.inline(f"Скорость: ±{int(f['speed']*100)}%", b"e_speed")],
        [Button.inline(f"👯 Копий: {s['copies_count']}", b"e_copies"), 
         Button.inline(f"📦 Пакет: {s['batch_size']}", b"e_batch")],
        [Button.inline("❌ Закрыть меню", b"close")]
    ]
    return f"**{title}**", buttons

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    text, buttons = get_dashboard(event.sender_id, "🎬 Uniqueizer Bot запущен")
    await event.respond(text, buttons=buttons)

@client.on(events.CallbackQuery())
async def handler(event):
    data = event.data.decode()
    user_id = event.sender_id
    if data == "close":
        await event.delete()
        return

    param_map = {
        "e_brightness": ("яркость (%)", "brightness"), "e_contrast": ("контраст (%)", "contrast"),
        "e_saturation": ("насыщенность (%)", "saturation"), "e_zoom": ("зум (%)", "zoom"),
        "e_speed": ("скорость (%)", "speed"), "e_copies": ("кол-во копий", "copies_count"),
        "e_batch": ("размер пакета", "batch_size")
    }

    if data in param_map:
        label, key = param_map[data]
        async with client.conversation(user_id) as conv:
            await conv.send_message(f"Введите значение для **{label}**:")
            res = await conv.get_response()
            if res.text.isdigit():
                val = int(res.text)
                if data.startswith("e_"):
                    if "copies" in data or "batch" in data:
                        s = store.get_user_settings(user_id); s[key] = val
                        if key == "batch_size": s['current_batch_count'] = 0
                        store.save_user_settings(user_id, s)
                    else:
                        store.update_filter(user_id, key, val/100)
                text, buttons = get_dashboard(user_id, "✅ Настройки обновлены")
                await event.respond(text, buttons=buttons)

@client.on(events.NewMessage(func=lambda e: e.video))
async def handle_video(event):
    user_id = event.sender_id
    settings = store.get_user_settings(user_id)
    settings['current_batch_count'] += 1
    store.save_user_settings(user_id, settings)
    
    curr, total = settings['current_batch_count'], settings['batch_size']
    status = await event.respond(f"📥 Видео {curr}/{total} получено...")

    input_fn = f"in_{uuid.uuid4().hex}.mp4"
    await event.download_media(file=input_fn)
    f_conf = VideoFilters.from_dict(settings['filters'])
    
    for i in range(1, settings['copies_count'] + 1):
        await status.edit(f"⚙️ Видео {curr}/{total} | Копия {i}/{settings['copies_count']}...")
        out_fn = f"out_{uuid.uuid4().hex}.mp4"
        vals, desc = f_conf.generate_random_state()
        
        if await run_ffmpeg(input_fn, out_fn, vals):
            # НОВЫЙ ФОРМАТ ПОДПИСИ
            caption = (
                f"📦 Видео {curr} из {total}\n"
                f"✅ Копия {i}/{settings['copies_count']}\n"
                f"🛠 Параметры: `{desc}`"
            )
            await event.client.send_file(event.chat_id, out_fn, caption=caption, parse_mode='markdown')
        
        if os.path.exists(out_fn): os.remove(out_fn)

    if os.path.exists(input_fn): os.remove(input_fn)

    if curr >= total:
        await event.respond("🏁 Пакет полностью обработан!")
        settings['current_batch_count'] = 0
        store.save_user_settings(user_id, settings)
        text, buttons = get_dashboard(user_id)
        await event.respond(text, buttons=buttons)

if __name__ == '__main__':
    client.run_until_disconnected()
