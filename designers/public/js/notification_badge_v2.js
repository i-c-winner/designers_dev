(function () {
	if (window.__designersNotificationBadgeInit) return;
	window.__designersNotificationBadgeInit = true;

	const SELECTORS_ITEM = [
		".standard-items-sections .sidebar-notification .item-anchor",
		".sidebar-notification .item-anchor",
		".sidebar-notification",
	];
	const BADGE_CLASS = "designers-notification-badge";
	const POLL_MS = 3000;
	let pollTimer = null;
	let refreshInFlight = false;

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
	}

	function isRead(row) {
		const raw = row?.read;
		if (raw === true || raw === 1 || raw === "1") return true;
		return false;
	}

	function refreshFromServer() {
		if (!window.frappe || !frappe.call || frappe.session?.user === "Guest") return;
		if (refreshInFlight) return;
		refreshInFlight = true;
		fetchLiveNotifications(100)
			.then((r) => {
				const logs = r?.message?.notification_logs || [];
				const unread = logs.reduce((acc, row) => acc + (isRead(row) ? 0 : 1), 0);
				renderCount(unread);
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
		// Keep server as a single source of truth to avoid flicker during dropdown rerenders.
		refreshFromServer();
		syncDropdownList();
	}

	function getNotificationsView() {
		return frappe?.app?.sidebar?.notifications?.tabs?.notifications || null;
	}

	function isDropdownOpen() {
		const dropdown = document.querySelector(".dropdown-notifications");
		return !!dropdown && !dropdown.classList.contains("hidden");
	}

	function syncDropdownList() {
		if (!window.frappe || frappe.session?.user === "Guest") return;
		if (!isDropdownOpen()) return;
		const view = getNotificationsView();
		if (!view) return;

		fetchLiveNotifications(view.max_length || 20).then((r) => {
			if (!r?.message) return;
			view.dropdown_items = r.message.notification_logs || [];
			if (typeof frappe.update_user_info === "function") {
				frappe.update_user_info(r.message.user_info || {});
			}
			if (typeof view.render_notifications_dropdown === "function") {
				view.render_notifications_dropdown();
			}
		});
	}

	function bindRealtime() {
		if (window.__designersBadgeRealtimeBound) return;
		if (!window.frappe?.realtime) {
			setTimeout(bindRealtime, 1000);
			return;
		}
		window.__designersBadgeRealtimeBound = true;

		frappe.realtime.on("notification", refreshFastThenServer);
		frappe.realtime.on("indicator_hide", refreshFastThenServer);
	}

	function startPolling() {
		if (pollTimer) return;
		pollTimer = setInterval(() => {
			if (document.hidden) return;
			refreshFromServer();
			syncDropdownList();
		}, POLL_MS);
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
				setTimeout(refreshFastThenServer, 50);
			}
		});

		document.addEventListener("page-change", () => {
			setTimeout(initTick, 0);
		});
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
