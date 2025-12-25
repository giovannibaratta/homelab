## Disable WiFi and bluetooth

1. Install `rfkill` if not already installed:
   ```bash
   sudo apt install rfkill
   ```
1. Create script `/root/disable-wifi.sh`:
   ```bash
   #!/bin/bash
   nmcli radio wifi off
   /usr/sbin/rfkill block all
   echo "auto" > /sys/bus/pci/devices/0000:02:00.0/power/control
   # MP60
   modprobe -r --force rtw89_8852be

   # UM790
   modprobe -r --force iwlwifi
   ```
2. Make the script executable:
   ```bash
   chmod +x /root/disable-wifi.sh
   ```
3. Create systemd service in `/etc/systemd/system/disable-wifi.service`:

   ```bash
    [Unit]
    Description=Block all rfkill devices for power savings
    # Wait for Network Manager and standard networking to finish
    After=multi-user.target NetworkManager.service systemd-networkd.service
    # Ensure it runs after the built-in restore service
    After=systemd-rfkill.service

    [Service]
    Type=oneshot
    ExecStartPre=/bin/sleep 60
    ExecStart=/root/disable-wifi.sh
    RemainAfterExit=yes

    [Install]
    WantedBy=multi-user.target
   ```

4. Enable the service:
   ```bash
   systemctl enable disable-wifi.service
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
