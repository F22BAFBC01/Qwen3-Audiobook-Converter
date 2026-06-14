# 🚀 Quick Start Guide

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

**Important**: Also install FFmpeg separately:
- Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
- Linux: `sudo apt-get install ffmpeg`
- Mac: `brew install ffmpeg`

## Step 2: Start Qwen Voice Model

1. Start your Qwen Gradio interface
2. Ensure it's running on `http://127.0.0.1:7860` (default)
3. Verify the API is accessible

## Step 3: Configure the Converter

Edit the configuration section at the top of `audiobook_converter.py`:

### For Custom Voice (Easiest - Recommended)

```python
VOICE_MODE = "custom_voice"
CUSTOM_VOICE_SPEAKER = "Ryan"  # Try: Ryan, Serena, Aiden, etc.
CUSTOM_VOICE_LANGUAGE = "English"
```

### For Voice Cloning

```python
VOICE_MODE = "voice_clone"
VOICE_CLONE_REF_AUDIO = r"C:/path/to/your/reference_audio.wav"
VOICE_CLONE_REF_TEXT = "The text spoken in the reference audio"
```

### For Voice Design

```python
VOICE_MODE = "voice_design"
VOICE_DESIGN_DESCRIPTION = "Speak in a clear, professional narrator voice."
```

## Step 4: Add Your Books

Place your books in the `book_to_convert/` folder:
- Supported formats: `.txt`, `.pdf`, `.epub`, `.docx`, `.doc`
- For best results, use a **formatted audiobook `.txt`** with blank-line markers:
  - 1 blank line = short paragraph pause (~0.6 s)
  - 2 blank lines = section pause (~1.5 s)
  - 3+ blank lines = chapter/major pause (~2.5 s)

## Step 5: Run the Converter

```bash
# Custom voice (default)
python audiobook_converter.py

# Voice clone with reference audio + transcript
python audiobook_converter.py --voice-clone --voice-sample path/to/reference.wav --transcript path/to/transcript.txt
```

The converter preserves paragraph/chapter breaks from your text file and inserts silence between audio segments at those boundaries.

## Step 6: Find Your Audiobook

Your completed audiobook will be in `audiobooks/<book title>/` as numbered section files:

```
audiobooks/My Book/
  01_Preface.mp3
  02_Introduction.mp3
  03_Chapter_2_The_Cost_of_Not_Having_Healthy_Boundaries.mp3
  ...
```

Each file is one chapter or front/back-matter section (ACX-style). ID3 tags include track number, section title, and book title for proper sorting in audiobook apps.

## Troubleshooting

**Can't connect to Qwen API?**
- Make sure Qwen Gradio is running
- Check the URL in configuration matches your Qwen server
- Try: `curl http://127.0.0.1:7860/` to test connection

**FFmpeg not found?**
- Install FFmpeg and add it to your system PATH
- Restart your terminal after installation

**Need help?**
- See `README.md` for detailed documentation
- Check `Qwen-API.md` for API details
