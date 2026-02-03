"""Test chat API endpoints"""

import pytest
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession


class TestChatAPI:
    """Test chat and query API endpoints"""

    @pytest.mark.asyncio
    async def test_process_query_new_session(self, client, db_session):
        """Test processing a query with a new session"""
        mock_agent = Mock()
        mock_agent.query = AsyncMock(
            return_value={
                "success": True,
                "answer": "Based on the records, this topic was discussed...",
                "context": [],
                "iteration": 1,
            }
        )

        from app.main import app
        from api.routes.chat import get_parliamentary_agent

        app.dependency_overrides[get_parliamentary_agent] = lambda: mock_agent

        response = client.post(
            "/api/query",
            json={
                "query": "What legislation was discussed recently?",
                "user_id": "test-user-123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["user_id"] == "test-user-123"
        assert "session_id" in data
        assert "message_id" in data
        assert "structured_response" in data

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_process_query_existing_session(self, client, db_session):
        """Test processing a query with an existing session"""
        from models.session import Session
        from models.message import Message
        from sqlalchemy import select
        import uuid

        session = Session(
            session_id=f"session_{str(uuid.uuid4())[:8]}",
            user_id="test-user-456",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        mock_agent = Mock()
        mock_agent.query = AsyncMock(
            return_value={
                "success": True,
                "answer": "Additional information on this topic...",
                "context": [],
                "iteration": 1,
            }
        )

        from app.main import app
        from api.routes.chat import get_parliamentary_agent

        app.dependency_overrides[get_parliamentary_agent] = lambda: mock_agent

        response = client.post(
            "/api/query",
            json={
                "query": "Tell me more about this topic",
                "user_id": "test-user-456",
                "session_id": session.session_id,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session.session_id
        assert data["user_id"] == "test-user-456"

        result = await db_session.execute(
            select(Message).where(Message.session_id == session.id)
        )
        messages = result.scalars().all()
        assert len(messages) >= 2

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_process_query_missing_user_id(self, client):
        """Test processing a query without user_id"""
        response = client.post(
            "/api/query",
            json={
                "query": "What legislation was discussed?",
            },
        )

        assert response.status_code == 400
        assert "user_id is required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_process_query_missing_query(self, client):
        """Test processing a query without query text"""
        response = client.post(
            "/api/query",
            json={
                "user_id": "test-user-123",
            },
        )

        assert response.status_code == 400
        assert "Query is required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_process_query_agent_error(self, client, db_session):
        """Test processing a query when agent returns error"""
        mock_agent = Mock()
        mock_agent.query = AsyncMock(
            return_value={
                "success": False,
                "error": "Knowledge graph is empty",
                "context": [],
                "iteration": 1,
            }
        )

        from app.main import app
        from api.routes.chat import get_parliamentary_agent

        app.dependency_overrides[get_parliamentary_agent] = lambda: mock_agent

        response = client.post(
            "/api/query",
            json={
                "query": "What legislation was discussed?",
                "user_id": "test-user-789",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "structured_response" in data
        assert data["structured_response"]["response_cards"][0]["summary"] == "Error"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_session(self, client, db_session):
        """Test getting session details"""
        from models.session import Session
        import uuid

        session = Session(
            session_id=f"session_{str(uuid.uuid4())[:8]}",
            user_id="test-user-session",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        response = client.get(f"/api/session/{session.session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session.session_id
        assert data["user_id"] == "test-user-session"
        assert data["message_count"] == 0
        assert data["archived"] is False

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client):
        """Test getting a non-existent session"""
        response = client.get("/api/session/nonexistent-session")

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_session_messages(self, client, db_session):
        """Test getting messages for a session"""
        from models.session import Session
        from models.message import Message
        import uuid

        session = Session(
            session_id=f"session_{str(uuid.uuid4())[:8]}",
            user_id="test-user-messages",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        user_message = Message(
            session_id=session.id,
            role="user",
            content="Test query",
        )
        db_session.add(user_message)

        assistant_message = Message(
            session_id=session.id,
            role="assistant",
            content="",
            structured_response={"intro_message": "Test response"},
        )
        db_session.add(assistant_message)
        await db_session.commit()

        response = client.get(f"/api/session/{session.session_id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "assistant"
        assert data["messages"][1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_session_messages_not_found(self, client):
        """Test getting messages for a non-existent session"""
        response = client.get("/api/session/nonexistent-session/messages")

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_archive_session(self, client, db_session):
        """Test archiving a session"""
        from models.session import Session
        import uuid

        session = Session(
            session_id=f"session_{str(uuid.uuid4())[:8]}",
            user_id="test-user-archive",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        assert session.archived is False

        response = client.post(f"/api/session/{session.session_id}/archive")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Session archived"

        await db_session.refresh(session)
        assert session.archived is True

    @pytest.mark.asyncio
    async def test_archive_session_already_archived(self, client, db_session):
        """Test archiving an already archived session"""
        from models.session import Session
        import uuid

        session = Session(
            session_id=f"session_{str(uuid.uuid4())[:8]}",
            user_id="test-user-archive",
            archived=True,
        )
        db_session.add(session)
        await db_session.commit()

        response = client.post(f"/api/session/{session.session_id}/archive")

        assert response.status_code == 400
        assert "Session already archived" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_archive_session_not_found(self, client):
        """Test archiving a non-existent session"""
        response = client.post("/api/session/nonexistent-session/archive")

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]
