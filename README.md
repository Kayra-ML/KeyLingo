# KeyLingo

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey?logo=apple)

**Translate the text you are typing between Turkish and English in any macOS app, with one keyboard shortcut.**

KeyLingo runs in the background and listens for global shortcuts. Press a shortcut in Discord, Safari, Slack, VS Code, Notes or any other text field, and the text in that field is replaced by its [DeepL](https://www.deepl.com/pro-api) translation. There is no switching between apps and no copy and paste.

## Shortcuts

| Keys | Direction |
|------|-----------|
| `é` + `→` | Turkish to English (`EN-US`) |
| `é` + `←` | English to Turkish (`TR`) |

## Features

- **Works in any text field.** It selects the text in the active field, translates it and puts the result back.
- **Normal typing is not affected.** The `é` key is only swallowed when an arrow key follows it. If you press `é` alone or with another key, the character is typed as usual. This is done with a Quartz event tap.
- **Your text is never lost.** On a network error, an API error, an invalid key, a timeout or an empty response, the original text stays untouched. An empty field does nothing.
- **Clipboard is restored.** Whatever was on the clipboard before is saved and put back after the translation is pasted.
- **No duplicate requests.** A lock prevents repeated key presses from sending several API calls at once.
- **API key stays private.** The key is redacted from logs and error messages.

## Requirements

- macOS
- Python 3
- A [DeepL API](https://www.deepl.com/pro-api) key
- Accessibility permission for your terminal (below)

### macOS permissions

Listening for global key events and selecting text requires **Accessibility** access.

1. Open **System Settings → Privacy & Security → Accessibility**.
2. Add your terminal app (Terminal, iTerm2 or Visual Studio Code) and switch it on.
3. If shortcuts still do not react, also enable your terminal under **Input Monitoring**.

## Installation

```bash
git clone https://github.com/Burak-ML/KeyLingo.git
cd KeyLingo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Put your key in `.env`:

```env
DEEPL_AUTH_KEY=your_deepl_api_key_here
```

Check the connection (optional), then start the tool:

```bash
python main.py --test-api
python main.py
```

Stop it with `Ctrl+C`.

## Usage

1. Type some text in any app, for example: *bu sistemi yarın sunucuya kuracağım ama önce api tarafındaki hatayı düzeltmem lazım*
2. Hold `é` and press `→`.
3. The text in the field becomes: *I will install this system on the server tomorrow, but first I need to fix the error on the api side*

Hold `é` and press `←` to go the other way.

## Keyboard layouts

The defaults match the standard Turkish Q layout, where `é` sits near `Esc` or left of `1` (macOS key codes `10` and `50`). On another layout, find the key code of your key:

```bash
python main.py --detect-key
```

Then list the codes in `.env`:

```env
E_KEYCODES=10,50,<your_code>
```

## Tests

```bash
python test_translator.py
```

The tests cover clipboard restoration, error handling and the shortcut logic.

## Project structure

```
main.py              event tap, DeepL client and clipboard handling
test_translator.py   unit tests
requirements.txt     dependencies
.env.example         configuration template
```

## License

MIT. See [LICENSE](LICENSE).
