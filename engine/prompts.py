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
POSES: {", ".join(POSES)}
FACES: {", ".join(FACES)}
BG: {", ".join(BGS)}
PROPS (only these!): {", ".join(PROPS)}
MAP REGIONS: Mesopotamia, Egypt, Africa, Europe, Greece, Rome, Britain, Levant, Turkey, Persia, Arabia, India, Indus, Pakistan, China, Japan, Siberia, Australia, Americas, Mexico, Maya, Peru, Scandinavia, Spain, France, world"""


def long_script_prompt(topic, minutes=8):
    words = int(minutes * 150)
    return f"""You are the head writer of a hugely successful English YouTube channel (US audience) that explains
"how did ancient / old-time humans do everyday things?" with simple stick-figure animation and calm,
dry, friendly humour (like Casually Explained meets a history teacher). Write a COMPLETE video script.

TOPIC: {topic}
LENGTH: about {words} words of narration (~{minutes} minutes).

STORY RULES
- First 15 seconds: ask the question, give one surprising fact, promise what the viewer will learn.
- Short spoken sentences. Dry jokes every 20-30 seconds. No cringe, no "smash that like button".
- Real history only: real dates, places, archaeology, named sources. If historians disagree, say so.
- A twist in the middle ("but here's the weird part..."). End with a line that makes people want the next video.
- 8-14 scenes. Each scene = one chapter (2-4 word chapter name with a keyword).
- Each scene has 6-14 shots; every shot has its own "say" (one short sentence or half sentence, 5-12 words),
  so a new picture appears every 2-3 seconds. About 45% "me", 10% "big", 45% scenes/diagrams/maps.
- Numbers can be written as digits ("10,000", "3000 BC"); the voice reads them correctly.

{SHOT_DOC}

OUTPUT: ONLY valid JSON (no markdown, no comments) in exactly this shape:
{{
 "title": "curiosity question under 60 characters, main keyword in first 4 words",
 "thumbnail_text": "2-3 WORDS?",
 "voice": "am_michael", "speed": 1.0,
 "thumbnails": [
   {{"text":"2-3 WORDS","face":"shocked","pose":"scared","bg":"cave","props":["skull","fire"]}},
   {{"text":"OTHER 2-3 WORDS","face":"smug","pose":"point_up","bg":"desert","props":["coin"]}},
   {{"text":"THIRD IDEA","face":"confused","pose":"shrug","bg":"village","props":["pot"],"mark":"x"}}
 ],
 "seo": {{
   "titles": ["5 title options, each under 60 chars"],
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

RULES for each Short (110-140 words total, 35-55 seconds):
- Shot 1 = the hook: a scroll-stopping line, type "big", same words in "text" and "say" (max 7 words).
- Then fast points: a new shot every 1.5-2 seconds (each "say" = 4-9 words). 14-22 shots in total.
- A funny twist near the end. The LAST line must loop naturally back into the first line so people rewatch.
- No "subscribe"/"follow" at the start. No emojis in "say".
- Mostly "me" shots (pose/face changes a lot) + "big", "list", "compare", "diagram", "draw" shots.

{SHOT_DOC}

OUTPUT: ONLY valid JSON:
{{
 "voice": "am_michael", "speed": 1.05,
 "shorts": [
  {{"topic":"...", "title":"curiosity title under 50 chars", "description":"1-2 lines + #shorts #tag1 #tag2",
    "pinned":"one question for viewers", "cover":"which moment makes the best cover frame",
    "shots":[ {{"type":"big","text":"IS SHE INTO YOU?","say":"Is she into you?"}}, {{"type":"me","pose":"think","face":"thinking","say":"..."}} ]}},
  {{ ...second short... }}
 ]
}}"""
