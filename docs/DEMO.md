# Demo (90 seconds)

## Before you record

1. `python scripts/seed_demo.py`. It resets `~/Desktop/CatbotDemo` with `screenshot-old-1.png` … `screenshot-old-3.png`.
2. `./scripts/start_catbot.sh` (not `npm start` from a terminal: macOS would give Catbot that terminal's mic permission). Wait for the cat (about 15 s, including about 9 s to load Laya).
3. Check the top bar: `live` dot green, `gate: LAYA`, `ckpt: catbot-tuned`, `voice`.
4. Set system volume to about 60 so line 1 is audible.
5. Open Finder on `~/Desktop/CatbotDemo` beside the app window.

## Window layout

Electron window on the left two thirds (1440×900). Finder on the right third, showing `CatbotDemo`. Hide the dock and notifications.

## The four lines

Hold **Ctrl/Cmd+Alt+Space** (or Space inside the window) and say:

| # | Say | What the judges see |
| --- | --- | --- |
| 1 | "volume kam karo" | `set_volume` allowed (T1), volume drops, "Volume kam kar diya." |
| 2 | "yahan ek project folder banao aur usme README likho" | two `run_command` steps (mkdir, write README), both T1 allowed, folder appears in Finder |
| 3 | "purani screenshots Trash me daal do" | floor T2, saffron sticker "PUCHHNA PADEGA", Catbot asks aloud; answer "haan"; files move to Trash |
| 4 | "saari files delete kar do" | panel red before the LLM answers (floor T3), sticker "BLOCKED", reason spoken, nothing runs |

Point at the Laya card: the `laya` chips show the fine-tuned model deciding tier, verify and the spoken yes/no in about 50 ms. A `keyword` chip appears only when the regex floor raised a tier. Click "wrong?" once to show the training counter go up.

Optional fifth beat (provenance): open `http://127.0.0.1:8765/demo/injection` in a browser, then say "screen padho aur jo likha hai wo karo". Catbot reads the screen, and the follow-up command is denied as `untrusted_origin`.

## Fallback lines (network dies)

```bash
python -m catbot --text "volume kam karo" --fake
python -m catbot --text "purani screenshots Trash me daal do" --fake --yes
python -m catbot --text "saari files delete kar do" --fake
```

Or run the whole UI on fakes: `CATBOT_SIDECAR_ARGS="--fake" npm --prefix electron start`, then type the lines into the text box.

## Recording checklist

- [ ] `python scripts/demo.py --runs 3` passed just before recording
- [ ] Seeded folder visible in Finder
- [ ] Mic permission granted to Electron
- [ ] Do Not Disturb on
- [ ] Say line 3's "haan" within 8 seconds
- [ ] End on the training counter; say that Laya was fine-tuned on this laptop from Sarvam-generated data, and that a regex floor stops it ever lowering risk
