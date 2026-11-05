"""Run privately: python -m kst_options.generate_push_keys /private/key-directory.
Writes a base64 DER private key and browser applicationServerKey. Never commit them.
"""
import base64,os,sys
from pathlib import Path
def main(directory):
 from cryptography.hazmat.primitives.asymmetric import ec
 from cryptography.hazmat.primitives import serialization
 p=Path(directory);p.mkdir(parents=True,exist_ok=True)
 private=p/'vapid_private.txt';public=p/'vapid_public.txt'
 if private.exists() or public.exists():raise ValueError('Refusing to overwrite existing keys')
 key=ec.generate_private_key(ec.SECP256R1())
 secret=base64.urlsafe_b64encode(key.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())).decode().rstrip('=')
 pub=base64.urlsafe_b64encode(key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)).decode().rstrip('=')
 fd=os.open(private,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'w') as f:f.write(secret)
 public.write_text(pub)
 print('Keys saved privately. Configure VAPID_PRIVATE_KEY in Railway and VAPID_PUBLIC_KEY in Cloudflare. Do not share the private file.')
if __name__=='__main__':main(sys.argv[1])
