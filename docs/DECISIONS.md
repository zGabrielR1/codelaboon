# Decision models

codelaboon can ask a model **typed questions** about an input and get
probability-bearing answers back. This is useful for routing, triage, and
classification where a free-form chat response is too vague.

Three question types are supported:

| Type | Answer |
|------|--------|
| `predicate` | probability that the answer is yes |
| `choice` | chosen value, probability per value, confidence |
| `score` | probability-weighted level, probability per level, confidence |

Answers always come back in the same order as the questions. If the host
declines a question, that answer is an error while the other answers remain
usable.

## Provider routes

| Provider | Route |
|----------|-------|
| `chatgpt` | OpenAI `/v1/decisions` |
| `openrouter` | System One `/systemone` |
| `nvidia`, `luna` | not supported |

## Questions file

Use `--questions` with a JSON array:

```json
[
  {
    "name": "refund",
    "type": "predicate",
    "instructions": "Is the customer asking for a refund?"
  },
  {
    "name": "department",
    "type": "choice",
    "instructions": "Which team should handle this?",
    "choices": [
      {"value": "billing", "description": "Payments and refunds"},
      {"value": "technical"}
    ]
  },
  {
    "name": "urgency",
    "type": "score",
    "instructions": "How urgent is this?",
    "levels": [
      {"label": "Can wait"},
      {"label": "Needs prompt attention"},
      {"label": "Blocking revenue"}
    ]
  }
]
```

Rules:

- names must be unique and non-empty
- `predicate` needs `instructions`
- `choice` needs a non-empty `choices` list; values may be strings or booleans
- `score` needs a non-empty ordered `levels` list

## Inline questions

For quick checks, repeat `--predicate`, `--choice` and `--score`:

```bash
python3 -m codelaboon decision openrouter my/decision-model \
  "I was charged twice. Please refund the duplicate payment." \
  --predicate 'refund=Is the customer asking for a refund?' \
  --choice 'department=Which team should handle this?|billing,technical' \
  --score 'urgency=How urgent is this?|Can wait,Prompt attention,Blocking revenue'
```

`NAME=INSTRUCTIONS|VALUE1,VALUE2` keeps the instructions before the first `|`.

## JSON output

```bash
python3 -m codelaboon decision chatgpt gpt-6-luna "hello" \
  --predicate 'greeting=Is this a greeting?' --json
```

Example shape:

```json
[
  {
    "name": "greeting",
    "type": "predicate",
    "probability": 0.97
  }
]
```

## Notes

- No API keys are bundled. Configure the provider first with
  `codelaboon configure <provider>` or by editing `providers.toml`.
- Decision support is exercised offline in `tests/test_codelaboon.py` with
  mocked HTTP responses; live endpoints require a provider key and a model that
  supports its decision API.
