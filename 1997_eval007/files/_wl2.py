# -*- coding: utf-8 -*-
import subprocess,sys,os,datetime,hashlib
D=r"E:\Python\Agent_1\work\clawhunt\s1997"
os.chdir(D)
L=["# WINDOWS side verification log",
   "# host: DESKTOP-6BLPI5P  os: Windows 11  platform: win32",
   "# python: "+sys.version.split()[0],
   "# generated: "+datetime.datetime.now().isoformat(timespec="seconds"),""]
py=sys.executable
for c in [[py,"tools/verify.py"],
          [py,"-m","pytest","tests","-v","--no-header","-p","no:cacheprovider","-o","addopts="],
          [py,"tools/mutate.py"],[py,"tools/build_docs.py"]]:
    p=subprocess.run(c,capture_output=True,text=True,encoding="utf-8",errors="replace",cwd=D,timeout=2400)
    L.append("$ "+" ".join(c[1:])); L.append(p.stdout.rstrip())
    if p.stderr.strip(): L.append("[stderr] "+p.stderr.strip()[-400:])
    L.append("[rc=%d]"%p.returncode); L.append("")
L.append("=== perf.json generated on WINDOWS (1000 cases, worst case with 20 error hits) ===")
L.append(open(os.path.join(D,"docs","perf.json"),encoding="utf-8").read().strip())
L.append("")
L.append("=== checksums after running the whole suite ===")
sys.path.insert(0,D)
from tools.make_zip import verify_sums
n,bad=verify_sums(D); L.append("%d files checked, %d mismatches"%(n,len(bad)))
L.append("")
L.append("=== determinism: README.md/ACCEPTANCE.md regenerated on this host vs the copy shipped in the zip ===")
for rel in ["README.md","ACCEPTANCE.md"]:
    L.append("%s  %s"%(hashlib.sha256(open(os.path.join(D,rel),"rb").read()).hexdigest(),rel))
open(os.path.join(D,"verify_logs","WINDOWS_20261128.log"),"w",encoding="utf-8",newline="\n").write("\n".join(L)+"\n")
print("OK")
