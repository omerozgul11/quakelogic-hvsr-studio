"""HVSR Studio licensing: signed per-computer licence files, verified offline, and a 14-day trial.

A licence file (.qlicense) is JSON: {"license": {...}, "signature": "<base64 Ed25519>"}. The
signature covers the canonical JSON of "license" and is made with QuakeLogic's private key,
which never ships with the application. Projects can always be opened, viewed and saved;
only new calculations and exports require an active trial or licence.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from . import ed25519

PRODUCT = 'HVSR Studio'
TRIAL_DAYS = 14
# QuakeLogic licence-signing public key (the matching private key is held by QuakeLogic).
PUBLIC_KEY = bytes.fromhex('731da844d2885c8c2c5834138fbfd171ff4430b6010965bf166698ff1e3d5529')
SALES = 'sales@quakelogic.net'
MAX_FILE = 64 * 1024


class LicenseRequired(Exception):
    pass


def _raw_machine_id() -> str:
    if os.name == 'nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Cryptography', 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return str(winreg.QueryValueEx(key, 'MachineGuid')[0])
    for path in ('/etc/machine-id', '/var/lib/dbus/machine-id'):
        try:
            value = Path(path).read_text().strip()
            if value:
                return value
        except OSError:
            pass
    if sys.platform == 'darwin':
        try:
            out = subprocess.run(['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'], capture_output=True, text=True, timeout=5).stdout
            for line in out.splitlines():
                if 'IOPlatformUUID' in line:
                    return line.split('"')[-2]
        except (OSError, subprocess.SubprocessError):
            pass
    return f'node-{uuid.getnode():012x}'


def machine_id() -> str:
    """A stable, anonymised identifier for this computer, e.g. 'K3J9Q-7ZP2M-…'."""
    digest = hashlib.sha256(b'QuakeLogic HVSR Studio machine v1|' + _raw_machine_id().encode()).digest()
    text = base64.b32encode(digest).decode()[:20]
    return '-'.join(text[i:i + 5] for i in range(0, 20, 5))


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def parse(content: bytes) -> dict:
    if len(content) > MAX_FILE:
        raise ValueError('This is not a HVSR Studio licence file (it is too large).')
    try:
        data = json.loads(content.decode('utf-8-sig'))
        payload, signature = data['license'], base64.b64decode(data['signature'], validate=True)
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise ValueError('This is not a valid HVSR Studio licence file.') from None
    if not isinstance(payload, dict) or not ed25519.verify(PUBLIC_KEY, canonical(payload), signature):
        raise ValueError('The licence file signature is not valid. It may have been edited or was not issued by QuakeLogic.')
    if payload.get('product') != PRODUCT:
        raise ValueError('This licence is for a different product.')
    return payload


def _date(value):
    return date.fromisoformat(value) if value else None


def evaluate(payload: dict, release_date: str, today: date | None = None, machine: str | None = None) -> dict:
    """Why a signed licence does or does not apply to this computer and version."""
    today = today or date.today()
    machine = machine or machine_id()
    ids = payload.get('machine_ids') or []
    if machine not in ids:
        return {'valid': False, 'reason': f'This licence is for another computer. This computer\'s Machine ID is {machine}.'}
    expires = _date(payload.get('expires'))
    if expires and today > expires:
        return {'valid': False, 'reason': f'This licence expired on {expires.isoformat()}.'}
    maintenance = _date(payload.get('maintenance_until'))
    if maintenance and date.fromisoformat(release_date) > maintenance:
        return {'valid': False, 'reason': f'Maintenance for this licence ended on {maintenance.isoformat()}, before this version was released '
                                          f'({release_date}). Renew maintenance, or use a version released before that date.'}
    return {'valid': True, 'reason': ''}


def _registry(value: str | None = None) -> str | None:
    """Windows only: a second copy of the trial record in the user's registry."""
    if os.name != 'nt':
        return None
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\QuakeLogic\HVSR Studio') as key:
            if value is not None:
                winreg.SetValueEx(key, 'Trial', 0, winreg.REG_SZ, value)
                return value
            return str(winreg.QueryValueEx(key, 'Trial')[0])
    except OSError:
        return None


class Licensing:
    def __init__(self, root: Path, release_date: str):
        self.dir = root / 'license'
        self.release_date = release_date
        self.machine = machine_id()
        self._key = hashlib.sha256(b'HVSR trial|' + self.machine.encode()).digest()

    # Trial: started on first use; integrity-protected and guarded against clock rollback.
    def _trial(self, today: date) -> dict:
        path = self.dir / 'trial.json'
        def read(text):
            try:
                data = json.loads(text)
                body = {k: data[k] for k in ('started', 'last_seen')}
                if hmac.compare_digest(data['mac'], hmac.new(self._key, canonical(body), 'sha256').hexdigest()):
                    return body
            except (ValueError, KeyError, TypeError):
                pass
            return False
        stored = path.read_text() if path.is_file() else None
        mirror = _registry()
        records = [r for r in (read(stored) if stored else None, read(mirror) if mirror else None) if r]
        if (stored and not read(stored)) or (mirror and not read(mirror)):
            return {'started': None, 'ends': None, 'days_left': 0, 'tampered': True}
        if records:  # the earliest start wins, so deleting one copy never restarts the trial
            record = {'started': min(r['started'] for r in records), 'last_seen': max(r['last_seen'] for r in records)}
        else:
            record = {'started': today.isoformat(), 'last_seen': today.isoformat()}
        started, last_seen = date.fromisoformat(record['started']), date.fromisoformat(record['last_seen'])
        rolled_back = today < last_seen - timedelta(days=1)
        record['last_seen'] = max(today, last_seen).isoformat()
        self.dir.mkdir(parents=True, exist_ok=True)
        text = json.dumps({**record, 'mac': hmac.new(self._key, canonical(record), 'sha256').hexdigest()})
        path.write_text(text)
        _registry(text)
        ends = started + timedelta(days=TRIAL_DAYS)
        days_left = 0 if rolled_back else max(0, (ends - today).days)
        return {'started': started.isoformat(), 'ends': ends.isoformat(), 'days_left': days_left, 'rolled_back': rolled_back}

    def installed(self) -> dict | None:
        path = self.dir / 'license.qlicense'
        if not path.is_file():
            return None
        try:
            return parse(path.read_bytes())
        except ValueError:
            return None

    def status(self, today: date | None = None) -> dict:
        today = today or date.today()
        payload = self.installed()
        result = {'machine_id': self.machine, 'release_date': self.release_date, 'sales': SALES, 'trial_days': TRIAL_DAYS}
        if payload:
            check = evaluate(payload, self.release_date, today, self.machine)
            summary = {k: payload.get(k) for k in ('license_id', 'customer', 'contact', 'edition', 'seats', 'issued', 'maintenance_until', 'expires')}
            if check['valid']:
                return {**result, 'state': 'licensed', 'allowed': True, 'trial': False, 'license': summary, 'message': f"Licensed to {payload.get('customer')}"}
            result.update({'license': summary, 'license_problem': check['reason']})
        trial = self._trial(today)
        result['trial_info'] = trial
        if trial['days_left'] > 0:
            return {**result, 'state': 'trial', 'allowed': True, 'trial': True,
                    'message': f"Trial · {trial['days_left']} day{'s' if trial['days_left'] != 1 else ''} left"}
        reason = result.get('license_problem') or ('The trial record was altered.' if trial.get('tampered') else
                 'The computer clock was set back during the trial.' if trial.get('rolled_back') else
                 f'The {TRIAL_DAYS}-day trial has ended.')
        return {**result, 'state': 'unlicensed', 'allowed': False, 'trial': False, 'message': 'Licence required', 'reason': reason}

    def require(self) -> bool:
        """Raise LicenseRequired unless calculations are allowed; return True while in trial."""
        status = self.status()
        if not status['allowed']:
            raise LicenseRequired(f"{status.get('reason','A licence is required.')} You can still open, view and save projects. "
                                  f"To continue analysing, open License in the navigator and import your licence file, or contact {SALES}.")
        return status['trial']

    def install(self, content: bytes) -> dict:
        payload = parse(content)
        check = evaluate(payload, self.release_date, machine=self.machine)
        if not check['valid']:
            raise ValueError(check['reason'])
        self.dir.mkdir(parents=True, exist_ok=True)
        target = self.dir / 'license.qlicense'
        if target.exists():  # keep the previous licence rather than overwrite it
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            target.replace(self.dir / f'license-replaced-{stamp}.qlicense')
        target.write_bytes(content)
        return self.status()


def default_root() -> Path:
    """Where the licence and trial record live: the launcher's data directory, else the per-user folder."""
    env = os.environ.get('HVSR_DATA_DIR')
    if env:
        return Path(env)
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
        return base / 'QuakeLogic' / 'HVSR Studio' / 'data'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'QuakeLogic HVSR Studio' / 'data'
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / 'quakelogic-hvsr-studio' / 'data'


def issue(secret: bytes, **fields) -> bytes:
    """Create a signed licence file (QuakeLogic issuing tool only)."""
    payload = {'product': PRODUCT, **fields}
    signature = base64.b64encode(ed25519.sign(secret, canonical(payload))).decode()
    return (json.dumps({'license': payload, 'signature': signature}, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
