# How To Add The SideKick Extension To Chrome

1. Open Chrome.
2. Go to `chrome://extensions`.
3. Turn on `Developer mode` in the top-right corner.
4. Click `Load unpacked`.
5. Select this folder:

   `extension/`

6. The SideKick extension should now appear in the extensions list.
7. If Chrome asks for permissions, approve them.

## How To Open It

1. Click the SideKick extension icon in Chrome.
2. Or use the keyboard shortcut `Alt+S`.

## If You Change The Extension Code

1. Go back to `chrome://extensions`.
2. Find `SideKick`.
3. Click the reload icon on the extension card.
4. Close and reopen the side panel.

## Before Testing

Make sure the Django app is running on:

`http://127.0.0.1:8000`

For Socket.IO updates, start the app with:

`py -m uvicorn sidekick.asgi:application --host 127.0.0.1 --port 8000`

## Connection Flow

1. Open the extension.
2. Click `Open SideKick`.
3. Log in on the web app.
4. Open your profile page in the app.
5. Click `Connect extension`.
6. Return to the extension.
