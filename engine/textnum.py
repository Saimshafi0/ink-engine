"""Turn numbers/symbols into words so the voice reads them correctly."""
import re

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
BIG = [(10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand"), (100, "hundred")]
ORD = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth", "nine": "ninth", "twelve": "twelfth"}


def num_words(n):
    n = int(n)
    if n < 0:
        return "minus " + num_words(-n)
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else "-" + ONES[n % 10])
    for v, name in BIG:
        if n >= v:
            head, rest = divmod(n, v)
            s = num_words(head) + " " + name
            if rest:
                s += (" and " if rest < 100 and v == 100 else " ") + num_words(rest)
            return s
    return str(n)


def year_words(n):
    n = int(n)
    if 2000 <= n <= 2009:
        return num_words(n)
    if 1000 <= n <= 2099 and n % 1000 != 0:
        hi, lo = divmod(n, 100)
        if lo == 0:
            return num_words(hi) + " hundred"
        return num_words(hi) + " " + (("oh " + ONES[lo]) if lo < 10 else num_words(lo))
    return num_words(n)


def ordinal(n):
    w = num_words(n)
    last = re.split(r"([ -])", w)
    tail = last[-1]
    if tail in ORD:
        tail = ORD[tail]
    elif tail.endswith("y"):
        tail = tail[:-1] + "ieth"
    else:
        tail += "th"
    return "".join(last[:-1]) + tail


def _dec(m):
    a, b = m.group(1).replace(",", ""), m.group(2)
    return num_words(int(a)) + " point " + " ".join(ONES[int(c)] for c in b)


def speakable(text):
    t = " " + text + " "
    t = t.replace("—", ", ").replace("–", " to ").replace("…", "...")
    t = re.sub(r"\$(\d[\d,]*)(\.\d+)?\s*(million|billion|thousand|trillion)?", lambda m: num_words(int(m.group(1).replace(",", ""))) + (" point " + " ".join(ONES[int(c)] for c in m.group(2)[1:]) if m.group(2) else "") + (" " + m.group(3) if m.group(3) else "") + " dollars", t)
    t = re.sub(r"(\d+)\s*%", lambda m: num_words(int(m.group(1))) + " percent", t)
    t = re.sub(r"(\d+)(st|nd|rd|th)\b", lambda m: ordinal(int(m.group(1))), t)
    t = re.sub(r"\b(\d{1,4})s\b", lambda m: (year_words(m.group(1)) if len(m.group(1)) == 4 else num_words(m.group(1))).rstrip("y") + ("ies" if (year_words(m.group(1)) if len(m.group(1)) == 4 else num_words(m.group(1))).endswith("y") else "s"), t)
    t = re.sub(r"\b(\d{3,4})\s*(BC|BCE|AD|CE|B\.C\.|A\.D\.)", lambda m: year_words(m.group(1)) + " " + {"BC": "B C", "BCE": "B C E", "AD": "A D", "CE": "C E", "B.C.": "B C", "A.D.": "A D"}[m.group(2)], t)
    t = re.sub(r"\bin (1[0-9]{3}|20[0-9]{2})\b", lambda m: "in " + year_words(m.group(1)), t)
    t = re.sub(r"\b(1[1-9][0-9]{2}|20[0-9]{2})\b(?![,\d])", lambda m: year_words(m.group(1)), t)
    t = re.sub(r"(\d[\d,]*)\.(\d+)", _dec, t)
    t = re.sub(r"\d{1,3}(?:,\d{3})+|\d+", lambda m: num_words(int(m.group(0).replace(",", ""))), t)
    t = t.replace("&", " and ").replace(" vs ", " versus ").replace(" vs. ", " versus ")
    t = re.sub(r"\s+", " ", t)
    return t.strip()


if __name__ == "__main__":
    for s in ["10,000,000 YEARS AGO.", "It cost $5.", "In 1347 the plague came.", "About 3000 BC", "the 1800s", "50% of people", "9 thousand years ago", "the 2nd time", "3.5 million years", "In 2008"]:
        print(s, "->", speakable(s))
