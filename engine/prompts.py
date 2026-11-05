"""Prompts for Gemini / ChatGPT (script writing)."""
from . import draw as D

PROPS = sorted(set(k for k in D.PROPS if k.isalpha() or "_" in k))
POSES = sorted(D.POSES)
FACES = D.FACES
BGS = D.BGS

SHOT_DOC = f"""SHOT TYPES (each shot = one picture, 2-3 seconds of narration):
- {{"type":"me","pose":P,"face":F,"text":"SHORT CAPS TEXT","prop":PROP,"cross":true|"tick":true}}  narrator stick figure on white (text/prop/cross optional)
- {{"type":"big","text":"40,000 YEARS AGO."}}  huge black text, ends with a full stop
- {{"type":"draw","bg":BG,"people":[{{"pose":P,"face":F,"hold":PROP,"wear":"fur|robe|toga|rich"}}],"props":[PROP,...],"label":"CAVE NAME","think":PROP,"cross":true,"text":"CAPS","ai":"one-line picture description"}}  a scene (max 3 people, max 3 props)
- {{"type":"crowd","bg":BG,"count":8,"poses":[P,...],"faces":[F,...],"hold":PROP}}  many small people doing something
- {{"type":"diagram","title":"CAPS TITLE","steps":[[PROP,"Caption"],[PROP,"Caption"],[PROP,"Caption"]]}}  process with arrows (2-4 steps)
- {{"type":"map","region":"Mesopotamia","label":"FIRST COINS?","prop":PROP}}  world map with a highlighted place
- {{"type":"compare","left":{{"title":"THEN","prop":PROP,"mark":"x"}},"right":{{"title":"NOW","prop":PROP,"mark":"tick"}}}}
- {{"type":"timeline","title":"CAPS","points":[["3000 BC",PROP],["500 BC",PROP],["1800 AD",PROP]]}}
- {{"type":"list","title":"CAPS","items":[[PROP,"short text"],[PROP,"short text"]]}}
ANIMALS (use them in "props", they move a little): cat, dog, lion, elephant, owl, chicken, bear, rabbit, frog, crocodile, ape, monkey, goat, cow, pig, horse, camel, mammoth, deer, wolf, fish, bird, snake
Sky props (sun, moon, cloud, star, bird) float in the sky; outdoor scenes get flying birds automatically; fire flickers.
POSES: {", ".join(POSES)}
FACES: {", ".join(FACES)}
BG: {", ".join(BGS)}
PROPS (only these!): {", ".join(PROPS)}
MAP REGIONS: Mesopotamia, Egypt, Africa, Europe, Greece, Rome, Britain, Levant, Turkey, Persia, Arabia, India, Indus, Pakistan, China, Japan, Siberia, Australia, Americas, Mexico, Maya, Peru, Scandinavia, Spain, France, world"""


THUMB_DOC = """THUMBNAILS (the most important part for clicks) - give 3 DIFFERENT ideas, each with its own title:
- "text": 2-4 words, ALL CAPS, a shocking question or claim that makes people NEED to know (never the title again).
  Great examples: "DRUNK APES?", "PAID IN BEER?!", "13,000 YEAR OLD BEER?", "NO TOILET?", "THEY ATE THIS?".
- "title": a different curiosity title (under 60 characters) that fits this thumbnail.
- "color": green|orange|yellow|red|blue|purple|dark|pink|teal  (all 3 different, bright)
- "hero": "person" (our stick figure) or an animal/prop name (ape, drunk_ape, cat, lion, owl, demon...), drawn BIG
- "pose"/"face"/"wear" for a person hero. Faces must be strong: shocked, scared, smug, disgusted, laugh, excited, confused.
- "hold": prop in the hero's hand | "above": big prop above the head | "bg_prop": big prop behind the hero
- "props": up to 2 props on the right side, "marks": ["x","tick"] = red X / green tick on them
- "sidekick": {"pose":"point_left","face":"shocked"} small second person (optional) | "arrow": true (red arrow)
- "effects": any of stars, hearts, sweat, question, exclaim, stink, money
Make all 3 look very different (different hero, color and idea)."""

EX_THUMBS = """   {"text":"DRUNK APES?","title":"Humans Were Drinking Before They Were Human","color":"green","hero":"drunk_ape","hold":"apple","effects":["stars"],"sidekick":{"pose":"point_left","face":"shocked"}},
   {"text":"13,000 YEAR OLD BEER?","title":"Who Made the First Beer in History?","color":"dark","hero":"person","pose":"carry","face":"shocked","wear":"fur","above":"beer_bowl","arrow":true},
   {"text":"PAID IN BEER?!","title":"How Did Ancient Humans Discover Alcohol?","color":"orange","hero":"person","pose":"celebrate","face":"excited","hold":"beer","bg_prop":"pyramid","props":["coin","beer"],"marks":["x","tick"]}"""

HOOK_RULE = """- First 15 seconds: talk straight to the viewer about their own life ("Right now, millions of people are..."),
  then hit them with a surprising fact ("It's older than writing. Older than farming. Older than humans."),
  then promise what they will learn. Never start with "In this video"."""


def long_script_prompt(topic, minutes=8):
    words = int(minutes * 150)
    return f"""You are the head writer of a hugely successful English YouTube channel (US audience) that explains
"how did ancient / old-time humans do everyday things?" with simple stick-figure animation and calm,
dry, friendly humour (like Casually Explained meets a history teacher). Write a COMPLETE video script.

TOPIC: {topic}
LENGTH: about {words} words of narration (~{minutes} minutes).

STORY RULES
{HOOK_RULE}
- SOUND LIKE A PERSON, NOT A LIST OF FACTS. Write like a funny friend telling a story out loud:
  * Sentences flow into each other. A "say" can end with a comma and the next shot continues the sentence.
  * Mix short punchy lines with longer flowing ones. Never 5 tiny "Fact. Fact. Fact." lines in a row.
  * Use spoken connectors: "So picture this,", "Now, here's the thing.", "And honestly?", "Which, to be fair,",
    "Okay, quick question.", "Let me guess.", "You know what?", "...and that's where it gets weird."
  * Talk to the viewer ("you", "imagine you're..."), react to the facts ("Pleats. Somebody pleated this."),
    and make small jokes about yourself and modern life. Explain WHY things matter, not just WHAT happened.
  * Each "say" is 6-20 words (one natural spoken thought). Dry joke every 20-30 seconds. No cringe, no "smash that like button".
- Real history only: real dates, places, archaeology, named sources. If historians disagree, say so.
- A twist in the middle ("but here's the weird part..."). End with a line that makes people want the next video.
- 8-22 scenes (more for longer videos). Each scene = one chapter (2-4 word chapter name with a keyword).
- Each scene has 6-14 shots; every shot has its own "say" (one spoken thought, 6-20 words),
  so a new picture appears every 2-3 seconds. SHOW, DON'T TALK: only about 20% "me" (narrator), 10% "big",
  70% visuals ("draw" scenes with backgrounds, people and props, "crowd", "map", "diagram", "compare", "timeline", "list").
  Never two "me" shots in a row. Whenever the line describes something, DRAW it as a scene.
- Numbers can be written as digits ("10,000", "3000 BC"); the voice reads them correctly.

{SHOT_DOC}

{THUMB_DOC}

OUTPUT: ONLY valid JSON (no markdown, no comments) in exactly this shape (the thumbnails below are only examples, make your own for this topic):
{{
 "title": "curiosity question under 60 characters, main keyword in first 4 words",
 "thumbnail_text": "2-3 WORDS?",
 "voice": "am_michael", "speed": 1.0,
 "thumbnails": [
{EX_THUMBS}
 ],
 "seo": {{
   "titles": ["the 3 thumbnail titles first, then 2 more, each under 60 chars"],
   "best_title": "the best one",
   "description_hook": "2 lines: hook + main keyword naturally",
   "paragraphs": ["2-3 short paragraphs using related keywords naturally"],
   "sources": ["Real book or paper - Author (Year)", "..."],
   "tags": ["15-20 tags: exact topic, broad, long-tail questions"],
   "hashtags": ["#maintopic", "#history", "#ancienthumans"],
   "pinned_comment": "one short question viewers want to answer"
 }},
 "shorts": [
   {{"scenes":[3],"hook":"3-6 WORD HOOK?","title":"curiosity title under 50 chars","description":"1-2 lines","hashtags":["#shorts","#history","#topic"],"pinned":"question"}}
 ],
 "scenes": [
   {{"chapter":"Chapter Name","shots":[ {{"type":"me","pose":"shrug","face":"confused","text":"NO TOILET PAPER.","say":"So, no toilet paper."}} ]}}
 ]
}}
Give 4 "shorts", each pointing to one scene (scene numbers start at 1) that is surprising on its own (30-55 s)."""


def quick_shorts_prompt(topic, variation=0):
    return f"""You write viral YouTube Shorts in a dry, deadpan, funny style like "Casually Explained":
a stick-figure narrator on a white background, quick drawn props, charts, labels, red X / green tick, big text.

USER TOPIC: {topic}
Write TWO different Shorts:
 1) exactly the user's topic
 2) a NEW related topic in the same style that you choose (say what it is in "topic").
{"Use completely different jokes and angles than the obvious ones (variation " + str(variation) + ")." if variation else ""}

RULES for each Short (100-130 words total, 35-50 seconds):
- Shot 1 = the hook: a scroll-stopping line, type "big", same words in "text" and "say" (max 7 words).
  Make it a surprising claim or a question everyone has but never asked ("Why do we say bless you?").
- Then fast points: a new shot every 1.5-2.5 seconds. 14-20 shots in total.
- SOUND LIKE A FUNNY FRIEND TALKING, NOT A LIST OF FACTS:
  * Each "say" is one spoken thought (4-14 words). Lines can flow into each other with commas.
  * Use spoken connectors: "So,", "Okay, but", "Here's the thing.", "And honestly?", "Which, to be fair,".
  * Talk to the viewer ("you"), react to the facts, deadpan jokes. Never 4 tiny "Fact. Fact." lines in a row.
- Real facts only (if it's history or science). Simple words, US English.
- A funny twist near the end. The LAST line must loop naturally back into the first line so people rewatch.
- No "subscribe"/"follow" at the start. No emojis in "say".
- Mostly VISUAL shots: "draw" scenes (background + people + props), "compare", "list", "diagram", "map", "big".
  Only about 30% "me" shots, never two "me" in a row.
  Use animals and props from the lists below so every shot has something to look at.

{SHOT_DOC}

OUTPUT: ONLY valid JSON:
{{
 "voice": "am_michael", "speed": 1.0,
 "shorts": [
  {{"topic":"...", "title":"curiosity title under 50 chars", "description":"1-2 lines + #shorts #tag1 #tag2",
    "pinned":"one question for viewers", "cover":"which moment makes the best cover frame",
    "shots":[ {{"type":"big","text":"IS SHE INTO YOU?","say":"Is she into you?"}}, {{"type":"me","pose":"think","face":"thinking","say":"..."}} ]}},
  {{ ...second short... }}
 ]
}}"""
