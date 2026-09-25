"""Expert: reusable functions, collections, iteration and exception handling.

Runs on a computer or any supported virtual hub. The same file is editable
in Blocks or Python; use the text editor to extend it beyond library templates.
"""

values = list((-3, 0, 4, 9))
report = {"accepted": 0}
results = list(())


def checked_double(value):
    if value < 0:
        raise ValueError("Negative input")
    return value * 2


for item in values:
    try:
        result = checked_double(item)
    except ValueError:
        continue
    results.append(result)
    report["accepted"] += 1

assert report["accepted"] == len(results), "Counts disagree"
print(results[:2], report["accepted"])
