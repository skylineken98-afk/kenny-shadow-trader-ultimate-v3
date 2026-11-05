"""Encrypted pg_dump archives for a persistent backup volume. No credentials logged.
python -m kst_pro.backup backup|verify PATH|restore PATH --confirm-disposable-target
Use a separate database URL for restore tests. Backups contain private user data.
"""
import argparse,base64,io,os,secrets,subprocess,tempfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,unquote
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
MAGIC=b'KSTBACKUP1'

def key(env):
 raw=base64.b64decode(env.get('BACKUP_ENCRYPTION_KEY',''),validate=True)
 if len(raw)!=32:raise ValueError('Configure a base64-encoded 32-byte backup encryption key')
 return raw

def pg_env(env,restore=False):
 url=urlsplit(env.get('RESTORE_DATABASE_URL' if restore else 'DATABASE_URL',''))
 if url.scheme not in ('postgres','postgresql') or not url.hostname or not url.username or not url.path.strip('/'):raise ValueError('Configure a valid database URL')
 return {**os.environ,'PGHOST':url.hostname,'PGPORT':str(url.port or 5432),'PGUSER':unquote(url.username),'PGPASSWORD':unquote(url.password or ''),'PGDATABASE':url.path.lstrip('/'),'PGSSLMODE':'require'}

def decrypt(path,env):
 data=Path(path).read_bytes()
 if not data.startswith(MAGIC):raise ValueError('Not a KST backup')
 start=len(MAGIC);return AESGCM(key(env)).decrypt(data[start:start+12],data[start+12:],MAGIC)

def backup(env=os.environ):
 destination=Path(env.get('BACKUP_DIRECTORY','/backups'));destination.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryFile() as output:
  r=subprocess.run(['pg_dump','--format=custom','--no-owner','--no-acl'],env=pg_env(env),stdout=output,stderr=subprocess.DEVNULL,timeout=300)
  if r.returncode:raise RuntimeError('Database backup failed')
  size=output.tell()
  if size>256*1024*1024:raise ValueError('Backup exceeds this beta runner capacity')
  output.seek(0);plain=output.read()
 nonce=secrets.token_bytes(12);encrypted=MAGIC+nonce+AESGCM(key(env)).encrypt(nonce,plain,MAGIC)
 path=destination/('kst-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.kstenc')
 fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'wb') as f:f.write(encrypted)
 if decrypt(path,env)!=plain:raise RuntimeError('Backup verification failed')
 for old in sorted(destination.glob('kst-*.kstenc'))[:-max(2,int(env.get('BACKUP_KEEP','7')))]:old.unlink()
 return str(path)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['backup','verify','restore']);parser.add_argument('path',nargs='?');parser.add_argument('--confirm-disposable-target',action='store_true');args=parser.parse_args()
 if args.action=='backup':print(backup())
 else:
  plain=decrypt(args.path,os.environ)
  if args.action=='verify':print('Archive authentication passed. A restore test is still required.')
  else:
   if not args.confirm_disposable_target or os.getenv('RESTORE_DATABASE_URL')==os.getenv('DATABASE_URL'):raise SystemExit('Restore requires a different disposable target and explicit confirmation')
   result=subprocess.run(['pg_restore','--no-owner','--no-acl','--exit-on-error','--dbname',pg_env(os.environ,True)['PGDATABASE']],env=pg_env(os.environ,True),input=plain,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=300)
   if result.returncode:raise SystemExit('Restore failed; inspect the disposable target')
   print('Restore completed. Validate application data in the disposable target.')
