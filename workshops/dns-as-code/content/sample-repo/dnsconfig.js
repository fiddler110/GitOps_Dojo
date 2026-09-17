// DNS-as-Code lab: dnscontrol manages this zone's records, PowerDNS serves
// them. "powerdns" here must match the key in creds.json exactly - that's
// how dnscontrol looks up which API/credentials to talk to.
var PDNS = NewDnsProvider("powerdns", {
	"zone_kind": "Native",
	// Governs how PowerDNS bumps the SOA serial on API-driven edits (the
	// SOA record itself must still be declared explicitly below - see the
	// comment there for why).
	"soa_edit_api": "DEFAULT",
});

// PowerDNS isn't a registrar (it doesn't sell/delegate the domain) - this
// project only manages the zone's records, same reasoning as the real
// dns-as-code-template's `NewRegistrar("none")` with Cloudflare.
var REG = NewRegistrar("none");

// dojo.test uses the IETF-reserved .test TLD (RFC 2606) - guaranteed to
// never be a real, resolvable domain, so nothing here can collide with
// production DNS. One D(...) block per zone; dnscontrol operates on every
// block automatically, so adding a second zone later needs no other changes.
D("dojo.test", REG,
	DnsProvider(PDNS),
	DefaultTTL(300),

	// dnscontrol deletes PowerDNS's placeholder SOA on first push and
	// won't replace it unless one is declared here - an SOA-less zone
	// REFUSEs every query (confirmed against a live PowerDNS container,
	// not a hypothetical). NAMESERVER (not NS - dnscontrol reserves NS for
	// delegating a *subdomain*) declares this zone's own nameserver, which
	// `pdnsutil check-zone` also expects at the apex. The SOA's serial
	// number is managed automatically; it isn't a field here. Don't touch
	// either of these two lines as part of the lab exercises below.
	SOA("@", "ns1.dojo.test.", "hostmaster.dojo.test.", 3600, 600, 604800, 1440),
	NAMESERVER("ns1.dojo.test."),

	A("@", "203.0.113.10"),
	A("www", "203.0.113.10"),
	A("mail", "203.0.113.20"),
	CNAME("app", "dojo.test."),
	MX("@", 10, "mail.dojo.test."),
	TXT("@", "v=spf1 -all"),
	TXT("_dmarc", "v=DMARC1; p=reject; sp=reject; adkim=s; aspf=s;"),
);
