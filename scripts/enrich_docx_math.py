#!/usr/bin/env python3
"""Incrementally add DOCX-derived rich fields without regenerating question IDs.

No fuzzy matching or formula guessing. Original text and existing question IDs
are immutable. Requires math_markup.py alongside this file (stdlib only).
"""
import argparse,collections,copy,hashlib,html,json,pathlib,re,shutil,unicodedata,zipfile
from math_markup import parse_docx

IMAGE_TYPES={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.webp':'image/webp'}
def normalized(text):return ''.join(c for c in unicodedata.normalize('NFKC',html.unescape(str(text))) if not c.isspace())
def occurrences(haystack,needle,start=0,end=None):
 if not needle:return []
 end=len(haystack) if end is None else end;hits=[];position=start
 while len(hits)<3:
  position=haystack.find(needle,position,end)
  if position<0:break
  hits.append(position);position+=max(1,len(needle))
 return hits

class RichIndex:
 def __init__(self,document):
  self.segments=[];self.refs=[];self.text='';self.intervals=[]
  for paragraph in document['paragraphs']:
   for segment in paragraph['segments']:
    s=dict(segment,paragraph=paragraph['index']);i=len(self.segments);self.segments.append(s)
    value=s.get('text',s.get('linearText','')) if s['type'] in ('text','math') else ''
    begin=len(self.refs)
    for match in re.finditer(r'&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z]+);|.',value,re.S):
     for char in normalized(match.group()):self.text+=char;self.refs.append((i,match.start(),match.end()))
    self.intervals.append((begin,len(self.refs)))
 def locate(self,value,start=0,end=None):
  key=normalized(value);hits=occurrences(self.text,key,start,end)
  return (hits[0],hits[0]+len(key)) if len(hits)==1 else None
 def locate_option(self,value,label,start,end):
  key=normalized(value);candidates=[]
  for prefix in (label+'.',label+'、',label+':','('+label+')',label+')'):
   for position in occurrences(self.text,prefix+key,start,end):candidates.append((position+len(prefix),position+len(prefix)+len(key)))
  return candidates[0] if len(set(candidates))==1 else None
 def select(self,span):
  start,end=span
  if start>=end:return None,'empty-match'
  first=self.refs[start][0];last=self.refs[end-1][0];result=[]
  last_paragraph=self.segments[last]['paragraph']
  # Include inline trailing objects in the same paragraph, never the next one.
  tail=last+1
  while tail<len(self.segments) and self.segments[tail]['paragraph']==last_paragraph and self.intervals[tail][0]==self.intervals[tail][1]:last=tail;tail+=1
  previous_paragraph=None
  for i in range(first,last+1):
   s=self.segments[i];lo,hi=self.intervals[i];kind=s['type']
   if result and previous_paragraph is not None and s['paragraph']!=previous_paragraph:result.append({'type':'text','text':'\n'})
   previous_paragraph=s['paragraph']
   if kind=='unsupported':return None,'unsupported-source-object'
   if kind=='math':
    if not s.get('complete'):return None,'incomplete-omml'
    if lo<start or hi>end:return None,'partial-formula-match'
    result.append({k:v for k,v in s.items() if k not in ('paragraph','linearText','warnings','sourceHash','complete')})
   elif kind=='image':result.append({k:v for k,v in s.items() if k!='paragraph'})
   elif kind=='text':
    if hi<=start or lo>=end:continue
    a=self.refs[start][1] if i==first else 0;b=self.refs[end-1][2] if i==self.refs[end-1][0] else len(s['text'])
    value=html.unescape(s['text'][a:b])
    if value:result.append({'type':'text','text':value})
  if not any(s['type'] in ('math','image') for s in result):return None,'plain-text-only'
  return result,None

def valid_image(data,extension):
 if extension=='.png':return data.startswith(b'\x89PNG\r\n\x1a\n')
 if extension in ('.jpg','.jpeg'):return data.startswith(b'\xff\xd8\xff')
 if extension=='.gif':return data[:6] in (b'GIF87a',b'GIF89a')
 if extension=='.webp':return data[:4]==b'RIFF' and data[8:12]==b'WEBP'
 return False

def materialize(segments,document,archive,media_output,url_prefix):
 refs={m['id']:m for m in document['media']};result=copy.deepcopy(segments);pending=[]
 for s in result:
  if s['type']!='image':continue
  ref=refs.get(s.get('mediaId'))
  if not ref or not ref['exists'] or ref['external']:return None,'missing-or-external-image'
  target=ref['packagePath'];ext=pathlib.PurePosixPath(target).suffix.lower()
  if ext not in IMAGE_TYPES:return None,'unsupported-image-format:'+ext
  if archive.getinfo(target).file_size>30*1024*1024:return None,'oversized-image'
  raw=archive.read(target)
  if not valid_image(raw,ext):return None,'image-signature-mismatch'
  digest=hashlib.sha256(raw).hexdigest();name=digest+ext;pending.append((name,raw))
  s.clear();s.update({'type':'image','src':url_prefix.rstrip('/')+'/'+name,'alt':'原文公式或示意图'})
 for name,raw in pending:
  media_output.mkdir(parents=True,exist_ok=True);destination=media_output/name
  if not destination.exists():destination.write_bytes(raw)
 return result,None

def enrich(questions,source,media_output,url_prefix='math-media/'):
 output=copy.deepcopy(questions);groups=collections.defaultdict(list);issues=[];changed=[];fields=collections.Counter();stats=[]
 for index,q in enumerate(output):
  if pathlib.PurePosixPath(q.get('sourcePath','')).suffix.lower()=='.docx':groups[q['sourcePath']].append(index)
 for path,indices in groups.items():
  source_path=(source/path).resolve()
  try:source_path.relative_to(source.resolve())
  except ValueError:issues.append({'sourcePath':path,'reason':'unsafe-source-path'});continue
  if not source_path.is_file():issues.append({'sourcePath':path,'reason':'missing-source-docx','questionCount':len(indices)});continue
  try:document=parse_docx(source_path)
  except Exception as e:issues.append({'sourcePath':path,'reason':'docx-parse-error','detail':str(e)});continue
  stats.append({'sourcePath':path,**document['stats']})
  if not document['stats']['math'] and not document['stats']['images']:continue
  index=RichIndex(document);stem_spans={i:index.locate(output[i]['stem']) for i in indices};starts=sorted(s[0] for s in stem_spans.values() if s)
  with zipfile.ZipFile(source_path) as archive:
   for i in indices:
    q=output[i];before=False;stem_span=stem_spans[i]
    if not stem_span:
     issues.append({'id':q['id'],'sourcePath':path,'field':'stem','reason':'no-unique-exact-match'});continue
    following=next((s for s in starts if s>stem_span[0]),len(index.text));region_end=min(following,stem_span[1]+12000)
    def apply(field,target,key,value,span=None):
     nonlocal before
     if not value:return
     selected=span if span is not None else index.locate(value,stem_span[0],region_end)
     if selected is None:
      # A long answer may reside in an answer section; only a unique exact match is accepted.
      if field=='answer' and len(normalized(value))>=12:selected=index.locate(value)
      if selected is None:issues.append({'id':q['id'],'sourcePath':path,'field':field,'reason':'no-unique-exact-match'});return
     rich,reason=index.select(selected)
     if reason:
      if reason!='plain-text-only':issues.append({'id':q['id'],'sourcePath':path,'field':field,'reason':reason})
      return
     rich,reason=materialize(rich,document,archive,media_output,url_prefix)
     if reason:issues.append({'id':q['id'],'sourcePath':path,'field':field,'reason':reason});return
     target[key]=rich;fields[field]+=1;before=True
    apply('stem',q,'stemRich',q['stem'],stem_span)
    for o in q.get('options',[]):apply('option',o,'rich',o['text'],index.locate_option(o['text'],o['label'],stem_span[1],region_end))
    if q.get('answer'):apply('answer',q,'answerRich',q['answer'])
    if before:changed.append(q['id'])
 # Assert immutable identity and original semantic fields across every record.
 for old,new in zip(questions,output):
  assert old['id']==new['id'] and old['stem']==new['stem'] and old.get('answer')==new.get('answer')
  assert [(o['label'],o['text']) for o in old.get('options',[])]==[(o['label'],o['text']) for o in new.get('options',[])]
 report={'schemaVersion':1,'questionCount':len(output),'docxQuestionCount':sum(map(len,groups.values())),'enrichedQuestionCount':len(changed),'enrichedFields':dict(fields),'changedQuestionIds':changed,'originalIdsAndTextUnchanged':True,'documents':stats,'issues':issues,'issueCounts':dict(collections.Counter(x['reason'] for x in issues)),'notes':['只接受规范化空白和字符宽度后的唯一原文匹配，不猜测图片公式。','原id、stem、answer、选项标签和文本保持不变；只增加rich字段。','无法渲染的媒体、部分公式范围、缺失对象保留原文并记入报告。']}
 return output,report

def main():
 p=argparse.ArgumentParser();p.add_argument('--questions',required=True,type=pathlib.Path);p.add_argument('--source',required=True,type=pathlib.Path);p.add_argument('--media-output',required=True,type=pathlib.Path);p.add_argument('--url-prefix',default='math-media/');p.add_argument('--output',required=True,type=pathlib.Path);p.add_argument('--report',required=True,type=pathlib.Path);p.add_argument('--allow-in-place',action='store_true');a=p.parse_args()
 if a.questions.resolve()==a.output.resolve() and not a.allow_in_place:raise SystemExit('Use a distinct --output or explicitly --allow-in-place.')
 questions=json.loads(a.questions.read_text(encoding='utf-8'));updated,report=enrich(questions,a.source,a.media_output,a.url_prefix)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(updated,ensure_ascii=False,indent=2),encoding='utf-8');a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:report[k] for k in ('questionCount','docxQuestionCount','enrichedQuestionCount','enrichedFields','originalIdsAndTextUnchanged','issueCounts')},ensure_ascii=False))
if __name__=='__main__':main()
