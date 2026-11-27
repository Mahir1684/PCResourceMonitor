# Contributing to PCResourceMonitor

Thank you for your interest in improving PCResourceMonitor! Here are the core guidelines for contributing:

## Principles & Scope

1. **Keep Source Code Portable**:
   - Never commit hardcoded personal machine paths (e.g. `C:\Users\<username>`, `/home/<username>`, or drive letters like `D:\...`).
   - Use relative paths (e.g. `$PSScriptRoot`, `Path(__file__).parent`) and environment variable fallbacks (`PC_MONITOR_PORT`, `PC_MONITOR_HOST`, `IPROXY_PATH`, `THEOS`).
   - Never commit personal device identifiers (UDIDs), SSH private keys, passwords, or tokens.

2. **Hardware Tolerance & Graceful Degradation**:
   - Hardware collectors must never crash if a sensor, GPU, or drive is absent.
   - If an optional tool (such as `PresentMon.exe`) is missing or permissions are not granted, report `status: "unavailable"` with a clear reason rather than failing the sampler thread.
   - Dynamically adapt to different CPU core/thread counts, GPU vendors (NVIDIA, AMD, Intel), and storage drive layouts.

3. **Legacy iOS Compatibility**:
   - The native client targets iOS 9.0+ and 32-bit ARMv7 (iPad mini 1).
   - Use ARC-compatible Objective-C and UIKit APIs supported on iOS 9.0.
   - Avoid mandatory iOS 10+ APIs and maintain zero-allocation rendering paths during 1 Hz polling ticks to preserve smooth 60 FPS performance on vintage A5 hardware.

4. **Testing Requirements**:
   - Before submitting changes, always run the full test suite:
     ```powershell
     pytest -o pythonpath=.
     ```
   - Ensure all unit tests pass with zero errors.
   - Add new unit tests under `tests/` whenever adding new features, collectors, or endpoints.

## Submission Workflow

1. Fork the repository at https://github.com/Mahir1684/PCResourceMonitor.
2. Create a descriptive topic branch (`git checkout -b feature/my-feature`).
3. Commit your changes with clear, imperative messages.
4. Push your branch and open a Pull Request describing your changes and verification steps.
