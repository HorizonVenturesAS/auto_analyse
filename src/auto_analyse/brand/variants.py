"""Conservative sale-variant evidence, independent of price and brand policy.

Claims retain their source and axis. Absence of a conflict is not proof of
agreement. Exact identifiers may fill missing dimensions, but never override
an explicit contradiction. No network calls or fuzzy identity matching.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
import math
import re
import unicodedata

NUMBER = r"\d+(?:[.,]\d+)?"
AXES = ("diameter_mm", "length_mm", "width_mm", "pack_count", "voltage_v",
        "battery_capacity_ah", "battery_count", "battery_included", "charger_included", "grit",
        "inner_diameter_mm", "outer_diameter_mm", "drive_profile")
BOOL_AXES = {'battery_included','charger_included'}
LABELS = {"diameter_mm": "diameter", "length_mm": "lengde", "width_mm": "bredde",
          "pack_count": "pakningsantall", "voltage_v": "spenning",
          "battery_capacity_ah": "batterikapasitet", "battery_count": "batteriantall",
          "battery_included": "batteri inkludert", "charger_included": "lader inkludert",
          "grit": "slipekorn", "model": "modell", "inner_diameter_mm":"boringsdiameter",
          "outer_diameter_mm":"utvendig diameter", "drive_profile":"skrutrekkerspiss"}


def _text(value):
    if value is None or isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', _text(value).casefold())
                   if c.isalnum() and not unicodedata.combining(c))


def _number(value):
    text = _text(value).replace(',', '.')
    try:
        result = float(text)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _bool(value):
    key = _text(value).casefold()
    return True if key in {'true','1','yes','ja'} else False if key in {'false','0','no','nei'} else None


def _valid_gtin(value):
    if not value.isascii() or not value.isdigit() or len(value) not in {8,12,13,14}:
        return False
    total = sum(int(digit) * (3 if index % 2 == 0 else 1)
                for index, digit in enumerate(reversed(value[:-1])))
    return (total + int(value[-1])) % 10 == 0


def _axis_value(axis, raw):
    if axis in BOOL_AXES:
        return _bool(raw)
    if axis=='grit':
        match=re.fullmatch(r'\s*[KP]?\s*(\d+)\s*',_text(raw),re.I)
        return int(match[1]) if match else None
    if axis=='drive_profile':
        match=re.fullmatch(r'\s*(PH|PZ|TX)\s*[- ]?\s*(\d+)\s*',_text(raw),re.I)
        return match[1].upper()+match[2] if match else None
    return _number(raw)


def _own_text(text):
    # "Bor for metall STA50105" is own identity; only explicit parent phrases
    # mark compatibility. A URL itself is never an independent model claim.
    text = re.sub(r'https?://\S+', ' ', _text(text))
    return re.split(r'\b(?:passer\s+til|compatible\s+with|for\s+h[øo]vel)\b', text, flags=re.I)[0]


def _codes(text):
    tokens = re.findall(r'(?<!\w)[A-Za-z0-9]+(?:[-/][A-Za-z0-9]+)*(?!\w)', _own_text(text))
    return {t.upper() for t in tokens if len(t) >= 4
            and ((re.search('[A-Za-z]', t) and re.search(r'\d', t))
                 or re.fullmatch(r'\d-\d{2}-\d{3}', t))
            and not re.fullmatch(r'[KP]\d+',t,re.I)
            and not re.fullmatch(r'(?:PH|PZ|TX)-?\d+',t,re.I)
            and not re.fullmatch(r'(?:PH|PZ|TX)-?\d+(?:/(?:(?:PH|PZ|TX)-?)?\d+)+',t,re.I)
            and not re.fullmatch(r'\d+(?:-[A-Z]+)?-?(?:PAKNING|PACK|STK|PCS)',t,re.I)
            and not re.fullmatch(r'(?:\d+[x×])?\d+-?(?:PAKNING|PACK|PK|STK|PCS)',t,re.I)
            and not (not re.fullmatch(r'\d-\d{2}-\d{3}',t) and re.fullmatch(NUMBER+r'(?:[x×-]'+NUMBER+r')*(?:MM|CM|M|AH|MAH|WH|V|W|KW|PCS|STK|PK|ML|KG|L|LM|N|NM|HZ|RPM|BAR|DB|GB|TB|MB|PSI|K)?', t,re.I))
            and not re.fullmatch(NUMBER+r'(?:L|M)/(?:T|H|MIN|S)',t,re.I)
            and not re.fullmatch(r'X?'+NUMBER+r'(?:MM|CM|M|METER|METRES|METERS|METROS)',t,re.I)}


def _attributes(value):
    if not _text(value):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return [{'_invalid': True}]
    if not isinstance(value, list):
        return [{'_invalid': True}]
    return [v for v in value if isinstance(v, dict)]


def _claims(row, prefix, bit_context):
    claims = []
    def add(axis, value, source, raw, role='sale_item'):
        if value is None or value == '':
            return
        if axis in AXES and axis not in BOOL_AXES and isinstance(value,(int,float)) and value<=0:
            axis,value='unparsed','non_positive_'+axis
        if axis=='model' and re.fullmatch(r'[A-Z]+\d+(?:MM|CM)',str(value),re.I):
            # A source may have flattened "STA36070 115MM" into one token.
            # Retain that token as uncertain; never invent the missing boundary.
            axis,value='unparsed','possible_merged_model_and_dimension'
        claim = {'axis':axis,'role':role,'value':value,'source':source,'raw_value':_text(raw)}
        if claim not in claims:
            claims.append(claim)
    title_key = 'offer_title' if prefix == 'offer_' else 'title'
    model_key = prefix + 'model' if prefix else 'model'
    for axis in AXES:
        field = prefix + axis if prefix else axis
        raw = row.get(field)
        value = _axis_value(axis,raw)
        add('unparsed' if _text(raw) and value is None else axis,
            'invalid_' + axis if _text(raw) and value is None else value, field, raw)
    model = _own_text(row.get(model_key))
    if model:
        gtins={_text(row.get('gtin')),_text(row.get('offer_gtin'))}-{''}
        add('unclassified_identifier' if model in gtins else 'model',model.upper(),model_key,model)
    texts = [(title_key, _own_text(row.get(title_key)))]
    attribute_key = prefix + 'attributes' if prefix else 'product_attributes'
    # Public typed columns use product_ prefix, while title/model are legacy.
    if not prefix:
        for axis in AXES:
            raw = row.get('product_'+axis)
            value = _axis_value(axis,raw)
            add('unparsed' if _text(raw) and value is None else axis,
                'invalid_' + axis if _text(raw) and value is None else value,'product_'+axis,raw)
    names = {'diameter':'diameter_mm','bordiameter':'diameter_mm','lengde':'length_mm',
             'length':'length_mm','bredde':'width_mm','width':'width_mm',
             'pakningsantall':'pack_count','antallipakken':'pack_count','packcount':'pack_count',
             'batterikapasitet':'battery_capacity_ah','batterycapacity':'battery_capacity_ah',
             'antallbatterier':'battery_count','battericount':'battery_count',
             'spenning':'voltage_v','voltage':'voltage_v','batteriinkludert':'battery_included',
             'laderinkludert':'charger_included','chargerincluded':'charger_included',
             'korning':'grit','grit':'grit','kornstorrelse':'grit','slipekorn':'grit',
             'boringsdiameter':'inner_diameter_mm','hulldiameter':'inner_diameter_mm',
             'innerdiameter':'inner_diameter_mm','bladdiameter':'outer_diameter_mm',
             'ytterdiameter':'outer_diameter_mm','skivediameter':'outer_diameter_mm',
             'driveprofile':'drive_profile','spisstype':'drive_profile'}
    blade_context=bool(re.search(r'sagblad|sirkelsagblad|kappeskive|saw\s*blade|cutting\s*disc',_text(row.get('title'))+' '+_text(row.get('category')),re.I))
    for attr in _attributes(row.get(attribute_key)):
        if attr.get('_invalid'):
            add('unparsed','invalid_attributes',attribute_key,'Invalid attribute JSON')
            continue
        name = _key(attr.get('name') or attr.get('title'))
        raw = attr.get('raw_value',attr.get('value'))
        source = attribute_key + '.' + _text(attr.get('name') or attr.get('title'))
        if name in {'produktnavn','productname','title','modell','model','mpn','sku'}:
            texts.append((source,_own_text(raw)))
            if name in {'modell','model','mpn','sku'} and _text(raw):
                gtins={_text(row.get('gtin')),_text(row.get('offer_gtin'))}-{''}
                add('unclassified_identifier' if _text(raw) in gtins else 'model',_text(raw).upper(),source,raw)
        axis = names.get(name)
        if axis:
            if axis in BOOL_AXES or axis in {'grit','drive_profile'}:
                value = _axis_value(axis,raw)
            else:
                m = re.fullmatch(r'\s*('+NUMBER+r')\s*(mm|cm|m|ah|v)?\s*',_text(raw),re.I)
                value = _number(m[1]) if m else None
                if value is not None and axis.endswith('_mm') and (m[2] or '').lower()=='cm':
                    value *= 10
                if value is not None and axis.endswith('_mm') and (m[2] or '').lower()=='m':
                    value *= 1000
            # Generic catalogue "Lengde" can mean total, working, blade or
            # packaging length. Do not turn that weak role into a contradiction.
            add('unknown_dimension_mm' if axis=='length_mm' or axis=='diameter_mm' and blade_context else axis,value,source,raw,
                role='unspecified_length' if axis=='length_mm' else 'sale_item')
    for source,text in texts:
        for code in sorted(_codes(text)):
            add('model',code,source,code)
        for match in re.finditer(r'(?<!\w)(PH|PZ|TX)\s*[- ]?\s*(\d+)\s*/\s*(\d+)(?!\w)',text,re.I):
            add('drive_profile',match[1].upper()+match[2],source,match[0])
            add('drive_profile',match[1].upper()+match[3],source,match[0])
        for match in re.finditer(r'(?<!\w)(PH|PZ|TX)\s*[- ]?\s*(\d+)(?!\w)',text,re.I):
            add('drive_profile',match[1].upper()+match[2],source,match[0])
        abrasive = bool(re.search(r'\b(?:slipepapir|slipeark|sandpaper|abrasive|slip\w*|korning|grit)\b',
                                  text+' '+_text(row.get('title'))+' '+_text(row.get('category')),re.I))
        for match in re.finditer(r'(?<!\w)(?:[KP]\s*(\d+)|(\d+)\s*K)(?!\w)',text,re.I):
            if abrasive:
                add('grit',int(match[1] or match[2]),source,match[0])
        for match in re.finditer(r'\b(?:korning|grit|slipekorn)\s*[:=]?\s*[KP]?\s*(\d+)\b',text,re.I):
            add('grit',int(match[1]),source,match[0])
        measured = []
        geometry=re.search(r'(?<![\w.,])('+NUMBER+r'(?:\s*[x×]\s*'+NUMBER+r')+)\s*(mm|cm|m)\b',text,re.I)
        if geometry and not bit_context:
            factor={'mm':1,'cm':10,'m':1000}[geometry[2].lower()]
            numbers=re.findall(NUMBER,geometry[1])
            add('unknown_dimension_mm','x'.join(format(_number(n)*factor,'g') for n in numbers),source,geometry[0],role='unordered_geometry')
        for match in re.finditer(r'(?:(?<![\w.,])|(?<=[x×]))('+NUMBER+r')\s*(mm|cm|m|meter|metres|meters|metros)\b',text,re.I):
            ambiguous=re.search(r'(?<![\w.,])\d+\s+$',text[:match.start()])
            if ambiguous:
                add('unparsed','ambiguous_decimal_dimension',source,text[ambiguous.start():match.end()])
                continue
            value = _number(match[1]) * ({'mm':1,'cm':10}.get(match[2].lower(),1000))
            before = text[max(0,match.start()-25):match.start()]
            axis = None
            for pattern,candidate in ((r'(?:boringsdiameter|hulldiameter|innerdiameter|bore\s+diameter)\s*[:=]?\s*$','inner_diameter_mm'),
                                      (r'(?:bladdiameter|skivediameter|ytterdiameter|outer\s+diameter)\s*[:=]?\s*$','outer_diameter_mm'),
                                      (r'(?:diameter|diam\.?|[øØ⌀])\s*[:=]?\s*$','unknown_dimension_mm' if blade_context else 'diameter_mm'),
                                      (r'(?:lengde|length)\s*[:=]?\s*$','length_mm'),
                                      (r'(?:bredde|width)\s*[:=]?\s*$','width_mm')):
                if re.search(pattern,before,re.I):
                    axis=candidate;break
            measured.append((match,value,axis))
        tape=bool(re.search(r'm[åa]leb[åa]nd|tape\s*measure',text+' '+_text(row.get('category')),re.I))
        if tape and len(measured)==2:
            # A blade-width in millimetres beside a reel length in metres is
            # role evidence; arbitrary rectangular dimensions are not.
            units=[m[0][2].lower() for m in measured]
            if units.count('mm')==1 and any(u in {'m','meter','metres','meters','metros'} for u in units):
                measured=[(match,value,axis or ('width_mm' if match[2].lower()=='mm' else 'length_mm'))
                          for match,value,axis in measured]
        ordered = re.search(r'(?<![\w.,])('+NUMBER+r')\s*[x×]\s*('+NUMBER+r')\s*(mm|cm)\b',text,re.I) if bit_context else None
        if ordered:
            factor=10 if ordered[3].lower()=='cm' else 1
            add('diameter_mm',_number(ordered[1])*factor,source,ordered[0])
            add('length_mm',_number(ordered[2])*factor,source,ordered[0])
        for match,value,axis in measured:
            if ordered and ordered.start() <= match.start() < ordered.end():
                continue
            local_bit = bool(re.search(r'\b(?:metallbor|trebor|murbor|betongbor|spiralbor|hss[- ]?[rg]?|drill\s+bits?|bor\s+for\s+(?:metall|tre)|sds[- +]*\w*\s*bor)\b',text,re.I))
            if not axis and bit_context and local_bit and len(measured)==1 and not re.search(r'\d\s*[-–/]\s*\d',text):
                axis='diameter_mm'
            if not axis and len(measured)==1 and re.search(r'm[åa]leb[åa]nd|tape\s*measure|vater|linjal|ruler',text+' '+_text(row.get('category')),re.I):
                axis='length_mm'
            add(axis or 'unknown_dimension_mm',value,source,match[0])
        for unit,axis in [('ah','battery_capacity_ah'),('v','voltage_v')]:
            for match in re.finditer(r'(?<![\w.,])('+NUMBER+r')\s*'+unit+r'\b',text,re.I):
                if unit=='ah' and re.search(r'\d\s+$',text[:match.start()]):
                    add('unparsed','ambiguous_decimal_ah',source,match[0]);continue
                add(axis,_number(match[1]),source,match[0])
        composite = re.search(r'\b(\d+)\s*[x×]\s*(\d+)\s*[- ]?(?:pakning|pack|pk)\b',text,re.I)
        if composite:
            add('pack_count',int(composite[1])*int(composite[2]),source,composite[0])
        else:
            for match in re.finditer(r'\b(\d+)\s*[- ]?(?:pakning|pack|pk|stk\.?|pcs\.?|pieces)\b',text,re.I):
                add('pack_count',int(match[1]),source,match[0])
        for match in re.finditer(r'\b(\d+)\s*[x×]\s*'+NUMBER+r'\s*ah\b',text,re.I):
            add('battery_count',int(match[1]),source,match[0])
        for match in re.finditer(r'\b(\d+)\s*(?:batterier|batteries)\b',text,re.I):
            add('battery_count',int(match[1]),source,match[0])
        negative = re.search(r'\b(?:uten|uden|without|ohne|u/)\s*(?:batteri|battery|akku)|\b(?:solo|naken|bare\s+tool|tool\s+only|body\s+only)\b',text,re.I)
        positive = re.search(r'\b(?:med|with|inkl(?:udert)?\.?|included)\s+(?:\d+\s*[x×]?\s*)?(?:'+NUMBER+r'\s*ah\s*)?(?:batteri|batteries|battery|akku)',text,re.I)
        if negative:
            add('battery_included',False,source,negative[0])
        if positive:
            add('battery_included',True,source,positive[0])
        for marker,value in ((r'(?:uten|uden|without|ohne)',False),(r'(?:med|with|inkl(?:udert)?\.?|included)',True)):
            charger=re.search(r'\b'+marker+r'\s+(?:(?:batteri\w*|batteries|battery)\s*(?:og|and|&)\s*)?(?:lader|charger)\b',text,re.I)
            if charger:
                add('charger_included',value,source,charger[0])
        charger_suffix=re.search(r'\b(?:lader|charger)\s+(?:inkludert|included)\b',text,re.I)
        if charger_suffix:
            add('charger_included',True,source,charger_suffix[0])
    return claims


def assess_variant(row):
    """Assess a mapping or namedtuple using only supplied saved evidence."""
    row = dict(row) if isinstance(row,Mapping) else row._asdict()
    context = _text(row.get('title'))+' '+_text(row.get('category'))
    bit = bool(re.search(r'\b(?:metallbor|trebor|murbor|betongbor|spiralbor|hss[- ]?[rg]?|drill\s+bits?|bor\s+for\s+(?:metall|tre)|sds[- +]*\w*\s*bor)\b',context,re.I))
    if re.search(r'sagblad|kappeskive|saw\s*blade|cutting\s*disc',context,re.I):
        bit=False
    product, offer = _claims(row,'',bit), _claims(row,'offer_',bit)
    evidence = {'product_claims':product,'offer_claims':offer}
    conflicts, missing = [], []
    def values(claims,axis):
        return {c['value'] for c in claims if c['axis']==axis}
    gtin, offer_gtin = _text(row.get('gtin')),_text(row.get('offer_gtin'))
    exact_gtin = bool(_valid_gtin(gtin) and _valid_gtin(offer_gtin) and gtin==offer_gtin)
    if offer_gtin and (not _valid_gtin(offer_gtin) or gtin and not _valid_gtin(gtin)):
        missing.append('GTIN-beviset har ugyldig format eller kontrollsiffer')
    if _valid_gtin(gtin) and _valid_gtin(offer_gtin) and gtin!=offer_gtin:
        conflicts.append('Tilbudets GTIN avviker fra produktet')
    pc,oc = values(product,'model'),values(offer,'model')
    exact_model=bool(pc & oc)
    if pc and oc and not exact_model:
        # Qualifying suffix omissions are unknown; adjacent model digits are
        # definite contradictions. No suffix is universally discarded.
        def suffix_missing(a,b):
            short,long=(a,b) if len(a)<len(b) else (b,a)
            return bool(long.startswith(short) and short[-1:].isdigit()
                        and re.fullmatch(r'[A-Z]+(?:-[A-Z]+)*',long[len(short):]))
        related=any(a.startswith(b+'-') or b.startswith(a+'-') or suffix_missing(a,b) for a in pc for b in oc)
        punctuation_alias=any(re.sub(r'[^A-Z0-9]','',a)==re.sub(r'[^A-Z0-9]','',b) for a in pc for b in oc)
        numeric_packaging=any(re.fullmatch(r'\d-\d{2}-\d{3}',a) and re.fullmatch(r'\d-\d{2}-\d{3}',b) and a[2:]==b[2:] for a in pc for b in oc)
        same_namespace=False
        for a in pc:
            for b in oc:
                ap,bp=re.match(r'[A-Z]{2,}',a),re.match(r'[A-Z]{2,}',b)
                if ap and bp and ap[0]==bp[0]:
                    same_namespace=True
                if re.fullmatch(r'\d-\d{2}-\d{3}',a) and re.fullmatch(r'\d-\d{2}-\d{3}',b) and a[:5]==b[:5]:
                    same_namespace=True
        if punctuation_alias and exact_gtin:
            exact_model=True
        elif related or punctuation_alias or numeric_packaging or not same_namespace:
            missing.append('Modellens suffiks eller modellnavnerom er uavklart')
        else:
            conflicts.append('Tilbudets modellkode avviker fra produktet')
    elif exact_model and pc != oc:
        missing.append('Flere egne modellkoder gir uavklart produktidentitet')
    elif pc and not oc and not exact_gtin:
        missing.append('Tilbudet mangler egen modellidentitet')
    for axis in AXES:
        left,right=values(product,axis),values(offer,axis)
        if left and right and left != right:
            if axis=='voltage_v' and re.search(r'\d+\s*v\s*max|max\s*\d+\s*v',context+' '+_text(row.get('offer_title')),re.I):
                missing.append('Nominell og maksimal spenning krever dokumentert referanse')
            else:
                conflicts.append('Motstridende '+LABELS[axis])
        elif left and not right:
            can_bridge=exact_gtin or (exact_model and axis in {'diameter_mm','inner_diameter_mm','outer_diameter_mm','length_mm','width_mm','voltage_v'})
            if not can_bridge:
                missing.append('Tilbudet mangler dokumentert '+LABELS[axis])
    if bit and not values(product,'diameter_mm') and not (exact_gtin or exact_model):
        missing.append('Produktets bordiameter er uavklart')
    battery_machine = bool(re.search(r'\b(?:drill|bormaskin|skrutrekker|vinkelsliper|bajonettsag|sirkelsag)\b',context,re.I)
                           and re.search(r'\b(?:batteri\w*|v20|\d+\s*v|\d+(?:[.,]\d+)?\s*ah)\b',context,re.I))
    battery_item = bool(re.search(r'\bbatteri\b',context,re.I) and not battery_machine)
    if not exact_gtin:
        if battery_machine:
            for claims, label in ((product,'Produktet'),(offer,'Tilbudet')):
                if not values(claims,'battery_included'):
                    missing.append(label+' mangler dokumentert batteriinnhold')
        if battery_item:
            for claims,label in ((product,'Produktet'),(offer,'Tilbudet')):
                for axis in ('battery_capacity_ah','voltage_v','battery_count'):
                    if not values(claims,axis):
                        missing.append(label+' mangler dokumentert '+LABELS[axis])
    unknown=values(offer,'unknown_dimension_mm')
    if unknown and any(values(product,a) for a in ('diameter_mm','inner_diameter_mm','outer_diameter_mm','length_mm','width_mm')):
        missing.append('Tilbudets mål har uavklart dimensjonsakse')
    if unknown and values(product,'unknown_dimension_mm') and unknown != values(product,'unknown_dimension_mm'):
        missing.append('Ulike mål har uavklart dimensjonsrolle')
    if values(product,'unparsed') or values(offer,'unparsed'):
        missing.append('Variantopplysninger kunne ikke tolkes entydig')
    if (values(product,'unclassified_identifier') or values(offer,'unclassified_identifier')) and not (exact_model or exact_gtin):
        missing.append('GTIN i modellfeltet dokumenterer ikke egen modellidentitet')
    relevant = bool(pc or oc or gtin and offer_gtin or bit or battery_machine or battery_item or product or offer)
    if conflicts:
        status='conflict';reasons=conflicts+missing
    elif missing:
        status='unverified';reasons=missing
    elif not relevant:
        status='not_applicable';reasons=[]
    elif exact_gtin or exact_model:
        status='compatible';reasons=[]
    else:
        status='unverified';reasons=['Egen produkt-/variantidentitet er ikke dokumentert']
    evidence.update(exact_gtin=exact_gtin,exact_model=exact_model,diameter_context=bit)
    return {'status':status,'reasons':list(dict.fromkeys(reasons)),'evidence':evidence}
