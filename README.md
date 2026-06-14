# 🎧 Qwen Audiobook Converter

> ## ⚠️ Fork notice — read before using
>
> **This is a modified fork** of [WhiskeyCoder/Qwen3-Audiobook-Converter](https://github.com/WhiskeyCoder/Qwen3-Audiobook-Converter). It is **not** the upstream project and **may contain bugs** introduced during customization.
>
> **What changed in this fork (high level):**
>
> - **Audiobook-oriented text handling** — preserves paragraph/chapter blank lines and inserts silence at those boundaries (instead of flattening all whitespace).
> - **One MP3 per section** — ACX-style numbered chapter files in `audiobooks/<book title>/`, with ID3 track metadata (`mutagen`).
> - **Structured EPUB extraction** — general-purpose semantic parsing for EPUBs (spine order, HTML roles/classes) to skip blurbs, TOC noise, and back matter; falls back to plain HTML extraction if needed.
> - **Smaller TTS chunks** for voice clone, title/section delivery tweaks, and narration `instruct` strings for custom voice mode.
> - **New modules:** `book_text.py`, `book_format.py`, `mp3_tags.py`.
>
> If something breaks, compare against upstream or [open an issue](https://github.com/F22BAFBC01/Qwen3-Audiobook-Converter/issues) on this fork. For the original behavior, use the upstream repo.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Qwen](https://img.shields.io/badge/Powered%20by-Qwen%20Voice-orange.svg)](https://github.com/QwenLM/Qwen3-TTS)

Convert PDFs, EPUBs, DOCX, DOC, and TXT files into high-quality audiobooks using **Qwen3 TTS Voice Model** - an open-source voice synthesis system that excels at natural speech generation and voice cloning.

## ✨ Features

- 🎤 **Dual Voice Modes**
  - **Custom Voice**: Pre-built high-quality speakers (Ryan, Serena, Aiden, etc.) with optimized audiobook narration style
  - **Voice Clone**: Clone any voice from a reference audio sample with automatic transcription
- 📚 **Multi-Format Support**: TXT, PDF, EPUB, DOCX, DOC
- 🤖 **Always 1.7B Model**: Uses the highest quality model for best results
- 🔄 **Smart Chunking**: Intelligent text splitting with sentence boundary detection
- 💾 **Intelligent Caching**: Avoids re-processing identical chunks
- 🔁 **Robust Error Handling**: Automatic retries and graceful failure recovery
- 📊 **Progress Tracking**: Real-time conversion progress with time estimates
- 🧹 **Auto Cleanup**: Automatic cleanup of temporary files, even on failure

## 🔊 Audio Demo

🎧 **Sample Output**  
<figure>
  <figcaption>Listen to the T-Rex:</figcaption>
  <audio controls src="https://github.com/WhiskeyCoder/Qwen3-Audiobook-Converter/blob/main/sample/test_audio.mp3"></audio>
  <a href="https://github.com/WhiskeyCoder/Qwen3-Audiobook-Converter/blob/main/sample/test_audio.mp3"> Download audio </a>
</figure>

No it's not broken, it's a raw mp3 file download it and play it, you can't embedded audio in a readme.md GitHub whenthe sample is on GitHub

## 🚀 Quick Start

### Prerequisites

1. **Qwen Voice Model** running locally
   - Download and run the Qwen3 TTS Gradio interface (One Click install with Pinokio)
   - Server should be accessible at `http://127.0.0.1:7860`
2. **Python 3.8+** with pip
3. **FFmpeg** - Required for audio processing

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/WhiskeyCoder/Qwen3-Audiobook-Converter.git
   cd Qwen3-Audiobook-Converter
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install FFmpeg**:
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) or `choco install ffmpeg`
   - **Linux**: `sudo apt-get install ffmpeg`
   - **macOS**: `brew install ffmpeg`

4. **Start Qwen Voice Model**:
   - Run your Qwen Gradio interface
   - Verify it's accessible at `http://127.0.0.1:7860`

5. **Add your books**:
   ```bash
   # Place your books in the book_to_convert folder
   cp your_book.pdf book_to_convert/
   ```

6. **Run the converter**:
   ```bash
   # Default: Custom Voice mode (Ryan speaker, English)
   python audiobook_converter.py

   # Voice Clone mode with automatic transcription
   python audiobook_converter.py --voice-clone --voice-sample path/to/reference.wav

   # Voice Clone mode with manual transcription
   python audiobook_converter.py --voice-clone --voice-sample path/to/reference.wav --transcript path/to/transcript.txt
   ```

## 📋 Requirements

### Python Dependencies

```
gradio_client>=0.7.0
requests>=2.28.0
PyPDF2>=3.0.0
ebooklib>=0.18
pydub>=0.25.1
python-docx>=0.8.11
docx2txt>=0.8
beautifulsoup4>=4.11.0
```

### System Requirements

- **Python**: 3.8 or higher
- **FFmpeg**: Required for audio processing (install separately)
- **Qwen Voice Model**: Running locally with Gradio API enabled
- **RAM**: 4GB+ recommended
- **Storage**: ~100MB per hour of audiobook

## ⚙️ Configuration

### Hardcoded Settings

The converter uses optimized hardcoded settings for best audiobook quality:

- **Speaker**: Ryan (professional male narrator)
- **Language**: English
- **Model Size**: 1.7B (always - highest quality)
- **Input Folder**: `book_to_convert/`
- **Output Folder**: `audiobooks/`
- **Style Instruction**: Optimized for engaging, professional audiobook narration

### Voice Modes

#### Custom Voice Mode (Default)

Uses the pre-built Ryan speaker with optimized audiobook narration style. Best for most use cases.

```bash
python audiobook_converter.py
```

**Available Speakers** (can be changed in code):
- `Ryan` - Male, clear and professional (default)
- `Serena` - Female, warm and friendly
- `Aiden` - Male, energetic
- `Dylan` - Male, calm
- `Eric` - Male, expressive
- `Ono_anna` - Female, Japanese accent
- `Sohee` - Female, Korean accent
- `Uncle_fu` - Male, Chinese accent
- `Vivian` - Female, versatile

#### Voice Clone Mode

Clone a specific voice from a reference audio file. The reference audio is automatically transcribed using Qwen's Whisper model.

```bash
python audiobook_converter.py --voice-clone --voice-sample path/to/reference.wav
```

**Requirements**:
- Reference audio file in WAV format
- Audio will be automatically transcribed (no need to provide text)
- Higher quality reference audio = better cloning results

### Processing Settings

| Setting | Value | Description |
|---------|-------|-------------|
| `CHUNK_SIZE_WORDS` | 1200 | Words per processing chunk |
| `MAX_WORKERS` | 1 | Concurrent chunks (keep at 1 to avoid rate limiting) |
| `AUDIO_FORMAT` | mp3 | Output format |
| `AUDIO_BITRATE` | 128k | Audio quality |
| `MAX_RETRIES` | 3 | Retry attempts for failed chunks |

## 📖 Supported File Formats

| Format | Extension | Status |
|--------|-----------|--------|
| Plain Text | `.txt` | ✅ Full support |
| PDF | `.pdf` | ✅ Full support |
| EPUB | `.epub` | ✅ Full support |
| Word Document | `.docx` | ✅ Full support (requires python-docx) |
| Legacy Word | `.doc` | ✅ Full support (requires docx2txt) |

## 🎯 Usage Examples

### Basic Conversion

```bash
# Place your book in the input folder
cp "my_book.pdf" book_to_convert/

# Run the converter
python audiobook_converter.py

# Output will be in: audiobooks/my_book.mp3
```

### Batch Processing

```bash
# Add multiple books
cp *.pdf book_to_convert/
cp *.epub book_to_convert/

# Convert all at once
python audiobook_converter.py
```

### Voice Cloning

```bash
# Clone a voice from reference audio
python audiobook_converter.py \
  --voice-clone \
  --voice-sample "reference_audio.wav"
```

The reference audio will be automatically transcribed, so you don't need to provide the text manually.

## 📁 Project Structure

```
qwen-audiobook-converter/
├── audiobook_converter.py    # Main conversion script
├── requirements.txt          # Python dependencies
├── README.md                # This file
├── LICENSE                  # MIT License
├── .gitignore              # Git ignore rules
├── book_to_convert/        # 📚 Input folder (place books here)
├── audiobooks/             # 🎧 Output folder (audiobooks saved here)
├── chunks/                 # ⚡ Temporary processing files (auto-cleaned)
├── cache/                  # 💾 Cached audio chunks
│   └── audio_chunks/
└── logs/                   # 📊 Processing logs
    └── audiobook_YYYYMMDD.log
```

## 🔍 How It Works

1. **Text Extraction**: Extracts text from various document formats (PDF, EPUB, DOCX, etc.)
2. **Intelligent Chunking**: Splits text into optimal chunks (~1200 words) while respecting sentence boundaries
3. **Voice Generation**: Sends chunks to Qwen API for voice synthesis using 1.7B model
4. **Progress Tracking**: Monitors chunk processing with real-time progress updates
5. **Audio Assembly**: Combines processed chunks into final audiobook
6. **Cleanup**: Automatically removes temporary files, even on failure

## 🛠️ Troubleshooting

### Qwen API Connection Failed

```
[ERROR] Cannot connect to Qwen API!
```

**Solutions**:
- Ensure Qwen Gradio server is running
- Check if server is accessible: `curl http://127.0.0.1:7860/`
- Verify firewall settings
- Check the `QWEN_API_URL` in the code matches your server

### Voice Clone Mode Errors

```
[ERROR] Configuration Error! Voice Clone mode requires a reference audio file.
```

**Solutions**:
- Ensure `--voice-sample` points to a valid WAV file
- Verify the audio file exists and is readable
- Check file format (must be WAV)

### No Text Extracted

```
[ERROR] No text extracted from document
```

**Solutions**:
- Verify file isn't corrupted
- Check if document contains selectable text (not just images)
- For image-based PDFs, use OCR first
- Try a different file format

### Processing Takes Too Long

**Solutions**:
- Each chunk takes ~4-5 minutes with 1.7B model (this is normal)
- Estimated time is shown: `~{chunks * 4} minutes`
- Processing is sequential to avoid rate limiting
- Large books will take time - be patient

### FFmpeg Not Found

```
[ERROR] FFmpeg not found
```

**Solutions**:
- Install FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html)
- Add FFmpeg to your system PATH
- Restart terminal/IDE after installation

### Chunks Not Cleaning Up

The script automatically cleans up chunks, but if they persist:

```bash
# Manually clean up
rm -rf chunks/*.wav
```

## 🔧 Advanced Usage

### Modifying Configuration

To change settings like speaker, language, or chunk size, edit the hardcoded configuration at the top of `audiobook_converter.py`:

```python
# Hardcoded Voice Settings
CUSTOM_VOICE_SPEAKER = "Ryan"  # Change to Serena, Aiden, etc.
CUSTOM_VOICE_LANGUAGE = "English"
CHUNK_SIZE_WORDS = 1200  # Adjust chunk size
AUDIO_BITRATE = "128k"  # Change to 192k or 256k for higher quality
```

### Custom Chunking

The chunking algorithm respects sentence boundaries. To modify chunking behavior, edit the `split_into_chunks` method in `audiobook_converter.py`.

### Logging

Logs are saved to `logs/audiobook_YYYYMMDD.log` with detailed information about:
- Text extraction progress
- Chunk processing status
- API calls and responses
- Errors and warnings

## 📊 Performance

- **Processing Speed**: ~4-5 minutes per chunk (1.7B model)
- **Quality**: High-quality audio output suitable for audiobooks
- **Memory Usage**: ~2-4GB RAM during processing
- **Storage**: ~1MB per minute of audio (128kbps MP3)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/WhiskeyCoder/qwen-audiobook-converter.git
cd qwen-audiobook-converter

# Install dependencies
pip install -r requirements.txt

# Make your changes
# Test thoroughly
# Submit PR
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **[Qwen Voice Model](https://github.com/QwenLM/Qwen3-TTS)** - Open-source voice synthesis technology
- **[Gradio](https://gradio.app/)** - API interface framework
- All contributors and users of this project

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/WhiskeyCoder/Qwen3-Audiobook-Converter/issues)
- **Documentation**: See `Qwen-API.md` for detailed API documentation
- **Questions**: Open a discussion on GitHub

## 🔮 Roadmap

- [ ] GUI interface for easier configuration
- [ ] Chapter detection and automatic splitting
- [ ] Multiple output formats (M4B, OGG, FLAC)
- [ ] Real-time preview functionality
- [ ] Voice quality enhancement options
- [ ] Batch voice model switching
- [ ] Progress persistence (resume interrupted conversions)

## ⭐ Star History

If you find this project useful, please consider giving it a star! ⭐

---

**Made with ❤️ for the audiobook community**
