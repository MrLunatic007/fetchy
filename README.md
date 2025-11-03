# Fetchy Download Manager

A powerful download manager for Linux with GUI, CLI, and Firefox browser integration. Similar to IDM/XDM but built specifically for Linux with modern Python technologies.

## Features

✨ **Multi-threaded Downloading**: Split files into chunks and download in parallel for maximum speed

🎨 **Beautiful GUI**: Modern PyQt6 interface with real-time progress tracking

⚡ **Powerful CLI**: Full-featured command-line interface for automation

🦊 **Firefox Integration**: Browser extension to intercept downloads automatically

📊 **Download Queue**: Manage multiple downloads with pause/resume support

🔄 **Resume Support**: Continue interrupted downloads from where they left off

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Firefox or Firefox-based browser (for extension)

### Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/fetchy.git
cd fetchy

# Run the installation script
chmod +x setup.sh
./setup.sh
```

The script will:
- Install Python dependencies (requests, PyQt6, rich)
- Create CLI and GUI launchers
- Set up the desktop entry
- Configure native messaging for Firefox

## Usage

### CLI Interface

```bash
# Download a file
fetchy download https://example.com/file.zip

# Download with custom output and threads
fetchy download https://example.com/file.zip -o myfile.zip -t 8

# Add to queue without starting
fetchy add https://example.com/file.zip

# View download queue
fetchy queue

# Process all queued downloads
fetchy process

# Get file information
fetchy info https://example.com/file.zip

# Clear completed downloads
fetchy clear
```

### GUI Interface

Launch the GUI:
```bash
fetchy-gui
```

Or from your application menu: **Applications → Internet → Fetchy Download Manager**

Features:
- Add downloads by pasting URLs
- Monitor progress with live speed updates
- Pause/Resume/Cancel individual downloads
- Adjust number of threads per download
- Right-click context menu for quick actions

### Firefox Extension

#### Installation

1. Open Firefox and navigate to: `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Navigate to the `extension/` folder and select `manifest.json`
4. Copy the extension ID that appears
5. Edit `~/.mozilla/native-messaging-hosts/com.fetchy.downloader.json`
6. Replace `{YOUR_EXTENSION_ID}@fetchy.com` with your actual extension ID

#### Usage

Once installed, the extension will:
- Automatically intercept downloads larger than 1 MB
- Send them to Fetchy for accelerated downloading
- Show notifications when downloads are added

You can:
- Toggle auto-intercept on/off from the extension popup
- Adjust minimum file size threshold
- Manually add URLs through the popup
- Right-click links and select "Download with Fetchy"

#### Supported Browsers

- Firefox
- Librewolf
- Waterfox
- Other Firefox-based browsers

## Project Structure

```
fetchy/
├── main.py                  # Main entry point
├── connection_manager.py    # HTTP connection handling
├── downloader.py           # Core download engine
├── gui.py                  # PyQt6 GUI application
├── cli.py                  # CLI interface
├── native_host.py          # Browser native messaging host
├── setup.sh                # Installation script
├── extension/              # Firefox extension
│   ├── manifest.json
│   ├── background.js
│   ├── popup.html
│   ├── popup.js
│   └── icons/
└── README.md
```

## Configuration

### CLI Queue Storage
Queue data is stored in: `~/.fetchy/queue.json`

### Extension Settings
- **Auto-intercept**: Automatically capture downloads
- **Min file size**: Only intercept files larger than this threshold (default: 1 MB)

### Download Settings
- **Threads**: Number of parallel connections (1-16, default: 4)
- **Output path**: Custom save location for downloads

## Advanced Usage

### Batch Downloads

Create a file with URLs (one per line):
```
https://example.com/file1.zip
https://example.com/file2.tar.gz
https://example.com/file3.iso
```

Then:
```bash
while read url; do
  fetchy add "$url"
done < urls.txt

fetchy process
```

### Integration with Scripts

```bash
#!/bin/bash
# Download and extract
fetchy download https://example.com/archive.tar.gz -o /tmp/archive.tar.gz
tar -xzf /tmp/archive.tar.gz
```

### Custom Threading Strategy

For faster speeds on good connections:
```bash
fetchy download https://example.com/bigfile.iso -t 16
```

For slower or rate-limited servers:
```bash
fetchy download https://example.com/file.zip -t 2
```

## Troubleshooting

### Extension not connecting to Fetchy

1. Verify native messaging host path:
   ```bash
   cat ~/.mozilla/native-messaging-hosts/com.fetchy.downloader.json
   ```

2. Check if the path points to your `native_host.py`

3. Ensure `native_host.py` is executable:
   ```bash
   chmod +x native_host.py
   ```

4. Check extension ID matches in the manifest

### Downloads failing

1. Check internet connection
2. Verify URL is accessible:
   ```bash
   fetchy info https://example.com/file.zip
   ```

3. Check if server supports range requests (parallel downloading)

4. Try reducing thread count

### GUI not launching

1. Check PyQt6 installation:
   ```bash
   python3 -c "from PyQt6.QtWidgets import QApplication"
   ```

2. Reinstall dependencies:
   ```bash
   pip install --force-reinstall PyQt6
   ```

## Development

### Running from Source

```bash
# Activate virtual environment
source venv/bin/activate

# Run GUI
python3 gui.py

# Run CLI
python3 cli.py download https://example.com/file.zip
```

### Adding Features

The codebase is modular:
- Extend `connection_manager.py` for new protocols
- Modify `downloader.py` for download logic
- Update `gui.py` or `cli.py` for interface changes
- Edit extension files for browser integration

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - feel free to use and modify

## Acknowledgments

- Inspired by IDM and XDM
- Built with PyQt6, requests, and rich
- Firefox extension API

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Contribute to documentation

---

**Made with ❤️ for the Linux community**
