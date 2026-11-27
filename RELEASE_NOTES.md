# PCResourceMonitor v1.0.0 Release Notes

PCResourceMonitor is a lightweight, low-overhead Windows 11 hardware telemetry server and companion native iOS dashboard specifically engineered for legacy devices such as the iPad mini 1 (iOS 9.3.5 / 32-bit Apple A5).

---

## Key Highlights

### 1. High-Performance Windows Telemetry Backend
- **Low-Footprint Flask & Waitress Server:** Bound strictly to loopback (`127.0.0.1:5001`) with configurable security tokens, sub-second polling endpoints, and zero cloud dependencies.
- **Hardware Telemetry Coverage:**
  - **CPU:** Real-time multi-core utilization, clock frequency, per-core metrics, and thermal sensing via LibreHardwareMonitor / WMI fallbacks.
  - **GPU:** Dedicated NVIDIA NVML collector for core utilization, VRAM usage, clock speeds, and temperature, paired with seamless WMI/fallback detection for AMD and Intel graphics.
  - **RAM:** Physical memory utilization, total/used/available split, and dynamic utilization tracking via `psutil`.
  - **Storage:** Dynamic partition re-querying supporting fixed SSDs/HDDs, removable USB storage, and drive space/rate counters without blocking the sample loop on unmounted media.
  - **Network:** Real-time upload and download rate tracking, active interface detection, and IP discovery.
  - **System:** OS metadata, CPU model identification, GPU identifier strings, and live system uptime.

### 2. Real-Time In-Game FPS Monitoring
- Built-in integration with Intel's `PresentMon.exe` ETW tracing engine.
- Runs completely hidden without console windows (`CREATE_NO_WINDOW`).
- Samples active 3D DirectX/Vulkan game processes, computing real-time FPS and frame-time latency alongside standard GPU compute metrics.

### 3. Native iOS 9.3.5 / ARMv7 Dashboard Client
- **Custom Native Objective-C Application:** Built against iOS 9 SDK with 32-bit ARMv7 support.
- **Apple A5 Zero-Allocation UI Engine:**
  - Premium dark glassmorphism card aesthetic optimized for 1024x768 resolution.
  - Fixed-card architecture with zero per-tick view allocations, caching all labels, layer properties, and formatted telemetry rows.
  - Explicit `opaque = YES` surface flags and optimized layer composition to ensure silky smooth 60 FPS scrolling and Notification Center pull-down on vintage hardware.
  - Dynamic scrollable volumes subview in the Storage card for multi-drive setups.

### 4. Robust USB Tethering & Reconnection Architecture
- Automated watchdog daemon (`PCResourceMonitor-Watchdog.ps1` + silent VBS launcher) for automatic detection of iPad connect/disconnect events over standard Apple USB cable.
- Instant automatic recovery of `iproxy` local port forwarding and reverse SSH tunneling (`5002 -> 5001`).
- Completely headless execution with zero visible popup terminal windows during Windows boot or cable replugs.

### 5. Prebuilt Binary & Open-Source Portability
- Includes prebuilt `PCResourceMonitor.ipa` in `dist/` ready for sideloading via Sideloadly, AltServer, or `appinst` on jailbroken devices.
- Makefile and build scripts ready for Theos toolchains on macOS, Linux, or WSL.
- Clean separation of configuration with environment variables and relative path resolution.

---

## System Requirements

- **Host PC:** Windows 10 or Windows 11 (x64) with Python 3.10+
- **Display Device:** Apple iPad mini 1 or any iOS device running iOS 9.0 through 9.3.6 (ARMv7 or ARM64)
- **Connection:** Standard Apple Lightning-to-USB cable (recommended) or local Wi-Fi
