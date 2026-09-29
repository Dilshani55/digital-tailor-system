"""GET /api/patterns/ links every saved pattern to the customer (measurement profile) it was made for."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from bson import ObjectId, DBRef
from flask_jwt_extended import create_access_token

from app import create_app


def _pattern(pid, session_ref):
    return SimpleNamespace(
        id=pid, _data={"session_id": session_ref}, garment_type="blouse", yardage_metres=1.2,
        selected_fabric_id="cotton-poplin", selected_fabric_name="Cotton Poplin", nesting_summary={},
        pattern_coordinates=[{}, {}, {}], generated_at="2026-09-30 10:00:00",
    )


class TestPatternList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            cls.h = {"Authorization": f"Bearer {create_access_token(identity='u1')}"}

    def test_each_pattern_reports_the_measurement_profile_of_its_session(self):
        s1, s2, s3 = ObjectId(), ObjectId(), ObjectId()
        m1, m2 = ObjectId(), ObjectId()
        sessions = [
            SimpleNamespace(id=s1, _data={"measurement_id": m1}),                    # stored ObjectId
            SimpleNamespace(id=s2, _data={"measurement_id": DBRef("measurements", m2)}),  # stored DBRef
            SimpleNamespace(id=s3, _data={"measurement_id": None}),                  # no profile linked
        ]
        patterns = [_pattern("p1", s1), _pattern("p2", DBRef("sessions", s2)), _pattern("p3", s3)]
        with patch("app.routes.patterns.User") as U, patch("app.routes.patterns.Session") as S, \
                patch("app.routes.patterns.PatternResult") as P:
            U.objects.return_value.first.return_value = MagicMock()
            S.objects.return_value = sessions
            P.objects.return_value.order_by.return_value = patterns
            r = self.app.test_client().get("/api/patterns/", headers=self.h)
        self.assertEqual(r.status_code, 200)
        got = {p["pattern_id"]: p["measurement_id"] for p in r.get_json()["patterns"]}
        self.assertEqual(got, {"p1": str(m1), "p2": str(m2), "p3": None})


if __name__ == "__main__":
    unittest.main()
