import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def spec():
    return {'openapi': '3.0.3', 'info': {'title': 'Demo', 'version': '1'},
            'paths': {'/pets': {'get': {'responses': {'200': {'description': 'OK'}}}}}}


def param(required=False):
    return {'name': 'limit', 'in': 'query', 'required': required, 'schema': {'type': 'integer'}}


class ContractTests(unittest.TestCase):
    def compare(self, a, b):
        from api_contract_watch.core import compare
        return compare(a, b)

    def codes(self, a, b):
        return {f['code'] for f in self.compare(a, b)}

    def test_unchanged(self):
        self.assertEqual(self.compare(spec(), spec()), [])

    def test_removed_endpoint(self):
        b = spec(); b['paths'] = {}
        self.assertIn('operation-removed', self.codes(spec(), b))

    def test_removed_method(self):
        b = spec(); b['paths']['/pets'] = {}
        self.assertIn('operation-removed', self.codes(spec(), b))

    def test_required_parameter(self):
        b = spec(); b['paths']['/pets']['get']['parameters'] = [param(True)]
        self.assertIn('parameter-required', self.codes(spec(), b))

    def test_optional_parameter_is_safe(self):
        b = spec(); b['paths']['/pets']['get']['parameters'] = [param()]
        self.assertEqual(self.compare(spec(), b), [])

    def test_optional_becomes_required(self):
        a = spec(); a['paths']['/pets']['parameters'] = [param()]
        b = copy.deepcopy(a); b['paths']['/pets']['parameters'][0]['required'] = True
        self.assertIn('parameter-required', self.codes(a, b))

    def test_override_path_parameter(self):
        a = spec(); a['paths']['/pets']['parameters'] = [param(True)]
        a['paths']['/pets']['get']['parameters'] = [param()]
        b = copy.deepcopy(a); b['paths']['/pets']['parameters'][0]['schema']['type'] = 'string'
        self.assertEqual(self.compare(a, b), [])

    def test_parameter_removed(self):
        a = spec(); a['paths']['/pets']['get']['parameters'] = [param()]
        self.assertIn('parameter-removed', self.codes(a, spec()))

    def test_enum_narrowed(self):
        a = spec(); p = param(); p['schema']['enum'] = [1, 2]
        a['paths']['/pets']['get']['parameters'] = [p]
        b = copy.deepcopy(a); b['paths']['/pets']['get']['parameters'][0]['schema']['enum'] = [1]
        self.assertIn('enum-narrowed', self.codes(a, b))

    def test_enum_widened(self):
        a = spec(); p = param(); p['schema']['enum'] = [1]
        a['paths']['/pets']['get']['parameters'] = [p]
        b = copy.deepcopy(a); b['paths']['/pets']['get']['parameters'][0]['schema']['enum'] = [1, 2]
        self.assertEqual(self.compare(a, b), [])

    def test_type_changed(self):
        a = spec(); a['paths']['/pets']['get']['parameters'] = [param()]
        b = copy.deepcopy(a); b['paths']['/pets']['get']['parameters'][0]['schema']['type'] = 'string'
        self.assertIn('parameter-type-changed', self.codes(a, b))

    def test_new_required_body(self):
        b = spec(); b['paths']['/pets']['get']['requestBody'] = {'required': True, 'content': {}}
        self.assertIn('request-body-required', self.codes(spec(), b))

    def test_response_schema_change_needs_review(self):
        b = spec(); b['paths']['/pets']['get']['responses']['200']['content'] = {'application/json': {'schema': {'type': 'string'}}}
        self.assertIn('operation-review', self.codes(spec(), b))

    def test_reference_needs_review(self):
        a = spec(); a['paths']['/pets']['get']['parameters'] = [{'$ref': '#/components/parameters/Limit'}]
        self.assertIn('unsupported-reference', self.codes(a, a))

    def test_metadata_ignored(self):
        b = spec(); b['info']['version'] = '2'; b['paths']['/pets']['get']['description'] = 'Better docs'
        self.assertEqual(self.compare(spec(), b), [])

    def test_servers_change_needs_review(self):
        b = spec(); b['servers'] = [{'url': 'https://example.org'}]
        self.assertIn('document-review', self.codes(spec(), b))

    def test_input_unchanged(self):
        a = spec(); b = copy.deepcopy(a)
        self.compare(a, b)
        self.assertEqual(a, spec())
        self.assertEqual(b, spec())

    def test_malformed_documents(self):
        from api_contract_watch.core import InputError
        for bad in [None, {}, {'openapi': '3.1.0', 'paths': {}}, {**spec(), 'paths': []}]:
            with self.subTest(bad=bad), self.assertRaises(InputError):
                self.compare(bad, spec())

    def test_invalid_parameter(self):
        from api_contract_watch.core import InputError
        for p in [{'name': 'bad'}, {**param(), 'required': 'false'}, {**param(), 'schema': []}]:
            a = spec(); a['paths']['/pets']['get']['parameters'] = [p]
            with self.subTest(p=p), self.assertRaises(InputError):
                self.compare(a, a)

    def test_duplicate_parameter(self):
        from api_contract_watch.core import InputError
        a = spec(); a['paths']['/pets']['parameters'] = [param(), param()]
        with self.assertRaises(InputError):
            self.compare(a, a)

    def test_cli_codes_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            old = Path(directory) / 'old.json'; new = Path(directory) / 'new.json'
            old.write_text(json.dumps(spec()))
            for b, expected in [(spec(), 0), ({**spec(), 'paths': {}}, 1), ({**spec(), 'servers': []}, 2), ({}, 2)]:
                new.write_text(json.dumps(b))
                result = subprocess.run([sys.executable, '-m', 'api_contract_watch', str(old), str(new), '--format', 'json'], capture_output=True, text=True)
                with self.subTest(expected=expected):
                    self.assertEqual(result.returncode, expected, result.stderr)
                    report = json.loads(result.stdout)
                    self.assertIn('status', report)

    def test_duplicate_json_key_rejected(self):
        from api_contract_watch.core import load, InputError
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'bad.json'; p.write_text('{"paths":{},"paths":{}}')
            with self.assertRaises(InputError):
                load(p)

    def test_missing_file_cli(self):
        result = subprocess.run([sys.executable, '-m', 'api_contract_watch', 'missing.json', 'missing2.json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('ERROR', result.stdout)

    def test_enum_boolean_is_not_number(self):
        a = spec(); p = param(); p['schema'] = {'enum': [True]}
        a['paths']['/pets']['get']['parameters'] = [p]
        b = copy.deepcopy(a); b['paths']['/pets']['get']['parameters'][0]['schema']['enum'] = [1]
        self.assertIn('enum-narrowed', self.codes(a, b))

    def test_nested_enum_boolean_is_not_number(self):
        a = spec(); p = param(); p['schema'] = {'enum': [{'flag': [True]}]}
        a['paths']['/pets']['get']['parameters'] = [p]
        b = copy.deepcopy(a); b['paths']['/pets']['get']['parameters'][0]['schema']['enum'] = [{'flag': [1]}]
        self.assertIn('enum-narrowed', self.codes(a, b))

    def test_unclassified_boolean_number_change(self):
        a = spec(); a['x-feature'] = True
        b = copy.deepcopy(a); b['x-feature'] = 1
        self.assertIn('document-review', self.codes(a, b))

    def test_overflow_json_number_rejected(self):
        from api_contract_watch.core import load, InputError
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'bad.json'; p.write_text('{"value":1e999}')
            with self.assertRaises(InputError):
                load(p)

    def test_oversized_integer_cli_error(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'huge.json'
            p.write_text('{"a":' + '9' * 5000 + '}')
            result = subprocess.run([sys.executable, '-m', 'api_contract_watch', str(p), str(p), '--format', 'json'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)['status'], 'error')
            self.assertNotIn('Traceback', result.stderr)
