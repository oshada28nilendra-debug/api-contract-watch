"""Pure, directional rules: old clients consuming a new API contract."""
import copy
import json
import math
import re
from pathlib import Path

METHODS = frozenset('get put post delete options head patch trace'.split())
DOC_FIELDS = frozenset(('summary', 'description', 'externalDocs', 'tags', 'operationId'))


class InputError(ValueError):
    """Malformed or unsupported input document."""


def _object(value, location):
    if not isinstance(value, dict):
        raise InputError(f'{location}: expected an object')
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def load(path):
    """Read strict UTF-8 JSON, rejecting duplicate keys and nonfinite values."""
    def invalid_constant(value):
        raise InputError(f'Invalid JSON constant: {value}')
    def bounded_int(value):
        if len(value.lstrip('-')) > 4300:
            raise InputError('JSON integer exceeds 4300 digits')
        return int(value)
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise InputError(f'JSON number exceeds finite range: {value}')
        return number
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                          object_pairs_hook=_pairs, parse_constant=invalid_constant, parse_float=finite_float, parse_int=bounded_int)
    except (OSError, ValueError, RecursionError) as error:
        raise InputError(f'{path}: {error}') from error


def _params(values, location):
    if not isinstance(values, list):
        raise InputError(f'{location}: parameters must be an array')
    result = {}
    for p in values:
        _object(p, location)
        if '$ref' in p:
            continue  # Globally reported as unsupported; never a silent pass.
        if not isinstance(p.get('name'), str) or not p['name'] or p.get('in') not in ('query', 'header', 'path', 'cookie'):
            raise InputError(f'{location}: parameter needs name and valid in')
        if 'required' in p and not isinstance(p['required'], bool):
            raise InputError(f'{location}: required must be boolean')
        if p['in'] == 'path' and p.get('required') is not True:
            raise InputError(f'{location}: path parameter must be required')
        if ('schema' in p) == ('content' in p):
            raise InputError(f'{location}: parameter needs exactly one of schema or content')
        if 'schema' in p:
            s = _object(p['schema'], location + '/schema')
            if 'type' in s and s['type'] not in ('string', 'number', 'integer', 'boolean', 'array', 'object'):
                raise InputError(f'{location}: invalid OpenAPI 3.0 schema type')
            if 'enum' in s and (not isinstance(s['enum'], list) or not s['enum']):
                raise InputError(f'{location}: enum must be nonempty array')
        if 'content' in p:
            _object(p['content'], location + '/content')
        key = (p['name'], p['in'])
        if key in result:
            raise InputError(f'{location}: duplicate parameter {key}')
        result[key] = p
    return result


def _operations(doc):
    _object(doc, 'document')
    if not re.fullmatch(r'3\.0\.\d+', str(doc.get('openapi', ''))):
        raise InputError('Only OpenAPI 3.0.x is supported')
    info = _object(doc.get('info'), 'info')
    if not all(isinstance(info.get(k), str) for k in ('title', 'version')):
        raise InputError('info requires string title and version')
    paths = _object(doc.get('paths'), 'paths')
    result = {}
    for path, item in paths.items():
        if path.startswith('x-'):
            continue
        if not path.startswith('/'):
            raise InputError(f'Invalid path: {path}')
        _object(item, path)
        inherited = _params(item.get('parameters', []), path)
        for method in sorted(METHODS & item.keys()):
            op = _object(item[method], f'{method} {path}')
            responses = _object(op.get('responses'), f'{method} {path}/responses')
            if not responses:
                raise InputError(f'{method} {path}: responses must not be empty')
            for code, response in responses.items():
                _object(response, f'{path}/responses/{code}')
            effective = {**inherited, **_params(op.get('parameters', []), path)}
            if 'requestBody' in op:
                body = _object(op['requestBody'], path + '/requestBody')
                if 'required' in body and not isinstance(body['required'], bool):
                    raise InputError(f'{path}: requestBody.required must be boolean')
            result[(path, method)] = (op, effective)
    return result


def _without(obj, keys):
    return {k: v for k, v in obj.items() if k not in keys}


def _same(a, b):
    """JSON equality: booleans are not numbers, including inside enums."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def compare(old, new):
    """Return sorted findings; never mutate callers' input dictionaries."""
    before, after = _operations(old), _operations(new)
    findings = []

    def add(code, location, message, severity='breaking'):
        findings.append(dict(code=code, location=location, message=message, severity=severity))

    def refs(value, location):
        if isinstance(value, dict):
            if '$ref' in value:
                add('unsupported-reference', location, 'Reference resolution requires manual review.', 'review')
            for key, child in value.items():
                refs(child, location + '/' + key.replace('~', '~0').replace('/', '~1'))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                refs(child, location + '/' + str(index))

    refs(old, 'old'); refs(new, 'new')
    for key in sorted(before):
        path, method = key
        location = f'{method.upper()} {path}'
        if key not in after:
            add('operation-removed', location, 'Existing operation is no longer available.')
            continue
        a, ap = before[key]; b, bp = after[key]
        for identity in sorted(ap.keys() | bp.keys()):
            label = f'{location} / {identity[1]}:{identity[0]}'
            p, q = ap.get(identity), bp.get(identity)
            if q is None:
                add('parameter-removed', label, 'Existing parameter was removed (conservative policy).')
                continue
            if q.get('required', False) and (p is None or not p.get('required', False)):
                add('parameter-required', label, 'New API requires a previously optional or absent parameter.')
            if p is None:
                continue
            s, t = copy.deepcopy(p.get('schema', {})), copy.deepcopy(q.get('schema', {}))
            if s.get('type') != t.get('type'):
                add('parameter-type-changed', label, 'Parameter type changed; existing inputs may be rejected.')
            if 'enum' in t and ('enum' not in s or any(not any(_same(v, w) for w in t['enum']) for v in s['enum'])):
                add('enum-narrowed', label, 'New API restricts previously accepted enum values.')
            # Type and enum were classified; everything else is conservatively reviewed.
            ps = _without(p, {'required', 'schema', 'description', 'example', 'examples'})
            qs = _without(q, {'required', 'schema', 'description', 'example', 'examples'})
            if not _same(ps, qs) or not _same(_without(s, {'type', 'enum', 'description', 'title', 'example'}), _without(t, {'type', 'enum', 'description', 'title', 'example'})):
                add('parameter-review', label, 'Other parameter constraints or serialization changed.', 'review')
        ab, bb = a.get('requestBody', {}), b.get('requestBody', {})
        if bb.get('required', False) and not ab.get('required', False):
            add('request-body-required', location, 'Request body became required.')
        ignored = DOC_FIELDS | {'parameters', 'requestBody'}
        if not _same(_without(a, ignored), _without(b, ignored)) or not _same(_without(ab, {'required', 'description'}), _without(bb, {'required', 'description'})):
            add('operation-review', location, 'Response, body, security, or other operation semantics changed.', 'review')
        # Path-level semantics outside inherited parameters.
        ignored_path = METHODS | {'parameters', 'summary', 'description'}
        if not _same(_without(old['paths'][path], ignored_path), _without(new['paths'][path], ignored_path)):
            add('path-review', location, 'Path-level semantics changed.', 'review')
    if not _same(_without(old, {'paths', 'info', 'openapi', 'tags', 'externalDocs'}), _without(new, {'paths', 'info', 'openapi', 'tags', 'externalDocs'})):
        add('document-review', 'document', 'Servers, components, security, or other document semantics changed.', 'review')
    return sorted(findings, key=lambda f: (f['location'], f['code']))
