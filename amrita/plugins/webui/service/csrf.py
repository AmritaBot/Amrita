from __future__ import annotations

import secrets

from fastapi import Request


class CSRFManager:
    _instance = None
    _csrf_tokens: dict[str, str]  # session_id -> csrf_token

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._csrf_tokens = {}
        return cls._instance

    def generate_csrf_token(self, session_id: str) -> str:
        """
        为给定的会话ID生成CSRF令牌

        Args:
            session_id: 用户会话ID

        Returns:
            生成的CSRF令牌
        """
        # 生成安全的随机令牌
        csrf_token = secrets.token_urlsafe(32)
        self._csrf_tokens[session_id] = csrf_token
        return csrf_token

    def validate_csrf_token(self, session_id: str, csrf_token: str) -> bool:
        """
        验证CSRF令牌

        Args:
            session_id: 用户会话ID
            csrf_token: 要验证的CSRF令牌

        Returns:
            验证是否成功
        """
        if session_id not in self._csrf_tokens:
            return False

        expected_token = self._csrf_tokens[session_id]
        # 使用时间常量比较防止时序攻击
        return secrets.compare_digest(expected_token, csrf_token)

    def get_csrf_token(self, session_id: str) -> str | None:
        """
        获取指定会话的CSRF令牌（如果存在）

        Args:
            session_id: 用户会话ID

        Returns:
            CSRF令牌或None
        """
        return self._csrf_tokens.get(session_id)

    def clear_csrf_token(self, session_id: str) -> None:
        """
        清除指定会话的CSRF令牌

        Args:
            session_id: 用户会话ID
        """
        self._csrf_tokens.pop(session_id, None)


def validate_csrf(request: Request) -> bool:
    """
    验证请求中的CSRF令牌

    Args:
        request: FastAPI请求对象

    Returns:
        验证是否成功
    """
    # 获取会话ID（这里使用access_token作为会话标识）
    session_id = request.cookies.get("access_token")
    if not session_id:
        return False

    # 获取请求中的CSRF令牌
    csrf_token = None
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        # 从表单数据中获取
        form_data = getattr(request, "_form", None)
        if form_data and "csrf_token" in form_data:
            csrf_token = form_data["csrf_token"]
        # 从头部获取（用于AJAX请求）
        elif "X-CSRF-Token" in request.headers:
            csrf_token = request.headers["X-CSRF-Token"]

    # 验证令牌
    if csrf_token:
        return CSRFManager().validate_csrf_token(session_id, csrf_token)

    # 对于需要CSRF保护的方法，如果没有令牌则验证失败
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        return False

    return True


def add_csrf_token(request: Request, context: dict) -> dict:
    """
    为模板上下文添加CSRF令牌

    Args:
        request: FastAPI请求对象
        context: 模板上下文

    Returns:
        添加了CSRF令牌的上下文
    """
    session_id = request.cookies.get("access_token")
    if session_id:
        csrf_manager = CSRFManager()
        csrf_token = csrf_manager.get_csrf_token(session_id)
        if not csrf_token:
            # 如果没有令牌，则生成一个
            csrf_token = csrf_manager.generate_csrf_token(session_id)
        context["csrf_token"] = csrf_token
    return context
