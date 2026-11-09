# Café Sabroso - Telegram voice bot

A Spanish-speaking Telegram bot that answers text and voice messages with both text and voice notes. It uses:

- Telegram Bot API for messages and voice notes.
- OpenRouter's `openrouter/free` router for zero-cost text inference. It never falls back to a paid model.
- Faster Whisper running locally in the container for Spanish voice transcription. The default `tiny` multilingual model keeps voice-note responses practical on Render's free CPU. No transcription API key is needed.
- Microsoft Edge neural voices through `edge-tts` for audio replies, converted to OGG/Opus with FFmpeg.

## Commands

- `/start` - introduction and preferred-name capture, followed by the main mode menu.
- `/menu` - reopen the main mode menu. Telegram's persistent Menu button also lists the available commands.
- `/nombre` - change the name the bot uses for you.
- `/voces` - choose from 38 Latin-American Spanish voices: 19 male and 19 female, covering Argentina, Mexico, Colombia, Chile, Uruguay, Peru, Venezuela, Bolivia, Costa Rica, Ecuador, Paraguay, Puerto Rico, the Dominican Republic, Cuba, Guatemala, Honduras, Nicaragua, Panama and El Salvador. This is the maximum balanced Latin-American set in the live Edge TTS Spanish catalog; Spain, United States and other non-Latin-American voices are excluded.
- `/duo` - choose two different voices. Both personas answer each message in alternating turns, joined into one voice note.
- `/trio` - choose three different voices. All three personas answer in alternating turns, joined into one voice note.
- `/cuarteto` - choose four different voices. Four personas answer in alternating turns, joined into one voice note.
- `/historia` - choose four different voices as four named characters, then supply a story theme. Each character speaks its own dialogue and continues the same scene in one joined voice note.
- `/musica <artist or song>` - search for music without leaving the selected voice mode. Natural Spanish requests such as `buscá música de Mercedes Sosa`, `quiero escuchar Alfonsina y el mar` and `buscá canciones de Soda Stereo` also work.
- `/individual` - leave duo, trio, quartet or story mode and return to the selected single voice.
- `/solo_texto` - turn off audio replies.
- `/con_voz` - turn audio replies back on.
- `/reset` - clear the conversation's short-term history.

The default voice is Tomás (`es-AR-TomasNeural`). Each user's preferred name is stored per chat in a local SQLite database and used in onboarding and voice-selection samples. Set `DATABASE_PATH` to change the database location (default `data/cafe_sabroso.db`); durable storage across hosting replacements requires a persistent volume, which is not included in Render's free plan. Answers go directly to the question without repeating a greeting or the saved name. In duo, trio and quartet modes, the first persona answers directly, later personas add complementary responses, and each persona introduces itself when the user asks for introductions. Story mode uses four selected voices as distinct characters who speak sequential dialogue within a shared scene. Their spoken turns are synthesized separately and joined with FFmpeg into one OGG/Opus voice note.

## Music search, sharing and permitted downloads

- Apple Music's public iTunes Search API supplies up to five song choices, with exact Apple Music links and official preview links when available. No Apple key or paid API is used.
- Every song has buttons for Apple Music, an official Spotify search and Telegram sharing. Spotify links open that service; the bot does not claim an unverified result is the requested recording.
- A separate Internet Archive search looks only for items carrying an explicit Creative Commons or public-domain license. When a matching item has a downloadable audio file, the bot links directly to that file on Internet Archive and shows its license and source page. It does not copy, host or redistribute the audio.
- There is no protected-music library or download button for material without an explicit reuse license. Music searches do not call OpenRouter and do not change the selected single, duo, trio, quartet or story mode.
- Sources: https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/SearchExamples.html and https://archive.org/developers/index-apis.html .

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
5. Optional: `OPENROUTER_MODEL` defaults to `openrouter/free`; `WHISPER_MODEL` defaults to `tiny`.
6. Deploy. The app registers the Telegram command menu and default Menu button on startup, sets the Telegram webhook, and exposes `GET /` as a health check.

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

Run all regression tests with `python -m unittest -v test_menu.py test_music.py test_replies.py` after installing the application dependencies.

Do not commit real tokens or API keys.
