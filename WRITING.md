# Writing instructions

## Technical text

Use ASD-STE100 Simplified Technical English, Issue 9, for new project explanations.
Use the [official standard](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf) for its full vocabulary and rules.

1. Use approved words with their approved meanings and parts of speech.
2. Define necessary technical terms when they first occur.
3. Use the same term for the same item throughout a document.
4. Keep descriptive sentences to 25 words or fewer.
5. Keep procedural sentences to 20 words or fewer.
6. Give one instruction in each sentence.
7. Use the active voice where possible.
8. Keep each paragraph to one topic and no more than six sentences.
9. Preserve exact identifiers, formulas, commands, measurements, and quoted source text.
10. Check technical accuracy separately from sentence length.

The current prose follows these instructions. It has no independent STE compliance
assessment. Sentence counts alone cannot establish compliance.

`PLAN.md` and the original part of `HANDOFF.md` are historical records.
Their original wording remains available for comparison with the completed work.

## Commit messages

Write a short subject that states the actual change in plain language.
Add a body only when the reason or a limitation needs an explanation.
Use specific verbs and concrete objects.

Examples:

- Make the reports easier to read
- Keep stale files out of profiling builds
- Reduce the size of the stateful verifier

Apply this style to new commits. Preserve published commit history unless the
repository owner explicitly requests a history rewrite.
