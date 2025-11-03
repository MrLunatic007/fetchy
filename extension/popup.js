// Popup logic
const interceptToggle = document.getElementById('interceptToggle');
const minSizeInput = document.getElementById('minSize');
const urlInput = document.getElementById('urlInput');
const downloadBtn = document.getElementById('downloadBtn');
const openFetchyBtn = document.getElementById('openFetchy');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const activeCount = document.getElementById('activeCount');
const queuedCount = document.getElementById('queuedCount');

// Initialize
browser.runtime.sendMessage({ action: "getStatus" }).then((response) => {
  if (response.enabled) {
    interceptToggle.classList.add('active');
  } else {
    interceptToggle.classList.remove('active');
  }
  
  minSizeInput.value = (response.minFileSize / (1024 * 1024)).toFixed(1);
});

// Load stats
loadStats();

// Toggle intercept
interceptToggle.addEventListener('click', () => {
  const isActive = interceptToggle.classList.toggle('active');
  browser.runtime.sendMessage({
    action: "setEnabled",
    enabled: isActive
  });
});

// Update min file size
minSizeInput.addEventListener('change', () => {
  const sizeInBytes = parseFloat(minSizeInput.value) * 1024 * 1024;
  browser.runtime.sendMessage({
    action: "setMinFileSize",
    size: sizeInBytes
  });
});

// Download button
downloadBtn.addEventListener('click', () => {
  const url = urlInput.value.trim();
  
  if (!url) {
    alert('Please enter a URL');
    return;
  }
  
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    alert('URL must start with http:// or https://');
    return;
  }
  
  browser.runtime.sendMessage({
    action: "downloadUrl",
    url: url,
    filename: ""
  }).then(() => {
    urlInput.value = '';
    showNotification('Download added to Fetchy!');
  }).catch((error) => {
    alert('Error: ' + error.message);
  });
});

// Open Fetchy
openFetchyBtn.addEventListener('click', () => {
  // Try to open Fetchy via protocol handler
  window.open('fetchy://open', '_blank');
  
  // Also check if we can launch it via native messaging
  browser.runtime.sendNativeMessage("com.fetchy.downloader", {
    action: "open"
  }).catch(() => {
    // Fallback: show message
    showNotification('Please open Fetchy manually');
  });
});

// Load statistics
function loadStats() {
  browser.storage.local.get(['pendingDownloads']).then((result) => {
    const pending = result.pendingDownloads || [];
    queuedCount.textContent = pending.length;
  });
  
  // Try to get stats from native app
  browser.runtime.sendNativeMessage("com.fetchy.downloader", {
    action: "stats"
  }).then((response) => {
    if (response.success) {
      activeCount.textContent = response.active || 0;
      statusDot.classList.remove('disconnected');
      statusDot.classList.add('connected');
      statusText.textContent = 'Connected to Fetchy';
    }
  }).catch(() => {
    statusDot.classList.remove('connected');
    statusDot.classList.add('disconnected');
    statusText.textContent = 'Fetchy not running';
  });
}

// Show notification
function showNotification(message) {
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    top: 10px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(255, 255, 255, 0.95);
    color: #667eea;
    padding: 10px 20px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    z-index: 1000;
    animation: slideDown 0.3s ease;
  `;
  notification.textContent = message;
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.remove();
  }, 2000);
}

// Reload stats every 5 seconds
setInterval(loadStats, 5000);
