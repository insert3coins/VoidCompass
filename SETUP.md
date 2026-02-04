# Setup Guide: EDSM & Discord Integration

This guide provides detailed steps for obtaining the necessary credentials to enable EDSM and Discord integration for Void Compass.

---

## 1. EDSM (Elite Dangerous Star Map) API Setup

Connecting to EDSM allows the application to upload your exploration data to the public database and fetch system traffic information.

1.  **Navigate to EDSM:**
    *   Open your web browser and go to [https://www.edsm.net/](https://www.edsm.net/).

2.  **Log In:**
    *   Log in using your Frontier account. If you don't have an account, you will need to create one.

3.  **Access Your Profile:**
    *   Once logged in, click on your commander name in the top-right corner of the page and select **"My EDSM profile"** from the dropdown menu.

4.  **Find Your Credentials:**
    *   On your profile page, look for a section on the right-hand side labeled **"Account"**.
    *   In this section, you will find your **`Commander Name`** and your **`API key`**.

    !EDSM API Key Location

5.  **Copy and Paste:**
    *   Copy both your `Commander Name` and the `API key` into the corresponding fields in the Void Compass **[ CONFIGURATION ]** panel.

---

## 2. Discord Webhook Setup

A Discord webhook provides a URL that the application can use to send live updates directly to a text channel in your server.

1.  **Choose a Server and Channel:**
    *   Open Discord and navigate to a server where you have administrative permissions (or at least the "Manage Webhooks" permission).

2.  **Open Server Settings:**
    *   Right-click on the server's icon on the left and select **Server Settings**.

3.  **Go to Integrations:**
    *   In the Server Settings menu, click on the **"Integrations"** tab.

4.  **Create a New Webhook:**
    *   Click on the **"Webhooks"** section, then click the **"New Webhook"** button.

5.  **Configure the Webhook:**
    *   Give your new webhook a name (e.g., "Void Compass") and choose the channel where you want the updates to be posted. You can also give it a custom icon if you wish.

6.  **Copy the Webhook URL:**
    *   Click the **"Copy Webhook URL"** button. This is the URL you need.

7.  **Paste into Configuration:**
    *   Paste the copied URL into the `Discord Webhook` field in the Void Compass **[ CONFIGURATION ]** panel.