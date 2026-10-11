#!/usr/bin/env python3
"""Reproducible conservative KUST extraction; no generated answers or automatic OCR.
Usage: python extract_questions.py --source SOURCE --tree tree.json --output public/data
Optional: pdftotext and antiword improve coverage; pypdf is the PDF fallback.
Every machine-separated question remains needs-review until manually checked.
"""
import argparse, collections, hashlib, html, json, pathlib, re, shutil, subprocess, sys, zipfile
import xml.etree.ElementTree as ET
from urllib.parse import quote

W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
M='{http://schemas.openxmlformats.org/officeDocument/2006/math}'
NUM=re.compile(r'^\s*(\d{1,3})\s*[、.．，]\s*(.*)')
SECTION=re.compile(r'^(?:[一二三四五六七八九十]+[、.．]|[（(][一二三四五六七八九十]+[）)])\s*(.*)')
KINDS=[('程序填充','程序填空题'),('程序改错','程序改错题'),('程序设计','程序设计题'),('程序运行结果','程序阅读题'),('函数的功能','程序阅读题'),('多项选择','多选题'),('单项选择','单选题'),('多选','多选题'),('单选','单选题'),('选择','选择题'),('判断','判断题'),('填空','填空题'),('简答','简答题'),('计算','计算题'),('论述','论述题'),('证明','证明题'),('综合','综合题'),('设计','设计题'),('分析','分析题')]
def uid(s): return hashlib.sha1(s.encode('utf-8')).hexdigest()[:16]
def write(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def docx_pages(path):
 with zipfile.ZipFile(path) as z:
  doc=ET.fromstring(z.read('word/document.xml'))
  lines=[]
  for p in doc.iter(W+'p'):
   s=''
   for n in p.iter():
    if n.tag in (W+'t',M+'t'): s+=n.text or ''
    elif n.tag in (W+'br',W+'cr'): s+='\n'
    elif n.tag==W+'tab': s+='\t'
   if s.strip(): lines.append(s)
  return [(None,'\n'.join(lines))], 'docx-xml', len(list(doc.iter(W+'drawing')))+len(list(doc.iter(W+'object')))
def extract(path,ext):
 if ext=='docx': return docx_pages(path)
 if ext in ('pptx','pptm'):
  A='{http://schemas.openxmlformats.org/drawingml/2006/main}';pages=[]
  with zipfile.ZipFile(path) as z:
   names=sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)),key=lambda n:int(re.search(r'slide(\d+)',n).group(1)))
   for name in names:
    doc=ET.fromstring(z.read(name));lines=[''.join(n.text or '' for n in para.iter(A+'t')) for para in doc.iter(A+'p')]
    pages.append((int(re.search(r'slide(\d+)',name).group(1)),'\n'.join(lines)))
  return pages,'pptx-xml',0
 if ext=='pdf':
  if shutil.which('pdftotext'):
   p=subprocess.run(['pdftotext','-layout','-enc','UTF-8',str(path),'-'],capture_output=True,timeout=120)
   if p.returncode: raise ValueError(p.stderr.decode(errors='replace')[:250])
   parts=p.stdout.decode('utf-8').split('\f')
   if parts and not parts[-1].strip(): parts.pop()
   method='pdftotext'
   try:
    import fitz
    with fitz.open(path) as doc:
     for i,page in enumerate(doc):
      if page.rect.width>page.rect.height*1.15:
       w,h=page.rect.width,page.rect.height
       left=page.get_text('text',clip=fitz.Rect(0,0,w/2,h),sort=True)
       right=page.get_text('text',clip=fitz.Rect(w/2,0,w,h),sort=True)
       if len(left.strip())+len(right.strip())>30:parts[i]=left+'\n'+right;method='pdftotext+pymupdf-columns'
   except ImportError:pass
   return list(enumerate(parts,1)),method,0
  from pypdf import PdfReader
  r=PdfReader(path); return [(i+1,p.extract_text() or '') for i,p in enumerate(r.pages)],'pypdf',0
 if ext=='doc':
  if not shutil.which('antiword'): raise RuntimeError('legacy-doc-converter-unavailable')
  p=subprocess.run(['antiword','-m','UTF-8.txt',str(path)],capture_output=True,timeout=90)
  if p.returncode: raise RuntimeError(p.stderr.decode(errors='replace')[:150])
  return [(None,p.stdout.decode('utf-8',errors='replace'))],'antiword',0
 if ext in ('txt','md'):
  raw=path.read_bytes()
  for enc in ('utf-8-sig','gb18030','utf-16'):
   try: return [(None,raw.decode(enc))],enc,0
   except UnicodeDecodeError: pass
 raise RuntimeError('source-only-format')
def clean(s):
 return html.unescape(s).replace('\u00a0',' ').replace('\x00','').strip()
def spreadsheet_questions(path,r):
 import xlrd
 book=xlrd.open_workbook(path);qs=[]
 for sheet in book.sheets():
  if sheet.nrows<2:continue
  header=[str(x).strip() for x in sheet.row_values(0)]
  if '题干' not in header or '答案' not in header:continue
  for i in range(1,sheet.nrows):
   vals=dict(zip(header,sheet.row_values(i)));stem=clean(str(vals.get('题干','')))
   if not stem:continue
   opts=[{'label':k,'text':clean(str(vals[k]))} for k in 'ABCDEFGH' if k in vals and str(vals[k]).strip()]
   answer=clean(str(vals.get('答案',''))).upper() or None
   kind=str(vals.get('题型','题目'));kind=kind if kind.endswith('题') or kind=='题目' else kind+'题'
   number=str(vals.get('序号',i));number=number[:-2] if number.endswith('.0') else number
   qs.append({'id':uid(r['path']+'|'+sheet.name+'|'+str(i+1)),'course':r['course'],'type':kind,'stem':stem,'options':opts,'answer':answer,'sourcePath':r['path'],'resourceId':r['id'],'page':None,'sheet':sheet.name,'row':i+1,'number':number,'status':'needs-review','extractionMethod':'xls-structured-columns','warnings':[],'sourceUrl':r['downloadUrl']})
 return qs
def question_records(pages,r,method,images):
 # Preserve page boundaries; a question can span pages but points at its starting page.
 questions=[]; current=None; section='题目'; answer_mode=False; batch=[]; answer_lines=[]; skip=False; appendix_page=None; section_context=[]
 def flush():
  nonlocal current
  if not current: return
  block='\n'.join(current['lines']).strip(); stem=block; answer=None; options=[]
  am=re.search(r'(?:^|\n)\s*(?:参考答案|正确答案|答案|解答|答|解)\s*[：:]\s*',block)
  if am: stem=block[:am.start()].strip();answer=block[am.end():].strip() or None
  elif r['title'].startswith('近代史简答') and '\n' in block:
   stem,answer=block.split('\n',1)
  elif section in ('简答题','论述题') and '\n' in block and len(block.split('\n')[0])<220 and re.search(r'[？?]$',block.split('\n')[0]):
   stem,answer=block.split('\n',1)
  inline=re.search(r'[（(]\s*([A-H](?:[\s,，、.．]*[A-H])*)\s*[）)]',stem)
  if inline and (r['ext'] in ('pptx','pptm') or '智慧树' in r['title'] or r['course'] in ('毛 概','新思想')):
   answer=re.sub(r'[^A-H]','',inline.group(1));stem=stem[:inline.start()]+'（    ）'+stem[inline.end():]
  opt=list(re.finditer(r'(?<![A-Za-z])([A-H])、?[.．:：]\s*',stem))
  if len(opt)<2:opt=list(re.finditer(r'(?:^|\n|\s{2,})[（(]([A-H])[）)]\s*',stem))
  if len(opt)<2:opt=list(re.finditer(r'(?:^|\n)\s*([A-H])、\s*',stem))
  if len(opt)<2 and '智慧树' in r['title']:
   opt=list(re.finditer(r'(?:^|\n)([A-H])(?:[.．、:：]\s*|\s+|(?=[\u4e00-\u9fff]))',stem))
  if len(opt)>=2 and opt[0].group(1)=='A':
   body=stem;stem=body[:opt[0].start()].strip()
   options=[{'label':m.group(1),'text':body[m.end():opt[i+1].start() if i+1<len(opt) else len(body)].strip()} for i,m in enumerate(opt)]
  if len(stem)>=8 and len(block)<=16000 and re.search(r'[\u4e00-\u9fffA-Za-z]',stem):
   warnings=[]
   if r['ext'] in ('pdf','doc') or images: warnings.append('公式、图表与排版请对照原文件')
   if answer is None: warnings.append('未匹配到独立答案')
   if r['title']=='模式识别简答' and '\n' in stem and answer is None: stem,answer=stem.split('\n',1)
   if options and len({o['label'] for o in options})!=len(options): warnings.append('选项边界存在歧义，请对照原文件')
   if section_context: stem='\n'.join(section_context)+'\n\n'+stem
   q={'id':uid(r['path']+'|'+str(len(questions))+'|'+current['number']+'|'+stem),'course':r['course'],'type':section if section!='题目' else ('选择题' if options else '题目'),'stem':stem,'options':options,'answer':answer,'sourcePath':r['path'],'resourceId':r['id'],'page':current['page'] if r['ext']=='pdf' else None,'number':current['number'],'status':'needs-review','extractionMethod':method,'warnings':warnings,'sourceUrl':r['downloadUrl']}
   if r['ext'] in ('pptx','pptm'):q['slide']=current['page']
   questions.append(q);batch.append(q)
  current=None
 def apply_answers():
  nonlocal answer_lines,batch
  pairs=re.findall(r'(\d{1,3})\s*[.．、:：]\s*([A-H]{1,8})(?=\s|\d|$)', ''.join(answer_lines))
  counts=collections.Counter(q['number'] for q in batch)
  for n,a in pairs:
   if counts[n]==1:
    q=next(q for q in batch if q['number']==n);q['answer']=a;q['warnings']=[x for x in q['warnings'] if x!='未匹配到独立答案']
  answer_lines=[];batch=[]
 for page,text in pages:
  for raw in text.splitlines():
   line=clean(raw)
   if not line: continue
   if re.match(r'^参考答案(?:与|及|和)(?:评分|解析)|^答案(?:与|及)评分',line) or (r['ext']=='pdf' and re.fullmatch(r'参考答案[：:]?',line)):
    flush();appendix_page=page;break
   if line in ('教材章节','教学建议','融入内容'): flush();skip=True;continue
   if re.match(r'^第[一二三四五六七八九十\d]+章.*(?:单元测试|重要知识点)$',line):
    flush()
    if answer_mode: apply_answers()
    answer_mode=False;skip='重要知识点' in line;continue
   if r['title']=='模式识别简答' and len(line)<100 and (re.match(r'^\d+\s*(?:简述|请解释|什么|如何|试述|说明)',line) or re.match(r'^(?:简述|什么叫|什么是|模式识别.{0,20}[？?])',line)):
    flush();current={'number':str(len(questions)+1),'page':page,'lines':[re.sub(r'^\d+\s*','',line)]};section='简答题';continue
   if re.match(r'^(?:第.{1,6}章.*)?重要知识点',line): flush();skip=True;continue
   if line in ('练习题','练习','习题') or re.match(r'^[一二三四五六七八九十]+[、.]\s*选择题',line): skip=False
   sec=SECTION.match(line)
   kind=next((v for k,v in KINDS if k in line),None) if len(line)<75 else None
   if kind and (sec or re.fullmatch(r'(?:单项选择|多项选择|单选|多选|选择|判断|填空|简答|计算|论述|证明|综合|设计|分析)题[：:]?',line)):
    flush()
    if answer_mode: apply_answers()
    answer_mode=False;section=kind;skip=False;section_context=[];continue
   if re.match(r'^(参考答案|答案及解析|答案与解析)\s*$',line): flush();answer_mode=True;continue
   if answer_mode: answer_lines.append(line);continue
   if skip: continue
   m=re.match(r'^(\d{1,2}[-－]\d{1,3})(?:[、.．]\s*|\s+)(.*)',line) or NUM.match(line)
   if m and (m.group(1)=='0' or (m.group(2) and not re.search(r'[\u4e00-\u9fffA-Za-z]',m.group(2)))): m=None
   if m:
    flush(); current={'number':m.group(1),'page':page,'lines':[m.group(2)]}
   elif current:
    if re.search(r'第\s*\d+\s*页.*共\s*\d+\s*页',line) or re.match(r'^[-—]?\s*\d{1,3}\s*[-—]?$',line): continue
    current['lines'].append(line)
   elif section=='设计题' and not re.search(r'得\s*分|共.*分|每.*分|第\s*\d+\s*页',line): section_context.append(line)
  if appendix_page is not None:break
 flush()
 if answer_mode: apply_answers()
 if appendix_page is not None:
  for q in questions:q['answerSourcePage']=appendix_page
 return questions
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',required=True,type=pathlib.Path);ap.add_argument('--tree',required=True,type=pathlib.Path);ap.add_argument('--output',required=True,type=pathlib.Path);ap.add_argument('--text-output',type=pathlib.Path);args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
 tree=json.loads(args.tree.read_text(encoding='utf-8-sig'));resources=[];questions=[];issues=[];seen={}
 for f in tree['tree']:
  if f['type']!='blob':continue
  name=f['path'];p=pathlib.PurePosixPath(name);ext=p.suffix.lower().lstrip('.');title=p.stem
  kind='答案' if re.search('答案|评分标准|评分细则',title) and not re.search('及答案|含答案|附答案|试题及|习题及|带参考',title) else ('题库' if re.search('题库|练习|习题',title) else '资料')
  lock=p.name.startswith('~') or ext=='tmp'
  r={'id':uid(name),'course':p.parts[0] if len(p.parts)>1 else '仓库说明','title':title,'path':name,'sourcePath':name,'ext':ext,'size':f.get('size',0),'kind':kind,'downloadUrl':'files/'+quote(name,safe='/'),'githubUrl':'https://github.com/123pyLeo/KUST-/blob/'+tree['sha']+'/'+quote(name,safe='/'),'status':'source-only','questionCount':0,'sha':f['sha']}
  resources.append(r)
  if lock: r['status']='excluded-temporary';continue
  if f['sha'] in seen: r['duplicateOf']=seen[f['sha']];r['status']='duplicate';continue
  seen[f['sha']]=r['id'];path=args.source/name
  if not path.exists():r['status']='missing-local';issues.append({'path':name,'reason':'missing-local'});continue
  try:
   if ext=='xls' and '题库' in title:
    qs=spreadsheet_questions(path,r);r['questionCount']=len(qs);questions.extend(qs);r['status']='extracted-needs-review' if qs else 'text-no-question-boundary';r['extractionMethod']='xls-structured-columns';continue
   pages,method,images=extract(path,ext);r['pageCount']=len(pages) if ext=='pdf' else None;r['extractionMethod']=method
   chars=sum(len(t.strip()) for _,t in pages)
   if chars<25:r['status']='needs-ocr';issues.append({'path':name,'reason':'no-readable-text','pages':len(pages)});continue
   all_text=''.join(t for _,t in pages)
   if ext=='pdf' and len(re.findall(r'[\u0500-\u1cff]',all_text))>max(50,chars*.15):
    r['status']='needs-ocr';issues.append({'path':name,'reason':'corrupt-font-text-encoding','pages':len(pages)});continue
   if args.text_output:
    txt=args.text_output/(r['id']+'.txt');txt.parent.mkdir(parents=True,exist_ok=True);txt.write_text('\n\n'.join('[PAGE '+str(pg)+']\n'+t for pg,t in pages),encoding='utf-8')
   if kind=='答案':r['status']='answer-source';continue
   if re.search('教学大纲|知识点.txt',name):r['status']='reference-text';continue
   qs=question_records(pages,r,method,images);r['questionCount']=len(qs);questions.extend(qs);r['status']='extracted-needs-review' if qs else 'text-no-question-boundary'
   if not qs:issues.append({'path':name,'reason':r['status']})
  except Exception as e:
   r['status']='source-only' if str(e)=='source-only-format' else 'extraction-error';issues.append({'path':name,'reason':str(e)[:300]})
  print(r['status'],r['questionCount'],name,flush=True)
 report={'schemaVersion':1,'repository':'https://github.com/123pyLeo/KUST-','commit':tree['sha'],'totalFiles':len(resources),'totalBytes':sum(r['size'] for r in resources),'fileTypes':dict(collections.Counter(r['ext'] for r in resources)),'courses':len(set(r['course'] for r in resources if r['course']!='仓库说明')),'resourcesByStatus':dict(collections.Counter(r['status'] for r in resources)),'questionCount':len(questions),'questionsWithAnswers':sum(q['answer'] is not None for q in questions),'verifiedQuestions':sum(q['status']=='verified' for q in questions),'questionsByCourse':dict(collections.Counter(q['course'] for q in questions)),'issues':issues,'notes':['所有题目均来自源文件，未生成或推测答案。','机器分题统一标为待校对，不代表逐题人工核验。','DOCX/DOC不虚构页码；PDF页码来自原文件。','图片、扫描PDF和无法转换的文件保留原件；公式与图表需打开原文件。','Git blob重复文件不重复入题，临时锁文件保留清单但不作为学习资料。']}
 write(args.output/'resources.json',resources);write(args.output/'questions.json',questions);write(args.output/'extraction-report.json',report)
 print(json.dumps({k:v for k,v in report.items() if k not in ('issues','notes')},ensure_ascii=False))
if __name__=='__main__': main()
