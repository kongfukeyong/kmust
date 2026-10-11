import argparse,hashlib,json,pathlib,io
import fitz
from PIL import Image

ap=argparse.ArgumentParser();ap.add_argument('--source',type=pathlib.Path,required=True);ap.add_argument('--public',type=pathlib.Path,required=True);args=ap.parse_args()
resources=json.loads((args.public/'data/resources.json').read_text())
thumbs=args.public/'thumbs';thumbs.mkdir(exist_ok=True)
hash_errors=[];made=0
for r in resources:
 p=args.source/r['sourcePath']
 raw=p.read_bytes();actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
 if actual!=r['sha']:hash_errors.append(r['sourcePath'])
 if r['status'].startswith('excluded'):continue
 out=thumbs/(r['id']+'.webp')
 try:
  if r['ext']=='pdf':
   with fitz.open(p) as d:
    page=d[0];pix=page.get_pixmap(matrix=fitz.Matrix(640/page.rect.width,640/page.rect.width),alpha=False);im=Image.open(io.BytesIO(pix.tobytes('png')))
  elif r['ext']=='jpg':im=Image.open(p);im.thumbnail((640,1000))
  else:continue
  im.convert('RGB').save(out,'WEBP',quality=75);r['thumbnail']='thumbs/'+out.name;made+=1
 except Exception as e:print('thumbnail skipped',r['id'],str(e)[:120])
if hash_errors:raise SystemExit('Repository integrity mismatch: '+repr(hash_errors))
(args.public/'data/resources.json').write_text(json.dumps(resources,ensure_ascii=False,indent=2),encoding='utf-8')
(args.public/'data/integrity.json').write_text(json.dumps({'filesVerified':len(resources),'hashAlgorithm':'Git blob SHA-1','mismatches':0,'thumbnails':made},indent=2))
print('Verified',len(resources),'files; created',made,'thumbnails')
