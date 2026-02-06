"""Factory for creating test models"""

from datetime import datetime, timezone
from uuid import uuid4

import factory

from models.agenda_item import AgendaItem
from models.entity import Entity
from models.session import Session
from models.speaker import Speaker
from models.video import Video


class VideoFactory(factory.Factory):
    """Factory for creating Video models"""

    class Meta:
        model = Video

    id = factory.Sequence(lambda n: str(n))
    video_id = factory.Sequence(lambda n: f"test_video_{n:03d}")
    session_id = factory.SubFactory(SessionFactory)
    platform = "youtube"
    url = factory.LazyAttribute(lambda o: f"https://youtube.com/watch?v={o.video_id}")
    duration_seconds = factory.Faker("random_int", min=1800, max=10800)


class AgendaItemFactory(factory.Factory):
    """Factory for creating AgendaItem models"""

    class Meta:
        model = AgendaItem

    id = factory.Sequence(lambda n: str(n))
    agenda_item_id = factory.Sequence(lambda n: f"s_000_0000_00_00_a{n:03d}")
    session_id = factory.SubFactory(SessionFactory)
    agenda_index = factory.Sequence(lambda n: n)
    title = factory.Faker("sentence")
    description = factory.Faker("paragraph")
    primary_speaker = factory.Faker("name")


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
    source = "test"
    source_ref = "factory"


class SessionFactory(factory.Factory):
    """Factory for creating Session models"""

    class Meta:
        model = Session

    id = factory.LazyFunction(uuid4)
    session_id = factory.Sequence(lambda n: f"s_{n:03d}_{2026_01_06}")
    date = factory.LazyFunction(lambda: datetime.now(timezone.utc).date())
    title = factory.Faker("sentence")
    sitting_number = factory.Sequence(lambda n: str(n))
    chamber = factory.Iterator(["senate", "house"])
