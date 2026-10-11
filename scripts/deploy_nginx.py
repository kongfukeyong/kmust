"""Add /kust/ to the two inspected server blocks, keeping timestamped backups."""
from pathlib import Path
import datetime,subprocess,shutil
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
paths=[Path('/etc/nginx/conf.d/news.conf'),Path('/etc/nginx/conf.d/news.kongfu.xyz.conf')]
snippet='''    # KUST study app - standalone static release
    location = /kust { return 301 /kust/; }
    location /kust/ {
        alias /opt/kust-study/current/public/;
        index index.html;
        autoindex off;
        add_header X-Content-Type-Options nosniff always;
        add_header Referrer-Policy strict-origin-when-cross-origin always;
        add_header Cache-Control "no-cache" always;
        gzip on;
        gzip_types application/json text/css application/javascript image/svg+xml;
    }

'''
changed=[]
for p in paths:
 text=p.read_text()
 if '# KUST study app' in text:continue
 marker='    location / {'
 if text.count(marker)!=1:raise SystemExit('Unexpected server config: '+str(p))
 backup=Path('/opt/kust-study/build')/(p.name+'.'+stamp+'.bak');shutil.copy2(p,backup)
 p.write_text(text.replace(marker,snippet+marker));changed.append((p,backup))
try:
 subprocess.run(['nginx','-t'],check=True)
 subprocess.run(['systemctl','reload','nginx'],check=True)
except Exception:
 for p,backup in changed:shutil.copy2(backup,p)
 raise
print('Deployment routes active: IP HTTP /kust/ and news.kongfu.xyz HTTPS /kust/')
