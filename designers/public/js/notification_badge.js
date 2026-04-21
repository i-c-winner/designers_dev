(function () {
	if (window.__designersNotificationBadgeInit) return;
	window.__designersNotificationBadgeInit = true;

	const SELECTORS_ITEM = [
		".standard-items-sections .sidebar-notification .item-anchor",
		".sidebar-notification .item-anchor",
		".sidebar-notification",
		".notifications-icon",
	];
	const BADGE_CLASS = "designers-notification-badge";
	const DECREASE_DELAY_MS = 1200;
	const POLL_MS = 15000;
	let refreshInFlight = false;
	let lastRefreshAt = 0;
	const MIN_REFRESH_GAP_MS = 800;
	let lastRenderedCount = 0;
	let decreaseTimer = null;
	let pollTimer = null;

	function fetchLiveNotifications(limit) {
		return frappe.call({
			method: "designers.api.notifications_live.get_notification_logs_live",
			args: { limit: limit || 20 },
		});
	}

	function getBadgeContainer() {
		const item = SELECTORS_ITEM.map((s) => document.querySelector(s)).find(Boolean);
		if (!item) return null;
		let badge = item.querySelector(`.${BADGE_CLASS}`);
		if (!badge) {
			badge = document.createElement("span");
			badge.className = `${BADGE_CLASS} hidden`;
			item.appendChild(badge);
		}
		return badge;
	}

	function renderCount(count) {
		const badge = getBadgeContainer();
		if (!badge) return;
		const safeCount = Math.max(0, Number(count) || 0);
		badge.textContent = safeCount > 9 ? "9+" : String(safeCount);
		badge.classList.toggle("hidden", safeCount === 0);
		lastRenderedCount = safeCount;
	}

	function renderCountStable(nextCount) {
		const safeNext = Math.max(0, Number(nextCount) || 0);
		if (safeNext >= lastRenderedCount) {
			if (decreaseTimer) {
				clearTimeout(decreaseTimer);
				decreaseTimer = null;
			}
			renderCount(safeNext);
			return;
		}
		if (decreaseTimer) clearTimeout(decreaseTimer);
		decreaseTimer = setTimeout(() => {
			renderCount(safeNext);
			decreaseTimer = null;
		}, DECREASE_DELAY_MS);
	}

	function isRead(row) {
		const raw = row?.read;
		if (raw === true || raw === 1 || raw === "1") return true;
		if (typeof raw === "string") {
			const v = raw.trim().toLowerCase();
			if (v === "true" || v === "yes" || v === "y") return true;
		}
		return false;
	}

	function refreshFromServer() {
		if (!window.frappe || !frappe.call || frappe.session?.user === "Guest") return;
		if (refreshInFlight) return;
		const now = Date.now();
		if (now - lastRefreshAt < MIN_REFRESH_GAP_MS) return;
		lastRefreshAt = now;
		refreshInFlight = true;
		fetchLiveNotifications(100)
			.then((r) => {
				const logs = r?.message?.notification_logs || [];
				let unread = logs.reduce((acc, row) => acc + (isRead(row) ? 0 : 1), 0);
				// Fallback to Frappe's native unseen indicator.
				if (!unread) {
					const unseenEl = document.querySelector(".notifications-icon .notifications-unseen");
					if (unseenEl && unseenEl.offsetParent !== null) {
						unread = 1;
					}
				}
				renderCountStable(unread);
				refreshInFlight = false;
			})
			.catch((err) => {
				if (window.console && typeof console.warn === "function") {
					console.warn("[designers] notification badge refresh failed", err);
				}
				refreshInFlight = false;
			});
	}

	function refreshFastThenServer() {
		// Only update badge count to avoid interfering with native dropdown rendering.
		refreshFromServer();
	}

	function bindRealtime() {
		if (window.__designersBadgeRealtimeBound) return;
		if (!window.frappe?.realtime) {
			setTimeout(bindRealtime, 1000);
			return;
		}
		window.__designersBadgeRealtimeBound = true;

		frappe.realtime.on("notification", refreshFastThenServer);
	}

	function bindUIActions() {
		if (window.__designersBadgeUiBound) return;
		window.__designersBadgeUiBound = true;

		document.addEventListener("click", (e) => {
			if (
				e.target.closest(".mark-all-read") ||
				e.target.closest(".notification-item") ||
				e.target.closest(".sidebar-notification")
			) {
				setTimeout(refreshFastThenServer, 120);
			}
		});

		document.addEventListener("page-change", () => {
			setTimeout(initTick, 0);
		});
	}

	function startPolling() {
		if (pollTimer) return;
		pollTimer = setInterval(() => {
			if (document.hidden) return;
			refreshFromServer();
		}, POLL_MS);
	}

	function initTick() {
		getBadgeContainer();
		bindRealtime();
		startPolling();
		refreshFastThenServer();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", initTick);
	} else {
		initTick();
	}

	bindUIActions();
})();
