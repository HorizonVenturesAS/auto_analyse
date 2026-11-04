import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from auto_analyse.verification import build_plan, main
from tests.test_brand_analysis import offer


class VerificationPlanTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_retail_screens_full_assortment_not_only_alerts(self):
        source = Path('examples/demo/retail.csv')
        before = source.read_bytes()
        plan = build_plan(source, 'retail', 'config/demo-retail.toml', demo=True, sample_size=2, seed=42)
        self.assertEqual(plan['products_screened'], 8)
        self.assertEqual(len({tuple(u['key']) for u in plan['units']}), 8)
        units = {u['key'][0]: u for u in plan['units']}
        self.assertIn('no_source_competitor', units['000006']['flags'])
        self.assertIn('large_price_gap', units['000008']['flags'])
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(plan['status'], 'review_pending')

    def test_brand_isolates_suppliers_and_preserves_offer_evidence(self):
        source = self.root/'brands.csv'
        pd.DataFrame([
            offer(gtin='', model='AX100', offer_title='AX200', offer_model='AX200'),
            offer(shop='b.no', gtin='', model='AX100', offer_title='AX100', offer_model='AX100'),
            offer(supplier='other.example', gtin=''),
        ]).to_csv(source, index=False)
        before = source.read_bytes()
        with patch('urllib.request.urlopen', side_effect=AssertionError('offline only')):
            plan = build_plan(source, 'brand', sample_size=0)
        self.assertEqual(plan['products_screened'], 2)
        self.assertEqual(len({tuple(u['key']) for u in plan['units']}), 2)
        first = next(u for u in plan['units'] if u['key'][0]=='supplier.no')
        self.assertIn('variant_conflict', first['flags'])
        self.assertIn('blocked_comparison', first['flags'])
        self.assertEqual(len(first['offers']), 2)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(plan['source_sha256'], hashlib.sha256(before).hexdigest())

    def test_sample_is_reproducible_even_if_input_rows_reorder(self):
        source = self.root/'brands.csv'
        rows = [offer(str(i), gtin='') for i in range(12)]
        pd.DataFrame(rows).to_csv(source, index=False)
        a = build_plan(source, 'brand', sample_size=3, seed=42)
        pd.DataFrame(list(reversed(rows))).to_csv(source, index=False)
        b = build_plan(source, 'brand', sample_size=3, seed=42)
        selection = lambda p: [u['key'] for u in p['units'] if u['random_sample']]
        self.assertEqual(selection(a), selection(b))
        self.assertEqual(len(selection(a)), 3)
        self.assertGreater(a['review_queue_count'], 3)  # risk queue is not capped by random sample

    def test_cli_protects_outputs_source_hardlinks_and_evidence(self):
        output = self.root/'plan.json'
        args = ['--mode','retail','--demo','--output',str(output)]
        with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.read_text())['products_screened'], 8)
        before = output.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit): main(args)
        self.assertEqual(output.read_bytes(), before)
        source = self.root/'source.csv'
        source.write_text('private source bytes')
        alias = self.root/'alias.json'
        try: alias.hardlink_to(source)
        except OSError: self.skipTest('hardlinks unavailable')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main([str(source),'--mode','brand','--output',str(alias),'--overwrite'])
        self.assertEqual(source.read_text(), 'private source bytes')
        evidence = self.root/'evidence.json'
        evidence.write_text('{"version":1,"offers":[]}')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['--mode','brand','--demo','--evidence-manifest',str(evidence),'--output',str(evidence),'--overwrite'])
        self.assertEqual(evidence.read_text(), '{"version":1,"offers":[]}')

    def test_invalid_options_and_demo_cannot_approve_real_data(self):
        with self.assertRaises(ValueError): build_plan(Path('examples/demo/brands.csv'),'brand',sample_size=-1)
        with self.assertRaises(ValueError): build_plan(Path('examples/demo/brands.csv'),'brand',gap_threshold=float('nan'))
        with self.assertRaises(ValueError): build_plan(Path('examples/demo/brands.csv'),'retail',evidence_manifest='anything')
        with self.assertRaises(ValueError): build_plan(self.root/'real.csv','brand',demo=True)


if __name__ == '__main__':
    unittest.main()
