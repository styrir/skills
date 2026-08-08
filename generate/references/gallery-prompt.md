# The gallery wall

A copy-paste prompt that builds a single-file local gallery page over the generations folder (`~/generations` for this install). One file, no server, opens in the browser. Because the skill saves flat into one folder, the wall never needs updating — new generations just appear.

Paste this into your agent exactly as written; it will ask about your folder path if it needs to:

```text
build me a single web page that shows every image and video my ai generates, all in one place, like a bento wall.
- it reads one folder on my computer called generations and shows everything sitting in it, newest at the top
- lay it out as a masonry wall - tiles keep their own shape, nothing gets cropped or squashed, rounded cards with even gaps, 4 columns wide and fewer as the window gets smaller
- videos start playing quietly when i hover over them and stop when i move away, images just sit there
- click any tile and it opens up big in the middle of the screen, click outside to close
- no search, no filters, no tabs, no side panels - just the wall of everything
keep it to one file so it runs by opening it, and make it feel like a proper finished gallery, not a rough draft.

when the page is done, add a line to my CLAUDE md so that from now on anything the /generate skill makes gets saved straight into that same generations folder, so it turns up on this page automatically. don't make the page pop open every time, just save the file there.
```

The last paragraph is the trick: it wires the folder rule into the agent's memory file, so the skill and the gallery stay pointed at the same folder forever.
