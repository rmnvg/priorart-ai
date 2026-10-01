# Demo video script (target 2:45, hard limit 3:00)

One inventor, one invention, one evidence-backed iteration. Everything else
(MCP server, examination preview, Ask, sketch input, the gallery) lives in the
README. The video's job is to make one outcome obvious:

> Describe your invention in your language, see what already exists, and explore
> a better design with evidence.

The rules ask for a screen recording of the project **running locally**. Record
at 1280×800 or larger, browser zoom 110%, one tab, with notifications off. The app
labels replays itself ("Replaying a saved analysis"), so leave that tag visible.

**Before recording** (see `launch-checklist.md`): run the Hindi crop-dryer idea
once, run the redesign studio on it with the two constraints below, and re-check
one alternative. Every step in the video is then a cached replay of a real run.

**Pick the take from the real outputs.** Before recording, read the cached report
and note which features were found, which weren't, and what the re-check showed.
Say what the screen actually shows; the lines below are a shape, not a script to
read over different results.

| Time | On screen | Say (roughly) |
|---|---|---|
| 0:00–0:15 | Home page | "A farmer in Maharashtra has an idea for a low-cost crop dryer. Finding out whether it's already patented usually means an expensive search, in English, done by a lawyer." |
| 0:15–0:30 | Click **हिंदी में उदाहरण** (or dictate a few words with 🎤), then **Analyze** | "She describes it in Hindi." |
| 0:30–0:50 | Progress checklist: "Understood your idea in Hindi", the **Indian Patent Office** search, the agent's terminology message, and **"Following up 2 documents the closest matches cite"** | "It searches US, European and Indian filings through SerpApi, learns the words the patents actually use and searches again, then fetches the documents the closest patents cite that keyword search missed." |
| 0:50–1:20 | **What we found**: the headline sentence, then one found feature with its quoted passage and the "from the claims" tag, then one "not found" feature | "No score to trust blindly. These features already exist, and here's the exact passage, checked word for word against the patent. This one wasn't found in the documents reviewed. That's what's different about her idea." |
| 1:20–1:30 | If the run has one: the blue **Citation follow-up changed this conclusion** note | "This came from a cited document keyword search never returned. It changed the answer, and the report says so." |
| 1:30–2:05 | **What you could change** → redesign studio: lock the feature that must stay, add **No electricity** and **under ₹2,000**, generate | "She keeps what she can't give up and sets her constraints. Each alternative names the overlap it moves away from, quoting the patent. Cost is a design target here, not a promise." |
| 2:05–2:35 | **Re-check this design** → the comparison card: original closest matches, what still overlaps (with quotes), new matches | "Then she re-checks one design against the same closest patents. What changed: the change isn't in either of them. What still overlaps, with the passage. And what's uncertain: the new matches this design ran into." |
| 2:35–2:45 | Scroll past the folded **Explore the research** to **How this report was built** | "Every query and every SerpApi call is there to audit." |

If the held-out benchmark has run, end with one line from
`backend/benchmark/results/latest.md` ("on 5 held-out inventions, 3 described in
Hindi, it found the real patent in the top ten N of 5 times"). If it hasn't run,
leave the benchmark out of the video rather than quoting a number.

**Voice versus the sample button.** Dictated text never matches the cached sample
exactly, so speaking starts a live run (about a minute, up to 16 searches). For a
cached take, dictate a few words to show the microphone, clear the box, then click
**हिंदी में उदाहरण**.

Cut first if you're over time: the progress-checklist narration, then the
"How this report was built" ending.
