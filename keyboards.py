from __future__ import annotations

from datetime import date
from typing import Iterable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


WEEKDAYS_UA_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]


def kb_main() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    return kb


def kb_booking_entry() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💅 Записатися на прийом",
                    callback_data="book:start",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🖼 Портфоліо робіт",
                    callback_data="portfolio:show",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Мої записи / Скасувати запис",
                    callback_data="my_bookings:show",
                )
            ],
        ]
    )


def kb_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Всі записи клієнтів", callback_data="admin:all_appts")],
            [InlineKeyboardButton(text="⏰ Управління робочим часом", callback_data="admin:manage_slots_days")],
            [InlineKeyboardButton(text="👁‍🗨 Тестовий перегляд як клієнт", callback_data="admin:view_as_client")],
        ]
    )


def kb_admin_weekdays() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, wd in enumerate(WEEKDAYS_UA_SHORT):
        rows.append([InlineKeyboardButton(text=wd, callback_data=f"admin_daywd:{idx}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад в адмін-панель", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_admin_time_slots(slots_info: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for s in slots_info:
        label = s["time_label"]
        status = s["status"]
        iso = s["iso"]

        if status == "available":
            btn_text = f"🟢 {label} — Відкрито (натисніть щоб закрити)"
            cb = f"admin_toggle_slot:{iso}"
        elif status == "blocked":
            btn_text = f"🔴 {label} — Заблоковано (натисніть щоб відкрити)"
            cb = f"admin_toggle_slot:{iso}"
        else:
            btn_text = f"🔒 {label} — Зайнято клієнтом ({s.get('client_name', 'Запис')})"
            cb = f"admin_delete:{s.get('appt_id')}" if s.get('appt_id') else "ignore"

        rows.append([InlineKeyboardButton(text=btn_text, callback_data=cb)])

    rows.append([InlineKeyboardButton(text="⬅️ Назад до вибору дня", callback_data="admin:manage_slots_days")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_admin_all_appts(appts: list[dict]) -> InlineKeyboardMarkup:
    from datetime import datetime

    rows: list[list[InlineKeyboardButton]] = []
    for appt in appts:
        appt_dt = datetime.fromisoformat(appt["appt_start"])
        dt_str = appt_dt.strftime("%d.%m %H:%M")
        btn_text = f"🗑 Видалити №{appt['id']} ({appt['name']} — {dt_str})"
        rows.append(
            [InlineKeyboardButton(text=btn_text, callback_data=f"admin_delete:{appt['id']}")]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад в адмін-панель", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_user_appointments(appts: list[dict]) -> InlineKeyboardMarkup:
    from datetime import datetime

    rows: list[list[InlineKeyboardButton]] = []
    for appt in appts:
        appt_dt = datetime.fromisoformat(appt["appt_start"])
        dt_str = appt_dt.strftime("%d.%m о %H:%M")
        btn_text = f"❌ Скасувати: {appt['service_title']} ({dt_str})"
        rows.append(
            [InlineKeyboardButton(text=btn_text, callback_data=f"cancel_appt:{appt['id']}")]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back:main")]
        ]
    )


def kb_masters(master_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=master_name,
                    callback_data="master:choose",
                )
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back:services")],
        ]
    )


def kb_services(services: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for s in services:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{s['title']} — {s['price']} грн",
                    callback_data=f"service:{s['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_weekdays() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, wd in enumerate(WEEKDAYS_UA_SHORT):
        rows.append(
            [InlineKeyboardButton(text=wd, callback_data=f"daywd:{idx}")]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:prices")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_times(*, times_iso: list[str]) -> InlineKeyboardMarkup:
    # Put 3 buttons per row for readability.
    rows: list[list[InlineKeyboardButton]] = []
    current: list[InlineKeyboardButton] = []
    for t in times_iso:
        label = t[11:16]  # HH:MM
        current.append(
            InlineKeyboardButton(text=label, callback_data=f"time:{t}")
        )
        if len(current) == 3:
            rows.append(current)
            current = []
    if current:
        rows.append(current)

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:day")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Так, підтвердити", callback_data="confirm:yes"),
                InlineKeyboardButton(text="❌ Ні, змінити", callback_data="confirm:no"),
            ]
        ]
    )

