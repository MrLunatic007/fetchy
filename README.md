# Fetchy Download Manager

A powerful download manager for Linux with GUI, CLI, and Firefox browser integration. Similar to IDM/XDM but built specifically for Linux with modern Python technologies.

## Features

✨ **Multi-threaded Downloading**: Split files into chunks and download in parallel for maximum speed

🎨 **Beautiful GUI**: Modern PyQt6 interface with real-time progress tracking

⚡ **Powerful CLI**: Full-featured command-line interface for automation

📊 **Download Queue**: Manage multiple downloads with pause/resume support

🔄 **Resume Support**: Continue interrupted downloads from where they left off

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Quick Install

```bash
# Clone the repository
git clone https://github.com/MrLunatic007/fetchy.git
cd fetchy

# Run the cli interface
python cli.py
```

You Could decide to build the apps using PyInstaller.

```bash
pip install PyInstaller
pyinstaller --onefile --noconsole --name fetchy cli.py
```

And also the gui file

```bash
pyinstaller --onefile --noconsole --name fetchy-gui gui.py
```

move the compiled binaries to /usr/bin

```bash
sudo cp dist/fetchy /usr/local/bin/ # For fetchy-cli
sudo cp dist/fetchy-gui /usr/local/bin # For fetchy-gui
```

For the GUI, make a desktop instance

```bash
# Inside /usr/share/applications/fetchy.desktop paste the following

[Desktop Entry]
Version=1.0
Type=Application
Name=Fetchy Download Manager
Comment=A Linux native Download Manager
Exec=/usr/local/bin/fetchy-gui
Terminal=false
Category=Network;FileTransfer
```

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

## Project Structure

```
fetchy/
├── main.py                  # Main entry point
├── connection_manager.py    # HTTP connection handling
├── downloader.py           # Core download engine
├── gui.py                  # PyQt6 GUI application
├── cli.py                  # CLI interface
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

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Contribute to documentation

---

**Made with ❤️ for the Linux community**
