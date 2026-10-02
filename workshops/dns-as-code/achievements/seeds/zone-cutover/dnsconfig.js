// {user}.dojo.test: your own zone, same as ~/lab/my-zone (whichever repo you push last wins).
var PDNS = NewDnsProvider("powerdns", {
	"zone_kind": "Native",
	"soa_edit_api": "DEFAULT",
});
var REG = NewRegistrar("none");

D("{user}.dojo.test", REG,
	DnsProvider(PDNS),
	DefaultTTL(300),

	SOA("@", "ns1.dojo.test.", "hostmaster.dojo.test.", 3600, 600, 604800, 1440),
	NAMESERVER("ns1.dojo.test."),

	A("@", "203.0.113.10"),
	A("mail", "203.0.113.20"),
	A("app", "10.10.0.5"),
	A("www", "10.10.0.5"),
	TXT("@", "owner={user}"),
);
