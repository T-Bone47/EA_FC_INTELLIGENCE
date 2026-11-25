"""Dependency-free policy and integrity regressions, also collected by pytest."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services import data_license_gate as gate
from backend.services.reference_distribution import (
    ReferenceDistributionMismatch, ReferenceDistributionUnavailable, resolve_serving_reference,
)
from scripts import ingest_fc27_card_identity as ingest


class PolicyTests(unittest.TestCase):
    def test_registered_reference_matrix(self):
        for game in ('FC26', 'FC27'):
            version = game.lower() + '-players-2026-09-r1'
            for env in gate.Environment:
                for research in (False, True):
                    for override in (None, version):
                        with self.subTest(game=game, env=env, research=research, override=override):
                            args = (game, 'game_player', research, env, override)
                            if game == 'FC27' and not research:
                                with self.assertRaises(ReferenceDistributionUnavailable):
                                    resolve_serving_reference(*args)
                            elif env == gate.Environment.PRODUCTION:
                                with self.assertRaises((gate.DataLicenseGateFailure, gate.ProductionOverrideForbidden)):
                                    resolve_serving_reference(*args)
                            else:
                                ref, restricted = resolve_serving_reference(*args)
                                self.assertEqual((ref.version, restricted), (version, game == 'FC27'))

    def test_wrong_scope_or_reference(self):
        with self.assertRaises(ReferenceDistributionMismatch):
            resolve_serving_reference('FC26', 'ut_card', True, gate.Environment.LOCAL)
        with self.assertRaises(ReferenceDistributionMismatch):
            resolve_serving_reference('FC26', 'game_player', True, gate.Environment.LOCAL, 'fc27-players-2026-09-r1')

    def test_warm_reference_still_requires_current_licence_entry(self):
        args = ('FC26', 'game_player', True, gate.Environment.LOCAL)
        ref, _ = resolve_serving_reference(*args)
        with patch.dict(gate._DATASET_LICENSE_REGISTRY, clear=True):
            with self.assertRaises(gate.DataLicenseGateFailure):
                resolve_serving_reference(*args, override=ref.version)


class IngestionTests(unittest.TestCase):
    def test_permission_required_before_database_access(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(ingest, 'APPROVAL', Path(tmp) / 'absent'):
            with self.assertRaises(SystemExit):
                ingest.check_approval()

    def test_approved_bytes_count_and_snapshot_are_all_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            inventory = {}
            for name in sorted(ingest.REQUIRED | {'raw/source.xml'}):
                p = pkg / name
                p.parent.mkdir(parents=True, exist_ok=True)
                data = ('snapshot_id,value\nsynthetic-id,test\n' if name.endswith('.csv')
                        else json.dumps({'dataset_name': 'synthetic', 'dataset_version': '0.1.0-research',
                                         'snapshot_id': 'synthetic-id'}))
                p.write_bytes(data.encode())
                inventory[name] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'rows': 1}
            record = {'files': inventory, 'snapshot_id': 'synthetic-id'}
            self.assertEqual(ingest.verify_inventory(pkg, record)['dataset_name'], 'synthetic')
            with self.assertRaises(SystemExit):
                ingest.verify_inventory(pkg, dict(record, snapshot_id='other'))
            name = 'canonical/fc27_game_players.csv'
            inventory[name]['rows'] = 2
            with self.assertRaises(SystemExit):
                ingest.verify_inventory(pkg, record)
            inventory[name]['rows'] = 1
            (pkg / name).write_bytes(b'changed')
            with self.assertRaises(SystemExit):
                ingest.verify_inventory(pkg, record)
            (pkg / name).unlink()
            with self.assertRaises(SystemExit):
                ingest.verify_inventory(pkg, record)

    def test_csv_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'bad.csv'
            for data in ('a,a\n1,2', 'a,b\n1', 'a,b\n1,2,3'):
                p.write_text(data)
                with self.assertRaises(SystemExit):
                    ingest.rd(p)

