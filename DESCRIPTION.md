# My Little Elephant

**An elephant never forgets — and neither will you.**

My Little Elephant is a self-hosted, AI-powered memory keeper for families. It lives in your pocket (via Telegram or WhatsApp), captures life as it happens, and every morning delivers a warm, personalized story about what happened on this day in years past. It also keeps track of the people in your life — birthdays, relationships, life milestones — so you never miss a moment that matters.

Think of it as a private family historian with the memory of an elephant and the heart of a storyteller.

---

## How it works

**You text. It remembers. It reminds.**

Every family moment — first steps, park days, a cousin visiting from abroad, a funny thing your kid said at dinner — gets captured in a simple text message. The elephant parses it, stores it, and files it away forever in a Git-backed archive that you own.

But the elephant doesn't just remember *events*. It remembers *people*. It knows your close friends' birthdays and reminds you weeks ahead so you have time to plan a gift. It tracks when you last spoke to someone, what's going on in their lives — engagements, weddings, moves, new jobs — and the relationships between them ("James's sister Clara has a birthday on March 12"). When you mention you talked to a friend, it updates your contact history. When it's been a while, it gently nudges you: *"It's been a few weeks since you last spoke to James. Last time you mentioned he was planning his wedding — how's that going?"*

Every morning, it looks back through the years and writes you a short, warm story about what happened on this day. Not a list of events. A *story* — the kind that makes you pause over your coffee and smile. And if someone's birthday is coming up, it weaves that in naturally.

---

## A day with the elephant

**7:00 AM — Morning digest**

> Good morning! Two years ago today, Lily took her first steps in the living room — four wobbly steps toward Dad before tumbling into his arms. And last year, you spent the afternoon at Riverside Park with Rafael, who was visiting from Brazil. He taught Lily to say "obrigada" and she wouldn't stop saying it for a week. What a day that was.
>
> Oh, and heads up — James's birthday is in 12 days. Might be a good time to start thinking about a gift!

**Throughout the day — Anytime logging**

> **You:** Lily lost her first tooth at school today!
>
> **Elephant:** Got it! Logged: Lily's first tooth. Was she excited or scared? Did the tooth fairy leave anything?

The elephant asks follow-up questions when a memory feels thin — gently, like a good journalist. Your answers enrich the original memory.

**People tracking — it remembers who matters to you**

> **You:** Had coffee with James today
>
> **Elephant:** Nice! How's he doing? Last time you mentioned he was getting ready for his wedding.

> **You:** He said the wedding is set for June! And his sister Clara is going to be maid of honor.
>
> **Elephant:** That's great! I've noted that — James's wedding in June, and Clara is his sister and maid of honor. I'll remind you as it gets closer.

The elephant keeps a profile for each person: birthdays, life events (engagements, weddings, trips, job changes), their relationships to each other, and when you last spoke. When someone goes quiet for a while, it may nudge you to reach out.

**8:00 PM — Evening check-in**

> Anything worth remembering from today? Big or small — I'm all ears.

**After a digest — Feedback loop**

> **You:** Love this one!
>
> **Elephant:** Noted! I'll surface more milestones like these.

Reply to any digest and the elephant learns what you treasure. Over weeks, your morning stories become increasingly *yours* — more milestones if you love milestones, more people-focused if that's what makes you smile.

---

## What makes it different

**It's private.** Your memories live in YAML files on your own server, version-controlled with Git. No cloud database, no third-party storage. The only external call is to the LLM for writing and parsing.

**It's personal.** The elephant learns your preferences from your reactions. Positive feedback on milestone memories? It'll prioritize those. Bored by mundane daily logs? It'll dial them down. The nostalgia weights shift with every interaction.

**It knows your people.** Every person in your life gets a profile: birthday, relationship, life milestones, connections to others. Close friends get birthday reminders weeks ahead. The elephant tracks when you last spoke to someone and what was happening in their life — so you can be the friend who actually remembers.

**It's gentle.** It doesn't nag. It asks one clarification question at a time, rate-limited to avoid being intrusive. The evening check-in is a soft nudge, not a demand.

**It's permanent.** Every memory is a YAML file with a full Git history. You can read them, edit them, grep them, back them up. Twenty years from now, they'll still be plain text files you can open with anything.

**It costs almost nothing.** Telegram is free. The LLM costs a few dollars a month. Run it on a Raspberry Pi, a NAS, or a $5 VPS.

---

## The name

Elephants are famous for their extraordinary memory — they recognize faces after decades, remember water sources across hundreds of miles, and mourn their dead at specific locations years later. "My Little Elephant" captures that legendary recall in something intimate and warm: a small, personal companion that never forgets what matters to your family.

---

## Visual identity notes

- **Mood:** Warm, nostalgic, intimate. Morning light. Coffee and family photos.
- **The elephant:** Small, friendly, wise. Not cartoonish — gentle and thoughtful. Carries a soft glow, like it holds your memories inside. Think Miyazaki, not Disney.
- **Color palette:** Warm amber, soft cream, muted sage green, dusty rose. The palette of a well-loved photo album.
- **Typography:** Rounded, approachable serifs. Handwritten accents for warmth.
- **Texture:** Linen, aged paper, soft watercolor edges. Nothing glossy or corporate.
- **Taglines:**
  - "An elephant never forgets."
  - "Your family's memory, one morning at a time."
  - "Remember everything. Miss nothing."
  - "The stories that make a family."
