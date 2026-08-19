# Homelab Troubleshooting & Known Issues

## 1. SSH `No route to host` from IDE Terminal on macOS Sequoia

### Symptom
Running `ssh ansible@<node-ip>` from Antigravity IDE terminal fails with `ssh: connect to host <node-ip> port 22: No route to host`, while `ssh` from standalone iTerm2 succeeds. `ping <node-ip>` from CLI task runner fails with `ping: sendto: No route to host`.

### Root Cause
macOS Sequoia (15.x+) introduced **Local Network Privacy**. If the parent IDE / CLI process is not granted Local Network permission, macOS silently drops ARP queries and outbound socket connections to local subnet IPs for child processes, returning `EHOSTUNREACH`.

### Resolution
1. Open **System Settings** → **Privacy & Security** → **Local Network**.
2. Enable access for **Antigravity** / **Antigravity IDE** / **node**.
3. If not listed, reset Local Network privacy rules to trigger prompt:
   ```bash
   tccutil reset LocalNetwork
   ```
4. Restart the IDE.

