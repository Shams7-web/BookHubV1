document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".password-toggle").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var input = document.getElementById(btn.dataset.target);
            if (!input) {
                return;
            }

            var showing = input.type === "password";
            input.type = showing ? "text" : "password";

            var icon = btn.querySelector("i");
            if (icon) {
                icon.classList.toggle("bi-eye");
                icon.classList.toggle("bi-eye-slash");
            }

            btn.setAttribute("aria-label", showing ? "Hide password" : "Show password");
        });
    });
});
