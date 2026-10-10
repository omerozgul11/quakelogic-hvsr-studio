"""Licensing: 14-day trial, signed licence files, tamper and clock-rollback protection, 402 gating."""
import hmac
import json
import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from hvsr_engine.io.canonical import save_recording
from hvsr_engine.synthetic import synthetic_recording
from hvsr_service import ed25519, licensing
from hvsr_service.app import create_app


def _license(secret, **overrides):
    fields = {'license_id': 'HVSR-TEST-0001', 'customer': 'Test Geo Ltd', 'contact': 'qa@example.com', 'edition': 'Professional',
              'seats': 1, 'machine_ids': [licensing.machine_id()], 'issued': '2026-10-10', 'maintenance_until': '2027-10-10', 'expires': None}
    fields.update(overrides)
    return licensing.issue(secret, **fields)


def _expire_trial(root):
    lic = licensing.Licensing(root, '2026-10-10')
    body = {'started': (date.today() - timedelta(days=20)).isoformat(), 'last_seen': date.today().isoformat()}
    (root / 'license').mkdir(exist_ok=True)
    (root / 'license' / 'trial.json').write_text(json.dumps({**body, 'mac': hmac.new(lic._key, licensing.canonical(body), 'sha256').hexdigest()}))


@pytest.fixture
def secret(monkeypatch):
    s = os.urandom(32)
    monkeypatch.setattr(licensing, 'PUBLIC_KEY', ed25519.public_key(s))
    return s


def test_trial_lock_and_activation(tmp_path, secret):
    rec = synthetic_recording(fs=100.0, duration_s=180.0, f0=2.5, amplification=4.0, damping=0.05, seed=1)
    path = tmp_path / 'rec.npz'; save_recording(rec, path)
    app = create_app(workers=1, license_root=tmp_path)
    with TestClient(app) as client:
        st = client.get('/license').json()
        assert st['state'] == 'trial' and st['allowed'] and st['trial_info']['days_left'] == 14 and len(st['machine_id']) == 23
        params = {'window_length_s': 30, 'overlap': 0.5, 'freq_min': 0.5, 'freq_max': 20, 'n_freq': 60, 'bootstrap': {'enabled': False}, 'sesame': False}
        job = client.post('/hvsr/analyze', json={'input_path': str(path), 'output_dir': str(tmp_path / 'a1'), 'params': params}).json()
        assert job['status'] in ('queued', 'running', 'done')
        import time
        for _ in range(300):
            j = client.get(f"/jobs/{job['id']}").json()
            if j['status'] in ('done', 'failed'):
                break
            time.sleep(0.1)
        assert j['status'] == 'done', j
        # trial exports carry the TRIAL notice
        assert (tmp_path / 'a1' / 'exports' / 'hvsr_mean.csv').read_text().startswith('# QuakeLogic HVSR Studio TRIAL')
        # expire the trial: calculations and exports now answer 402, viewing still works
        _expire_trial(tmp_path)
        r = client.post('/hvsr/analyze', json={'input_path': str(path), 'output_dir': str(tmp_path / 'a2'), 'params': params})
        assert r.status_code == 402 and r.json()['license_required'] and 'open, view and save' in r.json()['error']['message']
        assert client.post('/exports/report', json={'analysis_dir': str(tmp_path / 'a1'), 'output_path': str(tmp_path / 'r.pdf'), 'context': {}}).status_code == 402
        assert client.post('/recordings/data', json={'path': str(path), 'max_points': 200}).status_code == 200
        assert client.post('/analyses/load', json={'dir': str(tmp_path / 'a1')}).status_code == 200
        # forged, tampered, other-computer and lapsed-maintenance licences are refused
        assert client.post('/license', files={'file': ('x.qlicense', _license(os.urandom(32)))}).status_code == 422
        good = json.loads(_license(secret)); good['license']['seats'] = 99
        assert client.post('/license', files={'file': ('x.qlicense', json.dumps(good).encode())}).status_code == 422
        assert 'another computer' in client.post('/license', files={'file': ('x.qlicense', _license(secret, machine_ids=['AAAAA-BBBBB-CCCCC-DDDDD']))}).json()['error']['message']
        assert 'Maintenance' in client.post('/license', files={'file': ('x.qlicense', _license(secret, maintenance_until='2026-01-01'))}).json()['error']['message']
        ok = client.post('/license', files={'file': ('x.qlicense', _license(secret))})
        assert ok.status_code == 200 and ok.json()['state'] == 'licensed' and ok.json()['license']['customer'] == 'Test Geo Ltd'
        r = client.post('/hvsr/analyze', json={'input_path': str(path), 'output_dir': str(tmp_path / 'a3'), 'params': params})
        assert r.status_code == 200
        assert client.post('/license', files={'file': ('x.qlicense', _license(secret, license_id='HVSR-TEST-0002'))}).status_code == 200
        assert len(list((tmp_path / 'license').glob('license-replaced-*.qlicense'))) == 1, 'previous licence kept'


def test_trial_tampering_and_clock_rollback_end_the_trial(tmp_path):
    lic = licensing.Licensing(tmp_path, '2026-10-10')
    assert lic.status()['state'] == 'trial'
    later = date.today() + timedelta(days=5)
    assert lic.status(today=later)['trial_info']['days_left'] == 9
    assert lic.status(today=date.today())['state'] == 'unlicensed'  # clock set back by five days
    (tmp_path / 'license' / 'trial.json').write_text('{"started":"2099-01-01","last_seen":"2099-01-01","mac":"forged"}')
    assert lic.status()['reason'] == 'The trial record was altered.'


def test_issue_and_verify_roundtrip(tmp_path, secret):
    content = _license(secret)
    payload = licensing.parse(content)
    assert payload['product'] == 'HVSR Studio' and payload['customer'] == 'Test Geo Ltd'
    assert licensing.evaluate(payload, '2026-10-10')['valid']
    assert not licensing.evaluate(payload, '2027-12-01')['valid']  # released after maintenance ended
    with pytest.raises(ValueError):
        licensing.parse(content.replace(b'Test Geo Ltd', b'Someone Else'))
