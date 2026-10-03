# Search-recall benchmark

_Run 2026-10-03 23:22 · 5 cases · 45 SerpApi searches attempted_

Given only a plain description of a real, granted invention, how often does the search surface the actual patent? The held-out cases were written after the search was tuned and include Hindi descriptions; quote those figures, not the development ones.

## Held-out cases

| | Top 1 | Top 10 | Top 10, exact publication only | Anywhere in results |
|---|---|---|---|---|
| First search round | 0% | 0% | 0% | 0% |
| After refinement agent | 0% | 0% | 0% | 0% |

5 case(s) scored, 0 error(s). Refinement moved the target up in 0 case(s) and down (or out) in 0. 45 SerpApi searches; 64s in total, median 11s per case.

With citation chasing (5 cases measured): the target is in the top 10 or among the report's citation discoveries in **0%** of cases.

## All cases

| | Top 1 | Top 10 | Top 10, exact publication only | Anywhere in results |
|---|---|---|---|---|
| First search round | 0% | 0% | 0% | 0% |
| After refinement agent | 0% | 0% | 0% | 0% |

5 case(s) scored, 0 error(s). Refinement moved the target up in 0 case(s) and down (or out) in 0. 45 SerpApi searches; 64s in total, median 11s per case.

With citation chasing (5 cases measured): the target is in the top 10 or among the report's citation discoveries in **0%** of cases.

## Per case

| Case | Split | Patent | Rank before | Rank after | Citation discovery | Seconds | Searches |
|---|---|---|---|---|---|---|---|
| hi-snap-bricks | heldout | [US3005282A](https://patents.google.com/patent/US3005282A/en) Toy building brick | — | — | — | 24 | 9 |
| hi-twist-cube | heldout | [US4378116A](https://patents.google.com/patent/US4378116A/en) Spatial logical toy | — | — | — | 8 | 9 |
| hi-hook-loop | heldout | [US2717437A](https://patents.google.com/patent/US2717437A/en) Velvet type fabric and method of producing same | — | — | — | 12 | 9 |
| throwing-disc | heldout | [US3359678A](https://patents.google.com/patent/US3359678A/en) Flying saucer | — | — | — | 11 | 9 |
| sliding-teeth-closure | heldout | [US1219881A](https://patents.google.com/patent/US1219881A/en) Separable fastener | — | — | — | 9 | 9 |

## Failures (target not in the top 10)

### hi-snap-bricks — not returned at all

- Description: बच्चों के खेलने के लिए प्लास्टिक की छोटी ईंटें, जिनके ऊपर गोल उभार होते हैं और नीचे खोखला हिस्सा होता है, ताकि एक ईंट दूसरी पर दबाकर मज़बूती से जुड़ जाए और फिर आसानी से अलग भी हो सके।
- Translated for the search: Small plastic bricks intended for children's play, each featuring a rounded protrusion on the top surface and a hollow cavity on the bottom surface, enabling one brick to be pressed onto another so that they interlock securely yet can be easily separated.
- Queries run: `(plastic OR polymer) (brick OR block) (rounded protrusion OR knob) (hollow cavity OR socket) (interlock* OR snap fit)`; `(plastic block OR toy brick) (interlock* OR snap) (toy)`; `(building toy OR construction toy) (stackable OR snap fit OR interlocking) (child* OR kid*) (plastic OR polymer)`; `("stud" OR "male connector") ("recess" OR "female cavity" OR "tongue and groove") (plastic OR polymer) ("toy brick" OR "building block")`
- Refinement agent noticed: Patents describe the pieces using "stud"/"male connector" and "recess"/"female cavity" (tongue‑and‑groove) rather than rounded protrusion/knot.
- Results returned: 60. None of the queries used vocabulary that retrieves this patent.

### hi-twist-cube — not returned at all

- Description: हाथ में पकड़ने वाली घन के आकार की एक पहेली, जिसकी हर सतह की परतें अलग-अलग घुमाई जा सकती हैं ताकि रंग बिखर जाएँ, और खेलने वाले को घुमा-घुमाकर हर सतह पर फिर से एक ही रंग लाना हो।
- Translated for the search: A cube-shaped handheld puzzle in which each face consists of layers that can be rotated independently, causing the colors to become scrambled. The player must rotate the layers so that each face returns to a uniform single color.
- Queries run: `("cube puzzle" OR "cube-shaped puzzle") ("rotatable layers" OR "rotatable face layers") ("uniform color" OR "single color face")`; `(cube OR block) (puzzle OR game) (rotate OR twist)`; `(mechanical puzzle OR twist puzzle) (rotatable OR twistable) (color matching OR color alignment)`; `("rotating cube" OR "twistable cube") ("facelet" OR "colored facelet") ("slice rotation" OR "layered rotation mechanism")`
- Refinement agent noticed: Patents refer to the device as a "rotating cube" with "facelets" and "layered rotation mechanism", not just generic cube puzzle terms.
- Results returned: 21. None of the queries used vocabulary that retrieves this patent.

### hi-hook-loop — not returned at all

- Description: कपड़े या थैले बंद करने का एक तरीका जिसमें एक पट्टी पर बहुत छोटे-छोटे हुक होते हैं और दूसरी पट्टी पर मुलायम रोएँदार छल्ले, दोनों को दबाने पर वे चिपक जाते हैं और खींचने पर अलग हो जाते हैं — बटन या ज़िप की ज़रूरत नहीं।
- Translated for the search: A method for closing a garment or bag comprising a first strip that carries a multitude of very small hooks and a second strip that carries soft, fuzzy loops. When the two strips are pressed together, the hooks engage the loops and adhere, and when pulled apart they disengage. No buttons or zippers are required.
- Queries run: `("hook strip" OR "hooked strip") ("loop strip" OR "fuzzy loops") (fastening OR closure)`; `(hooks OR "hooked fastener") (loops OR "fuzzy loops") (garment OR bag)`; `(hook AND loop) (fastener OR closure OR "velcro") (textile OR garment OR bag)`; `("hook and loop fastener" OR "releasable fastener") (garment OR bag) (fastening OR closure)`
- Refinement agent noticed: Patents refer to your idea as a "hook and loop fastener" or "releasable fastener" rather than just hook/loop strips.
- Results returned: 58. None of the queries used vocabulary that retrieves this patent.

### throwing-disc — not returned at all

- Description: A light plastic disc with a curved rim that you throw with a flick of the wrist so it spins and glides a long way through the air, for playing catch on the beach.
- Queries run: `("light plastic disc" OR "plastic flying disc") ("curved rim") (throw OR flick) (spin OR glide)`; `("plastic disc" OR "toy disc") (beach OR sand) (throwable OR flick)`; `("flying toy" OR "throwable toy") (disc OR disk) (spinning OR rotating) (recreational OR play)`; `("circular airfoil" OR "convex/concave surface") ("peripheral flange" OR "edge flange") (throwable OR hand-throwable) (spin OR rotate)`
- Refinement agent noticed: Patents describe the rim as a "peripheral flange" or "edge flange" and the disc as a "circular airfoil" with a "convex/concave surface" which were not in earlier searches.
- Results returned: 20. None of the queries used vocabulary that retrieves this patent.

### sliding-teeth-closure — not returned at all

- Description: A way to close a bag or jacket using two cloth strips edged with small metal teeth that lock into each other when a little slider is pulled along them, and come apart when it is pulled back.
- Queries run: `("cloth strip" OR "fabric strip") ("metal tooth" OR "metal teeth" OR "tooth latch") (slider OR "pull slider" OR "slider actuator")`; `("fabric fastener" OR "cloth closure" OR "strip closure") (slider OR "pull tab" OR "actuator")`; `(fastener OR closure) (tooth OR "interlock" OR "locking tooth") (slider OR pull OR "adjustable strap")`; `("interlocking tape" OR "interlocking strip") ("slide fastener" OR zipper) (slider OR "pull tab" OR actuator)`
- Refinement agent noticed: Patents refer to your concept as an "interlocking tape" or "interlocking strip" within a slide‑fastener (zipper) system, not just cloth strips with metal teeth.
- Results returned: 60. None of the queries used vocabulary that retrieves this patent.


Ranks count patents and papers only (the full app also lists products). A match is the exact publication (any kind code); "(family)" marks a different publication with the identical title, which is likely but not verified to be the same invention. This measures retrieval, not the legal accuracy of any verdict.
