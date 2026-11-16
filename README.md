# EarnApp for Home Assistant

Custom Home Assistant integration to monitor your EarnApp account balance, total earnings, and active devices.

> ⚠️ **Note before installing:**  
> EarnApp does not provide a public API key or a simple username/password login for third-party tools. To use this integration, you must manually extract authentication cookies (`oauth-refresh-token` and `xsrf-token`) from your web browser's Developer Tools.  
> **If you do not know what a browser network/storage inspector or a cookie is, this integration is not for you.**

---

## Features

- **Current Balance ($)** – Tracks your available EarnApp balance.
- **Total Earned ($)** – Tracks your all-time earnings.
- **Active Devices** – Displays the total count of linked devices, with individual device details (UUID, title, device type, bandwidth, earnings) exposed as entity attributes.
- **UI Configuration** – Easy setup via Home Assistant's UI (`Config Flow`), no YAML required.

---

## Installation (HACS)

1. Open **HACS** in your Home Assistant instance.
2. Go to **Integrations** → click the three dots in the top right corner → **Custom repositories**.
3. Add the repository URL:
   ```text
   [https://github.com/SnowyCrunchybar/ha-earnapp](https://github.com/SnowyCrunchybar/ha-earnapp)
