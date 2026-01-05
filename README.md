# 🚀 Video Uniqueizer Bot (Ultimate Advanced Version)

This manual is intended for **Linux (Ubuntu/Debian)** based systems. The bot is built using the **Telethon** library and utilizes the full power of **FFmpeg** for deep video stream reprocessing.

## 🌟 Advanced Version Full Functionality

Unlike standard scripts, this bot implements a multi-level uniqueization system managed through dynamic settings (the `settings_store.py` module).

### 1. Visual Transformations (Video Filters)

* **🪞 Mirroring:** Horizontal video flip.
* **📐 Rotate:** Micro-rotation by an arbitrary degree to change the frame geometry.
* **🔍 Zoom/Crop:** Smart edge cropping (from 1% to 10%) that removes technical tags and watermarks from the edges.
* **🎬 FPS Change:** Recalculating the number of frames per second, which completely alters the file's temporal structure.

### 2. Deep Color Correction and Effects

* **🎨 Color Tuning:** Adjusting brightness, contrast, and saturation.
* **✨ Sharpness:** Enhancing detail or applying a slight blur to change the hash.
* **🧂 Noise:** Adding barely noticeable grain, making every frame unique for neural networks.
* **🏁 Drawgrid:** Overlaying a thin, subtle grid over the video with adjustable transparency.

### 3. Audio Uniqueization

* **🎵 Audio Pitch/Speed:** Changing the tone and speed of the audio stream. This allows bypassing "Audio Fingerprint" detection while maintaining speech intelligibility.
* **🔇 Audio Removal:** Option for complete removal of the audio track.

### 4. Technical Parameters and Protection

* **📉 Bitrate Modification:** Reassembling the video using **CRF (Constant Rate Factor)**. This allows changing the file weight and internal structure without visible quality loss.
* **🖼 Overlay:** Automatic overlay of a watermark or image (defaults to `best_offer.png`).
* **🧹 Metadata Cleaning:** Automatic removal of all metadata (EXIF, GPS, device, and software data).
* **💾 User Persistence:** All individual user preferences are saved in `user_settings.json` and are not reset after a bot restart.

---

## 🛠 Installation on Linux (Ubuntu/Debian)

### 1. Prerequisites

Ensure FFmpeg and Python components are installed on your system:

```bash
sudo apt update && sudo apt install ffmpeg python3-pip python3-venv -y

```

### 2. Installation Steps

```bash
# Clone the repository
git clone https://github.com/saulblueman/video-uniqueizer-telegram-bot.git
cd video-uniqueizer-telegram-bot

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

```

### 3. Environment Configuration

Create a `.env` file in the project root:

```bash
nano .env

```

Insert your credentials (obtainable at [my.telegram.org](https://my.telegram.org)):

```env
API_ID=12345678
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token

```

### 4. Asset Preparation

1. **Logo:** Place the `best_offer.png` file in the root folder for the Overlay function.
2. **Storage:** The `user_settings.json` file will be created automatically. The `settings_store.py` module uses it to store states (on/off) and filter values for each Telegram ID.

### 5. Launch

```bash
python3 bot.py

```

## 📂 Settings Structure (settings_store.py)

The bot supports saving the following parameters for each user:

* `is_mirror`: enables mirroring.
* `is_blur`: blur mode.
* `is_noise`: noise overlay.
* `is_rotate`: micro-rotation.
* `is_zoom`: frame zooming.
* `is_speed`: speed modification (1.01x - 1.1x).
* `is_bitrate`: quality/bitrate management.
* `is_metadata`: metadata cleaning.
* `is_logo`: image overlay.

---

*Note: This tool is designed to automate routine video processing tasks. Please use it in accordance with platform policies.*
