import os, subprocess, tempfile, threading, textwrap
import auth, server
from test_tfstate import TfState, A
class E(TfState):
    def test_e2e(self):
        port = self.httpd.server_address[1]
        env = {**os.environ, "TF_HTTP_USERNAME": auth.app_id(A), "TF_HTTP_PASSWORD": auth.client_secret(self.app.auth.key, A),
               "TF_IN_AUTOMATION": "1", "TF_CLI_ARGS": "-no-color"}
        tofu = "/tmp/claude-1000/-home-scott-Development-GitOps-Dojo/fb049c61-bac9-4a2e-b248-d2bdf36e6d87/scratchpad/s1/bin/tofu"
        cfg = textwrap.dedent(f'''
        terraform {{
        backend "http" {{
          address = "http://127.0.0.1:{port}/_dojo/tfstate/infra"
          lock_address = "http://127.0.0.1:{port}/_dojo/tfstate/infra"
          unlock_address = "http://127.0.0.1:{port}/_dojo/tfstate/infra"
          lock_method = "LOCK"
          unlock_method = "UNLOCK"
        }}
        }}
        resource "terraform_data" "x" {{ input = "hi" }}
        output "o" {{ value = terraform_data.x.output }}
        ''')
        def run(d, *a):
            r = subprocess.run([tofu, *a], cwd=d, env=env, capture_output=True, text=True, timeout=120)
            print(a, r.returncode, (r.stdout + r.stderr)[-400:]); return r
        d1, d2 = tempfile.mkdtemp(), tempfile.mkdtemp()
        for d in (d1, d2): open(d + "/main.tf", "w").write(cfg)
        self.assertEqual(run(d1, "init").returncode, 0)
        self.assertEqual(run(d1, "apply", "-auto-approve").returncode, 0)
        self.assertEqual(self.tf("GET", "infra")[0], 200)
        self.assertEqual(run(d2, "init").returncode, 0)
        r = run(d2, "output", "o"); self.assertIn("hi", r.stdout)
        self.assertEqual(self.tf("LOCK", "infra", b'{"ID":"held","Who":"other"}')[0], 200)
        r = run(d2, "apply", "-auto-approve", "-lock-timeout=0s"); self.assertNotEqual(r.returncode, 0); self.assertIn("lock", (r.stdout+r.stderr).lower())
        self.assertEqual(self.tf("UNLOCK", "infra")[0], 200)
        self.assertEqual(run(d2, "apply", "-auto-approve").returncode, 0)
