"""Factory for creating test models"""

from datetime import datetime
from uuid import uuid4

import factory

from models.entity import Entity
from models.message import Message
from models.session import Session
from models.speaker import Speaker
from models.video import Video


class VideoFactory(factory.Factory):
    """Factory for creating Video models"""

    class Meta:
        model = Video

    id = factory.LazyFunction(uuid4)
    youtube_id = factory.Sequence(lambda n: f"test_video_{n}")
    youtube_url = factory.LazyAttribute(lambda o: f"https://youtube.com/watch?v={o.youtube_id}")
    title = factory.Faker("sentence")
    chamber = factory.Iterator(["senate", "house"])
    session_date = factory.LazyFunction(datetime.utcnow)
    sitting_number = factory.Faker("random_int", min=1, max=100)
    duration_seconds = factory.Faker("random_int", min=1800, max=10800)
    transcript = factory.LazyAttribute(
        lambda o: {
            "session_title": o.title,
            "agenda_items": [],
            "speech_blocks": [],
        }
    )


class SpeakerFactory(factory.Factory):
    """Factory for creating Speaker models"""

    class Meta:
        model = Speaker

    id = factory.LazyFunction(uuid4)
    canonical_id = factory.Sequence(lambda n: f"speaker_{n}")
    name = factory.Faker("name")
    title = factory.Iterator(["Hon.", "Dr.", "Mr.", "Ms."])
    role = factory.Iterator(["Senator", "MP", "Minister"])
    chamber = factory.Iterator(["senate", "house"])
    aliases = factory.LazyFunction(list)
    pronoun = factory.Iterator(["he", "she", "they"])
    gender = factory.Iterator(["male", "female", "unknown"])


class EntityFactory(factory.Factory):
    """Factory for creating Entity models"""

    class Meta:
        model = Entity

    id = factory.LazyFunction(uuid4)
    entity_id = factory.Sequence(lambda n: f"entity_{n}")
    entity_type = factory.Iterator(["person", "organization", "place", "law", "concept"])
    name = factory.Faker("company")
    canonical_name = factory.LazyAttribute(lambda o: o.name.title())
    aliases = factory.LazyFunction(list)
    importance_score = factory.Faker("pyfloat", min_value=0.0, max_value=1.0)


class SessionFactory(factory.Factory):
    """Factory for creating Session models"""

    class Meta:
        model = Session

    id = factory.LazyFunction(uuid4)
    session_id = factory.Sequence(lambda n: f"session_{n}")
    user_id = factory.LazyFunction(uuid4)
    archived = False


class MessageFactory(factory.Factory):
    """Factory for creating Message models"""

    class Meta:
        model = Message

    id = factory.LazyFunction(uuid4)
    session_id = factory.SubFactory(SessionFactory)
    role = factory.Iterator(["user", "assistant"])
    content = factory.Faker("paragraph")
    structured_response = None
