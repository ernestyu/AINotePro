"""Pure Text Advanced parsing and validation; no Anki or Qt dependencies."""
from dataclasses import dataclass
from html.parser import HTMLParser
import json
import re


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int


def parse_prompt(prompt):
    tokens = []
    i = 0
    while i < len(prompt):
        start = i
        if prompt.startswith('{{', i) or prompt.startswith('}}', i):
            if i + 2 < len(prompt) and prompt[i + 2] == prompt[i]:
                raise ValueError(f'Invalid brace at {i}')
            tokens.append(Token('text', prompt[i], i))
            i += 2
        elif prompt[i] == '{':
            end = prompt.find('}', i + 1)
            if end < 0 or any(c in prompt[i + 1:end] for c in '{}\r\n'):
                raise ValueError(f'Invalid placeholder at {i}')
            value = prompt[i + 1:end]
            if not value:
                raise ValueError(f'Empty placeholder at {i}')
            kind = 'output' if value.startswith('OUT:') else 'input'
            value = value[4:] if kind == 'output' else value
            if not value:
                raise ValueError(f'Empty placeholder at {i}')
            tokens.append(Token(kind, value, i))
            i = end + 1
        elif prompt[i] == '}':
            raise ValueError(f'Unmatched brace at {i}')
        else:
            while i < len(prompt) and prompt[i] not in '{}':
                i += 1
            tokens.append(Token('text', prompt[start:i], start))
    return tokens


def validate_prompt(prompt, sources, destinations, fields):
    tokens = parse_prompt(prompt)
    s, d, f = set(sources), set(destinations), set(fields)
    if not s or not d or s & d or not (s | d) <= f:
        raise ValueError('Invalid source or destination selection')
    if any('{' in x or '}' in x for x in s | d):
        raise ValueError('Field names containing braces are unsupported')
    if any(x.startswith('OUT:') or x in ('Source', 'Source Field') for x in s):
        raise ValueError('Reserved source field name')
    inputs = {t.value for t in tokens if t.kind == 'input'}
    outputs = [t.value for t in tokens if t.kind == 'output']
    if inputs & {'Source', 'Source Field'}:
        raise ValueError('Easy placeholders are unsupported in Advanced')
    if len(outputs) != len(set(outputs)):
        raise ValueError('Duplicate output declaration')
    if inputs != s or set(outputs) != d:
        raise ValueError(f'Source missing: {sorted(s-inputs)}; extra: {sorted(inputs-s)}; destination missing: {sorted(d-set(outputs))}; extra: {sorted(set(outputs)-d)}')
    sections = []
    global_tokens = []
    current = global_tokens
    for token in tokens:
        if token.kind == 'output':
            current = []
            sections.append((token.value, current))
        else:
            current.append(token)
    if any(not ''.join(t.value if t.kind == 'text' else 'x' for t in section).strip() for _, section in sections):
        raise ValueError('Output instructions must not be empty')
    return global_tokens, sections


def compile_prompt(parsed, inputs):
    def render(tokens):
        return ''.join(t.value if t.kind == 'text' else inputs[t.value] for t in tokens)
    global_tokens, sections = parsed
    result = [render(global_tokens), '\nTarget field instructions:']
    for name, tokens in sections:
        result.append('\n' + json.dumps(name, ensure_ascii=False) + ':\n' + render(tokens))
    result.append('\nReturn only one JSON object with exactly these field names as keys and non-empty strings as values: ' + json.dumps([name for name, _ in sections], ensure_ascii=False) + '.')
    return ''.join(result)


def default_prompt(sources, destinations):
    return 'Inputs:\n' + '\n'.join(f'{x}: {{{x}}}' for x in sources) + '\n\nGenerate the following:\n' + '\n\n'.join(f'{{OUT:{x}}}\nGenerate content for this field.' for x in destinations)


def parse_response(response, destinations, max_size=1048576):
    if not isinstance(response, str) or len(response.encode('utf-8')) > max_size:
        raise ValueError('Invalid or oversized response')
    text = response.strip(' \t\r\n')
    if text.startswith('```'):
        match = re.fullmatch(r'```json\r?\n(.*)\r?\n```', text, re.DOTALL)
        if not match:
            raise ValueError('Invalid JSON fence')
        text = match.group(1)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    try:
        result = json.loads(text, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Invalid JSON constant')))
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid JSON response: ' + str(exc)) from exc
    if not isinstance(result, dict) or set(result) != set(destinations) or any(not isinstance(x, str) or not x.strip() or any(0xD800 <= ord(c) <= 0xDFFF for c in x) for x in result.values()):
        raise ValueError('Invalid JSON fields or values')
    return result


class _TextExtractor(HTMLParser):
    blocks = {'div', 'p', 'li', 'ul', 'ol', 'section', 'article', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr', 'blockquote', 'pre'}
    ignored = {'script', 'style', 'audio', 'video', 'source', 'img'}
    void = {'img', 'source'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = []
    def handle_starttag(self, tag, attrs):
        if self.skip:
            if tag not in self.void:
                self.skip.append(tag)
        elif tag in self.ignored:
            if tag not in self.void:
                self.skip.append(tag)
        elif tag == 'br':
            self.parts.append('\n')
        elif tag in self.blocks:
            self._boundary()
    def handle_startendtag(self, tag, attrs):
        if tag == 'br' and not self.skip:
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
        elif tag in self.blocks:
            self._boundary()
    def _boundary(self):
        if self.parts and not self.parts[-1].endswith('\n'):
            self.parts.append('\n')
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _cloze(text):
    def parse_at(start):
        match = re.match(r'\{\{c([1-9][0-9]*)::', text[start:])
        if not match:
            raise ValueError('Invalid Cloze marker')
        i = start + match.end()
        answer, hint = [], None
        while i < len(text):
            if text.startswith('}}', i):
                value = ''.join(answer)
                if not value.strip():
                    raise ValueError('Empty Cloze answer')
                return value, i + 2
            if text.startswith('::', i):
                if hint is not None:
                    raise ValueError('Ambiguous Cloze separators')
                hint = []
                i += 2
            elif text.startswith('{{c', i) and i + 3 < len(text) and (text[i+3].isdigit() or text[i+3] == ':'):
                if hint is not None:
                    raise ValueError('Nested Cloze in hint')
                value, i = parse_at(i)
                answer.append(value)
            else:
                (answer if hint is None else hint).append(text[i])
                i += 1
        raise ValueError('Unclosed Cloze')
    output = []
    i = 0
    while i < len(text):
        if text.startswith('{{c', i) and i + 3 < len(text) and (text[i+3].isdigit() or text[i+3] == ':'):
            value, i = parse_at(i)
            output.append(value)
        else:
            output.append(text[i])
            i += 1
    return ''.join(output)


def field_to_text(html):
    parser = _TextExtractor()
    parser.feed(html)
    text = re.sub(r'\[sound:[^\]]*\]', '', ''.join(parser.parts), flags=re.IGNORECASE)
    text = _cloze(text).replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[^\S\n]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()
