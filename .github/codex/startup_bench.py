import json, statistics, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from pyrite.config import KBConfig
from tests._world import build_world
root = Path(sys.argv[2]).resolve()
world = build_world(root, kbs=[KBConfig(name="demo", path=root / "kb")], rest=False)
try:
    world.add_entry("demo", "---\nid: startup-entry\ntitle: StartupNeedle\ntype: note\n---\nStartupNeedle body.\n")
    out = {"phase": sys.argv[1], "platform": sys.platform, "python": sys.version.split()[0]}
    with world.pointed():
        for name, args in [("help", ["--help"]), ("search", ["search", "StartupNeedle", "-k", "demo", "--format", "json"])]:
            values=[]
            for _ in range(5):
                start=time.perf_counter()
                result=subprocess.run([sys.executable,"-c","from pyrite.cli import main; main()",*args],capture_output=True,text=True,timeout=30)
                values.append(time.perf_counter()-start)
                assert result.returncode==0,result.stderr
                assert ("Usage" if name=="help" else "startup-entry") in result.stdout,result.stdout
            out[name]={"median_seconds":statistics.median(values),"samples_seconds":values}
    print(json.dumps(out))
finally:
    world.close()
