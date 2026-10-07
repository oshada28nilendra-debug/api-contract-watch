"""Command line interface and stable CI exit codes."""
import argparse
import json
from .core import InputError, compare, load


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compare OpenAPI 3.0 JSON contracts (old → new).')
    parser.add_argument('old', help='baseline JSON specification')
    parser.add_argument('new', help='candidate JSON specification')
    parser.add_argument('--format', choices=('text', 'json'), default='text')
    args = parser.parse_args(argv)
    try:
        findings = compare(load(args.old), load(args.new))
        code = 2 if any(f['severity'] == 'review' for f in findings) else (1 if findings else 0)
        status = {0: 'pass', 1: 'breaking', 2: 'review'}[code]
        report = {'status': status, 'scope': 'OpenAPI 3.0 JSON; endpoint and parameter rules, conservative review of other changes', 'findings': findings}
    except (InputError, RecursionError) as error:
        code = 2
        report = {'status': 'error', 'error': str(error), 'findings': []}
    if args.format == 'json':
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        print('API Contract Watch: ' + report['status'].upper())
        if 'error' in report:
            print(report['error'])
        else:
            for item in report['findings']:
                print(f"[{item['severity'].upper()}] {item['code']} | {item['location']} | {item['message']}")
            print('Scope: ' + report['scope'])
            if not report['findings']:
                print('No detected changes requiring action within this scope; not a compatibility guarantee.')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
