import unittest
from ainotepro.core.advanced_text import (
    build_snapshot, compile_prompt, default_prompt, field_to_text, parse_prompt,
    parse_response, preflight_requests, snapshot_matches, validate_prompt,
)


class AdvancedTextTests(unittest.TestCase):
    def test_compile_and_single_substitution(self):
        parsed = validate_prompt('Use {Text} and {中文}. {OUT:A:B} Explain {Text}. {OUT:OUT:X} Summarize.', ['Text', '中文'], ['A:B', 'OUT:X'], ['Text', '中文', 'A:B', 'OUT:X'])
        result = compile_prompt(parsed, {'Text': '{中文}', '中文': 'hello'})
        self.assertIn('{中文}', result)
        self.assertNotIn('{OUT:', result)

    def test_invalid_prompts(self):
        for text in ['{Text', '{Text{X}}', '{}', '{Source}', '{Text} {OUT:Y} x {OUT:Y} y', '{Text} {OUT:Y} ']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_prompt(text, ['Text'], ['Y'], ['Text', 'Y'])
        self.assertEqual(''.join(t.value for t in parse_prompt('{{"a":1}}')), '{"a":1}')

    def test_default(self):
        validate_prompt(default_prompt(['Text', 'Scenario'], ['A', 'B']), ['Text', 'Scenario'], ['A', 'B'], ['Text', 'Scenario', 'A', 'B'])

    def test_json(self):
        self.assertEqual(parse_response('```json\n{"A":"ok"}\n```', ['A']), {'A': 'ok'})
        for value in ['{"A":"x","A":"y"}', '{"A":" "}', '{"A":1}', 'prefix {"A":"x"}', '{"B":"x"}', '```JSON\n{"A":"x"}\n```', '{"A":"\\ud800"}']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_response(value, ['A'])

    def test_html_and_cloze(self):
        cases = {'A<br>B': 'A\nB', '<div>Hello</div><div>world</div>': 'Hello\nworld', '&amp; &lt; &gt;': '& < >', '{{c1::answer::hint}}': 'answer', '<img src="a">[sound:a]': '', '<p>Hi <b>there</b>.</p>': 'Hi there.', '<script>secret</script><p>Good</p>': 'Good', '{{c2::outer {{c1::inner}} tail::hint}}': 'outer inner tail', '{{literal}}': '{{literal}}'}
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(field_to_text(source), expected)
        for source in ['{{c0::x}}', '{{c01::x}}', '{{c1::}}', '{{c1::x', '{{c1::x::{{c2::y}}}}']:
            with self.subTest(source=source), self.assertRaises(ValueError):
                field_to_text(source)

    def test_batch_preflight_rejects_everything_on_one_invalid_note(self):
        records = [
            {"note_id": 1, "note_type_id": 9, "field_names": ["Text", "Out"],
             "raw_values": {"Text": "hello", "Out": ""}},
            {"note_id": 2, "note_type_id": 9, "field_names": ["Text", "Out"],
             "raw_values": {"Text": "<img src='x'>", "Out": ""}},
        ]
        with self.assertRaisesRegex(ValueError, "Note 2"):
            preflight_requests(records, ["Text"], ["Out"], "{Text} {OUT:Out} translate", ["Text", "Out"])

    def test_snapshot_compares_raw_values_and_full_definition(self):
        snapshot = build_snapshot(1, 3, ["Text", "Out"], {"Text": "A<br>B", "Out": ""}, ["Text"], ["Out"])
        self.assertEqual(snapshot.input_values, {"Text": "A\nB"})
        self.assertTrue(snapshot_matches(3, ["Text", "Out"], {"Text": "A<br>B", "Out": ""}, snapshot, ["Text"], ["Out"]))
        self.assertFalse(snapshot_matches(3, ["Text", "Out"], {"Text": "A\nB", "Out": ""}, snapshot, ["Text"], ["Out"]))
        self.assertFalse(snapshot_matches(3, ["Out", "Text"], {"Text": "A<br>B", "Out": ""}, snapshot, ["Text"], ["Out"]))

if __name__ == '__main__':
    unittest.main()
