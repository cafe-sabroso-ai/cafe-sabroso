# Café Sabroso - Telegram voice bot

A Spanish-speaking Telegram bot that answers text and voice messages with both text and voice notes. It uses:

- Telegram Bot API for messages and voice notes.
- OpenRouter's `openrouter/free` router for zero-cost text inference. It never falls back to a paid model.
- Faster Whisper running locally in the container for Spanish voice transcription. No transcription API key is needed.
- Microsoft Edge neural voices through `edge-tts` for audio replies, converted to OGG/Opus with FFmpeg.

## Commands

- `/start` - introduction and preferred-name capture, followed by single-voice or duo selection.
- `/nombre` - change the name the bot uses for you.
- `/voces` - choose from 12 male or female Spanish voices from Argentina, Spain, Mexico, United States, Colombia or Chile.
- `/duo` - choose two different voices. Both personas answer each message in alternating turns, joined into one voice note.
- `/trio` - choose three different voices. All three personas answer in alternating turns, joined into one voice note.
- `/individual` - leave duo or trio mode and return to the selected single voice.
- `/solo_texto` - turn off audio replies.
- `/con_voz` - turn audio replies back on.
- `/reset` - clear the conversation's short-term history.

The default voice is Tomás (`es-AR-TomasNeural`). Each user's preferred name is stored per chat in a local SQLite database and used by every persona. Set `DATABASE_PATH` to change the database location (default `data/cafe_sabroso.db`); durable storage across hosting replacements requires a persistent volume, which is not included in Render's free plan. In duo and trio modes, the first persona answers directly, later personas add complementary responses, and every speaker addresses the user by name. Their spoken turns are synthesized separately and joined with FFmpeg into one OGG/Opus voice note.

## Live weather and sports

- Weather questions use Open-Meteo geocoding and current conditions. If no place is supplied, the bot asks for one. Responses include the source's update time and a link to https://open-meteo.com/ as required by its CC BY 4.0 attribution terms. Non-commercial API use does not require a key or card; usage limits and commercial terms are at https://open-meteo.com/.
- Sports questions use ESPN's current public scoreboard feed. Supported queries cover general football and several mapped competitions (Argentina, Champions League, Libertadores, Premier League and Spain), plus NBA, NFL, MLB and NHL. The bot supports today, yesterday and tomorrow, filters recognized team names, and asks for sport/league or other details when the request is ambiguous or returns no events. ESPN's feed is not a committed or paid API and its availability or schema may change.
- Retrieved facts and the original question are passed to the selected persona flow with instructions not to invent additional values. If geocoding, the weather feed, or the sports feed fails, the bot returns a clarification or source-unavailable message instead of generating a forecast or result. Voice selections, duo settings and chat history are in memory, so they reset when the free service restarts.

## Deploy on Render free

1. Create a public GitHub repository with these files.
2. In Render, choose **New > Web Service** and connect that public repository.
3. Select the **Docker** runtime and the **Free** instance type.
4. Add these environment variables:
   - `TELEGRAM_BOT_TOKEN`: the token from BotFather.
   - `OPENROUTER_API_KEY`: an OpenRouter API key. No credits are required for `openrouter/free`.
   - `WEBHOOK_SECRET`: a long random string.
   - `PUBLIC_URL`: the final `https://<service>.onrender.com` URL, without a trailing slash.
5. Optional: `OPENROUTER_MODEL` defaults to `openrouter/free`; `WHISPER_MODEL` defaults to `base`.
6. Deploy. The app sets the Telegram webhook on startup and exposes `GET /` as a health check.

Free Render services can sleep after inactivity. The first message after sleep can take about a minute while the service wakes. The first voice message after a restart also downloads the local Whisper model.

## Local development

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
# ffmpeg must also be installed
cp .env.example .env
# fill .env, then export its values in your process environment
uvicorn app:app --host 0.0.0.0 --port 10000
```

Do not commit real tokens or API keys.
