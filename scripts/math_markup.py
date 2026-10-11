#!/usr/bin/env python3
"""Loss-aware DOCX OMML -> safe Presentation MathML and ordered rich segments.

This module never changes question IDs, guesses image formulae, executes OLE,
fetches external relationships, or extracts files from a ZIP archive.
API: omml_to_mathml(xml, display=False, defaults=None); parse_docx(path).
CLI: python math_markup.py SOURCE.docx --output result.json
MathML is generated from an allowlist, never copied from source markup.
"""
import argparse, collections, hashlib, json, mimetypes, pathlib, posixpath, re, zipfile
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit

M='http://schemas.openxmlformats.org/officeDocument/2006/math'
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
V='urn:schemas-microsoft-com:vml'
O='urn:schemas-microsoft-com:office:office'
MM='http://www.w3.org/1998/Math/MathML'
MC='http://schemas.openxmlformats.org/markup-compatibility/2006'
NS={'m':M,'w':W,'r':R,'a':A}
ALLOWED_TAGS={'math','mrow','mi','mn','mo','mtext','mspace','mfrac','msqrt','mroot','msub','msup','msubsup','munder','mover','munderover','mtable','mtr','mtd','mmultiscripts','mprescripts','none','mphantom','mpadded','menclose','merror'}
ALLOWED_ATTRS={'xmlns','display','mathvariant','stretchy','largeop','movablelimits','accent','accentunder','linethickness','notation','width','height','depth','lspace','columnalign','rowalign'}
MAX_XML_BYTES=32*1024*1024

def local(tag): return tag.rsplit('}',1)[-1]
def parse_xml(data):
 if isinstance(data,str):data=data.encode('utf-8')
 if len(data)>MAX_XML_BYTES:raise ValueError('XML part exceeds safe processing limit')
 if re.search(br'<!\s*(?:DOCTYPE|ENTITY)\b',data,re.I):raise ValueError('DTD/entities are not accepted')
 return ET.fromstring(data)
def node(tag,*children,text=None,**attrs):
 if tag not in ALLOWED_TAGS or not set(attrs)<=ALLOWED_ATTRS:raise ValueError('Unsafe MathML construction')
 e=ET.Element(tag,{k:str(v) for k,v in attrs.items()})
 if text is not None:e.text=str(text)
 e.extend(c for c in children if c is not None);return e
def val(parent,path,default=None):
 e=parent.find(path,NS)
 return default if e is None else e.get('{'+M+'}val',default)
def enabled(parent,path,default=False):
 e=parent.find(path,NS)
 return default if e is None else e.get('{'+M+'}val','1') not in ('0','false','off')

class OMMLConverter:
 def __init__(self,display=False,defaults=None):self.display=display;self.defaults=defaults or {};self.warnings=[];self.nodes=0
 def warn(self,code,tag):self.warnings.append({'code':code,'element':tag})
 def error(self,code,tag):
  self.warn(code,tag);return node('merror',node('mtext',text='[未解析公式:'+tag+']'))
 def children(self,e):return [self.convert(c) for c in e if not local(c.tag).endswith('Pr')]
 def arg(self,e,name):
  a=e.find('m:'+name,NS)
  return self.error('missing-required-argument',name) if a is None else self.convert(a)
 def token(self,text,variant=None,literal=False):
  if literal:return node('mtext',text=text)
  bits=re.findall(r'\s+|\d+(?:[.,]\d+)?|[^\W\d_]+|.',text,re.UNICODE);out=[]
  for s in bits:
   if s.isspace():out.append(node('mtext',text=s));continue
   tag='mn' if re.fullmatch(r'\d+(?:[.,]\d+)?',s) else ('mi' if s[0].isalpha() else 'mo')
   out.append(node(tag,text=s,**({'mathvariant':variant} if variant and tag in ('mi','mn') else {})))
  return node('mrow',*out)
 def convert(self,e):
  self.nodes+=1
  if self.nodes>20000:raise ValueError('Formula node limit exceeded')
  t=local(e.tag)
  if not e.tag.startswith('{'+M+'}'):
   if e.tag=='{'+W+'}r':return node('mtext',text=''.join(x.text or '' for x in e.iter('{'+W+'}t')))
   return self.error('unsupported-foreign-element',t)
  if t in ('oMath','oMathPara','e','num','den','sub','sup','deg','lim','fName'):return node('mrow',*self.children(e))
  if t=='r':
   style=val(e,'m:rPr/m:sty');script=val(e,'m:rPr/m:scr');variants={'p':'normal','b':'bold','i':'italic','bi':'bold-italic'}
   variant=variants.get(style)
   if script in ('script','fraktur','double-struck','sans-serif','monospace'):variant=script
   if script=='script' and style in ('b','bi'):variant='bold-script'
   if script=='fraktur' and style in ('b','bi'):variant='bold-fraktur'
   if script=='sans-serif' and style in variants:variant={'p':'sans-serif','b':'bold-sans-serif','i':'sans-serif-italic','bi':'sans-serif-bold-italic'}[style]
   return self.token(''.join(n.text or '' for n in e.iter('{'+M+'}t')),variant,enabled(e,'m:rPr/m:nor'))
  if t=='t':return self.token(e.text or '')
  if t=='f':
   mode=val(e,'m:fPr/m:type','bar');a,b=self.arg(e,'num'),self.arg(e,'den')
   # Stack even linear/skewed input: the ratio structure remains unambiguous.
   return node('mfrac',a,b,**({'linethickness':'0'} if mode=='noBar' else {}))
  if t=='sSub':return node('msub',self.arg(e,'e'),self.arg(e,'sub'))
  if t=='sSup':return node('msup',self.arg(e,'e'),self.arg(e,'sup'))
  if t=='sSubSup':return node('msubsup',self.arg(e,'e'),self.arg(e,'sub'),self.arg(e,'sup'))
  if t=='sPre':return node('mmultiscripts',self.arg(e,'e'),node('mprescripts'),self.arg(e,'sub'),self.arg(e,'sup'))
  if t=='rad':
   base=self.arg(e,'e');deg=e.find('m:deg',NS)
   if enabled(e,'m:radPr/m:degHide') or (deg is not None and not list(deg)):return node('msqrt',base)
   return node('mroot',base,self.arg(e,'deg'))
  if t=='nary':
   ch=val(e,'m:naryPr/m:chr','∫');op=node('mo',text=ch,largeop='true',movablelimits='false')
   setting='intLim' if ch in '∫∬∭∮∯∰' else 'naryLim'
   location=val(e,'m:naryPr/m:limLoc',self.defaults.get(setting,'undOvr' if self.display else 'subSup'))
   sub=e.find('m:sub',NS);sup=e.find('m:sup',NS)
   has_sub=sub is not None and len(sub)>0 and not enabled(e,'m:naryPr/m:subHide')
   has_sup=sup is not None and len(sup)>0 and not enabled(e,'m:naryPr/m:supHide')
   if has_sub and has_sup:op=node('munderover' if location=='undOvr' else 'msubsup',op,self.convert(sub),self.convert(sup))
   elif has_sub:op=node('munder' if location=='undOvr' else 'msub',op,self.convert(sub))
   elif has_sup:op=node('mover' if location=='undOvr' else 'msup',op,self.convert(sup))
   return node('mrow',op,self.arg(e,'e'))
  if t in ('limLow','limUpp'):return node('munder' if t=='limLow' else 'mover',self.arg(e,'e'),self.arg(e,'lim'))
  if t=='d':
   begin=val(e,'m:dPr/m:begChr','(');end=val(e,'m:dPr/m:endChr',')');sep=val(e,'m:dPr/m:sepChr','|');out=[]
   if begin:out.append(node('mo',text=begin,stretchy='true'))
   for i,part in enumerate(e.findall('m:e',NS)):
    if i and sep:out.append(node('mo',text=sep,stretchy='true'))
    out.append(self.convert(part))
   if end:out.append(node('mo',text=end,stretchy='true'))
   return node('mrow',*out)
  if t=='m':return node('mtable',*(node('mtr',*(node('mtd',self.convert(c)) for c in row.findall('m:e',NS))) for row in e.findall('m:mr',NS)))
  if t=='eqArr':return node('mtable',*(node('mtr',node('mtd',self.convert(c))) for c in e.findall('m:e',NS)),columnalign='left')
  if t=='func':return node('mrow',self.arg(e,'fName'),node('mo',text='\u2061'),self.arg(e,'e'))
  if t in ('acc','bar','groupChr'):
   over=val(e,'m:'+t+'Pr/m:pos','top' if t!='groupChr' else 'bot')!='bot'
   char=val(e,'m:'+t+'Pr/m:chr','¯' if t=='bar' else ('⏟' if t=='groupChr' else '̂'))
   return node('mover' if over else 'munder',self.arg(e,'e'),node('mo',text=char,stretchy='true'),**({'accent':'true'} if over else {'accentunder':'true'}))
  if t=='box':return self.arg(e,'e')
  if t=='borderBox':
   props=e.find('m:borderBoxPr',NS)
   notation=[]
   for edge in ('top','bottom','left','right'):
    hide={'top':'hideTop','bottom':'hideBot','left':'hideLeft','right':'hideRight'}[edge]
    if not enabled(e,'m:borderBoxPr/m:'+hide):notation.append(edge)
   for key,note in (('strikeH','horizontalstrike'),('strikeV','verticalstrike'),('strikeBLTR','updiagonalstrike'),('strikeTLBR','downdiagonalstrike')):
    if enabled(e,'m:borderBoxPr/m:'+key):notation.append(note)
   return node('menclose',self.arg(e,'e'),notation=' '.join(notation))
  if t=='phant':
   result=self.arg(e,'e')
   if not enabled(e,'m:phantPr/m:show',False):result=node('mphantom',result)
   attrs={name:'0' for key,name in (('zeroWid','width'),('zeroAsc','height'),('zeroDesc','depth')) if enabled(e,'m:phantPr/m:'+key)}
   return node('mpadded',result,**attrs) if attrs else result
  if t.endswith('Pr'):return node('mrow')
  return self.error('unsupported-omml-element',t)

def omml_to_mathml(xml,display=False,defaults=None):
 e=xml if isinstance(xml,ET.Element) else parse_xml(xml)
 c=OMMLConverter(display or local(e.tag)=='oMathPara',defaults)
 root=node('math',c.convert(e),xmlns=MM,display='block' if c.display else 'inline')
 markup=ET.tostring(root,encoding='unicode',short_empty_elements=True)
 raw=ET.tostring(e,encoding='utf-8')
 return {'type':'math','format':'mathml','mathml':markup,'display':c.display,'linearText':''.join(n.text or '' for n in e.iter('{'+M+'}t')),'complete':not c.warnings,'warnings':c.warnings,'sourceHash':hashlib.sha256(raw).hexdigest()}

def resolve_target(part,target):
 target=unquote(target.replace('\\','/'))
 if urlsplit(target).scheme or target.startswith('//'):return None
 result=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(part),target))
 return None if result=='..' or result.startswith('../') else result

def parse_docx(path):
 path=pathlib.Path(path);part='word/document.xml';warnings=[];paragraphs=[];media={}
 with zipfile.ZipFile(path) as z:
  names=set(z.namelist())
  def read_xml(name):
   if z.getinfo(name).file_size>MAX_XML_BYTES:raise ValueError('Oversized XML part: '+name)
   return parse_xml(z.read(name))
  doc=read_xml(part);rels={};types={};extensions={};defaults={}
  if '[Content_Types].xml' in names:
   for e in read_xml('[Content_Types].xml'):
    if local(e.tag)=='Override':types[e.get('PartName','').lstrip('/')]=e.get('ContentType')
    if local(e.tag)=='Default':extensions[e.get('Extension','').lower()]=e.get('ContentType')
  if 'word/settings.xml' in names:
   settings=read_xml('word/settings.xml')
   for key in ('intLim','naryLim'):
    prop=settings.find('.//m:'+key,NS)
    if prop is not None:defaults[key]=prop.get('{'+M+'}val')
  relpart='word/_rels/document.xml.rels'
  if relpart in names:
   for e in read_xml(relpart):rels[e.get('Id')]={'target':e.get('Target',''),'type':e.get('Type',''),'external':e.get('TargetMode')=='External'}
  def media_ref(rid,kind):
   if rid in media:return media[rid]
   rel=rels.get(rid);target=None if not rel or rel['external'] else resolve_target(part,rel['target'])
   exists=target in names if target else False
   item={'id':rid,'relationshipId':rid,'kind':kind,'packagePath':target,'external':bool(rel and rel['external']),'exists':exists,'contentType':(types.get(target) or extensions.get(pathlib.PurePosixPath(target).suffix.lstrip('.').lower()) or mimetypes.guess_type(target)[0]) if target else None}
   if exists:item['size']=z.getinfo(target).file_size
   if not exists:item['warning']='external-media-not-fetched' if item['external'] else 'missing-or-unsafe-media-relationship';warnings.append({'code':item['warning'],'relationshipId':rid})
   media[rid]=item;return item
  def image_segment(e,locator):
   image_ids=[];ole_ids=[]
   for n in e.iter():
    if n.tag=='{'+A+'}blip':
     rid=n.get('{'+R+'}embed') or n.get('{'+R+'}link')
     if rid:image_ids.append(rid)
    elif n.tag=='{'+V+'}imagedata':
     rid=n.get('{'+R+'}id')
     if rid:image_ids.append(rid)
    elif n.tag=='{'+O+'}OLEObject':
     rid=n.get('{'+R+'}id')
     if rid:ole_ids.append(rid)
   objects=[media_ref(rid,'ole-object')['id'] for rid in dict.fromkeys(ole_ids)]
   segments=[]
   for rid in dict.fromkeys(image_ids):
    ref=media_ref(rid,'image');segment={'type':'image','mediaId':rid,'sourceLocator':locator,'placeholder':'[pic]','available':ref['exists']}
    if objects:segment['embeddedObjectIds']=objects
    segments.append(segment)
   if not segments:
    segments=[{'type':'unsupported','kind':'embedded-object' if objects else 'drawing','embeddedObjectIds':objects,'sourceLocator':locator,'placeholder':'[pic]','warning':'no-renderable-preview'}]
   return segments
  for index,p in enumerate(doc.iter('{'+W+'}p')):
   locator=part+'#paragraph='+str(index+1);segments=[]
   def walk(e):
    tag=e.tag;t=local(tag)
    if tag in ('{'+M+'}oMath','{'+M+'}oMathPara'):
     item=omml_to_mathml(e,tag.endswith('oMathPara'),defaults);item['sourceLocator']=locator+';math='+str(sum(s['type']=='math' for s in segments)+1);segments.append(item);return
    if tag in ('{'+W+'}drawing','{'+W+'}pict','{'+W+'}object'):segments.extend(image_segment(e,locator));return
    if tag=='{'+MC+'}AlternateContent':
     choice=e.find('{'+MC+'}Choice');fallback=e.find('{'+MC+'}Fallback')
     chosen=choice if choice is not None else fallback
     if choice is not None and fallback is not None and not any(n.tag in ('{'+M+'}oMath','{'+M+'}oMathPara','{'+A+'}blip','{'+V+'}imagedata') for n in choice.iter()):chosen=fallback
     if chosen is not None:
      for child in chosen:walk(child)
     return
    if tag=='{'+W+'}t':segments.append({'type':'text','text':e.text or ''});return
    if tag in ('{'+W+'}br','{'+W+'}cr'):segments.append({'type':'text','text':'\n'});return
    if tag=='{'+W+'}tab':segments.append({'type':'text','text':'\t'});return
    if tag=='{'+W+'}sym':
     segments.append({'type':'unsupported','kind':'font-symbol','font':e.get('{'+W+'}font'),'fontChar':e.get('{'+W+'}char'),'sourceLocator':locator,'placeholder':'[符号]','warning':'font-dependent-symbol-requires-source-font'});return
    if tag in ('{'+W+'}del','{'+W+'}instrText','{'+W+'}pPr','{'+W+'}rPr'):return
    if tag=='{'+W+'}p' and e is not p:return
    for child in e:walk(child)
   walk(p)
   merged=[]
   for s in segments:
    if s['type']=='text' and merged and merged[-1]['type']=='text':merged[-1]['text']+=s['text']
    else:merged.append(s)
   if merged:paragraphs.append({'index':index+1,'sourcePart':part,'sourceLocator':locator,'segments':merged,'matchText':''.join(s.get('text',s.get('linearText',s.get('placeholder',''))) for s in merged)})
 all_segments=[s for p in paragraphs for s in p['segments']]
 return {'schemaVersion':1,'sourceFile':path.name,'paragraphs':paragraphs,'media':list(media.values()),'warnings':warnings,'stats':{'paragraphs':len(paragraphs),'math':sum(s['type']=='math' for s in all_segments),'incompleteMath':sum(s['type']=='math' and not s['complete'] for s in all_segments),'images':sum(s['type']=='image' for s in all_segments),'unsupported':sum(s['type']=='unsupported' for s in all_segments)}}

def main():
 p=argparse.ArgumentParser();p.add_argument('source',type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args();result=parse_docx(a.source);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result['stats'],ensure_ascii=False))
if __name__=='__main__':main()
