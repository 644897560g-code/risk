"""ChatSession + ChatMessage SQLAlchemy models for Agent Chat history"""
import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.database import Base


class ChatSession(Base):
    """聊天会话 — 对应 conversation_id"""

    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, default="新对话")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    messages = relationship(
        "ChatMessage", back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def to_dict(self, include_messages: bool = False) -> dict:
        d = {
            "id": self.id,
            "title": self.title,
            "created_at": self._iso(self.created_at),
            "updated_at": self._iso(self.updated_at),
        }
        if self.messages:
            last = self.messages[-1]
            d["last_message"] = last.content[:80] if len(last.content) > 80 else last.content
            d["last_role"] = last.role
        if include_messages:
            d["messages"] = [m.to_dict() for m in self.messages]
        return d

    @staticmethod
    def _iso(dt):
        if dt is None:
            return None
        return dt.isoformat() + "Z"


class ChatMessage(Base):
    """聊天消息 — 一条对话记录"""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False, default="")
    tool_call = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": (self.created_at.isoformat() + "Z") if self.created_at else None,
        }
        if self.tool_call:
            d["tool_call"] = self.tool_call
        return d
