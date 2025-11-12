## Disable WiFi and bluetooth
1. Install `rfkill` if not already installed:
   ```bash
   sudo apt install rfkill
   ```
2. Create systemd service in `/etc/systemd/system/rfkill-block-all.service`:
   ```bash
    [Unit]
    Description=Block all rfkill devices for power savings

    [Service]
    Type=oneshot
    ExecStart=/usr/sbin/rfkill block all
    RemainAfterExit=yes

    [Install]
    WantedBy=multi-user.target
    ```
3. Block WiFi and Bluetooth:
   ```bash
   systemctl enable rfkill-block-all.service
   ```

## Change governor to 'powersave'
1. Install `cpufrequtils` if not already installed:
   ```bash
   sudo apt-get install cpufrequtils
    ```
2. Check the current governor:
   ```bash
   cpufreq-info | grep "current policy"
   ```
3. Set the governor to 'powersave':
   ```bash
   echo 'GOVERNOR="powersave"' | sudo tee /etc/default/cpufrequtils
   ```