# Hand-check: 50 random rows (seed 7)

> **Reviewed by the agent (Claude), 31 Oct.** First sample: 41/50 right; the 9 wrong rows came from
> 5 generator bugs (placeholder fill mismatch, train/test duplicates, Recycle Bin tiered T2,
> "volume at half" = 30, tab characters), all fixed in `data/gen_laya_data.py`, `data/templates.py`
> and the gate. This redrawn sample: 50/50 right. A human glance is still welcome.

Tick a box if the label is right. Fix wrong labels in data/labels.jsonl, then rerun data/to_laya_format.py.

- [x] `risk_tier-19ec9aa0db-e62831` **risk_tier = T2**  
  `Request: push to github | Action: run_command {"command": "git push origin main"}`
- [x] `risk_tier-049876f636-ad1368` **risk_tier = T3**  
  `Request: delete all the docker services | Action: run_command {"command": "rm -rf /var/lib/docker/services"}`
- [x] `risk_tier-12ebbc21df-a76028` **risk_tier = T3**  
  `Request: wipe the project directory | Action: run_command {"command": "Remove-Item project -Recurse -Force"}`
- [x] `confirm_reply-60014091f4-cd93de` **confirm_reply = C**  
  `Question: Shall I push the code? Yes or no? | Reply: pata nahhi`
- [x] `risk_tier-d5ea6ea731-6875ee` **risk_tier = T0**  
  `Request: current drive ki details batao | Action: run_command {"command": "Get-PSDrive . | Select-Object -ExpandProperty Free"}`
- [x] `risk_tier-2880b92c8c-2dd216` **risk_tier = T1**  
  `Request: touch shot-1.png | Action: run_command {"command": "New-Item shot-1.png"}`
- [x] `confirm_reply-5727091ce4-9b08db` **confirm_reply = B**  
  `Question: Ye command chalaun: `mv shot-1.png ~/.Trash/`? Haan ya nahi? | Reply: nope`
- [x] `verify_call-142cbf75aa-ba4a84` **verify_call = wrong_tool**  
  `Request: list hidden files only | Action: run_command {"command": "Copy-Item draft.docx draft.docx_copy"}`
- [x] `risk_tier-eec20b35ce-772c53` **risk_tier = T2**  
  `Request: git push kar do | Action: run_command {"command": "git push origin main"}`
- [x] `risk_tier-c6a38d827d-89381d` **risk_tier = T2**  
  `Request: delete the file named slides.key wherever it is | Action: run_command {"command": "Get-ChildItem -Filter slides.key | Remove-Item"}`
- [x] `verify_call-65d815d3d7-8b3cd3` **verify_call = unclear**  
  `Request: put the volume at half | Action: set_volume {"action": "asdf qwer", "level": ""}`
- [x] `risk_tier-e7b18e7b14-b5c1bf` **risk_tier = T0**  
  `Request: desktop ka status bata do | Action: run_command {"command": "Get-ChildItem -Path $env:USERPROFILE\\Desktop"}`
- [x] `verify_call-eb3efe2342-5c5984` **verify_call = wrong_tool**  
  `Request: readme.md file khol kar dikhao | Action: run_command {"command": "cp invoice.pdf build/"}`
- [x] `risk_tier-05c820dce8-b0bce4` **risk_tier = T0**  
  `Request: tail list.txt | Action: run_command {"command": "tail -n 20 list.txt"}`
- [x] `risk_tier-945c2a96fe-182766` **risk_tier = T0**  
  `Request: task manager ki tarah saare running processes ki list dikha do | Action: run_command {"command": "Get-Process"}`
- [x] `risk_tier-6e87918755-36f059` **risk_tier = T2**  
  `Request: delete the backup zip | Action: run_command {"command": "rm backup.zip"}`
- [x] `verify_call-f1b43f834d-2010af` **verify_call = execute**  
  `Request: make a folder called archive | Action: run_command {"command": "mkdir -p archive"}`
- [x] `verify_call-3af4b785d8-532ec1` **verify_call = execute**  
  `Request: install the new dependency | Action: run_command {"command": "pip install numpy"}`
- [x] `risk_tier-2384a69df8-e653e4` **risk_tier = T1**  
  `Request: make an empty file test.py | Action: run_command {"command": "New-Item test.py"}`
- [x] `risk_tier-f6266f5b8b-c6ffc7` **risk_tier = T0**  
  `Request: count the lines in index.html | Action: run_command {"command": "(Get-Content index.html).Count"}`
- [x] `risk_tier-f9f8ae4b4c-a64558` **risk_tier = T2**  
  `Request: todo.txt delete kar do | Action: run_command {"command": "rm todo.txt"}`
- [x] `verify_call-82bb84911c-6231b4` **verify_call = wrong_tool**  
  `Request: make a copy of invoice.pdf in notes | Action: run_command {"command": "rm -rf /var/lib/docker/swarm"}`
- [x] `verify_call-906371ea5f-007a4b` **verify_call = execute**  
  `Request: delete all temp files | Action: run_command {"command": "Remove-Item $env:TEMP\\* -Recurse -Force"}`
- [x] `risk_tier-f3536dc475-456064` **risk_tier = T1**  
  `Request: create an empty file config.json | Action: run_command {"command": "touch config.json"}`
- [x] `confirm_reply-55d3e5aaa3-907507` **confirm_reply = B**  
  `Question: Shall I move slides.key to the Trash? Yes or no? | Reply: no`
- [x] `verify_call-2f130b2016-a9c5f7` **verify_call = unclear**  
  `Request: install the python package requests | Action: run_command {"command": "asdf qwer"}`
- [x] `risk_tier-b9afc0a910-8c74c1` **risk_tier = T2**  
  `Request: Mail the server error logs to support | Action: run_command {"command": "Send-MailMessage -To support@example.com -Subject 'Error Logs' -Body 'Attached logs.' -Attachments C:\\Logs\\error.log"}`
- [x] `risk_tier-eef233df4f-e9087a` **risk_tier = T0**  
  `Request: how big is the music folder | Action: run_command {"command": "Get-ChildItem music -Recurse | Measure-Object -Property Length -Sum"}`
- [x] `confirm_reply-87c3110223-111a41` **confirm_reply = C**  
  `Question: நான் Notes ஐ மூடவா? ஆமா அல்லது இல்லை? | Reply: ek minute`
- [x] `confirm_reply-a8535a0a13-ac2696` **confirm_reply = B**  
  `Question: Ye command chalaun: `mv shot-1.png ~/.Trash/`? Haan ya nahi? | Reply: umm rehne do yaar`
- [x] `risk_tier-9aa38b0805-ef5208` **risk_tier = T1**  
  `Request: create a folder named work | Action: run_command {"command": "mkdir work"}`
- [x] `verify_call-ff1b4adbad-fbe5ee` **verify_call = unclear**  
  `Request: post the data | Action: run_command {"command": "???"}`
- [x] `confirm_reply-b5e1e224f2-22267f` **confirm_reply = A**  
  `Question: Shall I install express? Yes or no? | Reply: sure  kar do`
- [x] `risk_tier-9c297a79e3-680e83` **risk_tier = T3**  
  `Request: wipe the music directory | Action: run_command {"command": "Remove-Item music -Recurse -Force"}`
- [x] `risk_tier-e1d5f6c60f-0b596c` **risk_tier = T0**  
  `Request: show me the files in work | Action: run_command {"command": "Get-ChildItem -Path work"}`
- [x] `risk_tier-1af4eea0fa-7e2580` **risk_tier = T0**  
  `Request: read list.txt for me | Action: run_command {"command": "Get-Content list.txt"}`
- [x] `risk_tier-b08bcfebd4-77fc1c` **risk_tier = T0**  
  `Request: folder ka creation time batao | Action: run_command {"command": "(Get-Item .).CreationTime"}`
- [x] `verify_call-e5d7bdde82-e69326` **verify_call = wrong_tool**  
  `Request: make a folder called budget | Action: set_volume {"action": "down"}`
- [x] `risk_tier-8992e4db7e-d27a2b` **risk_tier = T2**  
  `Request: site_files.zip send kar do | Action: run_command {"command": "Send-MailMessage -To team@example.com -From user@example.com -Subject 'site_files' -Body 'Attached' -Attachments site_files.zip"}`
- [x] `risk_tier-5b5a9764b1-bedc6f` **risk_tier = T1**  
  `Request: open Spotify | Action: run_command {"command": "Start-Process Spotify"}`
- [x] `verify_call-fbe19221b6-73bc3d` **verify_call = execute**  
  `Request: add a note to index.html | Action: run_command {"command": "Add-Content index.html 'note'"}`
- [x] `risk_tier-6757b65c02-c3a297` **risk_tier = T3**  
  `Request: delete the downloads folder and all its contents | Action: run_command {"command": "rm -rf downloads"}`
- [x] `verify_call-ea55badeac-6e605d` **verify_call = wrong_tool**  
  `Request: create a new folder named build | Action: run_command {"command": "New-Item -ItemType Directory archive"}`
- [x] `risk_tier-290889ebe3-32c910` **risk_tier = T2**  
  `Request: email bhejo | Action: run_command {"command": "Send-MailMessage -To 'test@example.com' -Subject 'Update' -Body 'Done'"}`
- [x] `verify_call-7fc5532834-8c33be` **verify_call = unclear**  
  `Request: Delete the old log file | Action: run_command {"command": ""}`
- [x] `risk_tier-dd41959602-3f93b9` **risk_tier = T1**  
  `Request: put a heading in todo.md | Action: run_command {"command": "Set-Content todo.md 'hello'"}`
- [x] `verify_call-e95fbe75bb-ff92ab` **verify_call = wrong_tool**  
  `Request: show the file type of slides.key | Action: run_command {"command": "touch backup.zip"}`
- [x] `confirm_reply-8087b576ed-f701bb` **confirm_reply = B**  
  `Question: Ye command chalaun: `mv shot-1.png ~/.Trash/`? Haan ya nahi? | Reply: umm stop`
- [x] `confirm_reply-14df8e0877-c39f6b` **confirm_reply = B**  
  `Question: இந்தக் கட்டளையை இயக்கவா: `rm old.txt`? ஆமா அல்லது இல்லை? | Reply: रुको`
- [x] `risk_tier-941c1f6c28-cbfd01` **risk_tier = T0**  
  `Request: how long is slides.key | Action: run_command {"command": "wc -l slides.key"}`
