import subprocess,sys,os,hashlib
# argv: runner.py <logpath> -- cmd...
log=sys.argv[1]; assert sys.argv[2]=='--'
cmd=sys.argv[3:]
p=subprocess.run(cmd,cwd=os.getcwd(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
b=p.stdout or b''
os.makedirs(os.path.dirname(os.path.abspath(log)),exist_ok=True)
open(log,'wb').write(b)
print('EXIT='+str(p.returncode))
print('LOG_BYTES='+str(len(b)))
print('LOG_SHA='+hashlib.sha256(b).hexdigest()[:12])
tail=b.decode('utf-8',errors='replace').splitlines()[-25:]
print(chr(10).join(tail))
