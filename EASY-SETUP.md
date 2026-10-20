# Easy Setup — HumanWrite AI v1

A beginner-friendly guide. No programming knowledge needed.

## Step 1 — Get the app folder

Unzip `HumanWrite-AI-v1.zip` anywhere you like (for example your Desktop).
Open the extracted folder. You should see `Start-Windows.cmd` inside.

> Do NOT run the app from inside the zip file — always extract first.

## Step 2 — Install Python (one time)

1. Go to https://www.python.org/downloads/
2. Download **Python 3.12 or 3.13** (64-bit Windows installer).
   - If the big yellow button offers Python 3.14 or newer, scroll down to
     "Looking for a specific release?" and pick 3.12 or 3.13 instead —
     the newest versions break some app packages.
3. Run the installer. On the **very first screen**, tick
   **"Add python.exe to PATH"**, then click *Install Now*.

## Step 3 — Start the app

Double-click **`Start-Windows.cmd`**.

- The first run takes 2–5 minutes: it creates a private environment and
  downloads the app's packages (needs internet, one time only).
- Your browser should open automatically at http://127.0.0.1:4322.
- If it doesn't, type that address into Chrome/Edge yourself.
- **Keep the black window open** while you use the app. Closing it stops
  the app.

## Step 4 — Try it

1. Click **"Try the demo"** on the Dashboard — a sample sentence appears.
2. Open the **Analyze** tab and click *Analyze text* — see the highlighted
   sentence and click it for explanations.
3. Open the **Humanize** tab, pick a mode (try *Natural*), set intensity
   to 3, click *Rewrite*, then *Accept* the suggestion and *Apply*.
4. Open **Export** and download the DOCX or PDF.

## Using your own AI key (optional)

The built-in offline engine works with no key. For AI-powered rewriting:

1. Open the **Settings** tab.
2. Fill in your provider (OpenAI-compatible, Google Gemini, or Ollama).
3. Click **Save**, then **Test connection** — it must say OK.

Your key is stored only on your computer, in the app's `data` folder.

## Stopping the app

Close the black window (or press Ctrl+C inside it). Your documents are
saved in the `data` folder and will be there next time.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Python was not found" | Reinstall Python and tick "Add python.exe to PATH" |
| Black window closes instantly | It needs Python 3.10–3.13; check Step 2 |
| Browser says "can't be reached" | The black window must stay open; wait for "[3/3] Starting" |
| Package install fails | Check internet, then double-click `Start-Windows.cmd` again |
| Uploaded PDF has no text | Scanned-image PDFs need OCR (roadmap, not in v1) — use a text PDF |
