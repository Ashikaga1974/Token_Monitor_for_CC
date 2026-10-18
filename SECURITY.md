# Security Policy

## Supported Versions

We actively maintain and provide security patches for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.0.x   | :white_check_mark: |

---

## Security Architecture & Principles

**Token Monitor for Claude Code** is built with strict privacy and security defaults:
- **Local-Only Operation**: The widget communicates exclusively with the local daemon on loopback (`127.0.0.1:48291`). No tracking, analytics, or telemetry is gathered or transmitted.
- **Strict File Permissions**: Historical token snapshots (`history.db`) and notification configurations are stored under `~/.local/share/token-monitor/` with restrictive permissions (`0700` directory, `0600` files) to prevent unauthorized read access from other local OS users.
- **CORS & Origin Guard**: The local HTTP daemon explicitly rejects incoming requests carrying external `Origin` headers with HTTP 403, preventing malicious websites in browsers from querying stats or manipulating daemon configurations.
- **Request Size Limits**: POST payloads to daemon endpoints are strictly capped at 64 KB to protect against denial-of-service / memory exhaustion attacks.
- **Sanitized Notifications**: All dynamic strings formatted into desktop notifications are sanitized against Pango markup injection before dispatching via D-Bus (`org.freedesktop.Notifications`).

---

## Reporting a Vulnerability

If you discover a security vulnerability or security-relevant bug in this project, please **do not open a public issue**.

Instead, report it directly and confidentially via:
- **Email**: [info@buells-united.com](mailto:info@buells-united.com)
- **Subject**: `[SECURITY] Token Monitor for Claude Code: <Brief Description>`

Please include in your report:
- A description of the vulnerability
- Steps or a proof-of-concept to reproduce the issue
- The potential impact on users
- Any suggested mitigations or fixes

You will receive an initial acknowledgment within 48 hours. We will coordinate a fix, release an update, and credit your discovery appropriately.
