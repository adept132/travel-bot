from math import floor

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.travel_session import Session
from app.travel_database import Achievement, User
from app.travel_achivements import ALL_ACHIEVEMENTS
from app.travel_utils import check_achievements
import app.traveler_keyboard as kb

router = Router()


@router.callback_query(F.data == "achievements")
async def view_achievements(callback: CallbackQuery):
    session = Session()

    user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        session.close()
        return

    unlocked_achievements = session.query(Achievement).filter_by(user_id=user.user_id).all()
    unlocked_codes = {a.code for a in unlocked_achievements}

    total = len(ALL_ACHIEVEMENTS)
    unlocked_count = len(unlocked_codes)
    progress = floor((unlocked_count / total) * 10)
    bar = "█" * progress + "░" * (10 - progress)

    text = f"🏆 <b>Достижения</b>\n\nПрогресс: [{bar}] {unlocked_count}/{total}\n\n"

    for ach in ALL_ACHIEVEMENTS:
        name = ach["name"]
        desc = ach["description"]
        if ach["code"] in unlocked_codes:
            text += f"✅ {name}\n   {desc}\n\n"
        else:
            text += f"🔒 {name}\n   {desc}\n\n"

    try:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=kb.achievements_keyboard
        )
    finally:
        session.close()


@router.callback_query(F.data == "refresh_achievements")
async def refresh_achievements(callback: CallbackQuery):
    session = Session()
    try:
        print("=== REFRESH ACHIEVEMENTS STARTED ===")

        user = session.query(User).filter_by(tg_id=callback.from_user.id).first()
        if not user:
            print("❌ User not found")
            await callback.answer("Пользователь не найден.", show_alert=True)
            return

        print(f"🔄 Checking achievements for user {user.user_id}")

        # Проверяем новые достижения
        try:
            new_achievements = check_achievements(user, session)
            print(f"✅ Checked achievements, found {len(new_achievements)} new")
        except Exception as e:
            print(f"❌ Error in check_achievements: {e}")
            import traceback
            traceback.print_exc()
            await callback.answer("❌ Ошибка проверки достижений", show_alert=True)
            return

        # Получаем обновленный список
        try:
            unlocked_achievements = session.query(Achievement).filter_by(user_id=user.user_id).all()
            unlocked_codes = {a.code for a in unlocked_achievements}
            print(f"📊 Unlocked achievements: {len(unlocked_codes)}")
        except Exception as e:
            print(f"❌ Error querying achievements: {e}")
            await callback.answer("❌ Ошибка загрузки достижений", show_alert=True)
            return

        total = len(ALL_ACHIEVEMENTS)
        unlocked_count = len(unlocked_codes)
        progress = floor((unlocked_count / total) * 10)
        bar = "█" * progress + "░" * (10 - progress)

        text = f"🏆 <b>Достижения</b>\n\nПрогресс: [{bar}] {unlocked_count}/{total}\n\n"

        if new_achievements:
            text += "🎉 <b>Новые достижения!</b>\n\n"
            for ach in new_achievements:
                text += f"✅ {ach.achievement_name}\n"
            text += "\n"

        # ЕДИНЫЙ ФОРМАТ ДЛЯ ВСЕХ ДОСТИЖЕНИЙ
        for ach in ALL_ACHIEVEMENTS:
            name = ach["name"]
            desc = ach["description"]
            if ach["code"] in unlocked_codes:
                text += f"✅ {name}\n   {desc}\n\n"
            else:
                text += f"🔒 {name}\n   {desc}\n\n"  # Убрано "(невыполнено)"

        print("📝 Generated achievement text")

        refresh_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_achievements")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
        ])

        try:
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=refresh_keyboard
            )
            print("✅ Message edited successfully")
        except Exception as e:
            print(f"❌ Error editing message: {e}")
            # Пробуем отправить новое сообщение
            await callback.message.answer(
                text,
                parse_mode="HTML",
                reply_markup=refresh_keyboard
            )
            print("✅ New message sent")

        await callback.answer("✅ Обновлено!")

    except Exception as e:
        print(f"❌ CRITICAL ERROR in refresh_achievements: {e}")
        import traceback
        traceback.print_exc()
        await callback.answer("❌ Ошибка обновления", show_alert=True)
    finally:
        session.close()
        print("=== REFRESH ACHIEVEMENTS COMPLETED ===")