# Lab 4 starter

Everything here except `main.py` is supplied. `main.py` is yours to write.
You may call the application itself whatever you like.

| File | Yours? |
|---|---|
| `client.py` | No. Do not edit. The only place your app talks to a model |
| `stub_client.py` | No. Do not edit. The offline fake model, eight modes |
| `check.py` | No. The same script used for marking. Run it on yourself |
| `SPEC.md` | Yes. Six fixed headings, fill them in **before** you write code |
| `DECISIONS.md` | Yes. At least three real choices |
| `QUESTION.md` | Yes. Create it. The block question, 150 words or fewer |
| `samples/` | Yes. Two JSON files, in your own schema. See `samples/README.md` |
| `.env.example` | Copy to `.env` and fill in. Never commit `.env` |

## Start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
python main.py "photosynthesis"
```

## Check yourself

```bash
python check.py .
```

Read the assignment brief for what is fixed, what is yours, and how it is marked.
