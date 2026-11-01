---
status: example
rolls: [1]
---

# Vertical batch: example

One file per batch of vertical videos. Each video is a `## N. Title` section with speech blocks
`### N.M`. The same rules as `videos/example/script.md`: paragraphs are pauses, [brackets] are
triggers, `>` lines are notes. Special blocks:

- `N.0` is the slate: when the person records all videos in one take, they say the number first
  ("video one", two seconds of pause). It is used to cut the recording and never goes into the video.
- `N.8` is the ending for YouTube Shorts (`yt`), `N.9` for Instagram Reels and TikTok (`ig`, `tt`).
  If `N.9` is missing, `N.9` falls back to `N.8`. An ending is one short line: ask for a like or a
  follow, or just close. The kit draws the platform's button on the trigger word.

Build: `python3 engine/vertical.py build vertical/example.md 1 yt`, scene in `engine/scenes/example/s1.js`
(the project name is the file name without `.md`).

## 1. The word for hello

### 1.0

Video one.

### 1.1

Some languages have [three] words for hello.

### 1.2

One for a stranger, one for a friend, and one for the people you see every [day].

### 1.3

Pick the wrong one and the conversation is over before it [started].

### 1.8

If you learned something, tap [like].

### 1.9

Follow for the next [one].
