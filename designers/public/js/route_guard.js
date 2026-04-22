(function () {
	if (window.__designersRouteGuardInit) return;
	window.__designersRouteGuardInit = true;

	function isBadRouteValue(value) {
		if (value == null) return true;
		const s = String(value).trim().toLowerCase();
		return s === "" || s === "undefined" || s === "/undefined" || s === "desk/undefined";
	}

	function normalizeHref(href) {
		try {
			const u = new URL(href, window.location.origin);
			return u.pathname.replace(/\/+$/, "");
		} catch (e) {
			return "";
		}
	}

	function redirectToDeskIfNeeded() {
		const path = (window.location.pathname || "").replace(/\/+$/, "");
		if (path === "/undefined" || path === "/desk/undefined") {
			window.location.replace("/desk");
		}
	}

	function patchSetRoute() {
		if (!window.frappe || typeof frappe.set_route !== "function") return;
		const original = frappe.set_route.bind(frappe);
		if (frappe.__designersSetRoutePatched) return;
		frappe.__designersSetRoutePatched = true;

		frappe.set_route = function (...args) {
			const first = args[0];
			if (Array.isArray(first)) {
				if (isBadRouteValue(first[0])) {
					return Promise.resolve();
				}
			} else if (isBadRouteValue(first)) {
				return Promise.resolve();
			}
			return original(...args);
		};
	}

	function blockBrokenLinks() {
		document.addEventListener(
			"click",
			(e) => {
				const a = e.target && e.target.closest ? e.target.closest("a[href]") : null;
				if (!a) return;
				const href = (a.getAttribute("href") || "").trim();
				const path = normalizeHref(href);
				if (isBadRouteValue(href) || path === "/undefined" || path === "/desk/undefined") {
					e.preventDefault();
					e.stopPropagation();
					if (window.frappe && typeof frappe.set_route === "function") {
						frappe.set_route("desk");
					} else {
						window.location.assign("/desk");
					}
				}
			},
			true
		);
	}

	redirectToDeskIfNeeded();
	patchSetRoute();
	blockBrokenLinks();
	document.addEventListener("page-change", () => {
		redirectToDeskIfNeeded();
		patchSetRoute();
	});
})();
