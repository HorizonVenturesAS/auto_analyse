"""Source-reported prices remain useful without claiming merchant verification."""
from copy import deepcopy
import json
import unittest

import pandas as pd

from auto_analyse.brand import BrandConfig, analyze_file
from tests import test_brand_price_evidence as evidence_fixtures


class BrandSourcePricesTest(unittest.TestCase):
    def setUp(self):
        # Reuse the independently saved HTTP/proof fixtures, not a second mocked gate.
        self.evidence=evidence_fixtures.PriceEvidenceTest('test_matching_sources_and_independent_merchant_evidence_qualifies')
        self.evidence.setUp()
        self.addCleanup(self.evidence.doCleanups)

    def analyze(self,*,mode='source',manifest=False):
        f=self.evidence
        source=f.root/'input.csv'; pd.DataFrame(f.rows).to_csv(source,index=False)
        path=f.root/'evidence.json'; path.write_text(json.dumps({'version':1,'offers':f.records}))
        return analyze_file(source,BrandConfig(price_evidence_mode=mode),
                            evidence_manifest=path if manifest else None)[0]

    def add_third_source_offer(self,price=200):
        self.evidence.rows.append({**deepcopy(self.evidence.rows[1]),
                                   'retailer':'shop2.example','offer_id':'o2','price':price})

    def test_fresh_source_prices_without_merchant_proof_have_a_useful_gap(self):
        result=self.analyze()
        self.assertEqual(result.products.iloc[0].price_stores,2)
        self.assertAlmostEqual(result.products.iloc[0].gap_pct,160/140-1)
        self.assertEqual(result.summary['comparable'],1)
        self.assertTrue(result.observations.audit_merchant_price_status.eq('missing').all())
        self.assertTrue(result.observations.audit_stock_validation_status.eq('source_only').all())
        self.assertEqual(result.summary['price_evidence_verified_offers'],0)
        self.assertTrue(result.observations.audit_price_basis.eq('source_observed').all())
        self.assertNotEqual(result.summary['release_status'],'verified')

    def test_brekkjern_102_140_source_match_does_not_require_second_merchant(self):
        f=self.evidence
        for index,price in enumerate((102,140)):
            f.rows[index]['price']=price
            for kind in ('source_api','source_public'):
                f.change_doc(index,kind,price=price)
        f.change_doc(0,'merchant',price=102)
        f.records[1].pop('merchant')
        result=self.analyze(manifest=True)
        product=result.products.iloc[0]
        self.assertEqual((product.min_price,product.max_price,product.price_stores),(102,140,2))
        self.assertAlmostEqual(product.gap_pct,140/102-1)
        self.assertTrue(result.observations.audit_source_consistency_status.eq('verified').all())
        self.assertEqual(result.observations.iloc[1].audit_merchant_price_status,'missing')
        self.assertEqual(result.summary['price_evidence_verified_offers'],1)
        self.assertEqual(result.observations.audit_price_basis.tolist(),['independently_verified','source_observed'])
        self.assertEqual(self.analyze(mode='strict',manifest=True).products.iloc[0].price_stores,1)

    def test_known_source_conflict_excludes_only_that_offer_before_minimum(self):
        self.add_third_source_offer()
        self.evidence.change_doc(0,'source_public',price=459)
        result=self.analyze(manifest=True)
        self.assertEqual(result.observations.iloc[0].audit_source_consistency_status,'conflict')
        self.assertFalse(result.observations.iloc[0].audit_price_eligible)
        self.assertEqual(result.products.iloc[0].min_price,160)
        self.assertEqual(result.products.iloc[0].price_stores,2)
        self.assertAlmostEqual(result.products.iloc[0].gap_pct,.25)
        self.assertEqual(result.observations.iloc[0].price,140)

    def test_known_merchant_price_conflict_cannot_fall_back_to_raw_source(self):
        self.add_third_source_offer()
        self.evidence.change_doc(0,'merchant',price=459)
        result=self.analyze(manifest=True)
        self.assertEqual(result.observations.iloc[0].audit_variant_status,'compatible')
        self.assertEqual(result.observations.iloc[0].audit_merchant_price_status,'conflict')
        self.assertFalse(result.observations.iloc[0].audit_price_eligible)
        self.assertEqual(result.products.iloc[0].min_price,160)
        self.assertEqual(result.products.iloc[0].price_stores,2)
        self.assertNotIn('o0',set(result.campaigns.offer_id))

    def test_bad_proof_hash_is_not_treated_as_absence_of_optional_proof(self):
        self.add_third_source_offer()
        self.evidence.records[0]['source_public']['sha256']='0'*64
        result=self.analyze(manifest=True)
        self.assertEqual(result.observations.iloc[0].audit_source_consistency_status,'invalid')
        self.assertFalse(result.observations.iloc[0].audit_price_eligible)
        self.assertEqual(result.products.iloc[0].min_price,160)
        self.assertEqual(result.products.iloc[0].price_stores,2)

    def test_variant_conflict_and_unknown_are_still_excluded_individually(self):
        for title,model,expected in [('Acme AX6000','AX6000','conflict'),('','','unverified')]:
            with self.subTest(status=expected):
                self.evidence.rows[0].update(offer_title=title,offer_model=model,offer_gtin='')
                result=self.analyze()
                self.assertEqual(result.observations.iloc[0].audit_variant_status,expected)
                self.assertFalse(result.observations.iloc[0].audit_price_eligible)
                self.assertEqual(result.products.iloc[0].price_stores,1)
                self.assertEqual(result.products.iloc[0].min_price,160)

    def test_manual_offer_review_still_blocks_only_the_affected_offer(self):
        self.add_third_source_offer()
        self.evidence.rows[0]['offer_review_reason']='Explicit unresolved model evidence'
        result=self.analyze()
        self.assertFalse(result.observations.iloc[0].audit_price_eligible)
        self.assertEqual(result.products.iloc[0].price_stores,2)
        self.assertEqual(result.products.iloc[0].min_price,160)

    def test_manual_product_flag_still_blocks_the_product(self):
        self.evidence.rows[0]['review_reason']='Product identity must be checked'
        result=self.analyze()
        self.assertEqual(result.summary['comparable'],0)
        self.assertFalse(result.observations.audit_price_eligible.any())

    def test_source_stock_uses_observation_while_strict_requires_independent_stock(self):
        for index in (0,1): self.evidence.change_doc(index,'merchant',availability=None)
        source=self.analyze(manifest=True)
        strict=self.analyze(mode='strict',manifest=True)
        self.assertEqual(source.summary['comparable'],1)
        self.assertEqual(strict.summary['comparable'],0)
        self.assertEqual(source.summary['stock_rate'],1)
        self.assertEqual(strict.summary['stock_rate'],1)
        self.assertTrue(source.observations.audit_stock_validation_status.eq('missing').all())

    def test_known_stock_conflict_is_not_hidden_by_source_stock_mode(self):
        self.evidence.change_doc(0,'merchant',availability='out_of_stock')
        result=self.analyze(manifest=True)
        self.assertEqual(result.observations.iloc[0].audit_stock_validation_status,'conflict')
        self.assertFalse(result.observations.iloc[0].audit_price_eligible)
        self.assertEqual(result.products.iloc[0].price_stores,1)
        self.assertEqual(result.summary['stock_rate'],1)

    def test_source_mode_keeps_existing_positive_currency_freshness_and_condition_rules(self):
        changes=[{'price':0},{'currency':'EUR'},{'is_stale':True},{'is_used':None},
                 {'price_qualifier':'member_only'},{'availability':'out_of_stock'}]
        original=deepcopy(self.evidence.rows[0])
        for change in changes:
            with self.subTest(change=change):
                self.evidence.rows[0]={**deepcopy(original),**change}
                result=self.analyze()
                self.assertFalse(result.observations.iloc[0].audit_price_eligible)
                self.assertEqual(result.summary['comparable'],0)
        self.evidence.rows[0]=original

    def test_strict_mode_remains_closed_without_independent_price_proof(self):
        result=self.analyze(mode='strict')
        self.assertEqual(result.summary['comparable'],0)
        self.assertEqual(result.products.iloc[0].price_stores,0)
        self.assertEqual(len(result.campaigns),0)
        self.assertFalse(result.observations.audit_price_eligible.any())


if __name__=='__main__': unittest.main()
