---
name: text-stats
description: Analyze a text file — word/line/character counts and the most common words.
---

# Text statistics

Use this skill when the user asks about the size, length, or word frequency of a
text file (e.g. "how many words is this?", "what are the most common words?").

## How to do it

1. Make sure you have the file path. If unclear, use `list_dir` to find it.
2. Call the **`count_text_stats`** tool with the file `path`. It returns the
   line, word, and character counts plus the five most common words.
3. Report the numbers clearly. If the user asked only one thing (e.g. word
   count), lead with that and keep the rest brief.

Do not read the whole file with `read_file` just to count it — the
`count_text_stats` tool is faster and won't flood your context.
