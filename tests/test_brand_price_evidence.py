from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from auto_analyse.brand import BrandConfig, analyze_file
from auto_analyse.brand.evidence import _binding


class PriceEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.stamp=datetime.now(timezone.utc).replace(microsecond=0)
        self.rows=[]
        self.records=[]
        for index,price in enumerate((140,160)):
            shop=f'shop{index}.example'
            row=dict(supplier='maker.example',requested_brand='Acme',product_id='p1',
                title='Acme AX5000',brand='Acme',category='Tools',retailer=shop,
                offer_id=f'o{index}',price=price,currency='NOK',availability='in_stock',
                observed_at=self.stamp.isoformat(),is_used=False,is_stale=False,
                model='AX5000',gtin='0001234567895',offer_title='Acme AX5000',
                offer_model='AX5000',regular_price=200)
            self.rows.append(row)
            rec={k:row[k] for k in ('supplier','product_id','offer_id')}
            rec['snapshot_at']=row['observed_at']
            for kind in ('source_api','source_public','merchant'):
                host=shop if kind=='merchant' else 'prisradar.no'
                doc=dict(kind=kind,product_id='p1',offer_id=row['offer_id'],retailer=shop,
                    observed_at=row['observed_at'],retrieved_at=row['observed_at'],
                    url=f'https://{host}/products/p1',price=price,currency='NOK',
                    gtin=row['gtin'],model='AX5000',vat_basis='included',
                    shipping_basis='excluded',availability='in_stock',variant_status='verified')
                name=f'{index}-{kind}.json'
                rec[kind]=self.save_doc(name,doc)
            self.records.append(rec)

    def save_doc(self,name,doc):
        # Independent synthetic raw HTTP observation, separate from derived claims.
        raw=dict(doc)
        offer_fields=('offer_id','price','currency','vat_basis','shipping_basis','availability')
        if doc['kind']!='merchant':
            raw['offer']={key:doc[key] for key in offer_fields}
        raw_data=json.dumps(raw).encode()
        raw_name=name+'.response.raw'
        (self.root/raw_name).write_bytes(raw_data)
        raw_hash=hashlib.sha256(raw_data).hexdigest()
        record={'status':200,'url':doc['url'],'final_url':doc['url'],
                'fetched_at':doc['retrieved_at'],'response_sha256':raw_hash}
        record_data=json.dumps(record).encode()
        record_name=name+'.http.json'; (self.root/record_name).write_bytes(record_data)
        doc['raw_response']={'path':raw_name,'sha256':raw_hash}
        doc['raw_record']={'path':record_name,'sha256':hashlib.sha256(record_data).hexdigest()}
        fields=('product_id','offer_id','price','currency','vat_basis','shipping_basis','availability','gtin','model')
        doc['bindings']={'format':'json','pointers':{key:('/offer/'+key if doc['kind']!='merchant' and key in offer_fields else '/'+key) for key in fields}}
        if doc['kind']!='merchant': doc['bindings']['offer_pointer']='/offer'
        data=json.dumps(doc).encode()
        (self.root/name).write_bytes(data)
        return {'path':name,'sha256':hashlib.sha256(data).hexdigest()}

    def change_doc(self,index,kind,**changes):
        spec=self.records[index][kind]
        doc=json.loads((self.root/spec['path']).read_text())
        doc.update(changes)
        self.records[index][kind]=self.save_doc(spec['path'],doc)

    def change_http_record(self,index,kind,**changes):
        spec=self.records[index][kind]
        doc=json.loads((self.root/spec['path']).read_text())
        path=self.root/doc['raw_record']['path']
        record=json.loads(path.read_text()); record.update(changes)
        content=json.dumps(record).encode(); path.write_bytes(content)
        doc['raw_record']['sha256']=hashlib.sha256(content).hexdigest()
        content=json.dumps(doc).encode(); (self.root/spec['path']).write_bytes(content)
        spec['sha256']=hashlib.sha256(content).hexdigest()

    def run_analysis(self,*,manifest=True):
        source=self.root/'input.csv'
        pd.DataFrame(self.rows).to_csv(source,index=False)
        path=self.root/'evidence.json'
        path.write_text(json.dumps({'version':1,'offers':self.records}))
        return analyze_file(source,BrandConfig(price_evidence_mode='strict'),evidence_manifest=path if manifest else None)[0]

    def test_matching_sources_and_independent_merchant_evidence_qualifies(self):
        result=self.run_analysis()
        self.assertEqual(result.summary['comparable'],1)
        self.assertEqual(result.summary['release_status'],'verified')
        self.assertIn('2/2 kildesamsvar',result.products.iloc[0].price_evidence)
        self.assertEqual(result.observations.audit_merchant_price_status.tolist(),['verified','verified'])
        self.assertEqual(result.observations.audit_stock_validation_status.tolist(),['verified','verified'])

    def test_same_sku_459_vs_140_is_price_conflict_not_variant_proof(self):
        self.change_doc(0,'merchant',price=459)
        result=self.run_analysis()
        row=result.observations.iloc[0]
        self.assertEqual(row.audit_variant_status,'compatible')
        self.assertEqual(row.audit_merchant_price_status,'conflict')
        self.assertFalse(row.audit_price_eligible)
        self.assertEqual(row.price,140)
        self.assertEqual(result.summary['comparable'],0)
        self.assertEqual(result.summary['release_status'],'provisional')
        self.assertNotIn('o0',set(result.campaigns.offer_id))

    def test_missing_manifest_does_not_qualify_or_claim_confirmed_stock(self):
        result=self.run_analysis(manifest=False)
        self.assertEqual(result.summary['comparable'],0)
        self.assertEqual(len(result.campaigns),0)
        self.assertTrue(result.observations.audit_stock_validation_status.eq('source_only').all())
        self.assertEqual(result.summary['stock_rate'],1)
        self.assertIn('0/2 kildesamsvar',result.products.iloc[0].price_evidence)

    def test_source_product_ids_do_not_supply_missing_merchant_identity(self):
        self.change_doc(0,'source_public',gtin='',model='')
        self.change_doc(0,'merchant',gtin='',model='')
        result=self.run_analysis()
        self.assertEqual(result.observations.iloc[0].audit_source_consistency_status,'verified')
        self.assertEqual(result.observations.iloc[0].audit_merchant_price_status,'missing')
        self.assertFalse(result.observations.iloc[0].audit_price_eligible)

    def test_api_public_price_mismatch_blocks_merchant_match(self):
        self.change_doc(0,'source_public',price=459)
        result=self.run_analysis()
        self.assertEqual(result.observations.iloc[0].audit_source_consistency_status,'conflict')
        self.assertEqual(result.observations.iloc[0].audit_merchant_price_status,'verified')
        self.assertFalse(result.observations.iloc[0].audit_price_eligible)

    def test_cache_reread_does_not_renew_source_observation(self):
        old=(self.stamp-timedelta(days=3)).isoformat()
        self.change_doc(0,'source_api',observed_at=old,retrieved_at=self.stamp.isoformat())
        result=self.run_analysis()
        self.assertEqual(result.observations.iloc[0].audit_source_consistency_status,'expired')
        self.assertEqual(result.observations.iloc[0].observed_at,self.stamp.isoformat())

    def test_product_offer_identity_and_hash_fail_closed(self):
        for field,value in [('product_id','other'),('offer_id','other'),('currency','EUR')]:
            with self.subTest(field=field):
                self.change_doc(0,'merchant',**{field:value})
                result=self.run_analysis()
                self.assertFalse(result.observations.iloc[0].audit_price_eligible)
                self.change_doc(0,'merchant',product_id='p1',offer_id='o0',currency='NOK')
        self.records[0]['merchant']['sha256']='0'*64
        self.assertEqual(self.run_analysis().observations.iloc[0].audit_merchant_price_status,'invalid')

    def test_unknown_vat_is_unverified_and_stock_conflict_is_separate(self):
        self.change_doc(0,'merchant',vat_basis='unknown')
        self.assertEqual(self.run_analysis().observations.iloc[0].audit_merchant_price_status,'missing')
        self.change_doc(0,'merchant',vat_basis='included',availability='out_of_stock')
        row=self.run_analysis().observations.iloc[0]
        self.assertEqual(row.audit_merchant_price_status,'verified')
        self.assertEqual(row.audit_stock_validation_status,'conflict')
        self.assertFalse(row.audit_price_eligible)

    def test_snapshot_window_and_expiration_do_not_reprice_old_source(self):
        self.change_doc(0,'merchant',retrieved_at=(self.stamp-timedelta(seconds=301)).isoformat())
        result=self.run_analysis()
        self.assertFalse(result.observations.iloc[0].audit_price_eligible)
        self.assertEqual(result.observations.iloc[0].price,140)

    def test_synthetic_requires_explicit_trusted_caller_and_stays_labelled(self):
        source=self.root/'input.csv'; pd.DataFrame(self.rows).to_csv(source,index=False)
        config=BrandConfig(price_evidence_mode='synthetic')
        with self.assertRaises(ValueError): analyze_file(source,config)
        result=analyze_file(source,config,allow_synthetic=True)[0]
        self.assertEqual(result.summary['release_status'],'synthetic')
        self.assertEqual(result.summary['price_evidence_verified_offers'],0)

    def test_original_raw_hash_and_price_are_checked_not_only_derived_claim(self):
        spec=self.records[0]['merchant']
        doc=json.loads((self.root/spec['path']).read_text())
        raw_path=self.root/doc['raw_response']['path']
        raw=json.loads(raw_path.read_text()); raw['price']=459
        content=json.dumps(raw).encode(); raw_path.write_bytes(content)
        self.assertEqual(self.run_analysis().observations.iloc[0].audit_merchant_price_status,'invalid')
        # Even with all hashes updated, a 459 source cannot substantiate 140.
        digest=hashlib.sha256(content).hexdigest(); doc['raw_response']['sha256']=digest
        record_path=self.root/doc['raw_record']['path']; record=json.loads(record_path.read_text()); record['response_sha256']=digest
        record_content=json.dumps(record).encode(); record_path.write_bytes(record_content)
        doc['raw_record']['sha256']=hashlib.sha256(record_content).hexdigest()
        content=json.dumps(doc).encode(); (self.root/spec['path']).write_bytes(content)
        spec['sha256']=hashlib.sha256(content).hexdigest()
        self.assertEqual(self.run_analysis().observations.iloc[0].audit_merchant_price_status,'conflict')

    def test_api_currency_can_only_use_explicit_verified_public_match(self):
        spec=self.records[0]['source_api']; doc=json.loads((self.root/spec['path']).read_text())
        doc['currency_basis']='source_public_match'
        doc['bindings']['pointers'].pop('currency')
        data=json.dumps(doc).encode(); (self.root/spec['path']).write_bytes(data)
        spec['sha256']=hashlib.sha256(data).hexdigest()
        self.assertEqual(self.run_analysis().summary['comparable'],1)
        self.change_doc(0,'source_public',currency='EUR')
        self.assertFalse(self.run_analysis().observations.iloc[0].audit_price_eligible)

    def test_original_retrieval_time_and_cache_age_cannot_be_renewed(self):
        spec=self.records[0]['merchant']; doc=json.loads((self.root/spec['path']).read_text())
        record_path=self.root/doc['raw_record']['path']; record=json.loads(record_path.read_text())
        record['fetched_at']=(self.stamp-timedelta(days=3)).isoformat()
        content=json.dumps(record).encode(); record_path.write_bytes(content)
        doc['raw_record']['sha256']=hashlib.sha256(content).hexdigest()
        content=json.dumps(doc).encode(); (self.root/spec['path']).write_bytes(content)
        spec['sha256']=hashlib.sha256(content).hexdigest()
        self.assertEqual(self.run_analysis().observations.iloc[0].audit_merchant_price_status,'expired')

    def test_rsc_exact_offer_price_and_embedded_jsonld_currency(self):
        product={'id':7,'title':'Acme tool','offers':[{'id':9,'price':140},{'id':10,'price':459}]}
        ld={'@type':'Product','offers':{'priceCurrency':'NOK'}}
        node={'product':product,'schema':{'__html':json.dumps(ld)}}
        raw='<script>self.__next_f.push([1,'+json.dumps('a:'+json.dumps(node))+'])</script>'
        self.assertEqual(_binding(raw,{'format':'next_rsc_product','product_id':7,'offer_id':10,'field':'price'},{}),459)
        self.assertEqual(_binding(raw,{'format':'jsonld','script_index':0,'pointer':'/offers/priceCurrency'},{}),'NOK')
        with self.assertRaises(ValueError):
            _binding(raw,{'format':'next_rsc_product','product_id':7,'offer_id':11,'field':'price'},{})
        faq='<script type="application/ld+json">'+json.dumps({'@type':'FAQPage'})+'</script>'
        self.assertEqual(_binding(faq+raw,{'format':'jsonld','script_index':1,'pointer':'/offers/priceCurrency'},{}),'NOK')

    def test_visible_unit_price_vat_requires_own_model_sku_and_same_exact_price(self):
        node={'@type':'Product','mpn':'AX5000','sku':'12345','offers':{'@type':'Offer','priceSpecification':[{'@type':'UnitPriceSpecification','price':140,'priceCurrency':'NOK'}]}}
        html='<h1>Acme AX5000 12345</h1><section class="product-price">Salgspris: 140 kr inkl. MVA</section><script type="application/ld+json">'+json.dumps(node)+'</script>'
        spec={'format':'visible_product_vat','text':'Salgspris: 140 kr inkl. MVA','product_binding':{'format':'jsonld','script_index':0,'pointer':''},'price_binding':{'format':'jsonld','script_index':0,'pointer':'/offers/priceSpecification/0/price'}}
        self.assertEqual(_binding(html,spec,{}),'included')
        with self.assertRaises(ValueError): _binding(html.replace('140 kr','459 kr'),spec,{})
        with self.assertRaises(ValueError): _binding(html.replace('AX5000 12345','AX5000'),spec,{})

    def test_source_unknown_vat_requires_independent_matching_merchant_gross_price(self):
        for kind in ('source_api','source_public'):
            self.change_doc(0,kind,vat_basis='unknown',price_context_basis='matched_merchant_offer')
        result=self.run_analysis(); row=result.observations.iloc[0]
        self.assertTrue(row.audit_price_eligible)
        self.assertEqual(row.audit_source_vat_basis,'unknown')
        self.assertEqual(row.audit_price_context_status,'verified')
        self.change_doc(0,'merchant',vat_basis='unknown')
        self.assertFalse(self.run_analysis().observations.iloc[0].audit_price_eligible)

    def test_capture_skew_is_distinct_from_bounded_original_http_cache_age(self):
        self.change_http_record(0,'source_public',response_headers={'age':'1548','cache-control':'max-age=28800'})
        result=self.run_analysis(); row=result.observations.iloc[0]
        self.assertTrue(row.audit_price_eligible)
        self.assertEqual(row.audit_source_cache_status,'cached')
        self.change_http_record(0,'source_public',response_headers={'age':'28801','cache-control':'max-age=28800'})
        self.assertEqual(self.run_analysis().observations.iloc[0].audit_source_consistency_status,'expired')


if __name__=='__main__': unittest.main()
