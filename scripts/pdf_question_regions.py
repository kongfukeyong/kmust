#!/usr/bin/env python3
"""Conservative PDF question regions; read-only with respect to question data.

Requires PyMuPDF only for reading/rendering PDF pages. Geometry analysis itself
is dependency-free and testable. Coordinates are PyMuPDF page points, top-left
origin. Rotated pages are deliberately returned as page fallbacks.
"""
import argparse,json,pathlib,re,statistics,unicodedata

LABEL=re.compile(r'^\s*(\d{1,3})\s*([.．、])\s*(.*)$')
def normalize(s):return unicodedata.normalize('NFKC',s).strip()
def detect_label(text):
 text=normalize(text);match=LABEL.match(text)
 if not match:return None
 number=int(match.group(1));rest=match.group(3)
 if not 1<=number<=999:return None
 # Decimal constants and isolated equation operands are not question labels.
 if rest and (rest[0].isdigit() or re.match(r'^[+−=×÷/*^<>]',rest)):return None
 return number
def fallback(width,height,page,reason,diagnostics=None,continuation=False):
 return {'mode':'page','page':page,'bbox':[0.0,0.0,float(width),float(height)],'normalizedBbox':[0.0,0.0,1.0,1.0],'reason':reason,'continuationPossible':continuation,'diagnostics':diagnostics or {}}

def analyze_lines(lines,width,height,number,page=1,graphics=(),rotation=0):
 """lines: [{text,bbox:[x0,y0,x1,y1],size,direction?}], all in points.

 Only labels within the left 30% of a column qualify. A cluster must contain
 >=3 label lines; the requested label must be unique and followed by n+1.
 """
 if not re.fullmatch(r'\d{1,3}',str(number).strip()):return fallback(width,height,page,'unsupported-question-number')
 number=int(str(number).strip())
 if rotation:return fallback(width,height,page,'rotated-page-needs-visual-layout')
 sizes=[float(l.get('size',0)) for l in lines if l.get('size',0)>0 and len(l.get('text','').strip())>=4]
 if not sizes:return fallback(width,height,page,'no-readable-text-coordinates')
 body=statistics.median(sizes);column_count=2 if width>height*1.15 else 1;cw=width/column_count;candidates=[]
 for line in lines:
  label=detect_label(line.get('text',''));box=line['bbox'];size=float(line.get('size',body));direction=line.get('direction',(1,0))
  if label is None or abs(direction[1])>.08:continue
  if box[1]<height*.035 or box[3]>height*.955:continue
  if size<body*.78 or size>body*1.35:continue
  column=min(column_count-1,max(0,int(box[0]/cw)));left=column*cw
  if not left<=box[0]<=left+cw*.30:continue
  candidates.append({'number':label,'bbox':list(box),'size':size,'column':column,'text':line.get('text','')[:160]})
 # Do not guess the column of an ambiguous repeated number on the same page.
 targets=[c for c in candidates if c['number']==number]
 diagnostics={'bodyFontSize':round(body,2),'columnCount':column_count,'candidateCount':len(candidates),'candidates':candidates}
 if len(targets)!=1:return fallback(width,height,page,'question-label-not-found' if not targets else 'ambiguous-repeated-question-label',diagnostics)
 target=targets[0];tol=max(5.0,body*.7)
 cluster=sorted([c for c in candidates if c['column']==target['column'] and abs(c['bbox'][0]-target['bbox'][0])<=tol],key=lambda c:c['bbox'][1])
 if len(cluster)<3:return fallback(width,height,page,'insufficient-aligned-label-evidence',diagnostics)
 position=cluster.index(target)
 if position and cluster[position-1]['number']!=number-1:return fallback(width,height,page,'nonconsecutive-previous-label',diagnostics)
 if position==len(cluster)-1:return fallback(width,height,page,'no-next-label-possible-page-continuation',diagnostics,True)
 next_label=cluster[position+1]
 if next_label['number']!=number+1:return fallback(width,height,page,'nonconsecutive-next-label',diagnostics)
 if abs(next_label['size']-target['size'])>body*.20:return fallback(width,height,page,'label-font-size-disagreement',diagnostics)
 x0=target['column']*cw;x1=x0+cw;y0=max(0,target['bbox'][1]-3);y1=next_label['bbox'][1]-3
 if y1-y0<max(24,body*2):return fallback(width,height,page,'question-region-too-short',diagnostics)
 # A full-width row on a landscape page can be a merged or non-column layout.
 if column_count==2:
  for line in lines:
   b=line['bbox']
   if y0<=b[1]<y1 and b[0]<cw-8 and b[2]>cw+8:return fallback(width,height,page,'text-crosses-column-gutter',diagnostics)
 # A graphic crossing a horizontal boundary might belong to either question.
 for b in graphics:
  if b[2]-b[0]<3 or b[3]-b[1]<3:continue
  if (b[2]-b[0])*(b[3]-b[1])>width*height*.65:continue # page frame/background
  if b[2]<=x0 or b[0]>=x1:continue
  if b[1]+1<y0<b[3]-1 or b[1]+1<y1<b[3]-1:return fallback(width,height,page,'graphic-crosses-question-boundary',diagnostics)
 for line in lines:
  b=line['bbox']
  if b[2]<=x0 or b[0]>=x1:continue
  if y0<=b[1]<y1-1 and b[3]>y1+1:return fallback(width,height,page,'text-crosses-question-boundary',diagnostics)
 return {'mode':'crop','page':page,'number':str(number),'bbox':[round(x0,3),round(y0,3),round(x1,3),round(y1,3)],'normalizedBbox':[round(x0/width,6),round(y0/height,6),round(x1/width,6),round(y1/height,6)],'reason':'aligned-consecutive-question-labels','continuationPossible':False,'diagnostics':diagnostics}

def page_layout(page):
 lines=[];graphics=[]
 for block in page.get_text('dict',sort=False).get('blocks',[]):
  if block.get('type')==1:graphics.append(block['bbox']);continue
  for line in block.get('lines',[]):
   spans=line.get('spans',[]);text=''.join(s.get('text','') for s in spans)
   weighted=[float(s.get('size',0)) for s in spans for _ in range(max(1,min(30,len(s.get('text','')))))]
   lines.append({'text':text,'bbox':list(line['bbox']),'size':statistics.median(weighted) if weighted else 0,'direction':line.get('dir',(1,0))})
 try:graphics.extend(list(d['rect']) for d in page.get_drawings())
 except Exception:pass
 return lines,graphics

def detect_question_region(pdf_path,page_number,number,question_id=None):
 import fitz
 with fitz.open(pdf_path) as document:
  if not 1<=int(page_number)<=len(document):raise ValueError('Source page is outside PDF')
  page=document[int(page_number)-1];lines,graphics=page_layout(page)
  result=analyze_lines(lines,page.rect.width,page.rect.height,number,int(page_number),graphics,page.rotation)
  result['pageCount']=len(document);result['sourceFile']=str(pdf_path)
  result['fallbackPages']=[int(page_number)]
  if result['continuationPossible'] and int(page_number)<len(document):result['fallbackPages'].append(int(page_number)+1)
  if question_id is not None:result['questionId']=question_id
  return result

def render_region(pdf_path,region,output,dpi=240):
 """Explicit optional renderer. It does not modify PDFs or question JSON."""
 import fitz
 if not 120<=dpi<=400:raise ValueError('Choose 120-400 DPI')
 output=pathlib.Path(output);output.parent.mkdir(parents=True,exist_ok=True)
 with fitz.open(pdf_path) as document:
  page=document[region['page']-1];clip=fitz.Rect(region['bbox']) if region['mode']=='crop' else page.rect
  page.get_pixmap(dpi=dpi,clip=clip,alpha=False,annots=True).save(output)
 return str(output)

def main():
 p=argparse.ArgumentParser();p.add_argument('--pdf',required=True,type=pathlib.Path);p.add_argument('--page',required=True,type=int);p.add_argument('--number',required=True);p.add_argument('--question-id');p.add_argument('--output',required=True,type=pathlib.Path);p.add_argument('--render',type=pathlib.Path);p.add_argument('--dpi',type=int,default=240);a=p.parse_args()
 result=detect_question_region(a.pdf,a.page,a.number,a.question_id);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 if a.render:render_region(a.pdf,result,a.render,a.dpi)
 print(json.dumps({k:v for k,v in result.items() if k!='diagnostics'},ensure_ascii=False))
if __name__=='__main__':main()
