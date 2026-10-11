"""Restore PDF glyph/layout fidelity, keeping question identity and source evidence."""
import argparse,collections,hashlib,json,re,io
from PIL import Image
from pathlib import Path
import pymupdf as fitz
from pdf_question_regions import analyze_lines,page_layout

def pua(s):
 if isinstance(s,str):return bool(re.search('[\ue000-\uf8ff]',s))
 if isinstance(s,list):return any(pua(x) for x in s)
 if isinstance(s,dict):return any(pua(x) for x in s.values())
 return False
def math(s):return {'type':'math','mathml':'<math xmlns="http://www.w3.org/1998/Math/MathML">'+s+'</math>'}
def fix_reported_question(q):
 q.setdefault('originalExtraction',{k:q[k] for k in ('stem','options')})
 vector='<mover accent="true"><mi>r</mi><mo>→</mo></mover>'
 q['stem']='质点在某瞬时位于矢径 r⃗(x, y) 的端点处，其速度大小为［　］'
 q['stemRich']=[{'type':'text','text':'质点在某瞬时位于矢径 '},math(vector+'<mo>(</mo><mi>x</mi><mo>,</mo><mi>y</mi><mo>)</mo>'),{'type':'text','text':' 的端点处，其速度大小为［　］'}]
 def frac(top):return '<mfrac><mrow><mi>d</mi>'+top+'</mrow><mrow><mi>d</mi><mi>t</mi></mrow></mfrac>'
 formulas=[frac('<mi>r</mi>'),frac(vector),frac('<mo>|</mo>'+vector+'<mo>|</mo>'),'<msqrt><mrow><msup><mrow><mo>(</mo>'+frac('<mi>x</mi>')+'<mo>)</mo></mrow><mn>2</mn></msup><mo>+</mo><msup><mrow><mo>(</mo>'+frac('<mi>y</mi>')+'<mo>)</mo></mrow><mn>2</mn></msup></mrow></msqrt>']
 texts=['dr/dt','d r⃗/dt','d|r⃗|/dt','√((dx/dt)²+(dy/dt)²)']
 q['options']=[{'label':label,'text':text,'rich':[math(formula)]} for label,text,formula in zip('ABCD',texts,formulas)]
 q['mathRecovery']={'method':'pdf-visual-transcription','sourcePage':1,'sourceQuestion':'2','answerUnchanged':True}

def main():
 p=argparse.ArgumentParser();p.add_argument('--public',required=True,type=Path);p.add_argument('--source',required=True,type=Path);a=p.parse_args();data=a.public/'data';media=a.public/'math-media';media.mkdir(exist_ok=True)
 qs=json.loads((data/'questions.json').read_text());before=[q['id'] for q in qs];report={'items':[]};docs={};layouts={};images={}
 def render(doc,path,page_no,box=None):
  key=(path,page_no,tuple(box) if box else None)
  if key in images:return images[key]
  page=doc[page_no-1];clip=fitz.Rect(box) if box else page.rect
  # 216 DPI and lossless WebP retain original glyph outlines without artefacts.
  pix=page.get_pixmap(matrix=fitz.Matrix(3,3),clip=clip,alpha=False)
  buffer=io.BytesIO();Image.frombytes('RGB',(pix.width,pix.height),pix.samples).save(buffer,format='WEBP',lossless=True,method=4);raw=buffer.getvalue();name='pdf-'+hashlib.sha256(raw).hexdigest()[:24]+'.webp';(media/name).write_bytes(raw)
  item={'type':'image','src':'math-media/'+name,'alt':f'原卷第 {page_no} 页，点按放大查看完整字形','width':round(clip.width*1.5)};images[key]=item;return item
 for q in qs:
  if q['id']=='1dee48963f35a62d':fix_reported_question(q);report['items'].append({'id':q['id'],'mode':'verified-mathml','page':1});continue
  if q.get('extractionMethod')!='pdftotext' or not any(pua(q.get(k)) for k in ('stem','options','answer')):continue
  path=q['sourcePath'];page_no=int(q['page']);doc=docs.setdefault(path,fitz.open(a.source/path)) if path not in docs else docs[path];page=doc[page_no-1]
  key=(path,page_no)
  if key not in layouts:layouts[key]=page_layout(page)
  lines,graphics=layouts[key];region=analyze_lines(lines,page.rect.width,page.rect.height,q['number'],page_no,graphics,page.rotation)
  # Confirm source content agrees with the extracted question before cropping.
  if region['mode']=='crop':
   anchor=''.join(re.findall('[\u4e00-\u9fff]',q['stem']))[:12]
   content=''.join(re.findall('[\u4e00-\u9fff]',page.get_text(clip=fitz.Rect(region['bbox']))))
   if len(anchor)<4 or anchor not in content:region['mode']='page';region['reason']='stem-anchor-not-in-crop'
  pages=[page_no]
  if region.get('continuationPossible') and page_no<len(doc):pages.append(page_no+1)
  if region['mode']=='crop':rich=[render(doc,path,page_no,region['bbox'])]
  else:rich=[render(doc,path,n) for n in pages]
  # Rich display takes priority; preserve original fields for search and audit.
  q['stemRich']=rich;q['pdfDisplay']={'mode':region['mode'],'page':page_no,'pages':pages,'question':q['number']};q['mathRecovery']={'method':'pdf-embedded-glyph-render','reason':region['reason']}
  if pua(q.get('answer')):
   answer_page=q.get('answerSourcePage')
   if answer_page and 1<=int(answer_page)<=len(doc):q['answerRich']=[render(doc,path,int(answer_page))]
   else:q['answerRich']=[{'type':'text','text':'本题答案含原卷公式，请在上方原卷图或“查看原卷”中查看。'}]
  report['items'].append({'id':q['id'],'sourcePath':path,'page':page_no,'mode':region['mode'],'reason':region['reason'],'bbox':region['bbox'] if region['mode']=='crop' else None})
 assert before==[q['id'] for q in qs]
 for doc in docs.values():doc.close()
 report['summary']={'questionCount':len(qs),'handled':len(report['items']),'modes':dict(collections.Counter(x['mode'] for x in report['items'])),'uniqueImages':len(images),'allIdsUnchanged':True}
 (data/'questions.json').write_text(json.dumps(qs,ensure_ascii=False,separators=(',',':')))
 (data/'pdf-glyph-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report['summary']))
if __name__=='__main__':main()
