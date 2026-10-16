# Vocabulary sourcing

Sabrina English ships a static daily-life library covering an approximate A1–B2 study range:

- 4,000 vocabulary entries: A1 800, A2 1,200, B1 1,200, B2 800
- 600 practical expressions
- 250 sentence patterns

## Pinned source

Vocabulary headwords, phonetics, frequency ranks, and Chinese glosses are generated from [ECDICT](https://github.com/skywind3000/ECDICT), licensed under MIT.

- Git revision: `82c9872576b23118d7c42e920c11beb77f510ae2`
- Build input: `ecdict.csv`
- SHA-256: `1a6947e04785db63613a92e14903cdae7954f7e84860b10e68e5c7cbb3f9c3cf`

The generator rejects a source file with a different checksum. It filters proper names and unusable records, ranks common words, assigns approximate A1–B2 study bands, and emits stable content IDs. The level bands are a practical study ordering, not an official CEFR certification.

Dictionary example sentences are not copied. Learning-context sentences, expression/pattern catalogs, Chinese usage notes, and examples are original deterministic templates in this repository. Full attribution is in `content/ATTRIBUTION.md`.

## Regeneration and validation

Keep the pinned CSV outside the repository, then run:

```sh
python3 scripts/generate_content.py --ecdict /tmp/sabrina-content-source/ecdict.csv --output content
python3 scripts/validate_content.py content
python3 -m unittest -v tests.test_content_library
```

Generated JSON and `content/manifest.json` are committed. Production downloads no dictionary and calls no external content or AI API.
