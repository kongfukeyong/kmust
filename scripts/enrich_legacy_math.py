"""Recover legacy DOC formula objects from paired LibreOffice XHTML/HTML exports.

Never changes question IDs or the original searchable text. Precise source spans
and a per-field recovery report are retained. Run after converting the 12 sources.
"""
import argparse,base64,hashlib,json,re,xml.etree.ElementTree as E
from html.parser import HTMLParser
from pathlib import Path
from PIL import Image

MARK='\ufffc'
def norm(s):return re.sub(r'\s+|\xad','',s).replace('[pic]',MARK).replace('【pic】',MARK)
class Images(HTMLParser):
 def __init__(self):super().__init__();self.images=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='img' and not a.get('name','').startswith('DrawObject'):self.images.append(a)

def parse_source(folder,rid,media):
 root=E.parse(folder/'html'/(rid+'.html')).getroot();hp=Images();hp.feed((folder/'web'/(rid+'.html')).read_text())
 objects=[e for e in root.iter() if e.tag.split('}')[-1] in ('math','img')]
 paired=len(objects)==len(hp.images);segments=[];oi=0
 def walk(e):
  nonlocal oi
  tag=e.tag.split('}')[-1]
  if tag in ('head','style','script'):return
  if tag in ('math','img'):
   loc=rid+':object:'+str(oi+1);preview=hp.images[oi] if paired else None;oi+=1
   if tag=='math':
    # Drop annotations and exporter-only sizing; the client repeats an allowlist.
    def clean(x):
     n=E.Element(x.tag.split('}')[-1],{k:v for k,v in x.attrib.items() if k not in ('mathsize','mathcolor','mathbackground')});n.text=x.text
     for ch in x:
      if ch.tag.split('}')[-1] not in ('annotation','annotation-xml'):n.append(clean(ch))
     return n
    m=clean(e);m.set('xmlns','http://www.w3.org/1998/Math/MathML')
    segments.append({'type':'math','mathml':E.tostring(m,encoding='unicode'),'sourceLocator':loc});return
   raw=base64.b64decode(e.get('src','').split('base64,')[-1]);ext=None
   if raw.startswith(b'\x89PNG'):ext='.png'
   elif raw.startswith(b'GIF8'):ext='.gif'
   elif raw.startswith(b'\xff\xd8'):ext='.jpg'
   elif preview:
    f=folder/'web'/preview['src'];raw=f.read_bytes();ext=f.suffix.lower()
   if not ext:raise ValueError('No browser-readable preview '+loc)
   name=hashlib.sha256(raw).hexdigest()[:24]+ext;(media/name).write_bytes(raw)
   # Validate the exported image instead of publishing opaque OLE/WMF bytes.
   with Image.open(media/name) as im:im.verify()
   width=re.search(r'width:([\d.]+)cm',e.get('style',''))
   segments.append({'type':'image','src':'math-media/'+name,'alt':'原文公式或图形，点按可放大','width':round(float(width[1])*37.8) if width else 400,'sourceLocator':loc});return
  if e.text:segments.append({'type':'text','text':e.text})
  for ch in e:
   walk(ch)
   if ch.tail:segments.append({'type':'text','text':ch.tail})
  if tag in ('p','tr'):segments.append({'type':'text','text':'\n'})
 walk(root)
 # A character index lets us restore only objects belonging to a matched field.
 chars=[];refs=[]
 for i,s in enumerate(segments):
  value=s['text'] if s['type']=='text' else MARK
  for j,c in enumerate(value):
   if norm(c):chars.append(c);refs.append((i,j))
 return ''.join(chars),refs,segments

def slice_rich(a,b,refs,segs):
 first,fc=refs[a];last,lc=refs[b-1];out=[]
 for i in range(first,last+1):
  s=dict(segs[i])
  if s['type']=='text':
   s['text']=s['text'][fc if i==first else 0:lc+1 if i==last else None]
   # Font-specific Symbol glyphs used in two physics source paragraphs.
   symbols={'\uf070':'π','\uf06e':'ν','\uf06c':'λ','\uf068':'η','\uf061':'α','\uf062':'β','\uf077':'ω','\uf06d':'μ'}
   for old,new in symbols.items():s['text']=s['text'].replace(old,new)
  if s.get('text')=='' :continue
  if s['type']=='text' and out and out[-1]['type']=='text':out[-1]['text']+=s['text']
  else:out.append(s)
 return out

def unique(needle,hay,lo=0,hi=None):
 hi=len(hay) if hi is None else hi;a=hay.find(needle,lo,hi)
 return (a,a+len(needle)) if needle and a>=0 and hay.find(needle,a+1,hi)<0 else None

def locate_stem(q,hay):
 s=norm(q['stem']);s=re.split('-{10,}',s)[0]
 # Known encoding differences, verified against the exported source paragraph.
 if q['id']=='7d66d73794b4e88e':s=s.replace('cos2(((t-x/()','cos2\uf070(\uf06et-x/\uf06c)')
 if q['id']=='2cd600dd596df0bd':s=s.replace('e(1+1/1!','e»1+1/1!')
 span=unique(s,hay)
 if span:return span
 # These two previously merged fields include end-of-paper drawing objects.
 # Exact unique start/end anchors retain intervening formulas in source order.
 if q['id'] in ('9f21886ee634f761','71b6f5d85b136413'):
  start=unique(s[:30],hay);end=unique(s[-28:],hay)
  if start and end and start[0]<end[1]:return start[0],end[1]
 return None

def main():
 p=argparse.ArgumentParser();p.add_argument('--conversion',type=Path,required=True);p.add_argument('--public',type=Path,required=True);a=p.parse_args();media=a.public/'math-media';media.mkdir(exist_ok=True)
 data=a.public/'data';questions=json.loads((data/'questions.json').read_text());before=json.loads(json.dumps(questions));report={'sources':[],'fields':[],'unresolved':[]}
 for m in json.loads((a.conversion/'manifest.json').read_text()):
  hay,refs,segs=parse_source(a.conversion,m['id'],media);qs=[q for q in questions if q['sourcePath']==m['sourcePath']];spans={q['id']:locate_stem(q,hay) for q in qs}
  report['sources'].append({'id':m['id'],'path':m['sourcePath'],'math':sum(s['type']=='math' for s in segs),'images':sum(s['type']=='image' for s in segs)})
  for q in qs:
   span=spans[q['id']];fields=[('stem',q['stem'],q,'stemRich')]+[('option-'+o['label'],o['text'],o,'rich') for o in q.get('options',[])]+[('answer',q.get('answer') or '',q,'answerRich')]
   if not span:
    if any('[pic]' in t or '【pic】' in t for _,t,_,_ in fields):report['unresolved'].append({'id':q['id'],'reason':'stem-not-uniquely-aligned'})
    continue
   end=min([v[0] for v in spans.values() if v and v[0]>=span[1]]+[len(hay)])
   cursor=span[1]
   for name,value,obj,key in fields:
    if '[pic]' not in value and '【pic】' not in value:continue
    if name=='stem':found=span
    elif name.startswith('option-'):
     # Options are searched sequentially within the current question only.
     needle=norm(value);pos=hay.find(needle,cursor,end);found=(pos,pos+len(needle)) if pos>=0 else None
     if found:cursor=found[1]
    else:found=unique(re.split('-{10,}',norm(value))[0],hay,span[1],end)
    if not found:report['unresolved'].append({'id':q['id'],'field':name,'reason':'field-not-aligned'});continue
    rich=slice_rich(*found,refs,segs);obj[key]=rich;q['mathRecovery']={'method':'source-doc-objects','review':'automatic-source-alignment'}
    report['fields'].append({'id':q['id'],'field':name,'objects':sum(s['type']!='text' for s in rich),'span':list(found)})
 for x,y in zip(before,questions):
  assert (x['id'],x['stem'],x.get('answer'))==(y['id'],y['stem'],y.get('answer'))
  assert [(o['label'],o['text']) for o in x.get('options',[])]==[(o['label'],o['text']) for o in y.get('options',[])]
 report['summary']={'questionsEnhanced':len({x['id'] for x in report['fields']}),'fieldsEnhanced':len(report['fields']),'objectsRecovered':sum(x['objects'] for x in report['fields']),'unresolved':len(report['unresolved'])}
 (data/'questions.json').write_text(json.dumps(questions,ensure_ascii=False,separators=(',',':')))
 (data/'legacy-math-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report['summary']));print(json.dumps(report['unresolved']))
if __name__=='__main__':main()
