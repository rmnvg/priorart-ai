# Demo video script (target 2:50, hard limit 3:00)

The rules ask for a screen recording of the project **running locally**. Record
at 1280×800 or larger, browser zoom 110%, one tab, with notifications off.

**Before recording** (see `launch-checklist.md`): warm the gallery, apply one
suggestion on the Hindi report once (so the re-check replays instantly), and run
the benchmark. Every run in the video is then a cached replay of a real run. The
progress events are the recorded ones, paced by `REPLAY_STEP_SECONDS`.

| Time | On screen | Say (roughly) |
|---|---|---|
| 0:00–0:15 | Home page | "A farmer in Maharashtra has an idea for a solar crop dryer. Finding out whether it's already patented means an expensive professional search, in English, done by a lawyer. PriorArt AI does a first pass in a minute, in her language." |
| 0:15–0:35 | Click 🎤, speak the Hindi idea (or click **हिंदी में उदाहरण**), then **Analyze** | "She just says it, in Hindi." |
| 0:35–0:55 | Progress checklist. Pause on "Understood your idea in Hindi", on the **Indian Patent Office filings** search, and on the agent's message about patent terminology | "It translates the idea into patent-search English, searches US, European and Indian filings through SerpApi, and then does what a professional searcher does: it reads the first results, learns the words the patents actually use, and searches again." |
| 0:55–1:15 | Hindi report: verdict, "यह आपके लिए क्या मतलब रखता है", then **Show in English** and back | "The verdict and advice come back in Hindi. The patent evidence stays in English, which is what a patent agent needs." |
| 1:15–1:30 | **Free to build on** section | "It also finds the patents in this space that have expired. That's technology she can legally use today." |
| 1:30–1:50 | Landscape graph (hover a node, point at citation arrows), then **Found by citation chasing** | "Every dot is real prior art. The arrows are actual patent citations, and citation chasing finds documents keyword search never returned." |
| 1:50–2:10 | **Apply & re-check** on a suggestion; the verdict moves | "Each suggestion is concrete. Apply one and the whole analysis re-runs, and you can watch the novelty score move." |
| 2:10–2:25 | India signal plus next steps, **Download attorney brief** (open the .md briefly) | "India-specific status, next steps with the Indian Patent Office, and a brief to hand to a patent agent." |
| 2:25–2:35 | Scroll to **How this report was built** | "Everything is traceable: the exact queries and every SerpApi call, across four engines." |
| 2:35–2:45 | Claude Desktop: ask "Has anyone patented a clay fridge that cools by evaporation?" and show the tool result | "And it's an MCP server too, so the same check works inside Claude or Cursor." |
| 2:45–2:55 | `backend/benchmark/results/latest.md` table | "On 12 real patents described in plain words, it finds the actual patent in the top ten X% of the time, and the refinement agent raises that from Y%." |

**Voice versus the sample button.** Dictated text never matches the cached sample
exactly, so speaking starts a live run: about a minute and up to 14 searches, which
is fine if you have quota and want it fully live. For a cached take, dictate a few
words to show the microphone working, clear the box, then click **हिंदी में उदाहरण**.

Cut first if you're over time: the attorney-brief file preview, then the English
toggle.
