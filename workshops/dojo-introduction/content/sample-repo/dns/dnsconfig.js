// DNS as code: the zone is declared here, in git, and dnscontrol makes the
// server match it. This copy uses the NONE provider, so `dnscontrol check`
// and `preview` work anywhere and change nothing. The dns-as-code workshop
// pushes the same kind of file to PowerDNS.
var REG_NONE = NewRegistrar("none");
var DNS_NONE = NewDnsProvider("none");

D("tour.dojo.test", REG_NONE, DnsProvider(DNS_NONE),
  A("@", "192.0.2.10"),
  A("www", "192.0.2.10"),
  CNAME("docs", "www"),
  TXT("_note", "declared in git, not clicked in a dashboard")
);
