# Security Policy

## Threat Model & Design Scope

PCResourceMonitor is designed strictly as a personal, local hardware telemetry dashboard. It monitors PC hardware resources and serves live metrics to a tethered or local client device (such as an iPad).

### 1. Loopback-Only Binding by Default
- The Flask HTTP backend binds strictly to `127.0.0.1` (port `5001`).
- Binding to `0.0.0.0` or `::` (wildcard/all-interfaces) is explicitly prohibited in `backend/config.py` and will raise a startup error.
- Telemetry communication between the host PC and iOS device is established over a local USB tunnel (`iproxy` on port 2222 forwarding SSH reverse tunnel `5002 -> 5001`), keeping network packets within the local USB interface.

### 2. Client IP Allowlisting & Anti-Spoofing
- The middleware in `backend/api/access.py` strictly evaluates `request.remote_addr`.
- Client-supplied `X-Forwarded-For` and `X-Real-IP` headers are ignored to prevent IP address spoofing.
- Unauthorized client IP addresses connecting to the backend are rejected with HTTP 403 Forbidden.

### 3. Hardened HTTP Response Headers
All API responses include standard security headers:
- `X-Content-Type-Options: nosniff` (MIME sniffing prevention)
- `X-Frame-Options: DENY` (Clickjacking prevention)
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'`
- `Cache-Control: no-store, no-cache, must-revalidate` (Prevents caching of live sensor data)

### 4. Safe Subprocess Execution
- Any optional external binaries (such as `PresentMon.exe`) are launched using explicit argument lists without `shell=True`, using `CREATE_NO_WINDOW` and `stdin=subprocess.DEVNULL`.
- No user-controlled input is ever passed to command line invocations.

### 5. Why Public Exposure is Discouraged
PCResourceMonitor is not designed as a multi-tenant public cloud service. It does not implement user accounts, TLS termination, or API token authentication. Exposing the telemetry backend to the public internet or untrusted shared Wi-Fi networks is strongly discouraged. If remote access outside a USB cable is required, always place the service behind an authenticated VPN (such as WireGuard or Tailscale) or an encrypted SSH tunnel.

## Reporting a Vulnerability

If you discover any security issue or vulnerability, please report it responsibly by opening a private GitHub Security Advisory or contacting the maintainer at https://github.com/Mahir1684.
