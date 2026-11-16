# Contributing

Keep a change tied to an observable behavior: a data failure, timing assumption, execution rule, or research result. Explain the before/after behavior and how you verified it.

Run `python -m unittest discover -s tests -v`. For execution changes, build the C++ library and run the full suite. Include a hand-calculated fixture when changing accounting or costs; parity between two implementations is not enough if both share the same bug.

Document changes to event timing, information availability, portfolio sizing, or evaluation splits in `docs/methodology.md`. Never silently alter a committed example to improve its return. Regenerate examples from their pinned input and explain numerical changes.

Do not commit private data, credentials, virtual environments, generated binaries, personal notes, or large output folders. The small `examples/review` set exists so reviewers can inspect an experiment without running it.
