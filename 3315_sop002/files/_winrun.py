import subprocess,sys,os
os.chdir(r"E:\Python\Agent_1\work\clawhunt\join3315")
PY=sys.executable
steps=[["tools/gen.py"],["tools/verify.py"],["-m","pytest","tests","-q"],["tools/mutate.py"],["tools/build_docs.py"],["tools/make_zip.py"]]
for s in steps:
    print("=== RUN", " ".join(s), flush=True)
    r=subprocess.run([PY]+s, capture_output=True)
    out=(r.stdout+r.stderr).decode("utf-8","replace")
    print(out, flush=True)
    print("=== RC", r.returncode, flush=True)
    if r.returncode!=0:
        print("=== STOP", flush=True); break
