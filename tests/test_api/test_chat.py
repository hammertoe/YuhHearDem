"""Test chat API endpoints"""

from unittest.mock import AsyncMock, Mock

import pytest


class TestChatAPI:
    """Test chat and query API endpoints"""

    @pytest.mark.anyio
    async def test_process_query_new_session(self, client):
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

        from api.routes.chat import get_parliamentary_agent
        from app.main import app

        app.dependency_overrides[get_parliamentary_agent] = lambda: mock_agent

        response = await client.post(
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

    @pytest.mark.anyio
    async def test_process_query_existing_session(self, client):
        """Test processing a query with an existing session"""
        mock_agent = Mock()
        mock_agent.query = AsyncMock(
            return_value={
                "success": True,
                "answer": "Additional information on this topic...",
                "context": [],
                "iteration": 1,
            }
        )

        from api.routes.chat import get_parliamentary_agent
        from app.main import app

        app.dependency_overrides[get_parliamentary_agent] = lambda: mock_agent

        initial_response = await client.post(
            "/api/query",
            json={
                "query": "Initial query",
                "user_id": "test-user-456",
            },
        )

        assert initial_response.status_code == 200
        initial_data = initial_response.json()

        response = await client.post(
            "/api/query",
            json={
                "query": "Tell me more about this topic",
                "user_id": "test-user-456",
                "session_id": initial_data["session_id"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == initial_data["session_id"]
        assert data["user_id"] == "test-user-456"

        app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_process_query_stream_unknown_session_creates_new(self, client):
        """Test streaming query with unknown session creates new session"""
        mock_agent = Mock()
        mock_agent.query = AsyncMock(
            return_value={
                "success": True,
                "answer": "Streaming response content",
                "context": [],
                "iteration": 1,
            }
        )

        from api.routes.chat import get_parliamentary_agent
        from app.main import app

        app.dependency_overrides[get_parliamentary_agent] = lambda: mock_agent

        response = await client.post(
            "/api/query/stream",
            json={
                "query": "Test streaming with unknown session",
                "user_id": "test-user-stream",
                "session_id": "non-existent-session",
            },
        )

        assert response.status_code == 200

        app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_process_query_missing_user_id(self, client):
        """Test processing a query without user_id"""
        response = await client.post(
            "/api/query",
            json={
                "query": "What legislation was discussed?",
            },
        )

        assert response.status_code == 400
        assert "user_id is required" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_process_query_missing_query(self, client):
        """Test processing a query without query text"""
        response = await client.post(
            "/api/query",
            json={
                "user_id": "test-user-123",
            },
        )

        assert response.status_code == 400
        assert "Query is required" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_process_query_agent_error(self, client):
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

        from api.routes.chat import get_parliamentary_agent
        from app.main import app

        app.dependency_overrides[get_parliamentary_agent] = lambda: mock_agent

        response = await client.post(
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

    @pytest.mark.anyio
    @pytest.mark.skip("Database setup issue - needs fixture dependency fix")
    async def test_process_query_invalid_session_id(self, client):
        """Test processing a query creates new session for missing session_id"""
        mock_agent = Mock()
        mock_agent.query = AsyncMock(
            return_value={
                "success": True,
                "answer": "Answer",
                "context": [],
                "iteration": 1,
            }
        )

        from api.routes.chat import get_parliamentary_agent
        from app.main import app

        app.dependency_overrides[get_parliamentary_agent] = lambda: mock_agent

        response = await client.post(
            "/api/query",
            json={
                "query": "Tell me more",
                "user_id": "test-user-404",
                "session_id": "missing-session",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "missing-session"
        assert data["user_id"] == "test-user-404"
        assert data["status"] == "success"

        app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_process_query_includes_entities(self, client, db_session_maker):
        """Test processing a query includes entities in response and storage"""
        mock_agent = Mock()
        mock_agent.query = AsyncMock(
            return_value={
                "success": True,
                "answer": "Answer with entities",
                "entities": [
                    {"entity_id": "entity-1", "name": "Entity 1", "type": "person"},
                    {"entity_id": "entity-2", "name": "Entity 2", "type": "bill"},
                ],
                "context": [],
                "iteration": 1,
            }
        )

        from sqlalchemy import select

        from api.routes.chat import get_parliamentary_agent
        from app.main import app
        from models.message import Message
        from models.session import Session

        app.dependency_overrides[get_parliamentary_agent] = lambda: mock_agent

        response = await client.post(
            "/api/query",
            json={
                "query": "Who was involved?",
                "user_id": "test-user-entities",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "entities" in data["structured_response"]
        assert len(data["structured_response"]["entities"]) == 2

        async with db_session_maker() as check_session:
            result = await check_session.execute(
                select(Session).where(Session.session_id == data["session_id"])
            )
            session = result.scalar_one_or_none()
            assert session is not None

            result = await check_session.execute(
                select(Message)
                .where(Message.session_id == session.id)
                .order_by(Message.created_at.desc())
            )
            messages = result.scalars().all()
            assert messages[0].structured_response is not None
            assert "entities" in messages[0].structured_response

        app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_get_session(self, client, db_session):
        """Test getting session details"""
        import uuid

        from models.session import Session

        session = Session(
            session_id=f"session_{str(uuid.uuid4())[:8]}",
            user_id="test-user-session",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        await db_session.close()
        response = await client.get(f"/api/session/{session.session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session.session_id
        assert data["user_id"] == "test-user-session"
        assert data["message_count"] == 0
        assert data["archived"] is False

    @pytest.mark.anyio
    async def test_get_session_not_found(self, client):
        """Test getting a non-existent session"""
        response = await client.get("/api/session/nonexistent-session")

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_get_session_messages(self, client, db_session):
        """Test getting messages for a session"""
        import uuid

        from models.message import Message
        from models.session import Session

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

        await db_session.close()
        response = await client.get(f"/api/session/{session.session_id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "assistant"
        assert data["messages"][1]["role"] == "user"

    @pytest.mark.anyio
    async def test_get_session_messages_not_found(self, client):
        """Test getting messages for a non-existent session"""
        response = await client.get("/api/session/nonexistent-session/messages")

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_archive_session(self, client, db_session, db_session_maker):
        """Test archiving a session"""
        import uuid

        from sqlalchemy import select

        from models.session import Session

        session = Session(
            session_id=f"session_{str(uuid.uuid4())[:8]}",
            user_id="test-user-archive",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        assert session.archived is False

        await db_session.close()
        response = await client.post(f"/api/session/{session.session_id}/archive")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Session archived"

        async with db_session_maker() as check_session:
            result = await check_session.execute(
                select(Session).where(Session.session_id == session.session_id)
            )
            updated_session = result.scalar_one()
            assert updated_session.archived is True

    @pytest.mark.anyio
    async def test_archive_session_already_archived(self, client, db_session):
        """Test archiving an already archived session"""
        import uuid

        from models.session import Session

        session = Session(
            session_id=f"session_{str(uuid.uuid4())[:8]}",
            user_id="test-user-archive",
            archived=True,
        )
        db_session.add(session)
        await db_session.commit()

        await db_session.close()
        response = await client.post(f"/api/session/{session.session_id}/archive")

        assert response.status_code == 400
        assert "Session already archived" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_archive_session_not_found(self, client):
        """Test archiving a non-existent session"""
        response = await client.post("/api/session/nonexistent-session/archive")

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_get_session_graph(self, client, db_session):
        """Test getting graph for a session"""
        import uuid

        from models.entity import Entity
        from models.message import Message
        from models.relationship import Relationship
        from models.session import Session

        # Create session with messages that have entities
        session = Session(
            session_id=f"session_{str(uuid.uuid4())[:8]}",
            user_id="test-user-graph",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Create user message
        user_message = Message(
            session_id=session.id,
            role="user",
            content="Who discussed the bill?",
        )
        db_session.add(user_message)

        # Create assistant message with entities in structured_response
        assistant_message = Message(
            session_id=session.id,
            role="assistant",
            content="",
            structured_response={
                "intro_message": "Analysis complete",
                "response_cards": [
                    {
                        "summary": "Entities found",
                        "details": "The following entities were mentioned...",
                    }
                ],
                "follow_up_suggestions": [],
                "entities": [
                    {"entity_id": "entity-1", "name": "Senator A", "type": "person"},
                    {"entity_id": "entity-2", "name": "Bill 123", "type": "bill"},
                ],
            },
        )
        db_session.add(assistant_message)
        await db_session.commit()

        # Create entities in database
        entity1 = Entity(
            entity_id="entity-1",
            entity_type="person",
            name="Senator A",
            canonical_name="Senator A",
            description="A senator from Barbados",
            importance_score=0.9,
        )
        entity2 = Entity(
            entity_id="entity-2",
            entity_type="bill",
            name="Bill 123",
            canonical_name="Bill 123",
            description="A bill about education",
            importance_score=0.8,
        )
        db_session.add_all([entity1, entity2])
        await db_session.commit()

        # Create relationship
        relationship = Relationship(
            source_id="entity-1",
            target_id="entity-2",
            relation_type="supports",
            sentiment="positive",
            evidence="The senator strongly supported this bill",
            video_id=None,
            timestamp_seconds=0,
        )
        db_session.add(relationship)
        await db_session.commit()

        await db_session.close()
        response = await client.get(f"/api/session/{session.session_id}/graph")

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1

        # Check node structure
        node1 = next((n for n in data["nodes"] if n["id"] == "entity-1"), None)
        assert node1 is not None
        assert node1["label"] == "Senator A"
        assert node1["type"] == "person"

        # Check edge structure
        edge = data["edges"][0]
        assert edge["source"] == "entity-1"
        assert edge["target"] == "entity-2"
        assert edge["relation"] == "supports"

    @pytest.mark.anyio
    async def test_get_session_graph_no_entities(self, client, db_session):
        """Test getting graph for session with no entities"""
        import uuid

        from models.message import Message
        from models.session import Session

        # Create session with messages but no entities
        session = Session(
            session_id=f"session_{str(uuid.uuid4())[:8]}",
            user_id="test-user-no-entities",
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Create user message
        user_message = Message(
            session_id=session.id,
            role="user",
            content="Hello",
        )
        db_session.add(user_message)

        # Create assistant message without entities
        assistant_message = Message(
            session_id=session.id,
            role="assistant",
            content="Hello!",
            structured_response={
                "intro_message": "Hello!",
                "response_cards": [],
                "follow_up_suggestions": [],
            },
        )
        db_session.add(assistant_message)
        await db_session.commit()

        await db_session.close()
        response = await client.get(f"/api/session/{session.session_id}/graph")

        assert response.status_code == 200
        data = response.json()
        assert data["nodes"] == []
        assert data["edges"] == []

    @pytest.mark.anyio
    async def test_get_session_graph_not_found(self, client):
        """Test getting graph for non-existent session"""
        response = await client.get("/api/session/nonexistent-session/graph")

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]
