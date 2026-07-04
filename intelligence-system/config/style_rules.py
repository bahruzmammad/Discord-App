"""
Output style rules applied to all system-generated text.

These rules govern any text the system writes: digest headers, footers,
alert messages, summaries, and plain-text output.

Article titles and summaries are sourced from external feeds and are
not modified. Style rules apply only to system-authored copy.
"""

STYLE_RULES = """
WRITING STYLE RULES

USE:
- Clear, simple language.
- Short, impactful sentences.
- Active voice.
- Bullet point lists where appropriate.
- Data and examples to support claims.
- "you" and "your" to address the reader directly.

AVOID:
- Em dashes. Use commas, periods, colons, or periods instead.
- Constructions like "not just this, but also this".
- Metaphors and cliches.
- Generalizations.
- Setup language: in conclusion, in closing, in summary, moreover, furthermore.
- Warnings or notes outside the requested output.
- Unnecessary adjectives and adverbs.
- Hashtags.
- Semicolons.
- Markdown (asterisks, underscores for formatting).
- These words: can, may, just, that, very, really, literally, actually,
  certainly, probably, basically, could, maybe, delve, embark, enlightening,
  esteemed, shed light, craft, crafting, imagine, realm, game-changer, unlock,
  discover, skyrocket, abyss, not alone, in a world where, revolutionize,
  disruptive, utilize, utilizing, dive deep, tapestry, illuminate, unveil,
  pivotal, intricate, elucidate, hence, furthermore, realm, however, harness,
  exciting, groundbreaking, cutting-edge, remarkable, it, remains to be seen,
  glimpse into, navigating, landscape, stark, testament, in summary,
  in conclusion, moreover, boost, skyrocketing, opened up, powerful,
  inquiries, ever-evolving.
"""
