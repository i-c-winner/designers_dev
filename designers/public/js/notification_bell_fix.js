(() => {
	if (window.__designersNotificationBellFixInit) return;
	window.__designersNotificationBellFixInit = true;

	function getBellIcon() {
		return document.querySelector('[item-icon="bell"]');
	}

	function getNotificationsView() {
		return frappe?.app?.sidebar?.notifications?.tabs?.notifications || null;
	}

	function ensureSquare(icon) {
		if (!icon) return null;
		let square = icon.querySelector('.square');
		if (square) return square;

		square = document.createElement('div');
		square.classList.add('square', 'none-unread');

		const counter = document.createElement('p');
		counter.classList.add('counter');
		counter.textContent = '0';

		square.appendChild(counter);
		icon.appendChild(square);
		return square;
	}

	function setUnseenIndicator(icon, hasUnread) {
		if (!icon) return;
		const seen = icon.querySelector('.notifications-seen');
		const unseen = icon.querySelector('.notifications-unseen');
		if (!seen || !unseen) return;
		seen.style.display = hasUnread ? 'none' : '';
		unseen.style.display = hasUnread ? '' : 'none';
	}

	function updateSquare(square, unreadCount) {
		if (!square) return;
		const counter = square.querySelector('.counter');
		if (counter) counter.textContent = String(unreadCount);

		if (unreadCount > 0) {
			square.classList.remove('none-unread');
		} else {
			square.classList.add('none-unread');
		}
	}

	function fetchNotificationLogs(limit = 20) {
		if (!window.frappe || !frappe.call) {
			return Promise.resolve({ notification_logs: [], user_info: {} });
		}

		return frappe
			.call({
				method: 'frappe.desk.doctype.notification_log.notification_log.get_notification_logs',
				args: { limit },
				type: 'GET',
				cache: false,
			})
			.then((r) => r?.message || { notification_logs: [], user_info: {} })
			.catch(() => ({ notification_logs: [], user_info: {} }));
	}

	let refreshInFlight = false;

	function refreshNotificationsUI() {
		if (refreshInFlight) return;
		refreshInFlight = true;

		const icon = getBellIcon();
		const square = ensureSquare(icon);

		fetchNotificationLogs(20)
			.then((payload) => {
				const logs = payload.notification_logs || [];
				const unreadCount = logs.filter((x) => !x.read).length;

				setUnseenIndicator(icon, unreadCount > 0);
				updateSquare(square, unreadCount);

				const view = getNotificationsView();
				if (view && typeof view.render_notifications_dropdown === 'function') {
					view.dropdown_items = logs;
					if (payload.user_info) {
						frappe.update_user_info(payload.user_info);
					}
					view.render_notifications_dropdown();
				}
			})
			.finally(() => {
				refreshInFlight = false;
			});
	}

	function bindDropdownRefresh() {
		const dropdown = document.querySelector('.dropdown-notifications');
		if (!dropdown || dropdown.__designersBellFixBound) return;
		dropdown.__designersBellFixBound = true;
		$(dropdown).on('show.bs.dropdown', refreshNotificationsUI);
	}

	function bindRealtimeRefresh() {
		if (!window.frappe || !frappe.realtime) return;
		frappe.realtime.off('notification', refreshNotificationsUI);
		frappe.realtime.on('notification', refreshNotificationsUI);
	}

	function install() {
		bindDropdownRefresh();
		bindRealtimeRefresh();
		refreshNotificationsUI();

		setInterval(bindDropdownRefresh, 10000);
		setInterval(refreshNotificationsUI, 15000);

		document.addEventListener('visibilitychange', () => {
			if (!document.hidden) refreshNotificationsUI();
		});
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', install);
	} else {
		install();
	}
})();
