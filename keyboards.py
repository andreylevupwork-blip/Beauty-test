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

