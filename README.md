# EarnApp for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![Status](https://img.shields.io/badge/Status-Work%20in%20Progress-orange.svg?style=for-the-badge)

> 🚧 **Work in Progress:**  
> This integration is currently under active development. Features, sensor names, and authentication handling may change or break without prior notice.

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

### Option 1: One-Click Add (Recommended)
Click the button below to automatically open this repository in your Home Assistant HACS instance:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=SnowyCrunchybar&repository=ha-earnapp&category=integration)

1. Click **Add** in the dialog that opens in Home Assistant.
2. Click **Download** on the EarnApp integration page.
3. **Restart Home Assistant**.

### Option 2: Manual HACS Setup
1. Open **HACS** in your Home Assistant instance.
2. Go to **Integrations** → click the three dots in the top right corner → **Custom repositories**.
3. Add the repository URL:
   ```text
   [https://github.com/SnowyCrunchybar/ha-earnapp](https://github.com/SnowyCrunchybar/ha-earnapp)
   ```
4. Select **Integration** as the category and click **Add**.
5. Search for **EarnApp**, click **Download**, and **restart Home Assistant**.

---

## How to Find Your Cookie Keys

1. Log in to [EarnApp Dashboard](https://earnapp.com/dashboard) on a desktop web browser.
2. Press `F12` (or right-click anywhere on the page and select **Inspect**) to open Developer Tools.
3. Open the cookie viewer:
   - **Chrome / Edge / Brave:** Go to the **Application** tab → expand **Cookies** on the left → click `https://earnapp.com`.
   - **Safari:** Enable **Develop** in Safari Settings → **Advanced**, then open **Develop → Show Web Inspector**. Open the **Storage** tab → **Cookies** → click `https://earnapp.com`.
   - **Firefox:** Go to the **Storage** tab → expand **Cookies** on the left → click `https://earnapp.com`.
4. Use the filter box to search for `token` and copy the **Value** column (not the Name) for these two rows:
   - `oauth-refresh-token`: A long string usually starting with `1%2F%2F...` (or `1//...`).
   - `xsrf-token`: A shorter alphanumeric string.

> 💡 **Important:** Do not click "Log out" in your browser after copying the cookies, as logging out invalidates the refresh token on EarnApp's servers. Simply close the browser tab when done.

---

## Configuration

1. In Home Assistant, go to **Settings → Devices & Services**.
2. Click **Add Integration** in the bottom right corner and search for **EarnApp**.
3. Follow the on-screen instructions in the setup dialog and paste your `oauth-refresh-token` and `xsrf-token`.

---

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed, or supported by EarnApp / Bright Data. Use at your own risk.

---
