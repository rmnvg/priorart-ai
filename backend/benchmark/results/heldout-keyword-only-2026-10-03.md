# Search-recall benchmark

_Run 2026-10-03 23:19 · 5 cases · 20 SerpApi searches attempted_

Given only a plain description of a real, granted invention, how often does the search surface the actual patent? The held-out cases were written after the search was tuned and include Hindi descriptions; quote those figures, not the development ones.

## Held-out cases

| | Top 1 | Top 10 | Top 10, exact publication only | Anywhere in results |
|---|---|---|---|---|
| First search round | 0% | 0% | 0% | 0% |
| After refinement agent | 0% | 0% | 0% | 0% |

5 case(s) scored, 0 error(s). Refinement moved the target up in 0 case(s) and down (or out) in 0. 20 SerpApi searches; 101s in total, median 20s per case.

## All cases

| | Top 1 | Top 10 | Top 10, exact publication only | Anywhere in results |
|---|---|---|---|---|
| First search round | 0% | 0% | 0% | 0% |
| After refinement agent | 0% | 0% | 0% | 0% |

5 case(s) scored, 0 error(s). Refinement moved the target up in 0 case(s) and down (or out) in 0. 20 SerpApi searches; 101s in total, median 20s per case.

## Per case

| Case | Split | Patent | Rank before | Rank after | Seconds | Searches |
|---|---|---|---|---|---|---|
| hi-snap-bricks | heldout | [US3005282A](https://patents.google.com/patent/US3005282A/en) Toy building brick | — | — | 18 | 4 |
| hi-twist-cube | heldout | [US4378116A](https://patents.google.com/patent/US4378116A/en) Spatial logical toy | — | — | 21 | 4 |
| hi-hook-loop | heldout | [US2717437A](https://patents.google.com/patent/US2717437A/en) Velvet type fabric and method of producing same | — | — | 24 | 4 |
| throwing-disc | heldout | [US3359678A](https://patents.google.com/patent/US3359678A/en) Flying saucer | — | — | 20 | 4 |
| sliding-teeth-closure | heldout | [US1219881A](https://patents.google.com/patent/US1219881A/en) Separable fastener | — | — | 18 | 4 |

## Failures (target not in the top 10)

### hi-snap-bricks — not returned at all

- Description: बच्चों के खेलने के लिए प्लास्टिक की छोटी ईंटें, जिनके ऊपर गोल उभार होते हैं और नीचे खोखला हिस्सा होता है, ताकि एक ईंट दूसरी पर दबाकर मज़बूती से जुड़ जाए और फिर आसानी से अलग भी हो सके।
- Translated for the search: Small plastic bricks intended for children's play, each featuring a rounded protrusion on the top surface and a hollow cavity on the bottom surface, enabling one brick to be pressed onto another so that they interlock securely yet can be easily disengaged.
- Queries run: `("plastic brick" OR "building block") ("rounded protrusion" OR "male stud") ("hollow cavity" OR "female socket")`; `("plastic brick" OR "toy block") ("stud" OR "socket")`; `("toy building block" OR "construction toy") (interlocking OR "snap fit") (stud OR hole OR socket)`; `("plastic brick" OR "building block") ("male connector" OR "female connector") ("snap-fit" OR "interlocking")`
- Refinement agent noticed: Patents describe your bricks using terms like "male connector" and "female connector" rather than just stud/socket, so search with that terminology.
- Results returned: 40. None of the queries used vocabulary that retrieves this patent.

### hi-twist-cube — not returned at all

- Description: हाथ में पकड़ने वाली घन के आकार की एक पहेली, जिसकी हर सतह की परतें अलग-अलग घुमाई जा सकती हैं ताकि रंग बिखर जाएँ, और खेलने वाले को घुमा-घुमाकर हर सतह पर फिर से एक ही रंग लाना हो।
- Translated for the search: A hand-held cubic puzzle, whose each face's layers can be rotated independently so that colors become scrambled, and the player must rotate them to bring each face back to a uniform single color.
- Queries run: `(hand-held OR portable) (cubic puzzle OR "cube puzzle") (rotatable face OR "face layer") (color scramble OR "uniform color")`; `(cube OR "rubik's cube") (rotatable OR twist) (puzzle)`; `(puzzle) (rotatable OR twist) (color) (cube OR block)`; `("twisting cube" OR "combinatorial twisting") (axis OR "central element") ("layer rotation" OR "face rotation")`
- Refinement agent noticed: Patents refer to the mechanism as a “twisting cube” with internal “axis” or “central element” for layer rotation, not just a hand‑held cube.
- Results returned: 41. None of the queries used vocabulary that retrieves this patent.

### hi-hook-loop — not returned at all

- Description: कपड़े या थैले बंद करने का एक तरीका जिसमें एक पट्टी पर बहुत छोटे-छोटे हुक होते हैं और दूसरी पट्टी पर मुलायम रोएँदार छल्ले, दोनों को दबाने पर वे चिपक जाते हैं और खींचने पर अलग हो जाते हैं — बटन या ज़िप की ज़रूरत नहीं।
- Translated for the search: A method for closing garments or bags comprising a first strip bearing a multitude of very small hooks and a second strip bearing soft, fuzzy loops; when the two strips are pressed together the hooks engage the loops, securing the closure, and when a pulling force is applied they disengage, releasing the closure—eliminating the need for buttons or zippers.
- Queries run: `("hook strip" OR "hook tape") ("soft fuzzy loop" OR "fuzzy loop strip") (press AND engage AND disengage)`; `(hook OR fastener) (loop OR fuzzy) (closure OR fastening)`; `("hook and loop" OR Velcro) (garment OR bag) (closure OR fastening OR buttonless OR zipperless)`; `("nap material" OR "hook material") ("loop material" OR "fuzzy nap") ("fabric panel" OR "closure seam")`
- Refinement agent noticed: Patents refer to the components as "nap material" and "fabric panel" rather than just hook or loop strips.
- Results returned: 43. None of the queries used vocabulary that retrieves this patent.

### throwing-disc — not returned at all

- Description: A light plastic disc with a curved rim that you throw with a flick of the wrist so it spins and glides a long way through the air, for playing catch on the beach.
- Queries run: `("light plastic disc" OR "plastic flying disc") ("curved rim" OR "rounded edge") ("flick throw" OR "wrist flick") (spin OR glide)`; `("plastic disc" OR "flying disc") ("curved rim" OR "rounded edge") (throw OR flick)`; `(disc OR flyer OR toy) (plastic OR polymer) (spin OR glide OR flight) (throw OR launch)`; `("launching disc" OR "handheld flyer") (slit OR bearing) (spin OR glide) (throw OR flick)`
- Refinement agent noticed: Prior patents describe it as a "launching disc" or "handheld flyer" with a "slit" or "bearing" rim, terms not in your queries.
- Results returned: 34. None of the queries used vocabulary that retrieves this patent.

### sliding-teeth-closure — not returned at all

- Description: A way to close a bag or jacket using two cloth strips edged with small metal teeth that lock into each other when a little slider is pulled along them, and come apart when it is pulled back.
- Queries run: `("cloth strip" OR "fabric strip") ("metal tooth" OR "metal teeth" OR "tooth latch") (slider OR "pull slider")`; `("fabric fastener" OR "cloth fastener") (slider OR "pull slider")`; `(fastener OR closure) (tooth OR interlock OR latch) (slider OR pull OR "adjustable pull")`; `("slide fastener" OR "zipper") ("strap" OR "tape") ("metal-tooth-like" OR "metal tooth") (slider OR "pull slider")`
- Refinement agent noticed: Patents refer to your concept as a "slide fastener" with "strap" or "tape" and "metal-tooth-like" elements, not just cloth strips.
- Results returned: 60. None of the queries used vocabulary that retrieves this patent.


Ranks count patents and papers only (the full app also lists products). A match is the exact publication (any kind code); "(family)" marks a different publication with the identical title, which is likely but not verified to be the same invention. This measures retrieval, not the legal accuracy of any verdict.
