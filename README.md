# 🎬 Navi-Automation — YouTube Shorts Pipeline

A **fully automated, 100% free-tier** Python pipeline that:
1. Generates a short video script with **Gemini AI**
2. Converts the script to a natural voiceover with **Microsoft Edge TTS**
3. Composes a 9:16 **YouTube Shorts**-optimised video with **MoviePy**
4. Uploads the video to YouTube via the **YouTube Data API v3**

> **Zero subscription costs · Zero credit cards required · Runs entirely locally**

---

## 📁 Project Structure

```
Navi-Automation/
├── main.py               # CLI entry point & pipeline orchestrator
├── config.py             # Environment variable loader & validation
├── script_generator.py   # Gemini AI script generation
├── voice_generator.py    # Edge TTS voiceover synthesis
├── video_editor.py       # MoviePy video composition
├── uploader.py           # YouTube Data API v3 uploader
├── requirements.txt      # Python dependencies
├── .env.example          # Template environment file
├── .env                  # Your actual secrets (create this yourself)
├── client_secrets.json   # YouTube OAuth credentials (see setup below)
├── token.json            # Auto-generated after first OAuth login
└── output/               # Generated audio and video files
```

---

## ⚡ Quick Start

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10 or higher |
| FFmpeg | Any recent version |
| Internet | Required for API calls |

### 1. Install FFmpeg

FFmpeg is required by MoviePy to encode video.

**Windows:**
```powershell
# Option A – winget (recommended)
winget install Gyan.FFmpeg

# Option B – Chocolatey
choco install ffmpeg

# Option C – Manual
# Download from https://www.gyan.dev/ffmpeg/builds/
# Extract and add the `bin` folder to your PATH
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt update && sudo apt install ffmpeg -y
```

Verify: `ffmpeg -version`

---

### 2. Clone & Install Python Dependencies

```bash
git clone https://github.com/your-username/Navi-Automation.git
cd Navi-Automation

# Create a virtual environment (strongly recommended)
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

---

### 3. Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env
```

Open `.env` in any text editor and fill in your keys:

```ini
GEMINI_API_KEY=your_key_here   # Required
PEXELS_API_KEY=                # Optional – leave blank to use animated background
PIXABAY_API_KEY=               # Optional – leave blank to use animated background
```

---

## 🔑 API Key Setup Guide

### A. Gemini API Key (Required)

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **"Create API key"** → Select any Google Cloud project (or create a new one)
3. Copy the key — it looks like `AIzaSy...`
4. Paste it into `.env` as `GEMINI_API_KEY=AIzaSy...`

> **Free tier:** Gemini 1.5 Flash offers 15 requests/minute and 1 million tokens/day at no cost.

---

### B. Pexels API Key (Optional)

Stock footage adds professional visual quality to your videos.

1. Go to [pexels.com/api](https://www.pexels.com/api/)
2. Click **"Get Started"** and create a free account
3. Navigate to **[Your Apps](https://www.pexels.com/api/new/)** and create an application
4. Copy the API key and paste it into `.env` as `PEXELS_API_KEY=...`

> **Free tier:** 25,000 requests/month — more than enough.

---

### C. Pixabay API Key (Optional)

An alternative to Pexels; used as a fallback.

1. Go to [pixabay.com/api/docs](https://pixabay.com/api/docs/)
2. Register for a free account and log in
3. Your API key is shown on the documentation page
4. Paste it into `.env` as `PIXABAY_API_KEY=...`

---

### D. YouTube Data API v3 (Required for uploading)

> **Skip this section if you only want to generate videos locally using `--no-upload`.**

This is the most involved step, but only needs to be done **once**.

#### Step 1 — Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Click the project dropdown (top-left) → **"New Project"**
3. Name it `Navi-Automation` (or anything) → **Create**
4. Make sure the new project is selected in the dropdown

#### Step 2 — Enable the YouTube Data API

1. In the left sidebar → **"APIs & Services"** → **"Library"**
2. Search for `YouTube Data API v3`
3. Click on it → **"Enable"**

#### Step 3 — Create OAuth 2.0 Credentials

1. Go to **"APIs & Services"** → **"Credentials"**
2. Click **"+ Create Credentials"** → **"OAuth client ID"**
3. If prompted to configure the consent screen:
   - Click **"Configure Consent Screen"**
   - Select **"External"** → **"Create"**
   - Fill in **App name**: `Navi-Automation`
   - Fill in **User support email**: your Google email
   - Fill in **Developer contact email**: your Google email
   - Click **"Save and Continue"** through all steps
   - On the **Test users** page, click **"+ Add Users"** and add **your own Gmail address**
   - Click **"Save and Continue"** → **"Back to Dashboard"**
4. Back on the Credentials page, click **"+ Create Credentials"** → **"OAuth client ID"** again
5. **Application type:** `Desktop app`
6. **Name:** `Navi-Automation Desktop`
7. Click **"Create"**
8. In the popup, click **"Download JSON"**
9. Rename the downloaded file to `client_secrets.json`
10. Move it to the `Navi-Automation/` project folder

#### Step 4 — First Run (Browser Consent)

On the very first upload, a browser window will open automatically:

```bash
python main.py "your topic here"
```

- A browser window opens → Sign in with the Gmail you added as a test user
- Click **"Allow"** to grant access
- The browser shows `"The authentication flow has completed"` — you can close it
- A `token.json` file is created in the project folder

**All future runs** will be fully headless — no browser interaction needed.

---

## 🚀 Usage

### Basic — Generate & Upload

```bash
python main.py "3 mind-blowing facts about black holes"
```

### Generate Only (No Upload)

```bash
python main.py "Python tips every developer should know" --no-upload
```

### Set Privacy to Public

```bash
python main.py "morning routine habits" --privacy public
```

### Use a Different Voice

```bash
# List all available voices first
python -c "from voice_generator import list_voices; list_voices()"

# Use Jenny's voice
python main.py "5 coffee facts" --voice en-US-JennyNeural
```

### Custom Output Directory

```bash
python main.py "ocean mysteries" --output-dir my_videos/today
```

### Keep All Intermediate Files

```bash
python main.py "AI breakthroughs 2025" --no-upload --keep-files
```

### Full Options Reference

```
usage: main.py [-h] [--topic TOPIC] [--no-upload] [--privacy {public,unlisted,private}]
               [--voice VOICE] [--output-dir OUTPUT_DIR] [--keep-files]
               [topic]

positional arguments:
  topic                          Video topic

optional arguments:
  -h, --help                     show this help message and exit
  --topic TOPIC                  Alternative way to pass the topic
  --no-upload                    Skip the YouTube upload step
  --privacy {public,unlisted,private}
                                 YouTube video privacy (default: unlisted)
  --voice VOICE                  Edge TTS voice name
  --output-dir OUTPUT_DIR        Override output directory
  --keep-files                   Keep intermediate audio/background files
```

---

## 🏗️ Architecture Overview

```
main.py
  │
  ├─► config.py            Load .env → typed constants
  │
  ├─► script_generator.py  Gemini API → JSON { script, title, description, tags, keywords }
  │
  ├─► voice_generator.py   Edge TTS (async) → output/voiceover.mp3
  │
  ├─► video_editor.py      Pexels/Pixabay clip (or gradient fallback)
  │                         + audio → output/final_video.mp4 (1080×1920)
  │
  └─► uploader.py          OAuth2 token → YouTube Data API v3 → video ID
```

### Visual Fallback Chain

```
1. Fetch portrait clip from Pexels  ──► success → use it
         │ fail / no key
         ▼
2. Fetch portrait clip from Pixabay ──► success → use it
         │ fail / no key
         ▼
3. Generate animated gradient background with MoviePy (always succeeds)
```

---

## 🔧 Configuration Reference

All settings live in `.env`. Copy from `.env.example`.

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Your Gemini API key |
| `PEXELS_API_KEY` | *(blank)* | Pexels video API key (optional) |
| `PIXABAY_API_KEY` | *(blank)* | Pixabay video API key (optional) |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Model name (`gemini-2.0-flash` also works) |
| `TTS_VOICE` | `en-US-ChristopherNeural` | Edge TTS voice |
| `TTS_RATE` | `+0%` | Speech rate (`+10%` = faster) |
| `TTS_VOLUME` | `+0%` | Audio volume offset |
| `VIDEO_WIDTH` | `1080` | Output video width in pixels |
| `VIDEO_HEIGHT` | `1920` | Output video height in pixels |
| `VIDEO_FPS` | `30` | Frames per second |
| `VIDEO_CODEC` | `libx264` | FFmpeg video codec |
| `AUDIO_CODEC` | `aac` | FFmpeg audio codec |
| `VIDEO_BITRATE` | `4000k` | Video bitrate |
| `OUTPUT_DIR` | `output` | Where to save generated files |
| `CLIENT_SECRETS_FILE` | `client_secrets.json` | YouTube OAuth secrets path |
| `TOKEN_FILE` | `token.json` | Cached OAuth token path |
| `DEFAULT_PRIVACY_STATUS` | `unlisted` | `public` / `unlisted` / `private` |
| `DEFAULT_CATEGORY_ID` | `22` | YouTube category (22 = People & Blogs) |

### Common YouTube Category IDs

| ID | Category |
|---|---|
| 22 | People & Blogs |
| 24 | Entertainment |
| 27 | Education |
| 28 | Science & Technology |

---

## 🐛 Troubleshooting

### `ffmpeg not found` / `MoviePy: cannot find ffmpeg`
→ Install FFmpeg and ensure it's on your system PATH. Verify with `ffmpeg -version`.

### `GEMINI_API_KEY is not set`
→ Copy `.env.example` to `.env` and add your key.

### `client_secrets.json not found`
→ Follow the **YouTube Data API v3** setup steps above to download the file.

### `Token refresh failed`
→ Delete `token.json` and re-run; a new browser login will be triggered.

### `quota exceeded` on Gemini
→ You've hit the free-tier rate limit. Wait 1 minute and retry, or switch to `gemini-2.0-flash` in `.env`.

### Video has no sound
→ Make sure FFmpeg was installed with AAC codec support (`ffmpeg -codecs | grep aac`).

### `HttpError 403` on YouTube upload
→ Ensure the YouTube Data API v3 is enabled in your Google Cloud project AND your Gmail is listed as a Test User in the OAuth consent screen.

### `HttpError 400: invalid video`
→ The exported video file may be corrupted. Run with `--keep-files` and inspect `output/final_video.mp4` manually.

---

## 📝 License

MIT License — free for personal and commercial use.

---

## 🤝 Contributing

Pull requests welcome! Please open an issue first to discuss major changes.
