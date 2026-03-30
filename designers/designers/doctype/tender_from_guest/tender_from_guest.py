# Copyright (c) 2026, Dmitriy and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document

PHONE_REGEX = re.compile(r"^\+?[0-9]{10,15}$")


class TenderFromGuest(Document):
    def validate(self):
        if self.your_phone and not PHONE_REGEX.fullmatch(self.your_phone.strip()):
            frappe.throw("Поле 'Ваш телефон' должно быть в формате +79991234567 (10-15 цифр).")
