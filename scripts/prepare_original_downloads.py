"""Build server-hosted original file bundles and add an attachment route."""
from pathlib import Path
import json,hashlib,zipfile,shutil,subprocess,datetime
root=Path('/opt/kust-study/releases/v1');public=root/'public';source=Path('/opt/kust-study/source-utf8/KUST--main')
resources=json.loads((public/'data/resources.json').read_text());downloads=public/'downloads';courses=downloads/'courses';courses.mkdir(exist_ok=True)
allzip=downloads/'kust-original-materials.zip';shutil.copy2('/opt/kust-study/build/kust.zip',allzip)
manifest={'all':{'url':'downloads/'+allzip.name,'count':len(resources),'size':allzip.stat().st_size},'courses':[]}
for course in sorted({r['course'] for r in resources if r['course']!='仓库说明'}):
 rows=[r for r in resources if r['course']==course];out=courses/(hashlib.sha256(course.encode()).hexdigest()[:16]+'.zip')
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
  for r in rows:z.write(source/r['sourcePath'],r['sourcePath'])
 manifest['courses'].append({'course':course,'url':'downloads/courses/'+out.name,'count':len(rows),'size':out.stat().st_size})
(public/'data/original-packages.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
snippet='''    # KUST original file downloads
    location /kust/original-files/ {
        alias /opt/kust-study/source-utf8/KUST--main/;
        autoindex off;
        add_header Content-Disposition "attachment" always;
        add_header X-Content-Type-Options nosniff always;
    }

'''
changed=[]
for name in ['news.conf','news.kongfu.xyz.conf']:
 p=Path('/etc/nginx/conf.d')/name;s=p.read_text()
 if '# KUST original file downloads' in s:continue
 marker='    # KUST study app - standalone static release'
 if s.count(marker)!=1:raise SystemExit('Unexpected nginx config')
 backup=Path('/opt/kust-study/build')/(name+'.originals-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.bak');shutil.copy2(p,backup);changed.append((p,backup));p.write_text(s.replace(marker,snippet+marker))
try:subprocess.run(['nginx','-t'],check=True);subprocess.run(['systemctl','reload','nginx'],check=True)
except Exception:
 for p,b in changed:shutil.copy2(b,p)
 raise
print('Original downloads ready:',len(resources),'files,',len(manifest['courses']),'course bundles,',allzip.stat().st_size,'bytes total archive')
