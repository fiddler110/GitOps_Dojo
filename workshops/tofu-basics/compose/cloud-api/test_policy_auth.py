import unittest

import auth
import policy


def cg(**over):
    props = {
        "osType": "Linux",
        "containers": [{"name": "hello", "properties": {
            "image": "dojo/hello:1.0", "ports": [{"port": 80}],
            "environmentVariables": [{"name": "MESSAGE", "value": "hi"}],
            "resources": {"requests": {"cpu": 0.25, "memoryInGB": 0.125}}}}],
        "ipAddress": {"type": "Public", "ports": [{"port": 80}], "dnsNameLabel": "hello-student01"},
    }
    args = dict(name="ci-hello-dev", location="canadacentral", tags={"owner": "s", "env": "dev"},
                props=props, other_groups=0, dns_taken=lambda label: False)
    args.update(over)
    return args


def code(**over):
    try:
        policy.check_container_group(**cg(**over))
    except policy.PolicyError as e:
        return e.code
    return None


class PolicyTests(unittest.TestCase):
    def test_valid(self):
        self.assertIsNone(code())

    def test_missing_tag(self):
        self.assertEqual(code(tags={"env": "dev"}), "RequestDisallowedByPolicy")
        self.assertEqual(code(tags={"owner": "s"}), "RequestDisallowedByPolicy")
        self.assertEqual(code(tags={"owner": " ", "env": "dev"}), "RequestDisallowedByPolicy")

    def test_check_tags_public(self):
        with self.assertRaises(policy.PolicyError):
            policy.check_tags("x", {"owner": "a"})
        policy.check_tags("x", {"owner": "a", "env": "b"})

    def test_region(self):
        self.assertEqual(code(location="mars"), "RequestDisallowedByPolicy")

    def test_naming(self):
        self.assertEqual(code(name="hello"), "InvalidContainerGroupName")
        with self.assertRaises(policy.PolicyError) as cm:
            policy.check_resource_group("mygroup", "canadacentral", {"owner": "a", "env": "b"})
        self.assertEqual(cm.exception.code, "InvalidResourceGroupName")

    def test_quota(self):
        self.assertEqual(code(other_groups=2), "QuotaExceeded")
        self.assertIsNone(code(other_groups=1))

    def test_image_size_ports(self):
        p = cg()["props"]
        p["containers"][0]["properties"]["image"] = "nginx:latest"
        self.assertEqual(code(props=p), "InvalidImage")
        p = cg()["props"]
        p["containers"][0]["properties"]["resources"]["requests"]["cpu"] = 1
        self.assertEqual(code(props=p), "InvalidResourceRequest")
        p = cg()["props"]
        p["containers"][0]["properties"]["ports"] = [{"port": 22}]
        self.assertEqual(code(props=p), "InvalidRequestContent")

    def test_no_command_override_and_env_rules(self):
        p = cg()["props"]
        p["containers"][0]["properties"]["command"] = ["sh"]
        self.assertEqual(code(props=p), "InvalidRequestContent")
        for bad in ("PATH", "LD_PRELOAD", "1X", "A B"):
            p = cg()["props"]
            p["containers"][0]["properties"]["environmentVariables"] = [{"name": bad, "value": "x"}]
            self.assertEqual(code(props=p), "InvalidRequestContent", bad)

    def test_dns_label(self):
        self.assertEqual(code(dns_taken=lambda l: True), "DnsNameLabelInUse")
        p = cg()["props"]
        p["ipAddress"]["dnsNameLabel"] = "Bad_Label"
        self.assertEqual(code(props=p), "InvalidDnsNameLabel")


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.users = auth.roster({"STUDENT_PREFIX": "student", "STUDENT_COUNT": "3",
                                  "BOT_PREFIX": "testuser", "BOT_COUNT": "1",
                                  "FACILITATOR_USERNAME": "admin"})
        self.a = auth.Auth(b"k" * 32, self.users, "admin", "https://login/")

    def test_roster(self):
        self.assertEqual(self.users, ["student01", "student02", "student03", "testuser1", "admin"])

    def test_roster_naming_matches_the_engine(self):
        # students zero-padded (allocator STUDENT_IDS), bots not (allocator BOT_IDS, entrypoint printf '%d')
        users = auth.roster({"STUDENT_COUNT": "11", "BOT_COUNT": "12", "FACILITATOR_USERNAME": ""})
        self.assertEqual(users[:11], [f"student{n:02d}" for n in range(1, 12)])
        self.assertEqual(users[11:], [f"testuser{n}" for n in range(1, 13)])  # testuser9, testuser10, ...
        self.assertEqual(auth.roster({"BOT_PREFIX": "b", "BOT_COUNT": "10"})[-11:-1], [f"b{n}" for n in range(1, 11)])

    def test_distinct_subscriptions_and_secrets(self):
        self.assertNotEqual(auth.subscription_id("student01"), auth.subscription_id("student02"))
        self.assertNotEqual(auth.client_secret(b"k" * 32, "student01"),
                            auth.client_secret(b"k" * 32, "student02"))

    def test_client_auth(self):
        cid, sec = auth.app_id("student01"), auth.client_secret(b"k" * 32, "student01")
        self.assertEqual(self.a.authenticate_client(cid, sec), "student01")
        self.assertIsNone(self.a.authenticate_client(cid, auth.client_secret(b"k" * 32, "student02")))
        self.assertIsNone(self.a.authenticate_client(cid, "wrong"))
        self.assertIsNone(self.a.authenticate_client("nope", sec))

    def test_tokens(self):
        tok = self.a.issue_token("student02", "aud")
        self.assertEqual(self.a.verify_token(tok), "student02")
        h, b, s = tok.split(".")
        self.assertIsNone(self.a.verify_token(f"{h}.{b}.{s[:-2]}xx"))
        other = auth.Auth(b"z" * 32, self.users, "admin", "x")
        self.assertIsNone(other.verify_token(tok))
        self.assertIsNone(self.a.verify_token("garbage"))


if __name__ == "__main__":
    unittest.main()
