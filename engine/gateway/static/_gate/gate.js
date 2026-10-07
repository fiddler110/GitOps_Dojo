// Sets the dojo_gate cookie to sha256("dojo-gate:" + code); the gateway
// (Caddyfile, GATEWAY_GATE_TOKEN) compares it with its own copy. A wrong code
// is detected by asking /_gate/probe, which answers 204 only with the cookie.
(function () {
  var form = document.getElementById("gate");
  var msg = document.getElementById("msg");
  function fail(t) { msg.textContent = t; msg.hidden = false; }
  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    msg.hidden = true;
    if (!(window.crypto && crypto.subtle)) {
      fail("This browser needs HTTPS (or localhost) to enter the access code.");
      return;
    }
    var bytes = new TextEncoder().encode("dojo-gate:" + document.getElementById("code").value);
    var digest = await crypto.subtle.digest("SHA-256", bytes);
    var hex = Array.from(new Uint8Array(digest)).map(function (b) { return b.toString(16).padStart(2, "0"); }).join("");
    var secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = "dojo_gate=" + hex + "; Path=/; Max-Age=43200; SameSite=Lax" + secure;
    var r = await fetch("/_gate/probe", { credentials: "same-origin", cache: "no-store" });
    if (r.status === 204) { location.replace("/"); return; }
    document.cookie = "dojo_gate=; Path=/; Max-Age=0";
    fail("That code isn't right.");
    document.getElementById("code").select();
  });
})();
