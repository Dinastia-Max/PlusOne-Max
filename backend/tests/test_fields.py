import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Field
from app.routers.fields import get_fields


class AsyncSessionAdapter:
    def __init__(self, session):
        self.session = session

    async def scalars(self, statement):
        return self.session.scalars(statement)


class FieldsListTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    async def test_returns_only_active_fields(self):
        with Session(self.engine) as session:
            session.add_all(
                [
                    Field(
                        id=1,
                        name="Яуза",
                        address="Москва, парк Яуза",
                        district="SVAO",
                        is_active=True,
                    ),
                    Field(
                        id=2,
                        name="Закрытое поле",
                        address="Москва",
                        district="SVAO",
                        is_active=False,
                    ),
                    Field(
                        id=3,
                        name="Арена",
                        address="Москва, улица Спортивная",
                        district="SVAO",
                        is_active=True,
                    ),
                ]
            )
            session.commit()

            result = await get_fields(AsyncSessionAdapter(session))

        self.assertEqual([field.id for field in result], [3, 1])
        self.assertEqual(result[0].name, "Арена")
        self.assertEqual(result[0].address, "Москва, улица Спортивная")
        self.assertEqual(result[0].district, "SVAO")

    async def test_empty_database_returns_empty_list(self):
        with Session(self.engine) as session:
            result = await get_fields(AsyncSessionAdapter(session))

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
