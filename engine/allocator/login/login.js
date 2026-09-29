// Front-door enhancements. The form works without any of this.
(function () {
  var form = document.querySelector("form");
  var card = document.querySelector(".card");
  var user = form.elements.username;
  var pass = form.elements.password;
  var reveal = document.querySelector(".reveal");
  var caps = document.querySelector(".caps");
  var submit = document.querySelector(".submit");

  // Keep the #slide fragment the browser was sent here with.
  if (location.hash) form.elements.next.value += location.hash;

  // Land on the empty field: password when the username came back filled in.
  (user.value ? pass : user).focus();

  reveal.hidden = false;
  reveal.addEventListener("click", function () {
    var show = pass.type === "password";
    pass.type = show ? "text" : "password";
    reveal.setAttribute("aria-pressed", String(show));
    reveal.setAttribute("aria-label", show ? "Hide password" : "Show password");
    reveal.classList.toggle("on", show);
    pass.focus();
  });

  function capsState(e) {
    if (e.getModifierState) caps.hidden = !e.getModifierState("CapsLock");
  }
  pass.addEventListener("keydown", capsState);
  pass.addEventListener("keyup", capsState);
  pass.addEventListener("blur", function () { caps.hidden = true; });

  form.addEventListener("submit", function (e) {
    if (!user.value.trim() || !pass.value) {
      e.preventDefault();
      card.classList.remove("shake");
      void card.offsetWidth; // restart the animation
      card.classList.add("shake");
      (user.value.trim() ? pass : user).focus();
      return;
    }
    submit.classList.add("busy");
    submit.disabled = true;
    // The page is replaced by the answer; if the browser comes back from
    // its cache (back button) don't leave the button stuck.
    window.addEventListener("pageshow", function () {
      submit.classList.remove("busy");
      submit.disabled = false;
    });
  });
})();
