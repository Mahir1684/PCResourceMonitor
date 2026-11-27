# PCResourceMonitor

A high-performance, lightweight Windows 10/11 hardware telemetry server and dedicated native iOS dashboard engineered specifically for legacy devices such as the **iPad mini 1** (iOS 9.3.5 / 32-bit Apple A5).

Turn an unused vintage iPad into a sleek, dedicated, low-latency PC telemetry display sitting on your desk.

Developed by [Mahir Patel](https://github.com/Mahir1684). Created with assistance from Gemini, Antigravity, and ChatGPT.

---

## Features

- **Real-Time Hardware Telemetry:**
  - **CPU:** Auto-detects **Intel** and **AMD** processors with total & per-core utilization, clock frequency, and thermal monitoring (via LibreHardwareMonitor / WMI fallback).
  - **GPU:** Auto-detects **NVIDIA**, **AMD**, and **Intel** GPUs with NVIDIA NVML metrics (engine clock, memory clock, core load, VRAM, temperature) and DXGI / sensor bridge fallback, returning `N/A` for metrics unavailable on a given GPU or driver.
  - **In-Game FPS:** Silent PresentMon ETW integration measuring live in-game frames per second and frame-times for active 3D applications.
  - **Memory:** Physical RAM total, used, available, and percentage.
  - **Storage:** Dynamic partition detection with support for NVMe/SATA SSDs, HDDs, and hotplugged USB drives.
  - **Network:** Real-time upload and download speeds with active interface tracking.
- **Engineered for Legacy iOS Hardware (Apple A5 / iOS 9.3.5):**
  - Native 32-bit ARMv7 Objective-C dashboard designed for the iPad mini 1 screen (1024x768).
  - Zero-allocation per-tick UI rendering engine keeping CPU and memory overhead minimal.
  - Glassmorphic dark card design with smooth 60 FPS scrolling and silky smooth Notification Center operation.
- **Silent USB Plug-and-Play Reconnection:**
  - Automated watchdog background service tracks USB plug/unplug events.
  - Recovers `iproxy` port forwarding and SSH reverse tunneling without showing command prompt or PowerShell popups.
- **Secure by Default:**
  - Backend server binds strictly to loopback (`127.0.0.1:5001`), never exposing data to the local network or internet unless explicitly reconfigured.
  - Optional bearer token authentication for dashboard API calls.

---

## System & Hardware Compatibility

### Operating Systems

| Platform | Status | Notes |
|---|---|---|
| **Windows 10 / Windows 11 (64-bit)** | **Supported** | Primary target; full telemetry, PresentMon ETW FPS tracking, and PowerShell/watchdog scripts are tested here. |
| **Windows 7 / 8 / 8.1** | **Not Supported** | Untested; modern Python builds, PresentMon ETW tracing, and DXGI features require Windows 10 or newer. |
| **Linux / macOS** | **Not Supported (Backend)** | Core collectors (`DXGI`, `PresentMon.exe`, LibreHardwareMonitor) and PowerShell scripts are Windows-specific. (WSL2 / Linux is only used if rebuilding the `.ipa` via Theos.) |

### Hardware & Sensors

- **Processors (CPU):** Supports both **Intel** and **AMD** CPUs and adapts dynamically to different core counts.
- **Graphics Cards (GPU):** Supports **NVIDIA**, **AMD**, and **Intel** GPUs via vendor/DXGI and optional sensor bridge providers; metrics not exposed by a specific GPU or driver fall back cleanly to `N/A`.
- **iOS Client:** Built for 32-bit/ARMv7 iOS devices (such as iOS 9.3.5 on iPad mini 1) via sideloading and local port forwarding, with dynamic layout handling for multi-volume storage.

---

## Architecture

+-------------------------------------------------------------+
|                   Windows 10/11 Host PC                     |
|                                                             |
|  [Hardware Sensors]      [PresentMon ETW]                   |
|   psutil / NVML / DXGI     In-Game FPS                      |
|   / LHM / WMI                   |                           |
|           |                     |                           |
|           +----------> + <------+                           |
|                        |                                    |
|              [Python Flask Telemetry API]                   |
|                 (127.0.0.1:5001 / JSON)                     |
|                        |                                    |
|                 [iproxy / SSH Tunnel]                       |
|           (Port 2222 -> Port 22 / Reverse 5002)             |
+------------------------|------------------------------------+
                         | Apple Lightning / 30-pin USB Cable
+------------------------v------------------------------------+
|               iPad mini 1 (iOS 9.3.5 / ARMv7)               |
|                                                             |
|             [Native PCResourceMonitor.app]                  |
|            - PRMTelemetryClient (127.0.0.1:5002)            |
|            - PRMDashboardViewController (1024x768)          |
|            - 6-Card Zero-Allocation UI Engine               |
+-------------------------------------------------------------+```

---

## Directory Structure

PCResourceMonitor/
├── backend/                  # Python telemetry service
│   ├── api/                  # Flask REST endpoints (/api/v1/telemetry)
│   ├── monitoring/           # Collectors: CPU, GPU, RAM, Storage, Network, FPS
│   ├── app.py                # Flask application factory
│   ├── config.py             # Configuration defaults & environment overrides
│   └── run.py                # Server entry point
├── dist/                     # Precompiled release binaries
│   └── PCResourceMonitor.ipa # Ready-to-install native iOS application
├── docs/                     # Technical architecture & USB setup guides
│   ├── ARCHITECTURE.md
│   └── USB_CONNECTIVITY.md
├── frontend/                 # Web fallback dashboard (HTML5/CSS3/Vanilla JS)
├── native/                   # Native iOS 9 Objective-C client
│   ├── src/                  # Controllers, Views, Models, Networking
│   ├── assets/               # High-resolution app icons
│   ├── Info.plist            # App bundle configuration
│   └── Makefile              # Theos build specification
├── scripts/                  # Automation, deployment, and watchdog scripts
│   ├── PCResourceMonitor-Watchdog.ps1    # Headless USB watchdog
│   ├── Start-PCResourceMonitor-Watchdog.vbs # Silent VBScript launcher
│   ├── Register-PCResourceMonitor-Task.ps1 # Task scheduler registration
│   ├── Start-PCResourceMonitor-Backend.ps1  # Backend runner
│   └── Install-App-USB.ps1                 # Deployment helper
├── tests/                    # Comprehensive unit tests (100 tests)
├── tools/                    # Bundled utilities (PresentMon.exe)
├── requirements.txt          # Python dependencies
├── LICENSE                   # MIT License
└── README.md
---

## Getting Started

### 1. Prerequisites

- **Windows PC:**
  - Windows 10 or 11 (64-bit)
  - Python 3.10, 3.11, or 3.12 (with `pip`)
  - [iTunes for Windows](https://www.apple.com/itunes/) or Apple Mobile Device Support (for USB communication)
- **iOS Device:**
  - iPad mini 1 (or any iPad / iPhone running iOS 9.0 through 9.3.6)
  - Jailbroken device (recommended for direct SSH/tethering installation) or a standard sideloading tool like [Sideloadly](https://sideloadly.io/) / [AltStore](https://altstore.io/).

---

### 2. Backend Setup

1. Open PowerShell and navigate to the project directory:
   ```powershell
   cd PCResourceMonitor
   ```

2. Create and activate a Python virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install required Python packages:
   ```powershell
   pip install -r requirements.txt
   ```

4. Verify that the test suite passes:
   ```powershell
   pytest tests/
   ```

5. Test running the backend server manually:
   ```powershell
   python -m backend.run
   ```
   The backend will start listening at `http://127.0.0.1:5001`. You can open `http://127.0.0.1:5001/api/v1/telemetry` in your browser to inspect live JSON metrics.

---

### 3. Installing the Native iOS App

A precompiled IPA is included in `dist/PCResourceMonitor.ipa`.

#### Option A: Sideloadly / AltStore (Non-Jailbroken or Jailbroken)
1. Download and open [Sideloadly](https://sideloadly.io/).
2. Connect your iPad via USB.
3. Drag `dist/PCResourceMonitor.ipa` into Sideloadly.
4. Enter your Apple ID to sign the application and click **Start**.
5. On the iPad, navigate to **Settings > General > Device Management** and trust your developer certificate.

#### Option B: Direct USB Deployment (Jailbroken Device with AppSync & OpenSSH)
If your iPad has OpenSSH and `appinst` installed:
```powershell
.\scripts\Install-App-USB.ps1
```

---

### 4. Setting Up Automatic Headless USB Watchdog

To have the monitor automatically connect whenever you plug your iPad into your PC:

1. Register the silent startup task in Windows Task Scheduler:
   ```powershell
   powershell.exe -ExecutionPolicy Bypass -File .\scripts\Register-PCResourceMonitor-Task.ps1
   ```
2. The watchdog runs via `scripts\Start-PCResourceMonitor-Watchdog.vbs` completely silently in the background (no console windows). When it detects your iPad on USB:
   - Starts the Python telemetry server on port `5001` (if not running).
   - Starts `iproxy.exe` to bridge port `2222 -> 22`.
   - Starts an SSH reverse tunnel routing iPad `127.0.0.1:5002` to PC `127.0.0.1:5001`.
   - Automatically reconnects within seconds if the cable is unplugged and replugged.

---

## Configuration & Environment Variables

You can customize port bindings and features using environment variables:

| Variable | Default | Description |
|---|---|---|
| `PC_MONITOR_HOST` | `127.0.0.1` | Network interface IP to bind Flask |
| `PC_MONITOR_PORT` | `5001` | Local port for the telemetry backend |
| `PC_MONITOR_TUNNEL_PORT` | `5002` | Remote port forwarded to the iPad |
| `PC_MONITOR_IPROXY_PORT` | `2222` | Local port for `iproxy` SSH bridge |
| `PC_MONITOR_AUTH_TOKEN` | *(None)* | Optional token for API request authentication |
| `PC_MONITOR_DEBUG` | `0` | Enable debug logging (`1` or `0`) |

---

## Building the iOS Client from Source

The native iOS client is written in pure Objective-C and compiles using the [Theos](https://theos.dev/) build framework.

### Build Requirements
- Linux, macOS, or Windows Subsystem for Linux (WSL)
- Theos installed (`git clone --recursive https://github.com/theos/theos.git ~/theos`)
- An iOS 9.3 SDK placed in `~/theos/sdks/iPhoneOS9.3.sdk`

### Build Command
```bash
cd native
make clean package
```
The resulting IPA package will be generated inside `native/packages/`.

---

## Security

Please see [SECURITY.md](SECURITY.md) for vulnerability disclosure and security policies. PCResourceMonitor is configured out-of-the-box to bind strictly to loopback (`127.0.0.1`) and never open unsolicited listening sockets across external networks.

---

## Contributing

Contributions, bug reports, and pull requests are welcome! Please review [CONTRIBUTING.md](CONTRIBUTING.md) for details on code style, testing requirements, and iOS 9 backward-compatibility rules.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 [Mahir Patel](https://github.com/Mahir1684).
"# PCResourceMonitor" 
