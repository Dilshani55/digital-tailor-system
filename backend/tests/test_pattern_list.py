"""The saved-pattern list (one source for dashboard, customers and library), pattern delete, missing references."""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from bson import ObjectId, DBRef
from flask_jwt_extended import create_access_token
from mongoengine.errors import DoesNotExist

from app import create_app
from app.utils.references import deref, pattern_owner_id, ref_id


def _pattern(pid, session_ref, **extra):
    return SimpleNamespace(
        id=pid, _data={"session_id": session_ref}, garment_type="blouse", yardage_metres=1.2,
        selected_fabric_id="cotton-poplin", selected_fabric_name="Cotton Poplin", nesting_summary={},
        pattern_coordinates=[{}, {}, {}], generated_at="2026-09-30 10:00:00", **extra,
    )


def _export(eid, pattern_id, file_path):
    return SimpleNamespace(id=eid, _data={"pattern_id": pattern_id}, file_path=file_path,
                           exported_at="2026-09-30 11:00:00")


class _Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            cls.h = {"Authorization": f"Bearer {create_access_token(identity='u1')}"}

    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.app.config["OUTPUT_FOLDER"] = self.out


class TestPatternList(_Routes):
    def _get(self, sessions, patterns, profiles=(), exports=()):
        with patch("app.routes.patterns.User") as U, patch("app.routes.patterns.Session") as S, \
                patch("app.routes.patterns.PatternResult") as P, patch("app.routes.patterns.PdfExport") as E, \
                patch("app.routes.patterns.MeasurementProfile") as M:
            U.objects.return_value.first.return_value = MagicMock()
            S.objects.return_value = sessions
            P.objects.return_value.order_by.return_value = patterns
            M.objects.return_value = list(profiles)
            E.objects.return_value.order_by.return_value = list(exports)
            return self.app.test_client().get("/api/patterns/", headers=self.h)

    def test_each_pattern_reports_the_measurement_profile_of_its_session(self):
        s1, s2, s3 = ObjectId(), ObjectId(), ObjectId()
        m1, m2 = ObjectId(), ObjectId()
        sessions = [
            SimpleNamespace(id=s1, _data={"measurement_id": m1}),                    # stored ObjectId
            SimpleNamespace(id=s2, _data={"measurement_id": DBRef("measurements", m2)}),  # stored DBRef
            SimpleNamespace(id=s3, _data={"measurement_id": None}),                  # no profile linked
        ]
        patterns = [_pattern("p1", s1), _pattern("p2", DBRef("sessions", s2)), _pattern("p3", s3)]
        r = self._get(sessions, patterns, profiles=[SimpleNamespace(id=m1, client_name="Amara Silva")])
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        got = {p["pattern_id"]: p["measurement_id"] for p in body["patterns"]}
        self.assertEqual(got, {"p1": str(m1), "p2": str(m2), "p3": None})
        self.assertEqual(body["total"], 3)
        names = {p["pattern_id"]: p["customer_name"] for p in body["patterns"]}
        # m2's profile was deleted: the pattern is still listed, its customer is simply unknown
        self.assertEqual(names, {"p1": "Amara Silva", "p2": None, "p3": None})

    def test_a_pattern_without_a_pdf_is_listed_with_no_exports(self):
        s1 = ObjectId()
        open(os.path.join(self.out, "pattern_p1.pdf"), "wb").close()
        patterns = [
            _pattern("p1", s1, design_spec={"attributes": {"neckline_type": "v-neck", "sleeve_length": "short-sleeve",
                                                           "sleeve_style": "puff-sleeve"}}),
            _pattern("p2", s1),
        ]
        exports = [_export("e2", "p1", "pattern_p1.pdf"), _export("e1", "p1", "pattern_p1.pdf"),
                   _export("e0", "p1", "pattern_gone.pdf")]
        r = self._get([SimpleNamespace(id=s1, _data={"measurement_id": None})], patterns, exports=exports)
        by_id = {p["pattern_id"]: p for p in r.get_json()["patterns"]}
        self.assertEqual(by_id["p2"]["exports"], [])                     # saved, PDF pending - still listed
        self.assertEqual([e["export_id"] for e in by_id["p1"]["exports"]], ["e2", "e1", "e0"])
        self.assertEqual([e["file_available"] for e in by_id["p1"]["exports"]], [True, True, False])
        self.assertEqual(by_id["p1"]["neckline_type"], "v-neck")
        self.assertEqual(by_id["p1"]["sleeve_style"], "puff-sleeve")
        self.assertIsNone(by_id["p2"]["neckline_type"])                   # not stored -> not invented


class TestPatternDelete(_Routes):
    def _pattern(self, owner="u1"):
        pat = MagicMock()
        pat.id = "p1"
        pat.session_id.user_id.id = owner
        return pat

    def _delete(self, pattern, exports=()):
        with patch("app.routes.patterns.PatternResult") as P, patch("app.routes.patterns.PdfExport") as E:
            P.objects.return_value.first.return_value = pattern
            E.objects.return_value = list(exports)
            return self.app.test_client().delete("/api/patterns/p1", headers=self.h)

    def test_owner_deletes_the_pattern_with_its_pdfs_and_nothing_else(self):
        pdf = os.path.join(self.out, "pattern_p1.pdf")
        open(pdf, "wb").close()
        other = os.path.join(self.out, "pattern_other.pdf")
        open(other, "wb").close()
        pat = self._pattern()
        e1, e2 = MagicMock(file_path="pattern_p1.pdf"), MagicMock(file_path="pattern_p1.pdf")
        r = self._delete(pat, [e1, e2])
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["deleted_pdfs"], 2)
        pat.delete.assert_called_once()
        e1.delete.assert_called_once()
        e2.delete.assert_called_once()
        self.assertFalse(os.path.exists(pdf))
        self.assertTrue(os.path.exists(other))                            # another pattern's file is untouched
        self.assertEqual(pat.session_id.status, "pattern_deleted")
        pat.session_id.save.assert_called_once()
        pat.session_id.delete.assert_not_called()                         # generation record, customer, photo kept
        pat.session_id.measurement_id.delete.assert_not_called()
        pat.session_id.image_id.delete.assert_not_called()

    def test_another_users_pattern_looks_missing_and_is_not_deleted(self):
        pat = self._pattern(owner="someone-else")
        e1 = MagicMock(file_path="pattern_p1.pdf")
        r = self._delete(pat, [e1])
        self.assertEqual(r.status_code, 404)
        pat.delete.assert_not_called()
        e1.delete.assert_not_called()

    def test_missing_pattern_is_404_and_login_is_required(self):
        self.assertEqual(self._delete(None).status_code, 404)
        self.assertEqual(self.app.test_client().delete("/api/patterns/p1").status_code, 401)

    def test_a_file_name_cannot_escape_the_output_folder(self):
        outside = os.path.join(tempfile.mkdtemp(), "keep.pdf")
        open(outside, "wb").close()
        r = self._delete(self._pattern(), [MagicMock(file_path=os.path.join("..", os.path.basename(os.path.dirname(outside)), "keep.pdf"))])
        self.assertEqual(r.status_code, 200)
        self.assertTrue(os.path.exists(outside))


class _Broken:
    """A record whose reference points at a deleted record (mongoengine raises on access)."""
    def __init__(self, **ok):
        self.__dict__.update(ok)

    def __getattr__(self, name):
        raise DoesNotExist("Trying to dereference unknown document")


class TestMissingReferences(_Routes):
    def test_helpers_answer_missing_instead_of_raising(self):
        self.assertIsNone(deref(_Broken(), "session_id"))
        self.assertIsNone(deref(None, "anything"))
        self.assertIsNone(deref(SimpleNamespace(image_id=DBRef("design_images", ObjectId())), "image_id"))
        self.assertIsNone(pattern_owner_id(_Broken()))                               # session deleted
        self.assertIsNone(pattern_owner_id(SimpleNamespace(session_id=_Broken())))   # user deleted
        self.assertEqual(pattern_owner_id(SimpleNamespace(session_id=SimpleNamespace(user_id=SimpleNamespace(id=7)))), "7")
        oid = ObjectId()
        self.assertEqual(ref_id(SimpleNamespace(_data={"x": DBRef("c", oid)}), "x"), str(oid))
        self.assertIsNone(ref_id(SimpleNamespace(_data={}), "x"))

    def test_pattern_whose_session_is_gone_is_refused_not_a_crash(self):
        with patch("app.routes.patterns.PatternResult") as P:
            P.objects.return_value.first.return_value = _Broken(id="p1")
            c = self.app.test_client()
            self.assertEqual(c.get("/api/patterns/p1", headers=self.h).status_code, 403)
            self.assertEqual(c.delete("/api/patterns/p1", headers=self.h).status_code, 404)

    def test_pdf_whose_pattern_is_gone_is_404_for_download_and_delete(self):
        orphan = _Broken(id="e1", file_path="pattern_x.pdf")
        orphan.delete = MagicMock()
        with patch("app.routes.export.PdfExport") as E:
            E.objects.return_value.first.return_value = orphan
            c = self.app.test_client()
            r = c.get("/api/export/download/e1", headers=self.h)
            self.assertEqual((r.status_code, r.get_json()["error_code"]), (404, "EXPORT_PATTERN_MISSING"))
            self.assertEqual(c.delete("/api/export/e1", headers=self.h).status_code, 404)
        orphan.delete.assert_not_called()

    def test_deleting_one_pdf_keeps_the_file_other_pdf_records_still_use(self):
        pdf = os.path.join(self.out, "pattern_p1.pdf")
        open(pdf, "wb").close()
        export = MagicMock(id="e1", file_path="pattern_p1.pdf")
        export.pattern_id.session_id.user_id.id = "u1"
        for others, kept in ((1, True), (0, False)):
            with patch("app.routes.export.PdfExport") as E:
                E.objects.return_value.first.return_value = export
                E.objects.return_value.count.return_value = others
                r = self.app.test_client().delete("/api/export/e1", headers=self.h)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(os.path.exists(pdf), kept)
        export.pattern_id.delete.assert_not_called()                      # deleting a PDF never deletes the pattern


if __name__ == "__main__":
    unittest.main()
