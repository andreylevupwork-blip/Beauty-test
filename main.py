from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramUnauthorizedError

from config import settings
from db import (
    admin_delete_appointment,
    cancel_appointment,
    create_appointment,
    get_all_appointments,
    get_user_appointments,
    init_db,
    is_slot_blocked,
    is_slot_taken,
    toggle_slot_block,
)
from keyboards import (
    kb_admin_all_appts,
    kb_admin_menu,
    kb_admin_time_slots,
    kb_admin_weekdays,
    kb_back_to_main,
    kb_booking_entry,
    kb_confirm,
    kb_masters,
    kb_services,
    kb_times,
    kb_user_appointments,
    kb_weekdays,
)
from states import Booking


router = Router()


def _parse_hhmm(hhmm: str) -> tuple[int, int]:
    hh, mm = hhmm.split(":")
    return int(hh), int(mm)


def _get_tz(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _format_date_ua(d: datetime | date) -> str:
    return d.strftime("%d.%m.%Y")


def _get_date_for_weekday_index(idx: int) -> date:
    booking = settings.content["booking"]
    tz_name = settings.tz_override or booking.get("timezone") or "Europe/Kyiv"
    tz = _get_tz(tz_name)
    today = datetime.now(tz).date()
    offset = (idx - today.weekday()) % 7
    return today + timedelta(days=offset)


async def _send_admin_start(message: types.Message | CallbackQuery.message):
    text = (
        "👑 <b>Панель адміністратора</b>\n\n"
        "Вітаємо! Оберіть потрібну дію в меню нижче:"
    )
    msg_obj = message.message if isinstance(message, CallbackQuery) else message
    await msg_obj.answer(text, parse_mode="HTML", reply_markup=kb_admin_menu())


async def _send_start_content(message: types.Message | CallbackQuery.message):
    text = (
        f"<b>{settings.content['greeting']}</b>\n\n"
        f"{settings.content['prices_message']}\n\n"
        "👇 <b>Щоб записатися — натисніть кнопку нижче:</b>"
    )
    msg_obj = message.message if isinstance(message, CallbackQuery) else message
    await msg_obj.answer(text, parse_mode="HTML", reply_markup=kb_booking_entry())


async def _available_times_for_date(appt_date, master_name: str) -> list[str]:
    booking = settings.content["booking"]
    tz_name = booking.get("timezone") or settings.content.get("timezone") or "Europe/Kyiv"
    tz_name = settings.tz_override or tz_name
    tz = _get_tz(tz_name)

    work_start_h, work_start_m = _parse_hhmm(booking["work_start"])
    work_end_h, work_end_m = _parse_hhmm(booking["work_end"])
    step_minutes = int(booking["slot_minutes"])

    now = datetime.now(tz)

    times: list[str] = []
    cursor = datetime(
        appt_date.year,
        appt_date.month,
        appt_date.day,
        work_start_h,
        work_start_m,
        tzinfo=tz,
    )
    end_dt = datetime(
        appt_date.year,
        appt_date.month,
        appt_date.day,
        work_end_h,
        work_end_m,
        tzinfo=tz,
    )

    # Generate slot starts where start + step <= end.
    while cursor + timedelta(minutes=step_minutes) <= end_dt:
        # Skip past times (only for today).
        if cursor < now and cursor.date() == now.date():
            cursor += timedelta(minutes=step_minutes)
            continue

        slot_iso = cursor.replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")
        if not await is_slot_taken(master_name, slot_iso):
            times.append(slot_iso)
        cursor += timedelta(minutes=step_minutes)
    return times


async def _generate_all_slots_for_date(appt_date: date, master_name: str) -> list[str]:
    booking = settings.content["booking"]
    tz_name = booking.get("timezone") or settings.content.get("timezone") or "Europe/Kyiv"
    tz_name = settings.tz_override or tz_name
    tz = _get_tz(tz_name)

    start_h, start_m = _parse_hhmm(booking.get("work_start", "10:00"))
    end_h, end_m = _parse_hhmm(booking.get("work_end", "19:00"))
    step_minutes = int(booking.get("slot_minutes", 60))

    cursor = datetime(appt_date.year, appt_date.month, appt_date.day, start_h, start_m, tzinfo=tz)
    end_dt = datetime(appt_date.year, appt_date.month, appt_date.day, end_h, end_m, tzinfo=tz)

    times = []
    while cursor + timedelta(minutes=step_minutes) <= end_dt:
        slot_iso = cursor.replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")
        times.append(slot_iso)
        cursor += timedelta(minutes=step_minutes)
    return times


@router.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id if message.from_user else None
    if settings.admin_chat_id and user_id and int(user_id) == int(settings.admin_chat_id):
        await _send_admin_start(message)
    else:
        await _send_start_content(message)


@router.callback_query(lambda c: c.data == "admin:menu")
async def admin_menu_handler(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    if not (settings.admin_chat_id and int(user_id) == int(settings.admin_chat_id)):
        await callback.answer("У вас немає прав адміністратора", show_alert=True)
        return

    await callback.answer()
    await _send_admin_start(callback.message)


@router.callback_query(lambda c: c.data == "admin:view_as_client")
async def admin_view_as_client_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    await _send_start_content(callback.message)


@router.callback_query(lambda c: c.data == "admin:manage_slots_days")
async def admin_manage_slots_days_handler(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    if not (settings.admin_chat_id and int(user_id) == int(settings.admin_chat_id)):
        await callback.answer("У вас немає прав адміністратора", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        "⏰ <b>Управління робочим часом</b>\n\nОберіть день для перегляду та налаштування слотів:",
        parse_mode="HTML",
        reply_markup=kb_admin_weekdays(),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("admin_daywd:"))
async def admin_day_slots_handler(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    if not (settings.admin_chat_id and int(user_id) == int(settings.admin_chat_id)):
        await callback.answer("У вас немає прав адміністратора", show_alert=True)
        return

    await callback.answer()
    day_idx = int(callback.data.split(":", 1)[1])
    target_date = _get_date_for_weekday_index(day_idx)
    master_name = settings.content["master_name"]

    all_slot_isos = await _generate_all_slots_for_date(target_date, master_name)
    appts = await get_all_appointments()
    appts_by_time = {a["appt_start"]: a for a in appts if a["master_name"] == master_name}

    slots_info = []
    for iso in all_slot_isos:
        time_label = iso[11:16]
        if iso in appts_by_time:
            appt = appts_by_time[iso]
            slots_info.append({
                "iso": iso,
                "time_label": time_label,
                "status": "booked",
                "client_name": appt["name"],
                "appt_id": appt["id"],
            })
        elif await is_slot_blocked(master_name, iso):
            slots_info.append({
                "iso": iso,
                "time_label": time_label,
                "status": "blocked",
            })
        else:
            slots_info.append({
                "iso": iso,
                "time_label": time_label,
                "status": "available",
            })

    dt_str = _format_date_ua(target_date)
    text = (
        f"⏰ <b>Управління слотами на {dt_str}</b>\n\n"
        "🟢 — Відкрито для запису (натисніть щоб закрити)\n"
        "🔴 — Заблоковано (натисніть щоб відкрити)\n"
        "🔒 — Зайнято клієнтом (натисніть щоб видалити)"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb_admin_time_slots(slots_info))


@router.callback_query(lambda c: c.data and c.data.startswith("admin_toggle_slot:"))
async def admin_toggle_slot_handler(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    if not (settings.admin_chat_id and int(user_id) == int(settings.admin_chat_id)):
        await callback.answer("У вас немає прав адміністратора", show_alert=True)
        return

    slot_iso = callback.data.split(":", 1)[1]
    master_name = settings.content["master_name"]

    is_blocked = await toggle_slot_block(master_name, slot_iso)
    time_label = slot_iso[11:16]

    if is_blocked:
        await callback.answer(f"🔴 Час {time_label} заблоковано для запису", show_alert=True)
    else:
        await callback.answer(f"🟢 Час {time_label} відкрито для запису", show_alert=True)

    target_dt = datetime.fromisoformat(slot_iso)
    all_slot_isos = await _generate_all_slots_for_date(target_dt.date(), master_name)
    appts = await get_all_appointments()
    appts_by_time = {a["appt_start"]: a for a in appts if a["master_name"] == master_name}

    slots_info = []
    for iso in all_slot_isos:
        lbl = iso[11:16]
        if iso in appts_by_time:
            appt = appts_by_time[iso]
            slots_info.append({
                "iso": iso,
                "time_label": lbl,
                "status": "booked",
                "client_name": appt["name"],
                "appt_id": appt["id"],
            })
        elif await is_slot_blocked(master_name, iso):
            slots_info.append({
                "iso": iso,
                "time_label": lbl,
                "status": "blocked",
            })
        else:
            slots_info.append({
                "iso": iso,
                "time_label": lbl,
                "status": "available",
            })

    dt_str = _format_date_ua(target_dt)
    text = (
        f"⏰ <b>Управління слотами на {dt_str}</b>\n\n"
        "🟢 — Відкрито для запису (натисніть щоб закрити)\n"
        "🔴 — Заблоковано (натисніть щоб відкрити)\n"
        "🔒 — Зайнято клієнтом (натисніть щоб видалити)"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb_admin_time_slots(slots_info))


@router.callback_query(lambda c: c.data == "portfolio:show")
async def portfolio_show_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    text = settings.content.get(
        "portfolio_text",
        "🖼 <b>Портфоліо робіт майстра Крістіни</b>\n\nПриклади наших робіт скоро тут!",
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb_back_to_main())


@router.callback_query(lambda c: c.data == "my_bookings:show")
async def my_bookings_show_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    user_id = str(callback.from_user.id)
    appts = await get_user_appointments(user_id)

    if not appts:
        await callback.message.answer(
            "У вас поки немає активних записів.",
            reply_markup=kb_back_to_main(),
        )
        return

    text = "<b>Ваші активні записи:</b>\nНатисніть на кнопку запису нижче, щоб скасувати його:"
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=kb_user_appointments(appts),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("cancel_appt:"))
async def cancel_appt_handler(callback: CallbackQuery) -> None:
    appt_id = int(callback.data.split(":", 1)[1])
    user_id = str(callback.from_user.id)

    success = await cancel_appointment(appt_id, user_id)
    if success:
        await callback.answer("Запис успішно скасовано!", show_alert=True)
        if settings.admin_chat_id:
            try:
                await callback.bot.send_message(
                    settings.admin_chat_id,
                    f"❌ <b>Скасування запису №{appt_id}</b>\nКористувач: @{callback.from_user.username or callback.from_user.full_name} ({user_id})",
                    parse_mode="HTML",
                )
            except Exception:
                pass
    else:
        await callback.answer("Запис не знайдено або вже скасовано.", show_alert=True)

    appts = await get_user_appointments(user_id)
    if not appts:
        await callback.message.answer(
            "У вас більше немає активних записів.",
            reply_markup=kb_back_to_main(),
        )
    else:
        await callback.message.answer(
            "<b>Ваші активні записи:</b>",
            parse_mode="HTML",
            reply_markup=kb_user_appointments(appts),
        )


@router.callback_query(lambda c: c.data == "admin:menu")
async def admin_menu_handler(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    if not (settings.admin_chat_id and int(user_id) == int(settings.admin_chat_id)):
        await callback.answer("У вас немає прав адміністратора", show_alert=True)
        return

    await callback.answer()
    text = "👑 <b>Панель адміністратора</b>\n\nОберіть потрібну дію:"
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb_admin_menu())


@router.callback_query(lambda c: c.data == "admin:all_appts")
async def admin_all_appts_handler(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    if not (settings.admin_chat_id and int(user_id) == int(settings.admin_chat_id)):
        await callback.answer("У вас немає прав адміністратора", show_alert=True)
        return

    await callback.answer()
    appts = await get_all_appointments()

    if not appts:
        await callback.message.answer(
            "📋 <b>Всі записи:</b>\n\nАктивних записів немає.",
            parse_mode="HTML",
            reply_markup=kb_admin_menu(),
        )
        return

    lines = ["📋 <b>Всі активні записи клієнтів:</b>\n"]
    for idx, appt in enumerate(appts, 1):
        appt_dt = datetime.fromisoformat(appt["appt_start"])
        dt_str = appt_dt.strftime("%d.%m.%Y о %H:%M")
        username_str = f" (@{appt['username']})" if appt.get("username") else ""
        note_str = f"\n   💬 Коментар: {appt['note']}" if appt.get("note") else ""
        lines.append(
            f"<b>{idx}) Запис №{appt['id']}</b>\n"
            f"   👤 Клієнт: {appt['name']}{username_str}\n"
            f"   📞 Тел: {appt['phone']}\n"
            f"   💅 Послуга: {appt['service_title']}\n"
            f"   👩‍🎨 Майстер: {appt['master_name']}\n"
            f"   📅 Час: <b>{dt_str}</b>{note_str}\n"
        )

    full_text = "\n".join(lines)
    await callback.message.answer(
        full_text,
        parse_mode="HTML",
        reply_markup=kb_admin_all_appts(appts),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("admin_delete:"))
async def admin_delete_handler(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    if not (settings.admin_chat_id and int(user_id) == int(settings.admin_chat_id)):
        await callback.answer("У вас немає прав адміністратора", show_alert=True)
        return

    appt_id = int(callback.data.split(":", 1)[1])
    success = await admin_delete_appointment(appt_id)

    if success:
        await callback.answer(f"Запис №{appt_id} видалено!", show_alert=True)
    else:
        await callback.answer("Запис не знайдено або вже видалено.", show_alert=True)

    appts = await get_all_appointments()
    if not appts:
        await callback.message.answer(
            "📋 <b>Всі записи:</b>\n\nАктивних записів більше немає.",
            parse_mode="HTML",
            reply_markup=kb_admin_menu(),
        )
    else:
        lines = ["📋 <b>Всі активні записи клієнтів:</b>\n"]
        for idx, appt in enumerate(appts, 1):
            appt_dt = datetime.fromisoformat(appt["appt_start"])
            dt_str = appt_dt.strftime("%d.%m.%Y о %H:%M")
            username_str = f" (@{appt['username']})" if appt.get("username") else ""
            note_str = f"\n   💬 Коментар: {appt['note']}" if appt.get("note") else ""
            lines.append(
                f"<b>{idx}) Запис №{appt['id']}</b>\n"
                f"   👤 Клієнт: {appt['name']}{username_str}\n"
                f"   📞 Тел: {appt['phone']}\n"
                f"   💅 Послуга: {appt['service_title']}\n"
                f"   👩‍🎨 Майстер: {appt['master_name']}\n"
                f"   📅 Час: <b>{dt_str}</b>{note_str}\n"
            )

        full_text = "\n".join(lines)
        await callback.message.answer(
            full_text,
            parse_mode="HTML",
            reply_markup=kb_admin_all_appts(appts),
        )


@router.callback_query(lambda c: c.data == "book:start")
async def book_start_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Booking.service)
    await callback.answer()
    await callback.message.answer(
        "Оберіть послугу:",
        reply_markup=kb_services(settings.content["services"]),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("service:"))
async def service_pick_handler(callback: CallbackQuery, state: FSMContext) -> None:
    data = callback.data.split(":", 1)[1]
    service = next((s for s in settings.content["services"] if s["id"] == data), None)
    if not service:
        await callback.answer("Невідома послуга")
        return

    await state.update_data(service_id=service["id"], service_title=service["title"])
    await state.set_state(Booking.master)
    await callback.answer()

    master_name = settings.content["master_name"]
    await callback.message.answer(
        "Оберіть майстра:",
        reply_markup=kb_masters(master_name),
    )


@router.callback_query(lambda c: c.data == "master:choose")
async def master_choose_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(master_name=settings.content["master_name"])
    await state.set_state(Booking.day)
    await callback.answer()
    await callback.message.answer("Оберіть день:", reply_markup=kb_weekdays())


@router.callback_query(lambda c: c.data and c.data.startswith("daywd:"))
async def day_pick_handler(callback: CallbackQuery, state: FSMContext) -> None:
    idx = int(callback.data.split(":", 1)[1])
    appt_date = _get_date_for_weekday_index(idx)

    await callback.answer()
    fsm_data = await state.get_data()
    master_name = fsm_data.get("master_name") or settings.content["master_name"]
    times = await _available_times_for_date(appt_date, master_name)
    if not times:
        await callback.message.answer(
            "На цей день немає доступних слотів. Оберіть інший день.",
            reply_markup=kb_weekdays(),
        )
        return

    await state.update_data(appt_date=appt_date.isoformat())
    await state.set_state(Booking.time)
    await callback.message.answer(
        f"Вільний час на {appt_date.strftime('%d.%m.%Y')}:",
        reply_markup=kb_times(times_iso=times),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("time:"))
async def time_pick_handler(callback: CallbackQuery, state: FSMContext) -> None:
    appt_start_iso = callback.data.split(":", 1)[1]
    await state.update_data(appt_start_iso=appt_start_iso)
    await state.set_state(Booking.name)
    await callback.answer()
    await callback.message.answer("Вкажіть, будь ласка, ім'я:")


@router.message(Booking.name)
async def name_input_handler(message: types.Message, state: FSMContext) -> None:
    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(Booking.phone)
    await message.answer("Тепер телефон (наприклад +380...):")


@router.message(Booking.phone)
async def phone_input_handler(message: types.Message, state: FSMContext) -> None:
    phone = message.text.strip()
    await state.update_data(phone=phone)
    await state.set_state(Booking.note)
    await message.answer(
        "Коментар (не обов'язково). Якщо не треба — напишіть «Пропустити»."
    )


@router.message(Booking.note)
async def note_input_handler(message: types.Message, state: FSMContext) -> None:
    note_raw = message.text.strip()
    note = None if note_raw.lower() in {"пропустити", "skip"} else note_raw
    await state.update_data(note=note)
    await state.set_state(Booking.confirm)

    data = await state.get_data()
    appt_start_iso = data["appt_start_iso"]
    appt_dt = datetime.fromisoformat(appt_start_iso)

    service_title = data["service_title"]
    master_name = data["master_name"]
    appt_date_str = data["appt_date"]
    appt_time = appt_dt.strftime("%H:%M")

    summary = (
        "Заявка:\n"
        f"Послуга: {service_title}\n"
        f"Майстер: {master_name}\n"
        f"Дата: {datetime.fromisoformat(appt_date_str).strftime('%d.%m.%Y')}\n"
        f"Час: {appt_time}\n"
        f"Ім'я: {data['name']}\n"
        f"Телефон: {data['phone']}\n"
    )
    if data.get("note"):
        summary += f"Коментар: {data['note']}\n"

    await message.answer(summary + "\n" + settings.content["confirm_text"], reply_markup=kb_confirm())


@router.callback_query(lambda c: c.data and c.data.startswith("confirm:"))
async def confirm_handler(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":", 1)[1]
    data = await state.get_data()
    user_id = str(callback.from_user.id)
    username = callback.from_user.username

    if action == "no":
        await callback.answer()
        await state.set_state(Booking.day)
        await callback.message.answer("Оберіть інший день:", reply_markup=kb_weekdays())
        return

    try:
        appt_id = await create_appointment(
            user_id=user_id,
            username=username,
            name=data["name"],
            phone=data["phone"],
            service_id=data["service_id"],
            service_title=data["service_title"],
            master_name=data["master_name"],
            appt_start_iso=data["appt_start_iso"],
            note=data.get("note"),
        )
    except Exception:
        # Most likely double-booking unique constraint.
        await callback.answer()
        await state.set_state(Booking.time)
        await callback.message.answer(
            "Вибраний час щойно зайняли. Оберіть інший слот:",
        )

        # Rebuild times for stored date.
        appt_date = datetime.fromisoformat(data["appt_date"]).date()
        times = await _available_times_for_date(appt_date, settings.content["master_name"])
        if times:
            await callback.message.answer(
                f"Вільний час на {appt_date.strftime('%d.%m.%Y')}:",
                reply_markup=kb_times(times_iso=times),
            )
        else:
            await callback.message.answer("Немає доступних слотів на цей день.", reply_markup=kb_weekdays())
        return

    await callback.answer()
    await state.clear()

    appt_dt = datetime.fromisoformat(data["appt_start_iso"])
    booking_message = (
        f"✅ Дякуємо! Заявку №{appt_id} прийнято.\n"
        f"Дата: {appt_dt.strftime('%d.%m.%Y')}\n"
        f"Час: {appt_dt.strftime('%H:%M')}\n\n"
        "Бажаємо вам вдалого манікюру!"
    )
    await callback.message.answer(booking_message)

    # Notify admin.
    admin_chat_id = settings.admin_chat_id
    if admin_chat_id:
        summary = (
            "Нова заявка:\n"
            f"ID: {appt_id}\n"
            f"Користувач: @{username or callback.from_user.full_name} ({user_id})\n"
            f"Послуга: {data['service_title']}\n"
            f"Майстер: {data['master_name']}\n"
            f"Дата: {datetime.fromisoformat(data['appt_date']).strftime('%d.%m.%Y')}\n"
            f"Час: {appt_dt.strftime('%H:%M')}\n"
            f"Ім'я: {data['name']}\n"
            f"Телефон: {data['phone']}\n"
        )
        if data.get("note"):
            summary += f"Коментар: {data['note']}\n"
        await callback.bot.send_message(admin_chat_id, summary)


@router.callback_query(lambda c: c.data and c.data.startswith("back:"))
async def back_handler(callback: CallbackQuery, state: FSMContext) -> None:
    target = callback.data.split(":", 1)[1]
    await callback.answer()

    if target == "main":
        await state.clear()
        await _send_start_content(callback.message)
        return

    if target == "services":
        await state.set_state(Booking.service)
        await callback.message.answer(
            "Оберіть послугу:",
            reply_markup=kb_services(settings.content["services"]),
        )
        return

    if target == "prices":
        await state.clear()
        await callback.message.answer(settings.content["prices_message"], reply_markup=kb_booking_entry())
        return

    if target == "day":
        await state.set_state(Booking.day)
        await callback.message.answer("Оберіть день:", reply_markup=kb_weekdays())
        return


@router.message()
async def fallback_message_handler(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await _send_start_content(message)


@router.callback_query()
async def fallback_callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await _send_start_content(callback)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("aiogram").setLevel(logging.INFO)

    await init_db()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    try:
        # Webhook scaffolding (optional). Polling is default.
        if settings.mode == "webhook" and settings.webhook_base_url:
            from aiohttp import web
            from aiogram.webhook.aiohttp_server import SimpleRequestHandler

            webhook_url = f"{settings.webhook_base_url}{settings.webhook_path}"
            webhook_app = web.Application()

            request_handler = SimpleRequestHandler(
                dispatcher=dp,
                bot=bot,
            )
            request_handler.register(webhook_app, path=settings.webhook_path)

            # Start app and set webhook.
            async def on_startup(_app: web.Application) -> None:
                await bot.set_webhook(webhook_url)

            webhook_app.on_startup.append(on_startup)

            print(f"Webhook enabled at {webhook_url}")
            web.run_app(
                webhook_app,
                host=settings.webhook_host,
                port=settings.webhook_port,
            )
            return

        # If webhook was previously enabled, polling won't receive updates.
        print("Polling mode: starting bot...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except TelegramUnauthorizedError:
        print(
            "ERROR: BOT_TOKEN is invalid (Telegram: Unauthorized).\n"
            "Open BotFather, copy your bot API token, and paste it into bot/.env:\n"
            "BOT_TOKEN=YOUR_TOKEN_HERE"
        )
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

