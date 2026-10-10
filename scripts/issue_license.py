"""QuakeLogic licence issuing tool for HVSR Studio (internal use only).

Creates a signed .qlicense file for one customer and one or more computers (Machine IDs, shown
in the app under License page). The private signing key stays outside the repository, by
default in ~/.config/quakelogic/masw-licensing/signing-key.hex. Every licence issued is
appended to hvsr-licenses-issued.csv beside the key.

Examples
  engine/.venv/bin/python scripts/issue_license.py issue --customer "Acme Geotechnical" \\
      --contact "jane@acme.example" --machine-id K3J9Q-7ZP2M-ABCDE-12345 --maintenance-years 1
  engine/.venv/bin/python scripts/issue_license.py verify Acme-Geotechnical-HVSR-2026-0001.qlicense
  engine/.venv/bin/python scripts/issue_license.py list
"""
from __future__ import annotations
import argparse
import csv
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from hvsr_service import licensing, ed25519  # noqa: E402

KEY_DIR = Path.home() / '.config/quakelogic/masw-licensing'
MACHINE = re.compile(r'^[A-Z2-7]{5}(-[A-Z2-7]{5}){3}$')


def load_key(path: Path) -> bytes:
    secret = bytes.fromhex(path.read_text().strip())
    if ed25519.public_key(secret) != licensing.PUBLIC_KEY:
        sys.exit('This signing key does not match the public key built into HVSR Studio.')
    return secret


def next_id(ledger: Path) -> str:
    year = date.today().year
    count = 0
    if ledger.exists():
        with ledger.open() as f:
            count = sum(1 for row in csv.DictReader(f) if row['license_id'].startswith(f'HVSR-{year}-'))
    return f'HVSR-{year}-{count + 1:04d}'


def issue(args):
    ids = [m.strip().upper() for m in args.machine_id]
    for m in ids:
        if not MACHINE.match(m):
            sys.exit(f'"{m}" is not a Machine ID (format XXXXX-XXXXX-XXXXX-XXXXX, from License page).')
    if args.seats < len(ids):
        sys.exit('Seats must be at least the number of Machine IDs.')
    ledger = args.key.parent / 'hvsr-licenses-issued.csv'
    today = date.today()
    maintenance = args.maintenance_until or date(today.year + args.maintenance_years, today.month, min(today.day, 28)).isoformat()
    fields = {'license_id': args.license_id or next_id(ledger), 'customer': args.customer, 'contact': args.contact,
              'edition': args.edition, 'seats': args.seats, 'machine_ids': ids, 'issued': today.isoformat(),
              'maintenance_until': maintenance, 'expires': args.expires, 'notes': args.notes}
    content = licensing.issue(load_key(args.key), **fields)
    name = re.sub(r'[^A-Za-z0-9]+', '-', args.customer).strip('-') + f"-{fields['license_id']}.qlicense"
    out = args.out or Path.cwd() / name
    out.write_bytes(content)
    new = not ledger.exists()
    with ledger.open('a', newline='') as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(['license_id', 'issued', 'customer', 'contact', 'edition', 'seats', 'machine_ids', 'maintenance_until', 'expires', 'file', 'notes'])
        writer.writerow([fields['license_id'], fields['issued'], args.customer, args.contact, args.edition, args.seats,
                         ' '.join(ids), maintenance, args.expires or '', str(out), args.notes])
    print(f"Issued {fields['license_id']} for {args.customer} ({len(ids)} computer(s), maintenance until {maintenance}).")
    print(f'Licence file: {out}')
    print('Send this file to the customer: License page → Import licence file.')


def verify(args):
    payload = licensing.parse(Path(args.file).read_bytes())
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print('Signature valid: issued by QuakeLogic.')


def show(args):
    ledger = args.key.parent / 'hvsr-licenses-issued.csv'
    if not ledger.exists():
        print('No licences issued yet.');return
    with ledger.open() as f:
        for row in csv.DictReader(f):
            print(f"{row['license_id']}  {row['issued']}  {row['customer']:<32}  seats {row['seats']}  maintenance {row['maintenance_until']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--key', type=Path, default=KEY_DIR / 'signing-key.hex', help='Private signing key (never commit it)')
    sub = parser.add_subparsers(dest='command', required=True)
    i = sub.add_parser('issue', help='Create a signed licence file')
    i.add_argument('--customer', required=True)
    i.add_argument('--contact', default='')
    i.add_argument('--machine-id', action='append', required=True, help='Repeat for each computer')
    i.add_argument('--seats', type=int, default=0, help='Defaults to the number of Machine IDs')
    i.add_argument('--edition', default='Professional')
    i.add_argument('--maintenance-years', type=int, default=1)
    i.add_argument('--maintenance-until', help='YYYY-MM-DD (overrides --maintenance-years)')
    i.add_argument('--expires', help='YYYY-MM-DD for a time-limited licence; omit for perpetual')
    i.add_argument('--license-id')
    i.add_argument('--notes', default='')
    i.add_argument('--out', type=Path)
    v = sub.add_parser('verify', help='Check a licence file and show its contents')
    v.add_argument('file')
    sub.add_parser('list', help='List licences issued from this key')
    args = parser.parse_args()
    if args.command == 'issue':
        args.seats = args.seats or len(args.machine_id)
        for value in (args.maintenance_until, args.expires):
            if value:
                date.fromisoformat(value)
        issue(args)
    elif args.command == 'verify':
        verify(args)
    else:
        show(args)


if __name__ == '__main__':
    main()
