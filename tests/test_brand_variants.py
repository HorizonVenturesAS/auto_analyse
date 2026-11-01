import json
from collections import namedtuple
import unittest

from auto_analyse.brand.variants import assess_variant


class VariantEvidenceTest(unittest.TestCase):
    def assess(self, title, offer_title, **more):
        return assess_variant({'title':title,'offer_title':offer_title,**more})

    def test_wrong_drill_and_correct_offer(self):
        attrs=json.dumps([{'name':'Produktnavn','raw_value':'Metallbor HSS-R 10mm AX50105'}])
        wrong=self.assess('Acme 10mm HSS-R metallbor','Metallbor HSS-R 1.5mm AX50005',product_attributes=attrs)
        correct=self.assess('Acme 10mm HSS-R metallbor','Metallbor HSS-R 10mm AX50105',product_attributes=attrs)
        self.assertEqual(wrong['status'],'conflict')
        self.assertEqual(correct['status'],'compatible')
        self.assertTrue(any(c['value']=='AX50105' for c in correct['evidence']['product_claims']))

    def test_units_and_decimal_preserved(self):
        self.assertEqual(self.assess('Acme HSS bor 10mm AX50105','Acme HSS bor 1cm AX50105')['status'],'compatible')
        self.assertEqual(self.assess('Acme HSS bor 1,5mm','Acme HSS bor 15mm')['status'],'conflict')

    def test_invalid_typed_variant_value_is_not_absence_of_evidence(self):
        self.assertEqual(self.assess('Acme AX5000', 'Acme AX5000', product_diameter_mm='unknown')['status'], 'unverified')
        self.assertEqual(self.assess('Acme AX5000', 'Acme AX5000', offer_battery_included='maybe')['status'], 'unverified')

    def test_gtin_identity_requires_valid_identifier(self):
        for value in ('unknown', '123', '0001234567890'):
            self.assertEqual(self.assess('Acme AX5000 med batteri', 'Acme AX5000', gtin=value, offer_gtin=value)['status'], 'unverified')

    def test_ordered_drill_dimensions_and_axis_labels(self):
        self.assertEqual(self.assess('Metallbor HSS AX50105 10x133mm','Metallbor HSS AX50105 diameter 10mm lengde 133mm')['status'],'compatible')
        result=self.assess('Bor HSS diameter 10mm lengde 133mm','Bor HSS diameter 133mm lengde 10mm')
        self.assertEqual(result['status'],'conflict')

    def test_unknown_dimension_does_not_claim_diameter_outside_context(self):
        result=self.assess('Acme aksel diameter 10mm','Acme aksel 133mm')
        self.assertEqual(result['status'],'unverified')
        self.assertFalse(any(c['axis']=='diameter_mm' for c in result['evidence']['offer_claims']))

    def test_length_is_not_diameter(self):
        result=self.assess('Acme diameter 10mm','Acme lengde 10mm')
        self.assertEqual(result['status'],'unverified')

    def test_exact_model_can_bridge_missing_dimension(self):
        self.assertEqual(self.assess('Metallbor HSS 10mm AX50105','Acme AX50105')['status'],'compatible')

    def test_gtin_never_overrides_conflict(self):
        self.assertEqual(self.assess('Metallbor HSS 10mm','Metallbor HSS 1.5mm',gtin='0001234567895',offer_gtin='0001234567895')['status'],'conflict')

    def test_generic_codes_across_brands_and_suffixes(self):
        self.assertEqual(self.assess('Bosch GSB18V','Bosch GSB12V')['status'],'conflict')
        self.assertEqual(self.assess('Acme AX50105','Acme AX50105-QZ')['status'],'unverified')

    def test_compatibility_model_is_not_sale_identity(self):
        result=self.assess('Acme AX50105 10mm','Tilbehør passer til AX50105')
        self.assertEqual(result['status'],'unverified')
        self.assertFalse(result['evidence']['offer_claims'])
        self.assertEqual(self.assess('Bor for metall STA50105','Bor for metall STA50105')['status'],'compatible')

    def test_url_is_not_identity(self):
        self.assertEqual(self.assess('Acme AX50105','Se https://example.com/AX50105')['status'],'unverified')

    def test_pack_count_and_composite(self):
        self.assertEqual(self.assess('Acme blad AX5000 100 stk','Acme blad AX5000 10x10-pakning')['status'],'compatible')
        self.assertEqual(self.assess('Acme blad 10 stk','Acme blad 100 stk')['status'],'conflict')
        self.assertEqual(self.assess('Acme AX5000 10 stk','Acme AX5000')['status'],'unverified')
        self.assertEqual(self.assess('Acme blad AX5000 100pk','Acme blad AX5000 10x10pk')['status'],'compatible')

    def test_catalogue_length_does_not_override_drill_diameter(self):
        attrs=[{'name':'Produktnavn','value':'Metallbor HSS 10mm STA50105'},
               {'name':'Lengde','value':'235 mm'}]
        result=self.assess('Metallbor HSS 10mm','Acme STA50105 1cm 133mm',product_attributes=attrs)
        self.assertEqual(result['status'],'unverified')
        self.assertFalse(any('Motstridende' in reason for reason in result['reasons']))

    def test_surform_lengths_have_unknown_roles(self):
        result=self.assess('Surform høvel 310mm 5-21-122','Surform 250mm 5-21-122 blad')
        self.assertEqual(result['status'],'unverified')

    def test_component_counts_are_not_automatically_sale_pack_counts(self):
        result=self.assess('Acme stemjernsett 4 stemjern med slipesett','Acme stemjernsett 6 deler')
        self.assertNotEqual(result['status'],'conflict')

    def test_required_drill_diameter_missing_on_offer(self):
        self.assertEqual(self.assess('Metallbor HSS 10mm','Metallbor HSS')['status'],'unverified')

    def test_battery_contents_capacity_and_count(self):
        self.assertEqual(self.assess('Acme AX5000 med batteri 2x2Ah','Acme AX5000 uten batteri 1x4Ah')['status'],'conflict')
        self.assertEqual(self.assess('Acme AX5000 med batteri','Acme AX5000')['status'],'unverified')
        self.assertEqual(self.assess('Acme AX5000 med batteri','Acme AX5000',gtin='0001234567895',offer_gtin='0001234567895')['status'],'compatible')

    def test_no_universal_18v_20v_equivalence(self):
        self.assertEqual(self.assess('Acme AX5000 18V','Acme AX5000 20V')['status'],'conflict')

    def test_battery_machine_and_standalone_required_axes(self):
        self.assertEqual(self.assess('Acme AX5000 drill 18V','Acme AX5000 drill 18V')['status'],'unverified')
        self.assertEqual(self.assess('Acme AX5000 batteri 18V 4Ah','Acme AX5000 batteri 18V 4Ah')['status'],'unverified')
        self.assertEqual(self.assess('Acme AX5000 drill 18V uten batteri','Acme AX5000 drill 18V uten batteri')['status'],'compatible')

    def test_typed_axes_namedtuple_and_json(self):
        Row=namedtuple('Row','title offer_title product_diameter_mm offer_diameter_mm')
        result=assess_variant(Row('Acme','Acme','10','1.5'))
        self.assertEqual(result['status'],'conflict')
        json.dumps(result)

    def test_flattened_decimal_is_unknown(self):
        self.assertEqual(self.assess('Acme AX5000 4 0Ah','Acme AX5000 4Ah')['status'],'unverified')

    def test_unrelated_product_not_applicable(self):
        self.assertEqual(self.assess('En vanlig vare','En vanlig vare')['status'],'not_applicable')

    def test_grit_conflict_and_grit_is_not_model(self):
        for left,right in [('K40','K80'),('K100','K120'),('P80','P120')]:
            result=self.assess('Mirka slipepapir '+left,'Mirka slipepapir '+right)
            self.assertEqual(result['status'],'conflict')
            self.assertFalse(any(c['axis']=='model' for c in result['evidence']['product_claims']))
        self.assertEqual(self.assess('Slipepapir STA33376 K40','Slipepapir STA33376 K80')['status'],'conflict')
        self.assertEqual(self.assess('Slipepapir STA33376 K40','STA33376 K80')['status'],'conflict')

    def test_same_identifier_cannot_hide_extra_conflicting_title_model(self):
        result=self.assess('Acme AX50105','Acme AX50005',model='AX50105',offer_model='AX50105',gtin='0001234567895',offer_gtin='0001234567895')
        self.assertEqual(result['status'],'unverified')

    def test_grit_structured_attributes_and_typed_axis(self):
        self.assertEqual(self.assess('Mirka slipeark','Mirka slipeark',
            product_attributes=[{'name':'Korning','value':'P80'}],
            offer_attributes=json.dumps([{'name':'grit','raw_value':'P120'}]))['status'],'conflict')
        self.assertEqual(self.assess('Mirka slipeark AX5000','Mirka slipeark AX5000',product_grit='K40',offer_grit=40)['status'],'compatible')
        self.assertEqual(self.assess('Mirka slipepapir 40K','Mirka slipepapir korning 80')['status'],'conflict')

    def test_charger_inclusion_other_brand(self):
        self.assertEqual(self.assess('Makita AX5000 med batteri og lader','Makita AX5000 med batteri uten lader')['status'],'conflict')
        self.assertEqual(self.assess('Makita AX5000 uten batteri og lader','Makita AX5000 uten batteri med lader')['status'],'conflict')
        self.assertEqual(self.assess('Makita AX5000 med lader','Makita AX5000')['status'],'unverified')
        self.assertEqual(self.assess('Makita AX5000','Makita AX5000',product_charger_included=True,offer_charger_included=False)['status'],'conflict')

    def test_measurement_capacity_tokens_not_model_codes(self):
        result=self.assess('Acme beholder 120L 1200W 1200LM 200RPM','Acme beholder 120L 1200W 1200LM 200RPM')
        self.assertFalse(any(c['axis']=='model' for c in result['evidence']['product_claims']))

    def test_generic_pack_measurement_and_tip_tokens_not_sku(self):
        for token in ['100-PAKNING','2-PAKNING','100M','850L/T','6-25MM','100K','75X457','PH-2','PZ2','2451N']:
            result=self.assess('Acme '+token,'Acme '+token)
            self.assertFalse(any(c['axis']=='model' for c in result['evidence']['product_claims']),token)

    def test_drive_profile_is_independent_axis(self):
        self.assertEqual(self.assess('Acme skrutrekker AX5000 PH2','Acme skrutrekker AX5000 PH-2')['status'],'compatible')
        self.assertEqual(self.assess('Acme skrutrekker PH2','Acme skrutrekker PH3')['status'],'conflict')
        self.assertEqual(self.assess('Acme bits TX20','Acme bits TX25')['status'],'conflict')

    def test_model_gtin_is_not_own_sku(self):
        result=self.assess('Acme vare','Acme AX5000',model='0001234567895',gtin='0001234567895')
        self.assertEqual(result['status'],'unverified')
        self.assertFalse(any(c['axis']=='model' for c in result['evidence']['product_claims']))

    def test_model_namespaces_and_numeric_packaging(self):
        self.assertEqual(self.assess('Acme RL600LR','Acme FMHT77449-1')['status'],'unverified')
        self.assertEqual(self.assess('Acme AX50105','Acme AX50005')['status'],'conflict')
        self.assertEqual(self.assess('Acme 0-33-218','Acme 1-33-218')['status'],'unverified')
        self.assertEqual(self.assess('Acme 0-58-911','Acme 0-58-913')['status'],'conflict')

    def test_blade_outer_diameter_not_mounting_bore(self):
        result=self.assess('Acme sagblad STA15645 boringsdiameter 30mm',
                           'Acme sagblad STA15645 bladdiameter 254mm boringsdiameter 30mm')
        self.assertEqual(result['status'],'compatible')
        self.assertFalse(any(c['axis']=='diameter_mm' for c in result['evidence']['product_claims']))
        self.assertEqual(self.assess('Sagblad boringsdiameter 30mm','Sagblad boringsdiameter 20mm')['status'],'conflict')

    def test_tape_measure_length(self):
        self.assertEqual(self.assess('Acme målebånd 8m','Acme målebånd 5m')['status'],'conflict')
        self.assertEqual(self.assess('Acme målebånd AX5000 1m','Acme målebånd AX5000 100cm')['status'],'compatible')

    def test_unlabelled_geometry_is_unknown_role(self):
        self.assertEqual(self.assess('Acme sliper 75x457mm','Acme sliper 75x533mm')['status'],'unverified')

    def test_attributes_alone_do_not_prove_sale_identity(self):
        for left,right in [('Batteridrill 18V med batteri','Batteridrill 18V med batteri'),
                           ('Acme blad 100pk','Acme blad 100pk'),('Acme bits 2stk','Acme bits 2stk')]:
            self.assertEqual(self.assess(left,right)['status'],'unverified')

    def test_sds_bore_diameter(self):
        self.assertEqual(self.assess('Acme SDS-PLUS Bor 6x110mm','Acme SDS-PLUS Bor 5x110mm')['status'],'conflict')
        self.assertEqual(self.assess('Acme spiralbor 6mm','Acme spiralbor 5mm')['status'],'conflict')

    def test_nominal_max_voltage_relation_not_assumed(self):
        for product,offered in [('18V','20V MAX'),('20V MAX','18V'),('20V','18V MAX')]:
            self.assertEqual(self.assess('Acme AX5000 '+product,'Acme AX5000 '+offered)['status'],'unverified')

    def test_zero_count_and_measurement_are_unknown_not_variant_conflict(self):
        for axis in ('pack_count','diameter_mm','battery_capacity_ah'):
            result=self.assess('Acme AX5000','Acme AX5000',**{'product_'+axis:0,'offer_'+axis:1})
            self.assertEqual(result['status'],'unverified')
            self.assertFalse(any('Motstridende' in reason for reason in result['reasons']))

    def test_punctuation_aliases_are_unknown_without_exact_reference(self):
        for left,right in [('STST83319-1','STST833191'),('FMST175763','FMST1-75763')]:
            self.assertEqual(self.assess('Acme '+left,'Acme '+right)['status'],'unverified')
            self.assertEqual(self.assess('Acme '+left,'Acme '+right,gtin='0001234567895',offer_gtin='0001234567895')['status'],'compatible')
        self.assertEqual(self.assess('Acme 0-58-911','Acme 0-58-913')['status'],'conflict')

    def test_tape_blade_width_and_reel_length(self):
        for unit in ('meter','m','metres','metros'):
            result=self.assess('Acme målebånd AX5000 32mm x8'+unit,'Acme målebånd AX5000 8m')
            self.assertEqual(result['status'],'compatible')
            self.assertFalse(any(c['axis']=='length_mm' and c['value']==32 for c in result['evidence']['product_claims']))
        self.assertEqual(self.assess('Acme målebånd 32mm x8meter','Acme målebånd 5m')['status'],'conflict')

    def test_reversible_drive_profile_shorthand(self):
        result=self.assess('Acme AX5000 PH1/PH2','Acme AX5000 PH1/2')
        self.assertEqual(result['status'],'compatible')
        self.assertEqual(self.assess('Acme AX5000 PH1/PH2','Acme AX5000 PH1/3')['status'],'conflict')

    def test_missing_alpha_sale_suffix_is_unknown_but_two_explicit_variants_conflict(self):
        self.assertEqual(self.assess('Acme SFMCST925','Acme SFMCST925B-XJ')['status'],'unverified')
        self.assertEqual(self.assess('Acme SFMCST925B','Acme SFMCST925D')['status'],'conflict')

    def test_flattened_decimal_dimension_remains_unparsed(self):
        result=self.assess('Acme metallbor STA50000 5 5mm','Acme metallbor STA50000 5.5mm')
        self.assertEqual(result['status'],'unverified')
        self.assertTrue(any(c['axis']=='unparsed' and c['raw_value']=='5 5mm' for c in result['evidence']['product_claims']))

    def test_merged_model_measurement_is_not_guessed_or_hard_conflict(self):
        result=self.assess('Acme STA36070115MM','Acme STA36070 115mm')
        self.assertEqual(result['status'],'unverified')
        self.assertTrue(any(c['axis']=='unparsed' and c['raw_value']=='STA36070115MM' for c in result['evidence']['product_claims']))


if __name__=='__main__':
    unittest.main()
