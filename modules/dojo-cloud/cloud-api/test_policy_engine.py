import datetime
import unittest

import policy
import policy_engine as pe

CG = pe.CG
RG = pe.RG
SUB = "SUB"
NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
ASSIGN_PREFIX = "/subscriptions/SUB/providers/Microsoft.Authorization/policyAssignments/"
DEF_PREFIX = "/providers/Microsoft.Authorization/policyDefinitions/"


def cond(field, op, value):
    return {"field": field, op: value}


def defn(slug, rule, effect="deny", params=None, mode="All", details=None, display=None):
    then = {"effect": effect}
    if details is not None:
        then["details"] = details
    return {"id": DEF_PREFIX + slug, "name": slug, "properties": {
        "displayName": display or slug, "policyType": "Custom", "mode": mode,
        "parameters": params or {}, "policyRule": {"if": rule, "then": then}}}


def pset(slug, members, params=None):
    return {"id": DEF_PREFIX + slug, "name": slug, "properties": {
        "displayName": slug, "parameters": params or {}, "policyDefinitions": members}}


def assignment(name, target, scope="/", **props):
    p = {"policyDefinitionId": target["id"], "scope": scope}
    p.update(props)
    return {"id": ASSIGN_PREFIX + name, "name": name, "properties": p}


def lookup_of(*items):
    table = {i["id"]: i for i in items}
    return table.get


def cgres(tags=None, props=None, name="ci-x", location="canadacentral", rg="rg1"):
    return pe.resource_view("containerGroup", name, location, tags, props, SUB, rg)


def rgres(name="rg1", location="canadacentral", tags=None):
    return pe.resource_view("resourceGroup", name, location, tags, {}, SUB, "-")


def containers(*cps):
    return {"containers": [{"name": f"c{i}", "properties": cp} for i, cp in enumerate(cps)]}


def run(res, defs, assignments=None, **kw):
    """evaluate_write for one or more definitions each assigned at '/' (or the given assignments)."""
    defs = defs if isinstance(defs, (list, tuple)) else [defs]
    if assignments is None:
        assignments = [assignment(f"a{i}", d) for i, d in enumerate(defs)]
    return pe.evaluate_write(res, assignments, lookup_of(*defs), now=NOW, **kw)


def denies(rule, res, params=None, supplied=None):
    d = defn("d", rule, params=params)
    a = assignment("a", d, parameters=supplied or {})
    return bool(pe.evaluate_write(res, [a], lookup_of(d), now=NOW).denied)


class OperatorTests(unittest.TestCase):
    def hit(self, field, op, value, res=None):
        return denies(cond(field, op, value), res or cgres(tags={"env": "Dev", "n": 5, "empty": ""}))

    def test_equals_notequals_case_insensitive(self):
        self.assertTrue(self.hit("tags.env", "equals", "dev"))
        self.assertFalse(self.hit("tags.env", "equals", "prod"))
        self.assertTrue(self.hit("tags.env", "notEquals", "prod"))
        self.assertFalse(self.hit("tags.env", "notEquals", "DEV"))

    def test_equals_does_not_confuse_bool_and_int(self):
        res = cgres(tags={"flag": True})
        self.assertTrue(self.hit("tags.flag", "equals", True, res))
        self.assertFalse(self.hit("tags.flag", "equals", 1, res))

    def test_in_notin(self):
        self.assertTrue(self.hit("tags.env", "in", ["dev", "test"]))
        self.assertFalse(self.hit("tags.env", "in", ["prod"]))
        self.assertTrue(self.hit("tags.env", "notIn", ["prod"]))
        self.assertFalse(self.hit("tags.env", "notIn", ["DEV"]))

    def test_inexact_is_case_sensitive(self):
        self.assertFalse(self.hit("tags.env", "inExact", ["dev"]))
        self.assertTrue(self.hit("tags.env", "inExact", ["Dev"]))
        res = cgres(tags={"n": 1})
        self.assertFalse(self.hit("tags.n", "inExact", [True], res))

    def test_in_needs_array(self):
        with self.assertRaises(pe.PolicyDefinitionError):
            self.hit("tags.env", "in", "dev")

    def test_like_notlike(self):
        self.assertTrue(self.hit("tags.env", "like", "d*"))
        self.assertTrue(self.hit("tags.env", "like", "*EV"))
        self.assertTrue(self.hit("tags.env", "like", "D*v"))
        self.assertFalse(self.hit("tags.env", "like", "e*"))
        self.assertFalse(self.hit("tags.env", "like", "de"))
        self.assertTrue(self.hit("tags.env", "notLike", "x*"))
        self.assertFalse(self.hit("tags.env", "notLike", "d*"))

    def test_like_treats_regex_chars_literally(self):
        res = cgres(tags={"v": "a.b"})
        self.assertTrue(self.hit("tags.v", "like", "a.b", res))
        self.assertFalse(self.hit("tags.v", "like", "a?b", res))
        self.assertFalse(self.hit("tags.v", "like", "a.b", cgres(tags={"v": "aXb"})))

    def test_contains_notcontains(self):
        self.assertTrue(self.hit("tags.env", "contains", "E"))
        self.assertFalse(self.hit("tags.env", "contains", "z"))
        self.assertTrue(self.hit("tags.env", "notContains", "z"))
        self.assertFalse(self.hit("tags.env", "notContains", "ev"))

    def test_contains_on_tags_object_checks_keys(self):
        self.assertTrue(self.hit("tags", "contains", "ENV"))
        self.assertFalse(self.hit("tags", "contains", "owner"))

    def test_exists(self):
        self.assertTrue(self.hit("tags.env", "exists", "true"))
        self.assertTrue(self.hit("tags.env", "exists", True))
        self.assertFalse(self.hit("tags.env", "exists", False))
        self.assertTrue(self.hit("tags.nope", "exists", "false"))
        self.assertFalse(self.hit("tags.nope", "exists", "true"))
        self.assertTrue(self.hit("tags.empty", "exists", "true"))

    def test_isblank(self):
        self.assertTrue(self.hit("tags.empty", "isBlank", "true"))
        self.assertTrue(self.hit("tags.nope", "isBlank", "true"))
        self.assertFalse(self.hit("tags.env", "isBlank", "true"))
        self.assertTrue(self.hit("tags.env", "isBlank", "false"))
        self.assertTrue(self.hit("tags.empty", "isBlank", False) is False)
        self.assertTrue(self.hit("tags.blank", "isBlank", "true", cgres(tags={"blank": "   "})))

    def test_ordering_numbers(self):
        self.assertTrue(self.hit("tags.n", "less", 6))
        self.assertFalse(self.hit("tags.n", "less", 5))
        self.assertTrue(self.hit("tags.n", "lessOrEquals", 5))
        self.assertFalse(self.hit("tags.n", "lessOrEquals", 4))
        self.assertTrue(self.hit("tags.n", "greater", 4))
        self.assertFalse(self.hit("tags.n", "greater", 5))
        self.assertTrue(self.hit("tags.n", "greaterOrEquals", 5))
        self.assertFalse(self.hit("tags.n", "greaterOrEquals", 6))

    def test_ordering_numeric_strings_compare_as_numbers(self):
        res = cgres(tags={"n": "10"})
        self.assertTrue(self.hit("tags.n", "greater", 9, res))

    def test_ordering_strings_and_mismatch(self):
        self.assertTrue(self.hit("tags.env", "less", "ZZZ"))
        self.assertTrue(self.hit("tags.env", "greater", "a"))
        # a missing value or a mixed pair is simply false for every ordering operator
        for op in ("less", "lessOrEquals", "greater", "greaterOrEquals"):
            self.assertFalse(self.hit("tags.nope", op, 1), op)
            self.assertFalse(self.hit("tags.env", op, 1), op)

    def test_ordering_bool_is_not_a_number(self):
        res = cgres(tags={"b": True})
        self.assertFalse(self.hit("tags.b", "less", 5, res))

    def test_basic_fields_case_insensitive_names(self):
        self.assertTrue(denies(cond("LOCATION", "equals", "CanadaCentral"), cgres()))
        self.assertTrue(denies(cond("type", "equals", CG.upper()), cgres()))
        self.assertTrue(denies(cond("name", "like", "ci-*"), cgres()))
        self.assertTrue(denies(cond("id", "contains", "/resourceGroups/rg1/"), cgres()))


class LogicalTests(unittest.TestCase):
    T = cond("location", "equals", "canadacentral")
    F = cond("location", "equals", "mars")

    def test_allof(self):
        self.assertTrue(denies({"allOf": [self.T, self.T]}, cgres()))
        self.assertFalse(denies({"allOf": [self.T, self.F]}, cgres()))

    def test_anyof(self):
        self.assertTrue(denies({"anyOf": [self.F, self.T]}, cgres()))
        self.assertFalse(denies({"anyOf": [self.F, self.F]}, cgres()))

    def test_not(self):
        self.assertTrue(denies({"not": self.F}, cgres()))
        self.assertFalse(denies({"not": self.T}, cgres()))

    def test_nesting(self):
        rule = {"allOf": [self.T, {"anyOf": [self.F, {"not": self.F}]}]}
        self.assertTrue(denies(rule, cgres()))
        rule = {"allOf": [self.T, {"not": {"anyOf": [self.F, self.T]}}]}
        self.assertFalse(denies(rule, cgres()))


class ArrayAliasTests(unittest.TestCase):
    IMG = CG + "/containers[*].image"
    PORT = CG + "/containers[*].ports[*].port"
    ENVC = CG + "/containers[*].environmentVariableCount"

    def test_all_elements_must_match(self):
        res = cgres(props=containers({"image": "a:1"}, {"image": "a:2"}))
        self.assertTrue(denies(cond(self.IMG, "like", "a:*"), res))
        res = cgres(props=containers({"image": "a:1"}, {"image": "b:2"}))
        self.assertFalse(denies(cond(self.IMG, "like", "a:*"), res))

    def test_not_turns_all_into_some_fail(self):
        rule = {"not": cond(self.IMG, "like", "a:*")}
        self.assertTrue(denies(rule, cgres(props=containers({"image": "a:1"}, {"image": "b:2"}))))
        self.assertFalse(denies(rule, cgres(props=containers({"image": "a:1"}, {"image": "a:2"}))))

    def test_empty_and_missing_arrays_are_vacuously_true(self):
        for props in ({"containers": []}, {}):
            res = cgres(props=props)
            self.assertTrue(denies(cond(self.IMG, "equals", "anything"), res), props)
        # nested arrays: no ports anywhere
        res = cgres(props=containers({"image": "a:1"}))
        self.assertTrue(denies(cond(self.PORT, "equals", 12345), res))

    def test_empty_array_exists_is_false(self):
        res = cgres(props={"containers": []})
        self.assertFalse(denies(cond(self.IMG, "exists", "true"), res))
        self.assertTrue(denies(cond(self.IMG, "exists", "false"), res))

    def test_nested_array_flattens(self):
        res = cgres(props=containers({"ports": [{"port": 80}, {"port": 81}]}, {"ports": [{"port": 80}]}))
        self.assertFalse(denies(cond(self.PORT, "equals", 80), res))
        self.assertTrue(denies(cond(self.PORT, "less", 90), res))

    def test_ip_ports_alias(self):
        res = cgres(props={"ipAddress": {"ports": [{"port": 80}, {"port": 443}]}})
        self.assertTrue(denies(cond(CG + "/ipAddress.ports[*].port", "in", [80, 443]), res))
        self.assertFalse(denies(cond(CG + "/ipAddress.ports[*].port", "in", [80]), res))

    def test_environment_variable_count(self):
        res = cgres(props=containers({"environmentVariables": [{"name": "A"}, {"name": "B"}]}, {}))
        self.assertFalse(denies(cond(self.ENVC, "equals", 2), res))  # second container has 0
        self.assertTrue(denies(cond(self.ENVC, "lessOrEquals", 2), res))
        self.assertTrue(denies(cond(self.ENVC, "greater", -1), res))

    def test_scalar_aliases(self):
        res = cgres(props={"osType": "Linux", "ipAddress": {"type": "Public", "dnsNameLabel": "abc"}})
        self.assertTrue(denies(cond(CG + "/osType", "equals", "linux"), res))
        self.assertTrue(denies(cond(CG + "/ipAddress.type", "equals", "public"), res))
        self.assertTrue(denies(cond(CG + "/ipAddress.dnsNameLabel", "equals", "ABC"), res))
        self.assertFalse(denies(cond(CG + "/ipAddress.dnsNameLabel", "exists", "false"), res))

    def test_memory_alias_matches_any_case(self):
        res = cgres(props=containers({"resources": {"requests": {"memoryInGB": 0.5, "cpu": 0.1}}}))
        self.assertTrue(denies(cond(CG + "/containers[*].resources.requests.memoryinGB", "equals", 0.5), res))
        self.assertTrue(denies(cond(CG + "/containers[*].resources.requests.cpu", "equals", 0.1), res))

    def test_unknown_alias_raises_at_eval(self):
        with self.assertRaises(pe.PolicyDefinitionError):
            denies(cond(CG + "/nonsense", "equals", 1), cgres())


class TagFieldTests(unittest.TestCase):
    def test_three_spellings_agree(self):
        res = cgres(tags={"Owner": "sam"})
        for fld in ("tags['owner']", 'tags["OWNER"]', "tags.owner", "TAGS.Owner"):
            self.assertTrue(denies(cond(fld, "equals", "SAM"), res), fld)
            self.assertTrue(denies(cond(fld, "exists", "true"), res), fld)

    def test_missing_tag(self):
        res = cgres(tags={"a": "b"})
        for fld in ("tags['x']", "tags.x"):
            self.assertTrue(denies(cond(fld, "exists", "false"), res), fld)

    def test_tags_object_exists_means_non_empty(self):
        self.assertTrue(denies(cond("tags", "exists", "true"), cgres(tags={"a": "b"})))
        self.assertTrue(denies(cond("tags", "exists", "false"), cgres(tags={})))

    def test_tag_with_dot_in_name_needs_brackets(self):
        res = cgres(tags={"a.b": "v"})
        self.assertTrue(denies(cond("tags['a.b']", "equals", "v"), res))
        self.assertTrue(pe.validate_definition(defn("d", cond("tags.a.b", "equals", "v"))))

    def test_resource_view_tags(self):
        self.assertEqual(cgres(tags=None)["tags"], {})
        with self.assertRaises(TypeError):
            cgres(tags=["x"])
        with self.assertRaises(ValueError):
            pe.resource_view("nope", "n", "l", {}, {}, SUB, "rg")

    def test_resource_view_ids(self):
        self.assertEqual(rgres("rg9")["id"], "/subscriptions/SUB/resourceGroups/rg9")
        self.assertEqual(rgres()["type"], RG)
        self.assertEqual(cgres()["id"], f"/subscriptions/SUB/resourceGroups/rg1/providers/{CG}/ci-x")


class ParameterTests(unittest.TestCase):
    def test_default_value_used(self):
        vals, errs = pe.resolve_parameters({"p": {"type": "String", "defaultValue": "x"}}, {})
        self.assertEqual((vals, errs), ({"p": "x"}, []))

    def test_supplied_overrides_default_both_shapes(self):
        decl = {"p": {"type": "String", "defaultValue": "x"}}
        self.assertEqual(pe.resolve_parameters(decl, {"p": {"value": "y"}})[0], {"p": "y"})
        self.assertEqual(pe.resolve_parameters(decl, {"p": "z"})[0], {"p": "z"})

    def test_type_defaults_to_string(self):
        self.assertEqual(pe.resolve_parameters({"p": {}}, {"p": "s"})[1], [])
        self.assertTrue(pe.resolve_parameters({"p": {}}, {"p": 5})[1])

    def test_missing_without_default(self):
        _, errs = pe.resolve_parameters({"p": {"type": "String"}}, {})
        self.assertEqual(len(errs), 1)
        self.assertIn("'p'", errs[0])

    def test_unknown_supplied(self):
        _, errs = pe.resolve_parameters({}, {"ghost": {"value": 1}})
        self.assertEqual(len(errs), 1)
        self.assertIn("'ghost'", errs[0])

    def test_type_errors(self):
        bad = {"String": 5, "Array": "a", "Integer": 1.5, "Float": "1.0", "Boolean": "true", "Object": []}
        for t, v in bad.items():
            _, errs = pe.resolve_parameters({"p": {"type": t}}, {"p": {"value": v}})
            self.assertEqual(len(errs), 1, t)
            self.assertIn(f"type {t}", errs[0])

    def test_type_accepts(self):
        good = {"String": "a", "Array": [1], "Integer": 3, "Float": 3, "Boolean": False, "Object": {}}
        for t, v in good.items():
            self.assertEqual(pe.resolve_parameters({"p": {"type": t}}, {"p": {"value": v}})[1], [], t)
        self.assertEqual(pe.resolve_parameters({"p": {"type": "Float"}}, {"p": 0.5})[1], [])

    def test_bool_is_not_integer_or_float(self):
        for t in ("Integer", "Float"):
            self.assertTrue(pe.resolve_parameters({"p": {"type": t}}, {"p": True})[1], t)

    def test_allowed_values(self):
        decl = {"p": {"type": "String", "allowedValues": ["A", "b"]}}
        self.assertEqual(pe.resolve_parameters(decl, {"p": "a"})[1], [])  # case-insensitive
        _, errs = pe.resolve_parameters(decl, {"p": "c"})
        self.assertEqual(len(errs), 1)
        self.assertIn("allowed values", errs[0])
        self.assertIn("'c'", errs[0])

    def test_default_value_is_also_checked(self):
        decl = {"p": {"type": "Integer", "defaultValue": "oops"}}
        self.assertTrue(pe.resolve_parameters(decl, {})[1])

    def test_errors_accumulate(self):
        decl = {"a": {"type": "Integer"}, "b": {"type": "String"}}
        _, errs = pe.resolve_parameters(decl, {"a": "x", "ghost": 1})
        self.assertEqual(len(errs), 3)

    def test_expression_substitution(self):
        decl = {"limit": {"type": "Integer"}}
        rule = cond("tags.n", "greater", "[parameters('limit')]")
        self.assertTrue(denies(rule, cgres(tags={"n": 7}), decl, {"limit": {"value": 5}}))
        self.assertFalse(denies(rule, cgres(tags={"n": 7}), decl, {"limit": {"value": 9}}))

    def test_expression_is_whole_string_only(self):
        decl = {"p": {"type": "String", "defaultValue": "dev"}}
        rule = cond("tags.env", "equals", "x-[parameters('p')]")
        self.assertFalse(denies(rule, cgres(tags={"env": "x-dev"}), decl))

    def test_undefined_parameter_in_expression_raises(self):
        with self.assertRaises(pe.PolicyDefinitionError):
            denies(cond("tags.n", "greater", "[parameters('nope')]"), cgres(tags={"n": 1}))

    def test_bad_supplied_value_makes_expand_raise(self):
        d = defn("d", cond("name", "equals", "x"), params={"p": {"type": "Integer"}})
        a = assignment("a", d, parameters={"p": {"value": "str"}})
        with self.assertRaises(pe.PolicyDefinitionError) as cm:
            pe.expand_assignment(a, lookup_of(d))
        self.assertIn("type Integer", str(cm.exception))

    def test_missing_definition_makes_expand_raise(self):
        a = {"id": ASSIGN_PREFIX + "a", "name": "a", "properties": {"policyDefinitionId": DEF_PREFIX + "gone"}}
        with self.assertRaises(pe.PolicyDefinitionError):
            pe.expand_assignment(a, lookup_of())

    def test_effect_parameter(self):
        decl = {"effect": {"type": "String", "defaultValue": "audit", "allowedValues": ["audit", "deny"]}}
        d = defn("d", cond("name", "equals", "ci-x"), effect="[parameters('effect')]", params=decl)
        out = pe.evaluate_write(cgres(), [assignment("a", d)], lookup_of(d), now=NOW)
        self.assertEqual((len(out.denied), len(out.audited)), (0, 1))
        a = assignment("a", d, parameters={"effect": {"value": "deny"}})
        out = pe.evaluate_write(cgres(), [a], lookup_of(d), now=NOW)
        self.assertEqual((len(out.denied), len(out.audited)), (1, 0))


class EffectTests(unittest.TestCase):
    HIT = cond("name", "equals", "ci-x")
    MISS = cond("name", "equals", "other")

    def test_deny(self):
        out = run(cgres(), defn("d", self.HIT, "deny"))
        self.assertEqual(len(out.denied), 1)
        v = out.denied[0]
        self.assertEqual((v.effect, v.enforced, v.definitionName), ("deny", True, "d"))
        self.assertEqual(out.audited, [])
        self.assertIn("ci-x", v.reason)

    def test_no_match_no_violation(self):
        out = run(cgres(), defn("d", self.MISS, "deny"))
        self.assertEqual((out.denied, out.audited, out.modified), ([], [], []))

    def test_audit_does_not_deny(self):
        out = run(cgres(), defn("d", self.HIT, "audit"))
        self.assertEqual(out.denied, [])
        self.assertEqual(len(out.audited), 1)
        self.assertEqual((out.audited[0].effect, out.audited[0].enforced), ("audit", False))

    def test_effect_case_insensitive(self):
        self.assertEqual(len(run(cgres(), defn("d", self.HIT, "Deny")).denied), 1)
        self.assertEqual(len(run(cgres(), defn("d", self.HIT, "AUDIT")).audited), 1)

    def test_disabled(self):
        out = run(cgres(), defn("d", self.HIT, "disabled"))
        self.assertEqual((out.denied, out.audited, out.modified), ([], [], []))

    def test_unknown_effect_is_ignored_at_evaluation(self):
        out = run(cgres(), defn("d", self.HIT, "explode"))
        self.assertEqual((out.denied, out.audited), ([], []))

    def test_modify_add_or_replace(self):
        ops = [{"operation": "addOrReplace", "field": "tags['env']", "value": "dev"}]
        d = defn("m", cond("type", "equals", CG), "modify", details={"operations": ops})
        res = cgres(tags={"owner": "s"})
        out = run(res, d)
        self.assertEqual(out.resource["tags"], {"owner": "s", "env": "dev"})
        self.assertEqual(out.modified, ["addOrReplace tags['env']"])
        self.assertEqual(res["tags"], {"owner": "s"})  # input untouched
        out = run(cgres(tags={"env": "prod"}), d)
        self.assertEqual(out.resource["tags"]["env"], "dev")
        out = run(cgres(tags={"env": "DEV"}), d)  # already equal ignoring case: nothing to do
        self.assertEqual(out.modified, [])
        self.assertEqual(out.resource["tags"]["env"], "DEV")

    def test_modify_keeps_existing_key_spelling(self):
        ops = [{"operation": "addOrReplace", "field": "tags['env']", "value": "dev"}]
        d = defn("m", cond("type", "equals", CG), "modify", details={"operations": ops})
        out = run(cgres(tags={"ENV": "prod"}), d)
        self.assertEqual(out.resource["tags"], {"ENV": "dev"})

    def test_modify_add_does_not_replace(self):
        ops = [{"operation": "add", "field": "tags.env", "value": "dev"}]
        d = defn("m", cond("type", "equals", CG), "modify", details={"operations": ops})
        self.assertEqual(run(cgres(tags={"env": "prod"}), d).resource["tags"], {"env": "prod"})
        self.assertEqual(run(cgres(tags={}), d).resource["tags"], {"env": "dev"})

    def test_modify_remove(self):
        ops = [{"operation": "remove", "field": "tags['secret']"}]
        d = defn("m", cond("type", "equals", CG), "modify", details={"operations": ops})
        out = run(cgres(tags={"secret": "x", "a": "b"}), d)
        self.assertEqual(out.resource["tags"], {"a": "b"})
        self.assertEqual(out.modified, ["remove tags['secret']"])
        self.assertEqual(run(cgres(tags={"a": "b"}), d).modified, [])

    def test_modify_only_when_condition_holds(self):
        ops = [{"operation": "add", "field": "tags.env", "value": "dev"}]
        d = defn("m", cond("name", "equals", "nope"), "modify", details={"operations": ops})
        self.assertEqual(run(cgres(), d).resource["tags"], {})

    def test_append_adds_only_missing_tags(self):
        details = [{"field": "tags['owner']", "value": "me"}, {"field": "tags['env']", "value": "dev"}]
        d = defn("ap", cond("type", "equals", CG), "append", details=details)
        out = run(cgres(tags={"OWNER": "you"}), d)
        self.assertEqual(out.resource["tags"], {"OWNER": "you", "env": "dev"})
        self.assertEqual(out.modified, ["append tags['env']"])

    def test_modify_runs_before_deny_sees_changed_resource(self):
        ops = [{"operation": "add", "field": "tags.env", "value": "dev"}]
        m = defn("m", cond("type", "equals", CG), "modify", details={"operations": ops})
        require = defn("req", cond("tags.env", "exists", "false"), "deny")
        # order of assignment does not matter: modify always goes first
        out = run(cgres(tags={}), [require, m])
        self.assertEqual(out.denied, [])
        out = run(cgres(tags={}), [m, require])
        self.assertEqual(out.denied, [])
        self.assertEqual(out.resource["tags"], {"env": "dev"})

    def test_modify_param_substitution_in_value(self):
        decl = {"v": {"type": "String", "defaultValue": "dev"}}
        ops = [{"operation": "add", "field": "tags.env", "value": "[parameters('v')]"}]
        d = defn("m", cond("type", "equals", CG), "modify", params=decl, details={"operations": ops})
        a = assignment("a", d, parameters={"v": {"value": "qa"}})
        out = pe.evaluate_write(cgres(tags={}), [a], lookup_of(d), now=NOW)
        self.assertEqual(out.resource["tags"], {"env": "qa"})

    def test_message_on_violation(self):
        d = defn("d", self.HIT)
        a = assignment("a", d, nonComplianceMessage="Nope.", displayName="Shown")
        v = pe.evaluate_write(cgres(), [a], lookup_of(d), now=NOW).denied[0]
        self.assertEqual((v.message, v.assignmentDisplayName, v.assignmentName), ("Nope.", "Shown", "a"))

    def test_messages_list_by_reference(self):
        d = defn("d", self.HIT)
        a = assignment("a", d, nonComplianceMessages=[
            {"message": "for other", "policyDefinitionReferenceId": "other"}, {"message": "generic"}])
        v = pe.evaluate_write(cgres(), [a], lookup_of(d), now=NOW).denied[0]
        self.assertEqual(v.message, "generic")

    def test_display_name_fallbacks(self):
        d = defn("slug", self.HIT, display="Def Display")
        v = run(cgres(), d).denied[0]
        self.assertEqual(v.assignmentDisplayName, "Def Display")
        self.assertEqual(v.displayName, "Def Display")


class EnforcementAndScopeTests(unittest.TestCase):
    HIT = cond("type", "equals", CG)

    def test_do_not_enforce_deny_is_audited_only(self):
        d = defn("d", self.HIT)
        a = assignment("a", d, enforcementMode="DoNotEnforce")
        out = pe.evaluate_write(cgres(), [a], lookup_of(d), now=NOW)
        self.assertEqual(out.denied, [])
        self.assertEqual(len(out.audited), 1)
        self.assertFalse(out.audited[0].enforced)

    def test_do_not_enforce_modify_changes_nothing(self):
        ops = [{"operation": "add", "field": "tags.env", "value": "dev"}]
        d = defn("m", self.HIT, "modify", details={"operations": ops})
        a = assignment("a", d, enforcementMode="DoNotEnforce")
        out = pe.evaluate_write(cgres(tags={}), [a], lookup_of(d), now=NOW)
        self.assertEqual(out.resource["tags"], {})
        self.assertEqual(out.modified, [])
        self.assertEqual(len(out.audited), 1)
        self.assertTrue(out.audited[0].reason.startswith("would "))

    def test_default_enforcement_mode_enforces(self):
        d = defn("d", self.HIT)
        a = assignment("a", d, enforcementMode="Default")
        self.assertEqual(len(pe.evaluate_write(cgres(), [a], lookup_of(d), now=NOW).denied), 1)

    def scoped(self, scope, res=None, **props):
        d = defn("d", self.HIT)
        a = assignment("a", d, scope=scope, **props)
        return bool(pe.evaluate_write(res or cgres(), [a], lookup_of(d), now=NOW).denied)

    def test_subscription_scope_covers_everything_under_it(self):
        self.assertTrue(self.scoped("/subscriptions/SUB"))
        self.assertTrue(self.scoped("/subscriptions/SUB/"))
        self.assertFalse(self.scoped("/subscriptions/OTHER"))

    def test_root_scope(self):
        self.assertTrue(self.scoped("/"))

    def test_resource_group_scope(self):
        self.assertTrue(self.scoped("/subscriptions/SUB/resourceGroups/rg1"))
        self.assertFalse(self.scoped("/subscriptions/SUB/resourceGroups/rg2"))

    def test_resource_group_scope_is_not_a_string_prefix_match(self):
        self.assertFalse(self.scoped("/subscriptions/SUB/resourceGroups/rg1", cgres(rg="rg10")))

    def test_scope_match_is_case_insensitive(self):
        self.assertTrue(self.scoped("/SUBSCRIPTIONS/sub/RESOURCEGROUPS/RG1"))
        self.assertTrue(self.scoped("/subscriptions/sub"))

    def test_rg_scope_applies_to_the_rg_itself_but_not_siblings(self):
        d = defn("d", cond("type", "equals", RG))
        a = assignment("a", d, scope="/subscriptions/SUB/resourceGroups/rg1")
        look = lookup_of(d)
        self.assertTrue(pe.evaluate_write(rgres("rg1"), [a], look, now=NOW).denied)
        self.assertFalse(pe.evaluate_write(rgres("rg2"), [a], look, now=NOW).denied)

    def test_subscription_scope_applies_to_rg_resource(self):
        d = defn("d", cond("type", "equals", RG))
        a = assignment("a", d, scope="/subscriptions/SUB")
        self.assertTrue(pe.evaluate_write(rgres(), [a], lookup_of(d), now=NOW).denied)

    def test_not_scopes_exclude(self):
        sub = "/subscriptions/SUB"
        self.assertFalse(self.scoped(sub, notScopes=[sub + "/resourceGroups/rg1"]))
        self.assertTrue(self.scoped(sub, notScopes=[sub + "/resourceGroups/rg2"]))
        self.assertFalse(self.scoped(sub, notScopes=[sub.upper() + "/RESOURCEGROUPS/RG1"]))

    def test_not_scopes_on_resource_itself(self):
        rid = cgres()["id"]
        self.assertFalse(self.scoped("/subscriptions/SUB", notScopes=[rid]))

    def test_assignment_missing_scope_defaults_to_everywhere(self):
        d = defn("d", self.HIT)
        a = {"id": ASSIGN_PREFIX + "a", "name": "a", "properties": {"policyDefinitionId": d["id"]}}
        self.assertTrue(pe.evaluate_write(cgres(), [a], lookup_of(d), now=NOW).denied)

    def test_assignment_that_cannot_expand_is_skipped(self):
        d = defn("d", self.HIT, params={"p": {"type": "Integer"}})
        a = assignment("a", d, parameters={"p": {"value": "bad"}})
        out = pe.evaluate_write(cgres(), [a], lookup_of(d), now=NOW)
        self.assertEqual((out.denied, out.audited), ([], []))


class ExemptionTests(unittest.TestCase):
    HIT = cond("type", "equals", CG)

    def setUp(self):
        self.d = defn("d", self.HIT)
        self.a = assignment("a", self.d)

    def ex(self, **props):
        base = {"policyAssignmentId": self.a["id"], "scope": "/subscriptions/SUB"}
        base.update(props)
        return {"id": "/subscriptions/SUB/providers/Microsoft.Authorization/policyExemptions/e", "name": "e",
                "properties": base}

    def denied(self, *exemptions, res=None):
        return pe.evaluate_write(res or cgres(), [self.a], lookup_of(self.d), exemptions, now=NOW).denied

    def test_no_exemption(self):
        self.assertEqual(len(self.denied()), 1)

    def test_active_exemption(self):
        self.assertEqual(self.denied(self.ex()), [])

    def test_exemption_with_future_expiry_is_active(self):
        self.assertEqual(self.denied(self.ex(expiresOn="2026-06-01T00:00:00Z")), [])

    def test_expired_exemption(self):
        self.assertEqual(len(self.denied(self.ex(expiresOn="2025-12-31T23:59:59Z"))), 1)

    def test_expiry_equal_to_now_is_expired(self):
        self.assertEqual(len(self.denied(self.ex(expiresOn="2026-01-01T00:00:00Z"))), 1)

    def test_naive_expiry_is_treated_as_utc(self):
        self.assertEqual(len(self.denied(self.ex(expiresOn="2025-12-31T00:00:00"))), 1)
        self.assertEqual(self.denied(self.ex(expiresOn="2026-01-02T00:00:00")), [])

    def test_unparseable_expiry_does_not_expire(self):
        self.assertEqual(self.denied(self.ex(expiresOn="soon")), [])

    def test_other_assignment_exemption_ignored(self):
        other = self.ex(policyAssignmentId=ASSIGN_PREFIX + "other")
        self.assertEqual(len(self.denied(other)), 1)

    def test_assignment_id_match_is_case_insensitive(self):
        self.assertEqual(self.denied(self.ex(policyAssignmentId=self.a["id"].upper())), [])

    def test_exemption_scope_must_cover_resource(self):
        self.assertEqual(self.denied(self.ex(scope="/subscriptions/SUB/resourceGroups/rg1")), [])
        self.assertEqual(len(self.denied(self.ex(scope="/subscriptions/SUB/resourceGroups/rg2"))), 1)
        self.assertEqual(len(self.denied(self.ex(scope="/subscriptions/SUB/resourceGroups/RG10"))), 1)

    def test_scope_inferred_from_exemption_id(self):
        e = self.ex()
        del e["properties"]["scope"]
        e["id"] = "/subscriptions/SUB/resourceGroups/rg2/providers/Microsoft.Authorization/policyExemptions/e"
        self.assertEqual(len(self.denied(e)), 1)
        e["id"] = "/subscriptions/SUB/resourceGroups/rg1/providers/Microsoft.Authorization/policyExemptions/e"
        self.assertEqual(self.denied(e), [])

    def test_exemption_without_assignment_id_is_ignored(self):
        e = self.ex()
        del e["properties"]["policyAssignmentId"]
        self.assertEqual(len(self.denied(e)), 1)

    def test_reference_ids_on_non_set_never_match(self):
        self.assertEqual(len(self.denied(self.ex(policyDefinitionReferenceIds=["d"]))), 1)

    def test_exemption_scoped_by_reference_ids(self):
        d1 = defn("d1", cond("type", "equals", CG))
        d2 = defn("d2", cond("type", "equals", CG))
        s = pset("s", [{"policyDefinitionId": d1["id"], "policyDefinitionReferenceId": "r1"},
                       {"policyDefinitionId": d2["id"], "policyDefinitionReferenceId": "r2"}])
        a = assignment("sa", s)
        look = lookup_of(s, d1, d2)
        e = {"id": "x", "properties": {"policyAssignmentId": a["id"], "scope": "/subscriptions/SUB",
                                       "policyDefinitionReferenceIds": ["R1"]}}
        out = pe.evaluate_write(cgres(), [a], look, [e], now=NOW)
        self.assertEqual([v.referenceId for v in out.denied], ["r2"])
        # no reference ids: the whole set is exempt
        e["properties"].pop("policyDefinitionReferenceIds")
        self.assertEqual(pe.evaluate_write(cgres(), [a], look, [e], now=NOW).denied, [])

    def test_exempt_modify_is_skipped(self):
        ops = [{"operation": "add", "field": "tags.env", "value": "dev"}]
        d = defn("m", self.HIT, "modify", details={"operations": ops})
        a = assignment("ma", d)
        e = {"id": "x", "properties": {"policyAssignmentId": a["id"], "scope": "/"}}
        out = pe.evaluate_write(cgres(tags={}), [a], lookup_of(d), [e], now=NOW)
        self.assertEqual(out.resource["tags"], {})


class PolicySetTests(unittest.TestCase):
    def test_set_expands_members_with_reference_ids(self):
        d1 = defn("d1", cond("name", "equals", "x"))
        d2 = defn("d2", cond("name", "equals", "y"))
        s = pset("s", [{"policyDefinitionId": d1["id"], "policyDefinitionReferenceId": "first"},
                       {"policyDefinitionId": d2["id"]}])
        out = pe.expand_assignment(assignment("a", s), lookup_of(s, d1, d2))
        self.assertEqual([(d["name"], ref) for d, _p, ref in out], [("d1", "first"), ("d2", "d2")])

    def test_non_set_has_no_reference_id(self):
        d = defn("d", cond("name", "equals", "x"))
        self.assertEqual(pe.expand_assignment(assignment("a", d), lookup_of(d))[0][2], None)

    def test_set_params_flow_down_to_members(self):
        member = defn("m", {"not": {"field": "location", "in": "[parameters('locs')]"}},
                      params={"locs": {"type": "Array"}})
        s = pset("s", [{"policyDefinitionId": member["id"], "policyDefinitionReferenceId": "loc",
                        "parameters": {"locs": {"value": "[parameters('setLocs')]"}}}],
                 params={"setLocs": {"type": "Array", "defaultValue": ["canadacentral"]}})
        look = lookup_of(s, member)
        a = assignment("a", s)
        self.assertEqual(pe.evaluate_write(cgres(), [a], look, now=NOW).denied, [])
        out = pe.evaluate_write(cgres(location="eastus"), [a], look, now=NOW)
        self.assertEqual([v.referenceId for v in out.denied], ["loc"])
        a = assignment("a", s, parameters={"setLocs": {"value": ["eastus"]}})
        self.assertEqual(pe.evaluate_write(cgres(location="eastus"), [a], look, now=NOW).denied, [])
        self.assertEqual(len(pe.evaluate_write(cgres(), [a], look, now=NOW).denied), 1)

    def test_literal_member_params_and_unwrapped_values(self):
        member = defn("m", cond("tags.n", "greater", "[parameters('lim')]"), params={"lim": {"type": "Integer"}})
        s = pset("s", [{"policyDefinitionId": member["id"], "parameters": {"lim": 3}}])
        out = pe.evaluate_write(cgres(tags={"n": 4}), [assignment("a", s)], lookup_of(s, member), now=NOW)
        self.assertEqual(len(out.denied), 1)

    def test_member_param_type_error_surfaces(self):
        member = defn("m", cond("name", "equals", "x"), params={"lim": {"type": "Integer"}})
        s = pset("s", [{"policyDefinitionId": member["id"], "parameters": {"lim": {"value": "str"}}}])
        with self.assertRaises(pe.PolicyDefinitionError):
            pe.expand_assignment(assignment("a", s), lookup_of(s, member))

    def test_set_level_error_surfaces(self):
        s = pset("s", [], params={"p": {"type": "Integer"}})
        with self.assertRaises(pe.PolicyDefinitionError):
            pe.expand_assignment(assignment("a", s, parameters={"p": {"value": "x"}}), lookup_of(s))

    def test_missing_member_raises(self):
        s = pset("s", [{"policyDefinitionId": DEF_PREFIX + "ghost"}])
        with self.assertRaises(pe.PolicyDefinitionError) as cm:
            pe.expand_assignment(assignment("a", s), lookup_of(s))
        self.assertIn("ghost", str(cm.exception))

    def test_members_have_independent_effects(self):
        d1 = defn("d1", cond("name", "equals", "ci-x"), "deny")
        d2 = defn("d2", cond("name", "equals", "ci-x"), "audit")
        d3 = defn("d3", cond("name", "equals", "ci-x"), "disabled")
        s = pset("s", [{"policyDefinitionId": d.get("id")} for d in (d1, d2, d3)])
        out = pe.evaluate_write(cgres(), [assignment("a", s)], lookup_of(s, d1, d2, d3), now=NOW)
        self.assertEqual([v.definitionName for v in out.denied], ["d1"])
        self.assertEqual([v.definitionName for v in out.audited], ["d2"])


class ModeTests(unittest.TestCase):
    RULE = cond("name", "like", "*")

    def test_all_mode_evaluates_resource_groups(self):
        self.assertEqual(len(run(rgres(), defn("d", self.RULE, mode="All")).denied), 1)

    def test_indexed_mode_skips_resource_groups(self):
        self.assertEqual(run(rgres(), defn("d", self.RULE, mode="Indexed")).denied, [])

    def test_indexed_mode_evaluates_container_groups(self):
        self.assertEqual(len(run(cgres(), defn("d", self.RULE, mode="Indexed")).denied), 1)

    def test_indexed_in_compliance_has_no_row_for_rg(self):
        d = defn("d", self.RULE, mode="Indexed")
        rows = pe.compliance([rgres(), cgres()], [assignment("a", d)], lookup_of(d), now=NOW)
        self.assertEqual([r["resourceId"] for r in rows], [cgres()["id"]])


class ValidateTests(unittest.TestCase):
    def errs(self, rule, effect="deny", **kw):
        return pe.validate_definition(defn("d", rule, effect, **kw))

    def test_valid_definition(self):
        self.assertEqual(self.errs(cond("location", "in", ["a"])), [])
        self.assertEqual(pe.validate_definition(defn("d", {"allOf": [cond("tags.x", "exists", True)]})), [])

    def test_all_builtins_validate(self):
        for d in policy.BUILTIN_DEFINITIONS.values():
            self.assertEqual(pe.validate_definition(d), [], d["name"])

    def test_not_an_object(self):
        self.assertEqual(pe.validate_definition([]), ["definition must be an object"])

    def test_bad_alias_is_named(self):
        errs = self.errs(cond(CG + "/containers[*].imag", "equals", "x"))
        self.assertEqual(len(errs), 1)
        self.assertIn("unknown field alias", errs[0])
        self.assertIn(CG + "/containers[*].imag", errs[0])

    def test_bad_alias_inside_nested_condition_names_path(self):
        errs = self.errs({"allOf": [cond("location", "equals", "x"), {"not": cond("bogus", "equals", 1)}]})
        self.assertEqual(len(errs), 1)
        self.assertIn("'bogus'", errs[0])
        self.assertIn("allOf[1]", errs[0])

    def test_bad_operator_is_named(self):
        errs = self.errs({"field": "location", "equalz": "x"})
        self.assertTrue(any("unknown operator 'equalz'" in e for e in errs))

    def test_no_operator(self):
        errs = self.errs({"field": "location"})
        self.assertTrue(any("no operator" in e and "location" in e for e in errs))

    def test_two_operators(self):
        errs = self.errs({"field": "location", "equals": "a", "notEquals": "b"})
        self.assertEqual(len(errs), 1)
        self.assertIn("equals", errs[0])
        self.assertIn("notEquals", errs[0])

    def test_missing_field(self):
        self.assertTrue(any("needs a 'field'" in e for e in self.errs({"equals": "x"})))

    def test_condition_must_be_object(self):
        self.assertTrue(any("must be an object" in e for e in self.errs("nope")))

    def test_logical_operators_cannot_mix(self):
        errs = self.errs({"allOf": [cond("location", "equals", "x")], "field": "name"})
        self.assertTrue(any("cannot be combined" in e for e in errs))

    def test_empty_allof_anyof(self):
        self.assertTrue(any("non-empty array" in e for e in self.errs({"allOf": []})))
        self.assertTrue(any("anyOf" in e and "non-empty" in e for e in self.errs({"anyOf": "x"})))

    def test_unknown_effect_is_named(self):
        errs = self.errs(cond("location", "equals", "x"), effect="explode")
        self.assertEqual(len(errs), 1)
        self.assertIn("unknown effect 'explode'", errs[0])

    def test_effect_parameter_checks_allowed_and_default(self):
        decl = {"e": {"type": "String", "allowedValues": ["deny", "nuke"], "defaultValue": "audit"}}
        errs = self.errs(cond("location", "equals", "x"), "[parameters('e')]", params=decl)
        self.assertEqual(len(errs), 1)
        self.assertIn("'nuke'", errs[0])

    def test_missing_effect_and_rule(self):
        d = {"properties": {"policyRule": {"if": cond("location", "equals", "x"), "then": {}}}}
        self.assertEqual(pe.validate_definition(d), ["policyRule.then.effect is missing"])
        self.assertEqual(pe.validate_definition({"properties": {}}), ["policyRule.if is missing"])

    def test_bad_mode(self):
        errs = self.errs(cond("location", "equals", "x"), mode="Everything")
        self.assertEqual(len(errs), 1)
        self.assertIn("'Everything'", errs[0])

    def test_bad_parameter_type(self):
        errs = self.errs(cond("location", "equals", "x"), params={"p": {"type": "Number"}})
        self.assertTrue(any("parameter 'p'" in e for e in errs))

    def test_undeclared_parameter_use(self):
        errs = self.errs(cond("location", "equals", "[parameters('ghost')]"))
        self.assertEqual(errs, ["parameters('ghost') is used but not declared"])

    def test_modify_needs_operations(self):
        self.assertTrue(any("needs then.details.operations" in e
                            for e in self.errs(cond("location", "equals", "x"), "modify")))

    def test_modify_bad_operation_and_field(self):
        ops = [{"operation": "explode", "field": "tags.a", "value": 1}]
        errs = self.errs(cond("location", "equals", "x"), "modify", details={"operations": ops})
        self.assertTrue(any("addOrReplace, add or remove" in e for e in errs))
        ops = [{"operation": "add", "field": "location", "value": "x"}]
        errs = self.errs(cond("location", "equals", "x"), "modify", details={"operations": ops})
        self.assertTrue(any("only change tags, not 'location'" in e for e in errs))

    def test_modify_value_required_except_remove(self):
        ops = [{"operation": "add", "field": "tags.a"}]
        errs = self.errs(cond("location", "equals", "x"), "modify", details={"operations": ops})
        self.assertTrue(any("needs a value" in e and "tags.a" in e for e in errs))
        ops = [{"operation": "remove", "field": "tags.a"}]
        self.assertEqual(self.errs(cond("location", "equals", "x"), "modify", details={"operations": ops}), [])

    def test_append_rules(self):
        c = cond("location", "equals", "x")
        self.assertTrue(any("append needs" in e for e in self.errs(c, "append")))
        errs = self.errs(c, "append", details=[{"field": "location", "value": "x"}])
        self.assertTrue(any("only add tags, not 'location'" in e for e in errs))
        errs = self.errs(c, "append", details=[{"field": "tags.a"}])
        self.assertTrue(any("needs a field and a value" in e for e in errs))
        self.assertEqual(self.errs(c, "append", details=[{"field": "tags.a", "value": "v"}]), [])

    def test_modify_via_effect_parameter_is_also_checked(self):
        decl = {"e": {"type": "String", "allowedValues": ["modify"]}}
        errs = self.errs(cond("location", "equals", "x"), "[parameters('e')]", params=decl)
        self.assertTrue(any("modify needs" in e for e in errs))


class ComplianceTests(unittest.TestCase):
    def rows(self, resources, defs, assignments=None, ex=()):
        defs = defs if isinstance(defs, (list, tuple)) else [defs]
        if assignments is None:
            assignments = [assignment(f"a{i}", d) for i, d in enumerate(defs)]
        return pe.compliance(resources, assignments, lookup_of(*defs), ex, now=NOW)

    def test_compliant_and_noncompliant(self):
        d = defn("d", cond("tags.env", "exists", "false"))
        good, bad = cgres(tags={"env": "x"}, name="ci-good"), cgres(tags={}, name="ci-bad")
        rows = {r["resourceId"].rsplit("/", 1)[1]: r for r in self.rows([good, bad], d)}
        self.assertEqual(rows["ci-good"]["state"], "Compliant")
        self.assertEqual(rows["ci-good"]["reason"], "")
        self.assertEqual(rows["ci-bad"]["state"], "NonCompliant")
        self.assertIn("tag 'env' does not exist", rows["ci-bad"]["reason"])

    def test_row_shape(self):
        d = defn("d", cond("name", "equals", "ci-x"))
        a = assignment("a", d)
        (row,) = self.rows([cgres()], d, [a])
        self.assertEqual(set(row), {"assignmentId", "definitionId", "referenceId", "resourceId", "state", "reason"})
        self.assertEqual((row["assignmentId"], row["definitionId"], row["referenceId"]),
                         (a["id"], d["id"], None))

    def test_audit_is_noncompliant_too(self):
        d = defn("d", cond("name", "equals", "ci-x"), "audit")
        self.assertEqual(self.rows([cgres()], d)[0]["state"], "NonCompliant")

    def test_exempt(self):
        d = defn("d", cond("name", "equals", "ci-x"))
        a = assignment("a", d)
        e = {"id": "x", "properties": {"policyAssignmentId": a["id"], "scope": "/"}}
        row = self.rows([cgres()], d, [a], [e])[0]
        self.assertEqual((row["state"], row["reason"]), ("Exempt", "an exemption applies"))

    def test_expired_exemption_is_noncompliant(self):
        d = defn("d", cond("name", "equals", "ci-x"))
        a = assignment("a", d)
        e = {"id": "x", "properties": {"policyAssignmentId": a["id"], "scope": "/",
                                       "expiresOn": "2020-01-01T00:00:00Z"}}
        self.assertEqual(self.rows([cgres()], d, [a], [e])[0]["state"], "NonCompliant")

    def test_exempt_even_when_condition_would_not_match(self):
        d = defn("d", cond("name", "equals", "nope"))
        a = assignment("a", d)
        e = {"id": "x", "properties": {"policyAssignmentId": a["id"], "scope": "/"}}
        self.assertEqual(self.rows([cgres()], d, [a], [e])[0]["state"], "Exempt")

    def test_disabled_and_out_of_scope_have_no_rows(self):
        self.assertEqual(self.rows([cgres()], defn("d", cond("name", "equals", "ci-x"), "disabled")), [])
        d = defn("d", cond("name", "equals", "ci-x"))
        a = assignment("a", d, scope="/subscriptions/OTHER")
        self.assertEqual(self.rows([cgres()], d, [a]), [])

    def test_do_not_enforce_still_reports_noncompliant(self):
        d = defn("d", cond("name", "equals", "ci-x"))
        a = assignment("a", d, enforcementMode="DoNotEnforce")
        self.assertEqual(self.rows([cgres()], d, [a])[0]["state"], "NonCompliant")

    def test_modify_and_append_states(self):
        ops = [{"operation": "add", "field": "tags.env", "value": "dev"}]
        m = defn("m", cond("type", "equals", CG), "modify", details={"operations": ops})
        ap = defn("ap", cond("type", "equals", CG), "append", details=[{"field": "tags.owner", "value": "o"}])
        res = cgres(tags={"env": "x"})
        by = {r["definitionId"]: r for r in self.rows([res], [m, ap])}
        self.assertEqual(by[m["id"]]["state"], "Compliant")  # tag already there: nothing to change
        self.assertEqual(by[ap["id"]]["state"], "NonCompliant")
        self.assertEqual(by[ap["id"]]["reason"], "would append tags['owner']")

    def test_set_rows_carry_reference_ids(self):
        d1 = defn("d1", cond("name", "equals", "ci-x"))
        d2 = defn("d2", cond("name", "equals", "zzz"))
        s = pset("s", [{"policyDefinitionId": d1["id"], "policyDefinitionReferenceId": "r1"},
                       {"policyDefinitionId": d2["id"], "policyDefinitionReferenceId": "r2"}])
        rows = pe.compliance([cgres()], [assignment("a", s)], lookup_of(s, d1, d2), now=NOW)
        self.assertEqual([(r["referenceId"], r["state"]) for r in rows],
                         [("r1", "NonCompliant"), ("r2", "Compliant")])


class ReasonTests(unittest.TestCase):
    def reason(self, rule, res=None):
        out = run(res or cgres(tags={"env": "dev"}), defn("d", rule))
        return out.denied[0].reason

    def test_simple_reason(self):
        self.assertEqual(self.reason(cond("tags.env", "equals", "dev")), "tag 'env' is 'dev'")

    def test_reason_names_the_value_then_the_rule(self):
        self.assertEqual(self.reason({"not": cond("location", "in", ["x", "y"])}, cgres(location="z")),
                         "location is 'z', which is not in [x, y]")
        self.assertEqual(self.reason(cond("tags.env", "notEquals", "prod"), cgres(tags={"team": "a"})), "tag 'env' is not set, which is not prod")

    def test_negated_reason_flips_wording(self):
        self.assertIn("is not in", self.reason({"not": cond("location", "in", ["x", "y"])}))
        self.assertIn("[x, y]", self.reason({"not": cond("location", "in", ["x", "y"])}))

    def test_allof_joins_with_and_and_not_flips_to_or(self):
        t = cond("name", "equals", "ci-x")
        self.assertIn(" and ", self.reason({"allOf": [t, t]}))
        self.assertIn(" or ", self.reason({"not": {"allOf": [cond("name", "notEquals", "ci-x"),
                                                              cond("name", "notEquals", "ci-x")]}}))


class BuiltinPolicyTests(unittest.TestCase):
    """Each built-in through the public checks. Only location and tags raise a 403 RequestDisallowedByPolicy; the
    legacy per-limit checks (image, cpu, memory, ports, env vars) keep their historical 400 codes."""

    def cg(self, **over):
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

    def err(self, **over):
        try:
            policy.check_container_group(**self.cg(**over))
        except policy.PolicyError as e:
            return e
        return None

    def mutate(self, fn):
        a = self.cg()
        fn(a["props"]["containers"][0]["properties"], a["props"])
        return a["props"]

    def assertPolicy403(self, e, name, policy_name):
        self.assertIsNotNone(e)
        self.assertEqual(e.status, 403)
        self.assertEqual(e.code, "RequestDisallowedByPolicy")
        self.assertEqual(e.target, name)
        self.assertEqual(e.policy, policy_name)

    def test_baseline_allowed(self):
        self.assertIsNone(self.err())

    # allowed locations
    def test_locations_allow_both_regions(self):
        for loc in ("canadacentral", "canadaeast"):
            self.assertIsNone(self.err(location=loc), loc)
            policy.check_resource_group("rg-hello-dev", loc, {"owner": "s", "env": "dev"})

    def test_locations_deny_container_group(self):
        self.assertPolicy403(self.err(location="eastus"), "ci-hello-dev", "Allowed locations")

    def test_locations_use_exact_match(self):
        # the built-in uses inExact (case-sensitive), unlike most engine comparisons
        e = self.err(location="CanadaCentral")
        self.assertPolicy403(e, "ci-hello-dev", "Allowed locations")

    def test_locations_deny_resource_group(self):
        with self.assertRaises(policy.PolicyError) as cm:
            policy.check_resource_group("rg-hello-dev", "westus", {"owner": "s", "env": "dev"})
        self.assertPolicy403(cm.exception, "rg-hello-dev", "Allowed locations")

    # required tags
    def test_tag_owner(self):
        self.assertIsNone(self.err(tags={"owner": "s", "env": "dev"}))
        self.assertPolicy403(self.err(tags={"env": "dev"}), "ci-hello-dev", "Require tag 'owner'")

    def test_tag_env(self):
        self.assertPolicy403(self.err(tags={"owner": "s"}), "ci-hello-dev", "Require tag 'env'")

    def test_tag_blank_value_is_denied(self):
        self.assertPolicy403(self.err(tags={"owner": "", "env": "dev"}), "ci-hello-dev", "Require tag 'owner'")
        self.assertPolicy403(self.err(tags={"owner": "s", "env": "  "}), "ci-hello-dev", "Require tag 'env'")

    def test_tag_names_case_insensitive(self):
        self.assertIsNone(self.err(tags={"OWNER": "s", "Env": "dev"}))

    def test_tags_none_denied(self):
        self.assertPolicy403(self.err(tags=None), "ci-hello-dev", "Require tag 'owner'")

    def test_tags_on_resource_group(self):
        policy.check_resource_group("rg-hello-dev", "canadacentral", {"owner": "s", "env": "dev"})
        with self.assertRaises(policy.PolicyError) as cm:
            policy.check_resource_group("rg-hello-dev", "canadacentral", {"owner": "s"})
        self.assertPolicy403(cm.exception, "rg-hello-dev", "Require tag 'env'")
        with self.assertRaises(policy.PolicyError) as cm:
            policy.check_resource_group("rg-hello-dev", "canadacentral", None)
        self.assertEqual((cm.exception.status, cm.exception.code), (403, "RequestDisallowedByPolicy"))

    def test_check_tags_alone(self):
        policy.check_tags("ci-x", {"owner": "s", "env": "dev"})
        with self.assertRaises(policy.PolicyError) as cm:
            policy.check_tags("ci-x", {"env": "dev"})
        self.assertPolicy403(cm.exception, "ci-x", "Require tag 'owner'")

    def test_tag_error_body_shape(self):
        body = self.err(tags={"env": "dev"}).body()["error"]
        self.assertEqual(body["code"], "RequestDisallowedByPolicy")
        self.assertEqual(body["target"], "ci-hello-dev")
        self.assertEqual(body["additionalInfo"][0]["info"]["policyDefinitionDisplayName"], "Require tag 'owner'")
        self.assertIn("was disallowed by policy", body["message"])

    # allowed images
    def test_images(self):
        for img in ("dojo/hello:1.0", "dojo/hello:2.0"):
            self.assertIsNone(self.err(props=self.mutate(lambda c, p: c.update(image=img))), img)
        e = self.err(props=self.mutate(lambda c, p: c.update(image="evil/miner:latest")))
        self.assertEqual((e.status, e.code), (400, "InvalidImage"))
        self.assertIn("evil/miner:latest", e.message)
        e = self.err(props=self.mutate(lambda c, p: c.update(image="DOJO/HELLO:1.0")))  # inExact
        self.assertEqual(e.code, "InvalidImage")

    # max cpu / memory
    def test_cpu(self):
        self.assertIsNone(self.err(props=self.mutate(lambda c, p: c["resources"]["requests"].update(cpu=0.1))))
        e = self.err(props=self.mutate(lambda c, p: c["resources"]["requests"].update(cpu=0.5)))
        self.assertEqual((e.status, e.code), (400, "InvalidResourceRequest"))

    def test_memory(self):
        self.assertIsNone(self.err(props=self.mutate(
            lambda c, p: c["resources"]["requests"].update(memoryInGB=0.0625))))
        e = self.err(props=self.mutate(lambda c, p: c["resources"]["requests"].update(memoryInGB=1)))
        self.assertEqual((e.status, e.code), (400, "InvalidResourceRequest"))

    # allowed ports
    def test_ports(self):
        self.assertIsNone(self.err())
        e = self.err(props=self.mutate(lambda c, p: c.update(ports=[{"port": 80}, {"port": 8080}])))
        self.assertEqual((e.status, e.code), (400, "InvalidRequestContent"))
        self.assertIn("8080", e.message)
        e = self.err(props=self.mutate(lambda c, p: p["ipAddress"].update(ports=[{"port": 22}])))
        self.assertEqual(e.code, "InvalidRequestContent")
        self.assertIn("22", e.message)

    # max env vars
    def test_env_vars(self):
        ok = [{"name": f"V{i}", "value": "x"} for i in range(10)]
        self.assertIsNone(self.err(props=self.mutate(lambda c, p: c.update(environmentVariables=ok))))
        many = [{"name": f"V{i}", "value": "x"} for i in range(11)]
        e = self.err(props=self.mutate(lambda c, p: c.update(environmentVariables=many)))
        self.assertEqual((e.status, e.code), (400, "InvalidRequestContent"))
        self.assertIn("10", e.message)

    # the declared contract of every built-in, straight through the engine
    def test_every_builtin_has_a_platform_assignment_that_expands(self):
        ids = {a["properties"]["policyDefinitionId"] for a in policy.PLATFORM_ASSIGNMENTS}
        self.assertEqual(ids, set(policy.BUILTIN_DEFINITIONS))
        for a in policy.PLATFORM_ASSIGNMENTS:
            (item,) = pe.expand_assignment(a, policy.builtin_lookup)
            self.assertIsNone(item[2])

    def test_check_with_assignments_builtin_denial_short_circuits(self):
        d = defn("aud", cond("name", "like", "*"), "audit")
        res = cgres(location="eastus", tags={"owner": "s", "env": "dev"})
        out = policy.check_with_assignments(res, [assignment("a", d)], lookup_of(d), now=NOW)
        self.assertEqual([v.definitionName for v in out.denied], ["dojo-allowed-locations"])
        self.assertEqual(out.audited, [])

    def test_check_with_assignments_student_policy_applies_after_builtins(self):
        d = defn("deny-name", cond("name", "equals", "ci-x"), "deny")
        res = cgres(tags={"owner": "s", "env": "dev"})
        out = policy.check_with_assignments(res, [assignment("a", d)], lookup_of(d), now=NOW)
        self.assertEqual([v.definitionName for v in out.denied], ["deny-name"])

    def test_check_with_assignments_student_modify_feeds_result(self):
        ops = [{"operation": "add", "field": "tags.env", "value": "dev"}]
        m = defn("m", cond("type", "equals", CG), "modify", details={"operations": ops})
        # built-ins run first on the unmodified resource, so a missing env tag is denied before modify runs
        out = policy.check_with_assignments(cgres(tags={"owner": "s"}), [assignment("a", m)], lookup_of(m), now=NOW)
        self.assertEqual([v.definitionName for v in out.denied], ["dojo-require-tag-env"])
        out = policy.check_with_assignments(cgres(tags={"owner": "s", "env": "x"}),
                                            [assignment("a", m)], lookup_of(m), now=NOW)
        self.assertEqual(out.denied, [])
        self.assertEqual(out.modified, [])

    def test_check_with_assignments_exemption_only_for_student_assignments(self):
        d = defn("deny-name", cond("name", "equals", "ci-x"), "deny")
        a = assignment("a", d)
        e = {"id": "x", "properties": {"policyAssignmentId": a["id"], "scope": "/"}}
        res = cgres(tags={"owner": "s", "env": "dev"})
        out = policy.check_with_assignments(res, [a], lookup_of(d), [e], now=NOW)
        self.assertEqual(out.denied, [])
        # an exemption naming a platform assignment is not honoured
        pa = policy.PLATFORM_ASSIGNMENTS[0]
        e2 = {"id": "x", "properties": {"policyAssignmentId": pa["id"], "scope": "/"}}
        out = policy.check_with_assignments(cgres(location="eastus", tags={"owner": "s", "env": "dev"}),
                                            [], lookup_of(), [e2], now=NOW)
        self.assertEqual(len(out.denied), 1)


if __name__ == "__main__":
    unittest.main()
