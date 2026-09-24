# Demo video script (target 2:50, hard limit 3:00)

The rules ask for a screen recording of the project **running locally**. Record
at 1280×800 or larger, browser zoom 110%, one tab, with notifications off.

The app labels replays itself ("Replaying a saved analysis"), so leave that tag
visible rather than hiding it.

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
| 1:30–1:40 | Landscape graph: point at the citation arrows | "Every dot is real prior art; the arrows are actual patent citations." |
| 1:40–2:00 | **See how an Indian patent examiner would respond**: the element table (tap a mark to show the quote), then the novelty core | "Then it reads the evidence like an Indian patent examiner: element by element, every match backed by a quote from the patent, checked in code. Here's what no patent covers, which is what she should build her application around." |
| 2:00–2:10 | Open the **herbal wound paste** example and its examination preview, showing the **Section 3(p)** flag | "And some ideas aren't patentable in India at all. This one is likely traditional knowledge under Section 3(p). She finds that out before paying filing fees." |
| 2:10–2:20 | **Apply & re-check** on a suggestion; show the comparison card | "Apply a suggestion and it re-checks against the original closest patents: the change isn't in either of them, here's what they still share, and here are the new matches the change ran into." |
| 2:20–2:30 | **Ask about this report**: tap the Hindi question "क्या मैं इसे भारत में बना कर बेच सकता हूँ?" and show the cited answer | "She can ask follow-ups in Hindi, and every answer cites the patents it's based on." |
| 2:30–2:37 | Scroll to **How this report was built** | "Every query and every SerpApi call, across four engines." |
| 2:37–2:45 | Claude Desktop: ask "Has anyone patented a clay fridge that cools by evaporation?" and show the tool result | "And it's an MCP server too, so the same check works inside Claude or Cursor." |
| 2:45–2:55 | `backend/benchmark/results/latest.md` table | "On 12 real patents described in plain words, it finds the actual patent in the top ten X% of the time, and the refinement agent raises that from Y%." |

**Voice versus the sample button.** Dictated text never matches the cached sample
exactly, so speaking starts a live run: about a minute and up to 14 searches, which
is fine if you have quota and want it fully live. For a cached take, dictate a few
words to show the microphone working, clear the box, then click **हिंदी में उदाहरण**.

Cut first if you're over time: the English toggle, then "Found by citation
chasing". If you have spare seconds, show **Download attorney brief** next to the
India next-steps card.
