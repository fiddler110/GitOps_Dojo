"""Private CA + server certificate for the Dojo Cloud endpoints.

The CA key and server key stay in cloud-api's private data dir. Only the CA
certificate is copied to the shared cloud_pki volume, which terminals mount
read-only and trust (SSL_CERT_FILE).
"""
import os
import shutil
import subprocess

HOSTS = ("management.dojo.cloud", "login.dojo.cloud", "portal.dojo.cloud", "graph.dojo.cloud",
         "cloud-api", "localhost")


def _run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ensure(private_dir, shared_dir):
    os.makedirs(private_dir, exist_ok=True)
    ca_key, ca_pem = f"{private_dir}/ca.key", f"{private_dir}/ca.pem"
    key, crt = f"{private_dir}/server.key", f"{private_dir}/server.pem"
    if not (os.path.exists(ca_key) and os.path.exists(ca_pem)):
        _run("openssl", "req", "-x509", "-newkey", "rsa:3072", "-nodes", "-keyout", ca_key,
             "-out", ca_pem, "-days", "30", "-subj", "/CN=Dojo Cloud Training CA")
        os.chmod(ca_key, 0o600)
        for stale in (key, crt):
            if os.path.exists(stale):
                os.remove(stale)
    if not (os.path.exists(key) and os.path.exists(crt)):
        csr, ext = f"{private_dir}/server.csr", f"{private_dir}/server.ext"
        with open(ext, "w") as f:
            f.write("subjectAltName=" + ",".join(f"DNS:{h}" for h in HOSTS) + "\n")
            f.write("extendedKeyUsage=serverAuth\n")
        _run("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", csr,
             "-subj", "/CN=management.dojo.cloud")
        _run("openssl", "x509", "-req", "-in", csr, "-CA", ca_pem, "-CAkey", ca_key,
             "-CAcreateserial", "-out", crt, "-days", "30", "-extfile", ext)
        os.chmod(key, 0o600)
    os.makedirs(shared_dir, exist_ok=True)
    shutil.copyfile(ca_pem, f"{shared_dir}/dojo-cloud-ca.pem")
    os.chmod(f"{shared_dir}/dojo-cloud-ca.pem", 0o644)
    return crt, key
