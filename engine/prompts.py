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
PEOPLE extras: "hat": long_hair (woman) | blonde_hair | black_hair | red_hair | egypt_hair | curly_hair | short_hair | crown | helmet | turban, "beard": true,
  "wear": white|robe|toga|fur|rich|red|blue|green|pink|purple|yellow|gold. Use long_hair etc. so women look like women.
BG "ancient" = Greek/Roman temples (use it for Athens, Rome, Egypt cities; "city" is MODERN buildings).
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

HOOK_RULE = """- First 12-18 seconds are everything. Structure:
  1) Pattern interrupt or relatable open ("Right now you're sitting on something that used to be a death sentence.")
  2) Immediate surprising fact with a number or name.
  3) Clear promise of what they'll understand by the end.
  Never start with "In this video", "Today we're going to", or "Have you ever wondered"."""


def long_script_prompt(topic, minutes=8):
    words = int(minutes * 155)
    return f"""You are the head writer of a top-performing English YouTube channel that makes people unable to stop watching. Stick-figure animation, dry confident humour, Casually Explained energy mixed with modern high-retention history channels.

TOPIC: {topic}
LENGTH: about {words} words of narration (~{minutes} minutes). Every second must earn the next.

STORY RULES (non-negotiable)
- First 15 seconds must create an open loop the viewer needs closed. Start with a pattern interrupt, shocking fact, or direct challenge to the viewer. Never start with "In this video", "Today", or "Have you ever wondered".
- SOUND LIKE A PERSON talking to one friend. Mix short punches with flowing sentences. Use connectors: "So picture this,", "Here's the thing though,", "And honestly?", "Which is wild when you think about it.", "Okay but wait.", "You know what the crazy part is?"
- Talk directly to the viewer ("you", "imagine you're..."). React to the facts. Explain WHY it mattered and what it felt like, not just what happened.
- Dry joke or sharp observation every 20-30 seconds. No cringe, no like-and-subscribe.
- Real history only: real dates, places, archaeology, named sources. If historians disagree, say so clearly.
- One clear twist in the middle. End on a line that makes people want the next video or leaves a strong final image.
- Inject a pattern interrupt or mini-surprise roughly every 40-50 seconds.
- 10-18 scenes. Each scene = one short chapter name (2-4 words with a keyword). End each chapter with a mini-hook into the next.
- Each scene has 8-16 shots. Every shot has its own "say" (one natural spoken thought, 5-18 words). A new picture must appear every 2-3 seconds.
- VISUAL DOMINANCE: Maximum 12% "me" shots. Prefer "draw", "crowd", "diagram", "compare", "map", "timeline", "list". Never two "me" shots in a row. Whenever the narration describes an action, object, place, or person, draw it as a scene with specific props, poses, and faces.
- Prefer expressive poses: flex, panic, whisper, celebrate, facepalm, shrug, point_up, lean, present, clap, look, bow.
- Numbers as digits ("10,000", "3000 BC").

{SHOT_DOC}

{THUMB_DOC}

OUTPUT: ONLY valid JSON (no markdown, no comments) in exactly this shape. Thumbnails below are examples only — invent strong new ones for this topic:
{{
 "title": "curiosity question under 60 characters, main keyword in first 4 words",
 "thumbnail_text": "2-4 WORDS?",
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
   {{"chapter":"Chapter Name","shots":[ {{"type":"draw","bg":"grass","people":[{{"pose":"shrug","face":"confused"}}],"props":["toilet"],"text":"NO TOILET.","say":"So picture this. No toilet paper."}} ]}}
 ]
}}
Give 4 "shorts", each pointing to one scene (scene numbers start at 1) that is surprising on its own (30-55 s)."""


def quick_shorts_prompt(topic, variation=0):
    return f"""You write elite, high-retention YouTube Shorts in a dry, deadpan, slightly smug style (Casually Explained + modern viral history channels).

USER TOPIC: {topic}
Write TWO different Shorts:
 1) exactly the user's topic
 2) a NEW related topic that is even more surprising or shareable (you invent it — put the real topic name in "topic")
{"Variation " + str(variation) + ": deliberately avoid the most obvious angle and jokes. Find a fresher, weirder, or more specific angle." if variation else ""}

VIRAL RULES (non-negotiable):
- Length: 110-140 words total spoken (≈42-52 seconds). 15-20 shots.
- Shot 1 MUST be type "big". The text + say must be identical, max 7 words, and create an open loop or pattern interrupt.
  Good examples: "ROMANS BRUSHED TEETH WITH PEE", "THE OLDEST JOKE IS A FART", "OK WAS LITERALLY A JOKE"
  Bad examples: "Interesting fact about history", "Have you ever wondered..."
- Structure: 1) Pattern-interrupt hook  2) Quick confirmation  3) Origin  4) Weird twist  5) Modern comparison  6) Rewatch loop ending
- Voice: smart, slightly tired friend. Use "you", "honestly", "which is wild". Never lecture.
- Every "say" = 4-13 words. Real specific facts. Max 30% "me" shots. Never two "me" in a row.
- Prefer expressive poses: lean, present, clap, look, bow, flex, celebrate, facepalm, shrug, point_up, hips.
- Title under 48 chars. Description 1-2 punchy lines + hashtags. Pinned = spicy question.

{SHOT_DOC}

OUTPUT: ONLY valid JSON (no markdown):
{{
 "voice": "am_michael", "speed": 1.0,
 "shorts": [
  {{
   "topic": "...", "title": "curiosity title under 48 chars",
   "description": "1-2 strong lines + #shorts #history #tag",
   "pinned": "one question people will answer",
   "cover": "best visual moment",
   "shots": [ {{"type":"big","text":"HOOK IN CAPS.","say":"Hook in caps."}}, {{"type":"me","pose":"shrug","face":"unimpressed","text":"YES. REALLY.","say":"Yes. Really."}} ]
  }},
  {{ ... second short ... }}
 ]
}}"""
