"""Validate independently captured, hash-bound offer evidence without fetching data.

Version 1 manifest: {version: 1, offers: [{supplier, product_id, offer_id,
snapshot_at, source_api: {path, sha256}, source_public: {path, sha256},
merchant: {path, sha256}}]}. Evidence paths are relative to the manifest.
Each evidence JSON binds kind, product_id, offer_id, retailer, observed_at,
retrieved_at, url, price, currency, gtin/model, variant_status, vat_basis,
shipping_basis and (separately) availability. Hashes bind saved evidence, never
establish its truth. This module checks consistency, not live page authenticity.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


def _time(value):
    stamp=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Evidence time needs an explicit timezone')
    return stamp.astimezone(timezone.utc)


def _domain(value):
    return (urlsplit(str(value) if '://' in str(value) else '//'+str(value)).hostname or '').lower().removeprefix('www.')


def _money(value):
    try:
        result=Decimal(str(value))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def _stock(value):
    text=str(value or '').rstrip('/').rsplit('/',1)[-1].casefold().replace('_','')
    return {'instock':'in_stock','outofstock':'out_of_stock','backorder':'backorder',
            'preorder':'preorder'}.get(text,str(value or ''))


class _VisiblePrice(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.text=[]; self.headers=[]; self.blocks=[]; self.header=None; self.block=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        hidden=(tag in ('script','style','noscript') or 'hidden' in attrs or attrs.get('aria-hidden','').lower()=='true'
                or bool(re.search(r'display\s*:\s*none|visibility\s*:\s*hidden',attrs.get('style',''),re.I)))
        if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}: self.stack.append((tag,hidden))
        if tag=='h1': self.header=[]
        if tag=='section' and re.search(r'(?:^|\s)product(?:-page)?-price(?:\s|$)',attrs.get('class','')): self.block=[]
    def handle_endtag(self,tag):
        if tag=='h1' and self.header is not None: self.headers.append(' '.join(self.header)); self.header=None
        if tag=='section' and self.block is not None: self.blocks.append(re.sub(r'\s+',' ',' '.join(self.block)).strip()); self.block=None
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag: del self.stack[i:]; break
    def handle_data(self,value):
        if not any(hidden for _,hidden in self.stack):
            self.text.append(value)
            if self.header is not None: self.header.append(value)
            if self.block is not None: self.block.append(value)


def _gtin(value):
    value=str(value or '')
    return (value.isdigit() and len(value) in (8,12,13,14)
            and sum(int(c)*(3 if i%2==0 else 1) for i,c in enumerate(value[-2::-1]))%10 == (-int(value[-1]))%10)


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.ldparts=[]; self.current=None; self.is_ld=False
    def handle_starttag(self,tag,attrs):
        if tag=='script':
            self.current=[]; self.is_ld=dict(attrs).get('type','').lower()=='application/ld+json'
    def handle_data(self,data):
        if self.current is not None: self.current.append(data)
    def handle_endtag(self,tag):
        if tag=='script' and self.current is not None:
            try:
                parsed=json.loads(''.join(self.current)); self.parts.append(parsed)
                if self.is_ld: self.ldparts.append(parsed)
            except ValueError: pass
            self.current=None


def _pointer(document,path):
    if path=='': return document
    if not str(path).startswith('/'): raise ValueError('JSON pointer must start with /')
    for part in path[1:].split('/'):
        token=part.replace('~1','/').replace('~0','~')
        document=document[int(token)] if isinstance(document,list) else document[token]
    return document


def _rsc_product(raw,product_id):
    """Read JSON values only, without evaluating JavaScript/RSC expressions."""
    decoder=json.JSONDecoder(); chunks=[]
    for match in re.finditer(r'self\.__next_f\.push\(\[\s*1\s*,\s*("(?:\\.|[^"\\])*")\s*\]\)',raw,re.S):
        decoded=json.loads(match[1])
        if isinstance(decoded,str): chunks.append(decoded)
    queue=[''.join(chunks)]; seen=set(); candidates={}
    while queue:
        value=queue.pop()
        if isinstance(value,dict):
            if str(value.get('id',''))==str(product_id) and isinstance(value.get('offers'),list):
                candidates[json.dumps(value,sort_keys=True)]=value
            queue.extend(value.values())
        elif isinstance(value,list): queue.extend(value)
        elif isinstance(value,str) and value not in seen:
            seen.add(value)
            for match in re.finditer(r'[\[{]',value):
                try: node,_=decoder.raw_decode(value[match.start():])
                except ValueError: continue
                if isinstance(node,(dict,list)): queue.append(node)
    if len(candidates)!=1: raise ValueError('RSC product identity is missing or ambiguous')
    return next(iter(candidates.values()))


def _embedded_jsonld(raw):
    """JSON-LD may be carried by Next RSC dangerouslySetInnerHTML.__html."""
    decoder=json.JSONDecoder(); queue=[]; found={}; chunks=[]
    for match in re.finditer(r'self\.__next_f\.push\(\[\s*1\s*,\s*("(?:\\.|[^"\\])*")\s*\]\)',raw,re.S):
        text=json.loads(match[1])
        if isinstance(text,str): chunks.append(text)
    text=''.join(chunks)
    for start in re.finditer(r'[\[{]',text):
        try: node,_=decoder.raw_decode(text[start.start():])
        except ValueError: continue
        queue.append(node)
    while queue:
        item=queue.pop(0)
        if isinstance(item,dict):
            if item.get('@type')=='Product' or '@graph' in item:
                found[json.dumps(item,sort_keys=True)]=item
            value=item.get('__html')
            if isinstance(value,str):
                try:
                    doc=json.loads(value)
                    if isinstance(doc,dict) and ('@type' in doc or '@graph' in doc):
                        found[json.dumps(doc,sort_keys=True)]=doc
                except ValueError: pass
            queue.extend(item.values())
        elif isinstance(item,list): queue.extend(item)
    return list(found.values())


def _binding(raw,spec,defaults):
    if isinstance(spec,str): spec={**defaults,'pointer':spec}
    fmt=spec.get('format',defaults.get('format'))
    if fmt=='visible_vat_policy':
        page=_VisiblePrice(); page.feed(raw); visible=re.sub(r'\s+',' ',' '.join(page.text))
        literal=str(spec.get('text',''))
        pattern=r'\b(?:alle\s+priser|all\s+prices)\b.{0,35}\b(?:inkl(?:usive|udert)?\.?\s*(?:mva|moms)|includ(?:e|ing)\s+(?:vat|tax))\b'
        if not literal or literal not in visible or not re.fullmatch(pattern,literal,re.I):
            raise ValueError('Global VAT policy is not explicitly visible')
        return 'included'
    if fmt=='visible_product_vat':
        page=_VisiblePrice(); page.feed(raw)
        product=_binding(raw,spec['product_binding'],{})
        price=_binding(raw,spec['price_binding'],{})
        if not isinstance(product,dict) or len(page.headers)!=1 or len(page.blocks)!=1 or page.blocks[0]!=spec.get('text'):
            raise ValueError('VAT text is not in a single primary product price region')
        header=page.headers[0]; block=page.blocks[0]
        in_header=lambda value: value and re.search(r'(?<![a-z0-9])'+re.escape(str(value))+r'(?![a-z0-9])',header,re.I)
        if not in_header(product.get('sku')) or not any(in_header(product.get(k)) for k in ('model','mpn')):
            raise ValueError('VAT price region lacks own model and SKU in the sole H1')
        prices=re.findall(r'(?<![\d.,])([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:kr\b|NOK\b)',block,re.I)
        included=re.search(r'\binkl(?:usive|udert)?\.?\s*(?:mva|moms)\b',block,re.I)
        excluded=re.search(r'\bekskl(?:usive|udert)?\.?\s*(?:mva|moms)\b',block,re.I)
        if len(prices)!=1 or _money(prices[0].replace(',','.'))!=_money(price) or not included or excluded:
            raise ValueError('VAT text is not bound to the independently observed exact item price')
        return 'included'
    if fmt=='next_rsc_product':
        product=_rsc_product(raw,spec['product_id'])
        field=spec.get('field')
        if field in ('product_id','ean','code','gtin','model'):
            return product.get({'product_id':'id','gtin':'ean','model':'code'}.get(field,field))
        offers=[o for o in product['offers'] if str(o.get('id',''))==str(spec['offer_id'])]
        if len(offers)!=1: raise ValueError('RSC offer identity is missing or ambiguous')
        return offers[0].get('id' if field=='offer_id' else field)
    if fmt=='json': document=json.loads(raw)
    elif fmt in ('html_script_json','jsonld'):
        scripts=_Scripts(); scripts.feed(raw)
        if fmt=='jsonld':
            existing={json.dumps(doc,sort_keys=True) for doc in scripts.ldparts}
            documents=scripts.ldparts+[doc for doc in _embedded_jsonld(raw) if json.dumps(doc,sort_keys=True) not in existing]
        else: documents=scripts.parts
        document=documents[int(spec.get('script_index',defaults.get('script_index',0)))]
    else: raise ValueError('Unsupported raw claim binding format')
    return _pointer(document,spec['pointer'])


class PriceEvidence:
    def __init__(self, manifest=None, *, now=None, max_age_hours=48, max_source_cache_age_hours=8):
        self.now=now or datetime.now(timezone.utc)
        self.max_age_seconds=max_age_hours*3600
        self.max_source_cache_age_seconds=max_source_cache_age_hours*3600
        self.records={}
        self.manifest_sha256=None
        self.root=None
        if manifest is not None:
            path=Path(manifest).resolve()
            data=path.read_bytes()
            self.manifest_sha256=hashlib.sha256(data).hexdigest()
            raw=json.loads(data)
            if not isinstance(raw,dict) or raw.get('version')!=1 or not isinstance(raw.get('offers'),list):
                raise ValueError('Unsupported price-evidence manifest schema')
            self.root=path.parent
            for record in raw['offers']:
                key=(_domain(record['supplier']),str(record['product_id']),str(record['offer_id']),_time(record['snapshot_at']))
                if key in self.records:
                    raise ValueError('Duplicate price-evidence identity/snapshot')
                self.records[key]=record

    def _read(self, spec, kind):
        if not isinstance(spec,dict) or not spec.get('path') or not spec.get('sha256'):
            return None,'missing','Missing '+kind+' evidence'
        try:
            file=(self.root/spec['path']).resolve()
            if not file.is_relative_to(self.root):
                return None,'invalid','Evidence path escapes manifest directory'
            content=file.read_bytes()
            if hashlib.sha256(content).hexdigest()!=str(spec['sha256']).lower():
                return None,'invalid','Evidence SHA-256 mismatch: '+kind
            doc=json.loads(content)
            if not isinstance(doc,dict) or doc.get('kind')!=kind:
                return None,'invalid','Evidence document kind mismatch: '+kind
            return doc,None,None
        except (OSError,ValueError,TypeError):
            return None,'invalid','Unreadable evidence: '+kind

    def _raw_check(self,doc,kind):
        """Bind derived claims to original saved bytes and original retrieval time."""
        try:
            blobs={}
            for name in ('raw_record','raw_response'):
                spec=doc.get(name)
                if not isinstance(spec,dict) or not spec.get('path') or not spec.get('sha256'):
                    return 'missing','Missing original raw evidence: '+kind
                path=(self.root/spec['path']).resolve()
                if not path.is_relative_to(self.root): return 'invalid','Raw evidence path escape: '+kind
                data=path.read_bytes()
                if hashlib.sha256(data).hexdigest()!=str(spec['sha256']).lower():
                    return 'invalid','Original raw evidence SHA-256 mismatch: '+kind
                blobs[name]=data
            record=json.loads(blobs['raw_record'])
            if record.get('status')!=200 or record.get('error'):
                return 'invalid','Original HTTP observation was not successful: '+kind
            if record.get('response_sha256')!=hashlib.sha256(blobs['raw_response']).hexdigest():
                return 'invalid','Response bytes do not match original HTTP record: '+kind
            if _time(record['fetched_at'])!=_time(doc['retrieved_at']):
                return 'expired','Original retrieval time differs from derived evidence: '+kind
            age=(record.get('response_headers') or {}).get('age')
            date=(record.get('response_headers') or {}).get('date')
            if date:
                try:
                    if parsedate_to_datetime(date).tzinfo is None: raise ValueError('Naive HTTP Date')
                except (ValueError,TypeError): return 'invalid','Invalid original HTTP Date header: '+kind
            if age is not None:
                try:
                    limit=self.max_source_cache_age_seconds if kind!='merchant' else 300
                    max_age=re.search(r'\b(?:s-maxage|max-age)\s*=\s*(\d+)',str((record.get('response_headers') or {}).get('cache-control','')),re.I)
                    if max_age: limit=min(limit,int(max_age[1]))
                    if float(age)<0 or float(age)>limit:
                        return 'expired','Original HTTP response cache age exceeds declared/configured bound: '+kind
                except (TypeError,ValueError): return 'invalid','Invalid original response cache age: '+kind
            if _domain(record.get('final_url') or record.get('url',''))!=_domain(doc.get('url','')):
                return 'conflict','Original HTTP source differs from derived evidence: '+kind
            bindings=doc.get('bindings')
            if not isinstance(bindings,dict): return 'missing','Missing raw claim bindings: '+kind
            raw=blobs['raw_response'].decode('utf-8-sig')
            pointers=bindings.get('pointers') or {}
            required=['price','currency','vat_basis','shipping_basis']
            if kind=='source_api' and doc.get('currency_basis')=='source_public_match': required.remove('currency')
            if kind!='merchant' and doc.get('vat_basis')=='unknown' and doc.get('price_context_basis')=='matched_merchant_offer': required.remove('vat_basis')
            structural_shipping=bindings.get('shipping_basis_structural')=='item_price_field'
            if structural_shipping: required.remove('shipping_basis')
            if doc.get('availability'): required.append('availability')
            if kind!='merchant': required+=['product_id','offer_id']
            if kind=='merchant': required.append('gtin' if _gtin(doc.get('gtin')) else 'model')
            else:
                required += [field for field in ('gtin','model') if doc.get(field)]
            for field in required:
                if field not in pointers: return 'missing','Missing raw '+field+' binding: '+kind
                observed=_binding(raw,pointers[field],bindings)
                expected=doc.get(field)
                if field=='price': equal=_money(observed)==_money(expected) and _money(observed) is not None
                elif field=='availability': equal=_stock(observed)==_stock(expected)
                elif field=='vat_basis' and observed is True:
                    pointer=pointers[field] if isinstance(pointers[field],str) else pointers[field].get('pointer','')
                    equal=expected=='included' and pointer.rsplit('/',1)[-1] in {'valueAddedTaxIncluded','includesVat','vatIncluded'}
                else: equal=str(observed)==str(expected)
                if not equal: return 'conflict','Derived '+field+' differs from original response: '+kind
            if kind!='merchant':
                json_pointer=lambda x: x if isinstance(x,str) else x.get('pointer') if isinstance(x,dict) and x.get('format',bindings.get('format'))=='json' else None
                pp,ip=json_pointer(pointers.get('price')),json_pointer(pointers.get('offer_id'))
                offer_pointer=bindings.get('offer_pointer') or (pp.rsplit('/',1)[0] if pp else None)
                rsc_price=pointers.get('price') if isinstance(pointers.get('price'),dict) else {}
                rsc_id=pointers.get('offer_id') if isinstance(pointers.get('offer_id'),dict) else {}
                rsc_bound=(rsc_price.get('format')=='next_rsc_product' and rsc_id.get('format')=='next_rsc_product'
                           and str(rsc_price.get('product_id'))==str(doc['product_id'])==str(rsc_id.get('product_id'))
                           and str(rsc_price.get('offer_id'))==str(doc['offer_id'])==str(rsc_id.get('offer_id')))
                if not rsc_bound and (not offer_pointer or not pp or not ip or pp.rsplit('/',1)[0]!=offer_pointer or ip.rsplit('/',1)[0]!=offer_pointer):
                    return 'missing','Price and offer ID lack a shared raw offer object: '+kind
                if structural_shipping and not rsc_bound and pp.rsplit('/',1)[-1]!='price':
                    return 'missing','Item price basis is not an exact offer price field: '+kind
            elif structural_shipping:
                spec=pointers.get('price')
                spec={**bindings,'pointer':spec} if isinstance(spec,str) else spec
                pointer=spec.get('pointer','')
                parent_spec={**spec,'pointer':pointer.rsplit('/',1)[0]}
                parent=_binding(raw,parent_spec,bindings)
                if isinstance(parent,dict) and parent.get('@type')=='UnitPriceSpecification' and '/priceSpecification' in pointer:
                    ancestor_pointer=pointer.split('/priceSpecification',1)[0]
                    offer_parent=_binding(raw,{**spec,'pointer':ancestor_pointer},bindings)
                    specifications=offer_parent.get('priceSpecification') if isinstance(offer_parent,dict) else None
                    single_spec=(isinstance(specifications,dict) or isinstance(specifications,list) and len(specifications)==1)
                    qualifiers=('eligibleCustomerType','validForMemberTier','eligibleTransactionVolume','eligibleQuantity','referenceQuantity','billingIncrement')
                    if not isinstance(offer_parent,dict) or offer_parent.get('@type')!='Offer' or not single_spec or any(obj.get(key) is not None for obj in (offer_parent,parent) for key in qualifiers):
                        return 'missing','Unit price specification is not a single unconditional concrete Offer price: '+kind
                elif not isinstance(parent,dict) or parent.get('@type')!='Offer':
                    return 'missing','Merchant price is not a concrete JSON-LD Offer.price: '+kind
                if pointer.rsplit('/',1)[-1]!='price':
                    return 'missing','Merchant price is not a concrete JSON-LD Offer.price: '+kind
            return 'verified',''
        except (OSError,ValueError,TypeError,KeyError,IndexError):
            return 'invalid','Original raw evidence cannot be validated: '+kind

    def _check(self, doc, kind, row, snapshot):
        for field, expected in [('product_id',row.product_id),('offer_id',row.offer_id)]:
            if str(doc.get(field,''))!=str(expected):
                return 'conflict','Evidence '+field+' mismatch: '+kind
        if _domain(doc.get('retailer',''))!=row.shop:
            return 'conflict','Evidence retailer mismatch: '+kind
        domain=_domain(doc.get('url',''))
        if not str(doc.get('url','')).startswith(('https://','http://')) or (kind=='merchant' and domain!=row.shop) or (kind!='merchant' and domain not in {'prisradar.no','gql.prisradar.no'}):
            return 'invalid','Evidence URL is not bound to the expected source: '+kind
        try:
            observed,retrieved=_time(doc['observed_at']),_time(doc['retrieved_at'])
        except (KeyError,TypeError,ValueError):
            return 'invalid','Missing or invalid evidence observation/retrieval time: '+kind
        if abs((observed-snapshot).total_seconds())>300 or abs((retrieved-snapshot).total_seconds())>300:
            return 'expired','Evidence outside product snapshot 300-second window: '+kind
        if (self.now-observed).total_seconds()>self.max_age_seconds or observed>self.now or retrieved>self.now:
            return 'expired','Evidence observation is expired or in the future: '+kind
        if _money(doc.get('price')) is None or _money(doc.get('price'))<=0 or not str(doc.get('currency') or ''):
            return 'missing','Exact price or currency is not observed: '+kind
        if _money(doc.get('price'))!=_money(row.price) or str(doc.get('currency',''))!=row.currency:
            return 'conflict','Evidence price/currency mismatch: '+kind
        deferred_vat=kind!='merchant' and doc.get('vat_basis')=='unknown' and doc.get('price_context_basis')=='matched_merchant_offer'
        if (doc.get('vat_basis')!='included' and not deferred_vat) or doc.get('shipping_basis')!='excluded':
            return 'missing','Unknown or different VAT/shipping price basis: '+kind
        # No title-only or price-only bridge. Every explicit identity conflict wins.
        rg,rm=str(row.gtin or ''),str(row.model or '').strip().upper()
        dg,dm=str(doc.get('gtin') or ''),str(doc.get('model') or '').strip().upper()
        if rg and dg and rg!=dg or rm and dm and rm!=dm:
            return 'conflict','Evidence product identity conflict: '+kind
        if kind=='merchant' and not ((_gtin(rg) and rg==dg) or (rm and rm==dm)):
            return 'missing','Missing exact valid GTIN/model identity bridge: '+kind
        if kind=='merchant' and doc.get('variant_status')!='verified':
            return 'missing','Evidence sale variant is not independently verified: '+kind
        return self._raw_check(doc,kind)

    def assess(self,row):
        result={'source_consistency_status':'missing','merchant_price_status':'missing',
                'stock_validation_status':'source_only','price_evidence_reason':'No price-evidence manifest record',
                'source_cache_status':'unknown','source_vat_basis':'unknown','price_context_status':'missing'}
        key=(row.supplier_key,str(row.product_id),str(row.offer_id),row.audit_observed_utc.to_pydatetime())
        record=self.records.get(key)
        if record is None:
            return result
        documents={}; statuses={}; reasons=[]
        for kind in ('source_api','source_public','merchant'):
            doc,status,reason=self._read(record.get(kind),kind)
            if doc is not None:
                status,reason=self._check(doc,kind,row,key[-1])
                documents[kind]=doc
            statuses[kind]=status
            if reason: reasons.append(reason)
        source_status=next((statuses[k] for k in ('source_api','source_public') if statuses[k]!='verified'),'verified')
        merchant_status=statuses['merchant']
        if source_status=='verified' and merchant_status=='verified':
            stamps=[key[-1]]+[_time(d[f]) for d in documents.values() for f in ('observed_at','retrieved_at')]
            if (max(stamps)-min(stamps)).total_seconds()>300:
                source_status=merchant_status='expired'
                reasons.append('Combined product evidence observation window exceeds 300 seconds')
        cache_status='unknown'
        for kind in ('source_api','source_public'):
            doc=documents.get(kind)
            if not doc: continue
            try:
                metadata=json.loads((self.root/doc['raw_record']['path']).read_bytes())
                age=(metadata.get('response_headers') or {}).get('age')
                if age is not None and float(age)>0: cache_status='cached'
                elif cache_status!='cached': cache_status='fresh' if age is not None else 'unknown'
            except (OSError,KeyError,ValueError,TypeError): pass
        source_vat='included' if all(documents.get(k,{}).get('vat_basis')=='included' for k in ('source_api','source_public')) else 'unknown'
        context='verified' if source_status=='verified' and merchant_status=='verified' else 'missing'
        stock='source_only'
        if source_status=='verified' and merchant_status=='verified':
            stock_values=[_stock(d.get('availability')) for d in documents.values()]
            stock='verified' if all(v==_stock(row.availability) and v for v in stock_values) else 'conflict' if all(stock_values) else 'missing'
        return {'source_consistency_status':source_status,'merchant_price_status':merchant_status,
                'stock_validation_status':stock,'price_evidence_reason':'; '.join(reasons),
                'source_cache_status':cache_status,'source_vat_basis':source_vat,'price_context_status':context}
