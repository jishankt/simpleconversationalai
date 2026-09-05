# Anti-Hallucination Recommendation V3

## Contract

The customer may ask naturally and broadly about Kepler products. The system may understand and rephrase natural language, but factual product claims must come from verified catalog evidence.

**Customer controls the question. Catalog controls facts. Python controls requirements and ranking. The LLM controls wording only.**

## Non-negotiable rules

1. Missing data is `unknown`; it is never converted to `false`, a default value, or a model-name guess.
2. Search results are candidates, not recommendations.
3. Critical requirements must be verified before a candidate is called a strong match.
4. A customer statement may update a requirement. An inferred requirement may not silently become confirmed.
5. Product numbers/units in generated prose must exist in the evidence supplied to the response layer.
6. Product facts must never come from pretrained model knowledge.
7. Direct product questions use deterministic evidence-first answering where possible.
8. If evidence is insufficient, say so and ask one useful clarification only when it helps product selection.

## Conversation flow

Customer message -> normalize -> classify/update explicit requirements -> ask one missing critical requirement -> catalog search -> assess eligibility -> rank -> build evidence -> natural response -> validate claims/numbers -> send.

## Confidence

- HIGH: no verified failure and all critical requirements are supported.
- MEDIUM: useful verified matches exist, but optional or some critical product metadata remains unknown.
- LOW: a requirement fails or there is not enough evidence to recommend reliably.

## Regression cases

`tests/test_anti_hallucination.py` protects against the known failure classes:

- inferring 36-inch/A0 from a T5/T5400-like model name;
- defaulting missing ink technology to UltraChrome;
- treating lack of scanner text as proof that a scanner is absent;
- introducing numeric specifications not present in evidence;
- ranking an unknown scanner capability as though it satisfied a scanner requirement.

## Migration

`agent/evidence_guard.py` is safe to adopt independently for direct product questions.
`agent/recommendation_engine.py` is designed to sit after catalog retrieval and before response composition. The existing UI cards and catalog retriever can remain in place while orchestration is migrated incrementally.
