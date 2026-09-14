"""Адаптер автентифікації: verify_init_data (Telegram) і DevAuth (AUTH_MODE=dev).

Єдине місце в бекенді, що знає про initData (ADR-0001). Назовні
віддає лише TeacherId; хто підписав — деталь адаптера.
"""
