# Setup Guide: Discord Integration

Void Compass fetches EDSM traffic and system data automatically; no EDSM credentials or setup are required.

---

## Discord Webhook Setup

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
