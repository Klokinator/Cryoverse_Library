# Agent Plan: Converting The Cryopod to Hell to Third Person Omniscient Past-Tense

**Project Goal:** Convert all chapters of "The Cryopod to Hell" from mixed narrative perspectives and tenses to consistent third-person omniscient past-tense narration, with character thoughts italicized and attributed, while maintaining all story content and cleaning up grammar.

IMPORTANT: UNDER NO CIRCUMSTANCES SHOULD YOU ATTEMPT TO PERFORM THIS OPERATION WITH ANY SORT OF BATCH PYTHON COMMAND. YOU MUST EDIT EVERY PART ONE BY ONE. DO **NOT** CREATE A BATCH EDITING TOOL TO 'SPEED UP' THE WORKFLOW!!

**Last Updated:** January 20, 2026

---

## Core Conversion Rules

### 1. Narrative Perspective
- **Convert to Third-Person Omniscient:** All narration shifts to omniscient third-person perspective
- **All characters referred to by name or pronoun:** Never use first-person direct address (e.g., "I", "my", "me", "we")
- **Example conversion:**
  - Original (first-person narration): My hopes dash against the rocks.
  - Converted: Jason's hopes were dashed against the rocks.

### 2. Tense Standardization
- **Convert all action to past tense**
- **Maintain past tense consistently throughout**
- **Special cases:**
  - Dialogue remains in present context but past-tense framing: `"What is this?" Jason asked.`
  - Subjective observations become "seemed to be" or similar hedging: "The air seemed to be trembling in fear."
  - Universal truths and facts may remain timeless: "Water was essential to life." (if describing general knowledge)

### 3. Internal Thought Formatting
- **All character thoughts italicized with em-dashes or "he/she/they thought" tags**
- **Thought attribution rules:**
  - Add character name tags when multiple characters' thoughts appear in close succession (same scene/paragraph sequence)
  - Add tags when perspective clearly shifts between characters
  - Use common sense: if reader confusion is possible, add a tag; if the character is obvious from context, tags are optional
  - Format: `_Character's thought here._ Character thought.` OR `_Character's thought here._` (if context is clear)
- **Example:**
  ```
  Jason's hopes were dashed against the rocks. 
  
  _Let's be realistic about this, Jason, and consider what we know._ He thought.
  
  The floor was comfortably warm, like sitting a few feet away from a fire, while also covered in smooth dirt. The air itself seemed to be trembling in fear.
  
  _Everyone I've ever known and loved is probably dead. I'm at least somewhat sure that I'm not in the original CryoTek lab where I started out, and I may have evolved a spider-sense._ Jason thought.
  ```

### 4. Dialogue Handling — **CRITICAL RULE: DO NOT ALTER DIALOGUE TENSE OR WORDING**
- **ALL dialogue in quotation marks remains EXACTLY AS WRITTEN in the original file**
- **Do NOT change the tense, pronouns, or any wording within dialogue, even if it doesn't match narrative tense**
- **Only change the attribution tag from present to past:** `Jason says` → `Jason said`
- **WRONG:** `"I can't believe this," he says.` → `"I couldn't believe this," he said.` ❌ DO NOT DO THIS
- **CORRECT:** `"I can't believe this," he says.` → `"I can't believe this," he said.` ✓ KEEP DIALOGUE EXACTLY AS-IS
- **Bracketed `[dialogue]` is reserved for:**
  - Telepathic communication between mind-linked characters
  - Internal Mind Realm communication
  - These are NOT thoughts; they are communication between characters
  - Preserve bracketed content exactly as written
- **Maintain all intentional accents and speech impediments exactly as written**
- **Example distinction:**
  - Telepathy (preserve exactly): `[I sense someone approaching,] Uzziel communicated.` → `[I sense someone approaching,] Uzziel communicated.`
  - Regular dialogue (preserve exactly, change only attribution): `"You bastard! What the hell are you?" Oni shouts.` → `"You bastard! What the hell are you?" Oni shouted.`
  - Thought (convert to first-person if narration): `_Damn. Can't feel my arms or legs._ Oni thought.`

### 5. Scene Break Formatting
- **Major scene breaks (location/time change):** Maintain EXACT original dot separator count (typically 50+ dots)
- **Minor time shifts within same scene:** Use exactly three dots `...` on their own line
- **Example:**
  ```
  [End of scene]
  .................................................. (50+ dots - exact count from original)
  [New scene begins]
  
  [Later in same location]
  ...
  [Scene continues]
  ```

### 6. Grammar and Spelling Cleanup
- **Correct obvious typos and spelling errors**
- **EXCEPTION:** Preserve intentional misspellings in dialogue/thoughts that indicate:
  - Character accents or dialect
  - Character intelligence level or education
  - Emphasis or emotional state
- **Fix:**
  - Capitalization errors outside dialogue
  - Punctuation consistency
  - Subject-verb agreement
  - Tense inconsistencies
  - Proper noun capitalization
- **Do NOT fix:**
  - Intentional accent markers (e.g., "pwetty hawd" for character speech impediment)
  - Character-voiced misspellings that add characterization
  - Stylistic choices (e.g., creative onomatopoeia like "Fwooooom!")

### 8. File Size Validation
- **After conversion, compare file sizes: `_complete` file must be ≥ original file**
- **If `_complete` is smaller:** Review for accidentally deleted text; re-examine entire chapter once
- **If `_complete` is larger:** Acceptable
- **Size check procedure:**
  - Document original file byte size
  - Document `_complete` file byte size
  - If 2kb+ discrepancy exists, audit the entire file for missing content
  - Only audit the file once

---

## Identified Pain Points and Solutions

### Pain Point 1: Perspective Shift Complexity
**Issue:** Multiple POV characters in single chapters with simultaneous scenes
**Solution:** Use character name tags strategically to clarify whose thoughts/perspective the reader is in when switching
**Implementation:** Review before major perspective shifts; add tags where confusion is likely

### Pain Point 2: Tense Consistency
**Issue:** Present-tense action mixed with past-tense reflection
**Solution:** Standardize all to past tense; use "seemed to be" or similar for subjective observations that were originally present-tense
**Example:** The air is trembling → The air seemed to be trembling

### Pain Point 3: Internal Monologue Format Variation
**Issue:** Some thoughts italicized, some plain text, some bracketed inconsistently
**Solution:** All character thoughts are italicized; all bracketed content is telepathy/Mind Realm communication
**Implementation:** Scan entire chapter for variations and standardize

### Pain Point 4: First-Person to Omniscient Bridge
**Issue:** Early chapters establish intimate first-person; later chapters are omniscient
**Solution:** Convert all first-person narration to third-person omniscient with character name (e.g., "Jason's hopes were dashed...")
**Implementation:** Replace all "I/my/me/we/us" with character names/pronouns

### Pain Point 5: Lengthy Italicized Passages
**Issue:** Multi-paragraph thoughts difficult to distinguish from action/dialogue in reformatted version
**Solution:** Add character name tags to clarify who is thinking; consider strategic paragraph breaks
**Implementation:** Review passages longer than 3-4 lines; add clarification tags

### Pain Point 6: Simultaneous Scene Shifts
**Issue:** Two "current moment" scenes occurring simultaneously without clear POV anchor
**Solution:** Ensure scene separators and perspective tags make it clear which scenes are concurrent vs. sequential
**Implementation:** Check context before and after major dot separators

### Pain Point 7: Dialogue Impediments and Accents
**Issue:** Intentional speech patterns must be preserved consistently
**Solution:** Maintain exact spelling and formatting for character-specific speech patterns
**Implementation:** Do not "correct" dialect/accent markers

### Pain Point 8: Information Dumps in Internal Monologue
**Issue:** Lengthy backstory/world-building conveyed through single character's thought
**Solution:** Preserve as written (it's narrative content, not an error); ensure thought attribution is clear
**Implementation:** Add character name tags to long monologues; maintain all text

---

## Conversion Checklist (Per Chapter)

Before moving to the next chapter, verify:

- [ ] All first-person pronouns converted to third-person (character name/pronoun)
- [ ] All narration converted to past tense
- [ ] All character thoughts italicized and attributed where necessary for clarity
- [ ] Bracketed content verified as telepathy/Mind Realm communication (not thought)
- [ ] All dialogue checked for consistency and punctuation
- [ ] Intentional accents and misspellings preserved
- [ ] Major scene breaks maintain original dot count
- [ ] Minor time shifts use exactly three dots `...`
- [ ] Grammar errors corrected (except intentional character speech patterns)
- [ ] File size validated: `_complete` ≥ original
- [ ] Entire chapter text preserved (no accidental deletions)
- [ ] Formatting consistent with previous completed chapters

---

## Notes for Future Agents

- **Reference this document before starting each chapter** to ensure consistency
- **When encountering edge cases not covered here,** use narrative clarity as the guide: prioritize reader understanding
- **Maintain quality and professionalism** while preserving the story's voice and intent
- **If new patterns emerge during conversion,** update this document with solutions for consistency in remaining chapters
- **Each completed chapter brings the story closer to completion** — maintain attention to detail throughout
