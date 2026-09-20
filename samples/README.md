# samples/

Two files go here. You write both. They are in **your** schema, whatever
you decided in SPEC.md.

## valid_response.json

One model reply that your program must accept and process normally.
This is your happy path, frozen.

## invalid_response.json

One model reply that is **valid JSON** but that your validation must
**reject**. Not broken punctuation - `json.loads` has to succeed on it.
Something that parses fine and is still unusable: a field missing, a
number out of range, a list the wrong length, an index pointing at
nothing.

In SPEC.md, under Failure cases, name the rule this file breaks.

The stub reads these two files. Everyone in the class has a different
schema and the same stub, which is the whole idea.
